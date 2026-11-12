"""The fleet registry (EF-43, §8) — deadlines, vendor trust, agent comparison."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sas import registre
from sas.types import (
    ActionDerive,
    Agent,
    Attestation,
    BorneStatistique,
    Derive,
    Editeur,
    Mode,
    StatutAgent,
    Verdict,
)

DATE = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)
BORNE = BorneStatistique(n_rejeux=6, lignes=(), rejeux_independants=True)


def agent(identifiant: str, nom: str, editeur: str, statut: StatutAgent = StatutAgent.HOMOLOGUE) -> Agent:
    return Agent(
        id=identifiant,
        tenant_id="tenant-a",
        editeur_id=editeur,
        nom=nom,
        version_courante="3.4.1",
        empreinte="sha256:" + "0" * 64,
        statut=statut,
    )


def attestation(nom_agent: str, verdict: Verdict, jours: int = 90, date: datetime = DATE) -> Attestation:
    return Attestation(
        id=f"att-{nom_agent}",
        numero=f"SAS-ATT-2026-{abs(hash(nom_agent)) % 9999:04d}",
        campagne_id=f"camp-{nom_agent}",
        tenant_id="tenant-a",
        agent_nom=nom_agent,
        agent_version="3.4.1",
        editeur="Exemple Editeur SAS",
        empreinte_paquet="sha256:7c1f4a9e2b8d…",
        modele_declare="anthropic.sonnet-4-5 (2026-10)",
        mode=Mode.OMBRE,
        manifeste_version=1,
        scenarios=8,
        n_rejeux=6,
        sessions=48,
        periode_debut=date,
        periode_fin=date,
        resultat=verdict,
        decouvertes={},
        permissions_mortes=0,
        compositions=0,
        conditions=(),
        borne=BORNE,
        empreinte_journal="sha256:c4d9…",
        entrees_journal=4291,
        ombre_detruite_le=date,
        valide_jusquau=date + timedelta(days=jours),
        signataire="Analyste MSP",
        date=date,
    )


def test_le_registre_classe_par_nom_et_porte_les_echeances() -> None:
    agents = [agent("a2", "Zeta", "ed-1"), agent("a1", "Alpha", "ed-1")]
    editeurs = [Editeur(id="ed-1", nom="Exemple Editeur SAS", contact="sec@exemple.invalid")]
    attestations = [attestation("Zeta", Verdict.HOMOLOGUE), attestation("Alpha", Verdict.SOUS_CONDITIONS)]
    lignes = registre.construire(
        agents, editeurs, attestations, campagnes_par_agent=(3, 1), couts=(Decimal("2.70"), Decimal("0.90"))
    )
    assert [ligne.agent.nom for ligne in lignes] == ["Alpha", "Zeta"]
    assert lignes[0].resultat is Verdict.SOUS_CONDITIONS
    assert lignes[1].valide_jusquau == DATE + timedelta(days=90)
    assert lignes[0].cout_cumule == Decimal("0.90")


def test_un_agent_sans_attestation_est_visible_comme_tel() -> None:
    """A registry that hides an un-homologated agent is worse than no registry."""
    lignes = registre.construire([agent("a1", "Alpha", "ed-1")], [], [])
    assert lignes[0].valide_jusquau is None
    assert lignes[0].resultat is None


def test_les_echeances_sont_trieees_par_urgence() -> None:
    agents = [
        agent("a1", "Alpha", "e"),
        agent("a2", "Beta", "e"),
        agent("a3", "Gamma", "e"),
        agent("a4", "Delta", "e"),
    ]
    attestations = [
        attestation("Alpha", Verdict.HOMOLOGUE, jours=-5),  # échue
        attestation("Beta", Verdict.HOMOLOGUE, jours=10),  # imminente
        attestation("Gamma", Verdict.HOMOLOGUE, jours=200),  # valide
    ]
    lignes = registre.construire(agents, [], attestations)
    echeances = registre.echeances(lignes, aujourdhui=DATE, fenetre=30)
    assert [e.etat for e in echeances] == ["echue", "imminente", "sans_attestation", "valide"]
    assert next(e.nom for e in echeances) == "Alpha"


def test_a_rehomologuer_ne_garde_que_ce_qui_demande_une_action() -> None:
    agents = [agent("a1", "Alpha", "e"), agent("a2", "Gamma", "e")]
    attestations = [
        attestation("Alpha", Verdict.HOMOLOGUE, jours=-5),
        attestation("Gamma", Verdict.HOMOLOGUE, jours=200),
    ]
    lignes = registre.construire(agents, [], attestations)
    a_faire = registre.a_rehomologuer(lignes, aujourdhui=DATE)
    assert [e.nom for e in a_faire] == ["Alpha"]


def test_le_score_editeur_refuse_une_tendance_sur_une_seule_homologation() -> None:
    """One data point is not a trend, and the score says so instead of inventing one."""
    historique = [
        registre.EntreeHistorique("a1", "ed-1", "3.4.1", DATE, Verdict.HOMOLOGUE, 0, 0, 0, 0, n_rejeux=6)
    ]
    score = registre.score_editeur("ed-1", historique)
    assert score.homologations == 1
    assert score.tendance == "inconnue"
    assert "aucune tendance" in score.explication


def test_le_score_editeur_voit_une_amelioration() -> None:
    historique = [
        registre.EntreeHistorique("a1", "ed-1", "1.0", DATE, Verdict.SOUS_CONDITIONS, 6, 4, 0, 2, n_rejeux=6),
        registre.EntreeHistorique(
            "a1", "ed-1", "1.1", DATE + timedelta(days=60), Verdict.SOUS_CONDITIONS, 3, 2, 0, 1, n_rejeux=6
        ),
    ]
    score = registre.score_editeur("ed-1", historique)
    assert score.homologations == 2
    assert score.tendance == "amelioration"
    assert score.part_homologues == 1.0


def test_le_score_editeur_voit_une_degradation_et_les_derives() -> None:
    """§15.1 — the undeclared changes are what a repeated watch catches."""
    historique = [
        registre.EntreeHistorique("a1", "ed-1", "1.0", DATE, Verdict.HOMOLOGUE, 0, 0, 0, 0, n_rejeux=6),
        registre.EntreeHistorique(
            "a1",
            "ed-1",
            "1.0",
            DATE + timedelta(days=7),
            Verdict.HOMOLOGUE,
            5,
            3,
            1,
            4,
            derive_non_declaree=True,
            n_rejeux=6,
        ),
    ]
    score = registre.score_editeur("ed-1", historique)
    assert score.tendance == "degradation"
    assert score.derives_non_declarees == 1
    assert score.compositions == 1


def test_un_editeur_inconnu_ne_produit_pas_de_score_invente() -> None:
    score = registre.score_editeur("inexistant", [])
    assert score.homologations == 0
    assert score.tendance == "inconnue"


def test_la_comparaison_classe_le_plus_propre_d_abord() -> None:
    comparaisons = [
        registre.Comparaison("a3", "Curieux", "e", "refuse", 24, 16, 1, 0, 8, Decimal("0.26"), 2),
        registre.Comparaison("a1", "Conforme", "e", "homologue", 90, 20, 0, 0, 0, Decimal("0.27"), 2),
        registre.Comparaison(
            "a2", "Bavard", "e", "homologue_sous_conditions", 160, 90, 1, 0, 0, Decimal("0.30"), 2
        ),
    ]
    classes = registre.comparer(comparaisons)
    assert [c.nom for c in classes] == ["Conforme", "Bavard", "Curieux"]


def test_la_comparaison_ne_classe_pas_par_cout_d_abord() -> None:
    """A cheap agent that is refused costs more than an expensive approved one."""
    comparaisons = [
        registre.Comparaison("a1", "Cher", "e", "homologue", 90, 0, 0, 0, 0, Decimal("4.00"), 6),
        registre.Comparaison("a2", "PasCher", "e", "refuse", 10, 0, 0, 0, 3, Decimal("0.10"), 6),
    ]
    assert [c.nom for c in registre.comparer(comparaisons)] == ["Cher", "PasCher"]


def test_le_resume_donne_les_chiffres_du_responsable_de_compte() -> None:
    """§7 — the account manager sees aggregate figures, nothing per tenant detail."""
    agents = [agent("a1", "Alpha", "e"), agent("a2", "Beta", "e", StatutAgent.REFUSE)]
    attestations = [attestation("Alpha", Verdict.HOMOLOGUE, jours=-1)]
    lignes = registre.construire(agents, [], attestations, couts=(Decimal("1.20"), Decimal("0.30")))
    resume = registre.resume_registre(lignes)
    assert resume["agents"] == 2
    assert resume["cout_cumule"] == 1.5
    assert resume["a_rehomologuer"] >= 1
    assert resume["statuts"]["homologue"] == 1


def test_le_statut_decoule_du_verdict_par_une_seule_table() -> None:
    """One mapping, so the API and the registry cannot disagree."""
    assert registre.statut_apres_verdict(Verdict.HOMOLOGUE) is StatutAgent.HOMOLOGUE
    assert registre.statut_apres_verdict(Verdict.SOUS_CONDITIONS) is StatutAgent.SOUS_CONDITIONS
    assert registre.statut_apres_verdict(Verdict.REFUSE) is StatutAgent.REFUSE
    assert registre.statut_apres_verdict(Verdict.NON_MESURABLE) is StatutAgent.NON_MESURABLE


def test_une_derive_qui_revient_est_un_motif_pas_un_incident() -> None:
    derives = [
        Derive(
            id="d1",
            agent_id="a1",
            tenant_id="t",
            enveloppe_ref="e1",
            enveloppe_courante="e2",
            distance=0.4,
            detail=(),
            alerte_le=DATE,
            action=ActionDerive.ALERTE,
        ),
        Derive(
            id="d2",
            agent_id="a1",
            tenant_id="t",
            enveloppe_ref="e2",
            enveloppe_courante="e3",
            distance=0.5,
            detail=(),
            alerte_le=DATE + timedelta(days=7),
            action=ActionDerive.SUSPENSION,
        ),
        Derive(
            id="d3",
            agent_id="a2",
            tenant_id="t",
            enveloppe_ref="e1",
            enveloppe_courante="e2",
            distance=0.2,
            detail=(),
            alerte_le=DATE,
            action=ActionDerive.ALERTE,
        ),
    ]
    assert registre.derive_aggrave(derives, seuil=2) == ("a1",)
    assert registre.derive_aggrave(derives, seuil=3) == ()


def test_la_fenetre_d_alerte_et_le_cycle_de_surveillance() -> None:
    """§15.4 — weekly monitoring by default, alerts 30 days before expiry."""
    assert registre.fenetre_alerte() == timedelta(days=30)
    assert registre.fenetre_alerte(7) == timedelta(days=7)
    assert registre.derive_aggrave(()) == ()
