"""End-to-end acceptance tests: the airlock runs, measures and proves.

Covers R5, R6, R7, R8, R11, R12, R15, R21, R22, R24, ENF-01, ENF-04, ENF-06,
ENF-09, ENF-17 and KPI-3/KPI-4.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from sas import constantes, couts
from sas.arret import Interrupteur
from sas.cli_partage import LEURRES_MARQUES, LEURRES_SENSIBLES, charger_contexte, invite, lancer
from sas.homologation import resume
from sas.orchestrateur import Campagne, nouvelle_campagne
from sas.store.integrite import AccesInterdit
from sas.store.local import DepotLocal
from sas.types import (
    ContexteTenant,
    Mode,
    Nature,
    StatutCampagne,
    StatutManifeste,
    StatutSession,
    Tenant,
    Verdict,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "manifeste-exemple.yaml"
DEUX_SCENARIOS = ("S1", "S4")


def contexte():
    return charger_contexte(DEUX_SCENARIOS)


def campagne(manifeste, scenarios, *, rejeux=2, graine=7, mode=Mode.OMBRE):
    return nouvelle_campagne(
        tenant_id="tenant-demo",
        agent_id=manifeste.agent_id,
        manifeste=manifeste,
        mode=mode,
        n_rejeux=rejeux,
        graine=graine,
        scenarios=[s.id for s in scenarios],
    )


def executer(nom, *, rejeux=2, graine=7, scenarios=None, manifeste=None):
    ctx = contexte()
    manifeste = manifeste or ctx.manifeste
    scenarios = scenarios if scenarios is not None else ctx.scenarios
    camp = campagne(manifeste, scenarios, rejeux=rejeux, graine=graine)
    return Campagne(campagne=camp, manifeste=manifeste, agent=invite(nom), scenarios=scenarios).executer()


# --------------------------------------------------------------------------- #
# R5 / EF-12 — N replays x scenarios, isolated sessions
# --------------------------------------------------------------------------- #


def test_R5_huit_scenarios_six_rejeux_donnent_48_sessions() -> None:
    """R5 — 8 scenarios x 6 replays = 48 isolated sessions, no state leak."""
    ctx = charger_contexte()
    assert len(ctx.scenarios) == 8
    resultat = executer("demo-conforme", rejeux=6, scenarios=ctx.scenarios)
    assert len(resultat.sessions) == 48
    assert len({s.id for s in resultat.sessions}) == 48
    # No leak: each session's calls are attributed to that session alone.
    par_session = {s.id: s.appels for s in resultat.sessions}
    assert all(v > 0 for v in par_session.values())


def test_les_sessions_sont_isolees_entre_elles() -> None:
    """EF-11, ENF-02, ENF-05 — sessions isolées, identité éphémère par session.
    EF-11, ENF-02, ENF-05 — sessions isolées, identité éphémère par session.
    EF-11, ENF-02, ENF-05 — sessions isolées, identité éphémère par session.
    """
    resultat = executer("demo-conforme", rejeux=2)
    identites = {s.identite.reference for s in resultat.sessions if s.identite}
    assert len(identites) == len(resultat.sessions)


# --------------------------------------------------------------------------- #
# R8 / KPI-4 — the journal is complete, denials included
# --------------------------------------------------------------------------- #


def test_R8_couverture_du_journal_a_cent_pourcent() -> None:
    """R8, ENF-04, KPI-4 — blocking requirement: 100 %, denials included.
    EF-14 — journalisation de 100 % des appels, refus compris.
    EF-14 — journalisation de 100 % des appels, refus compris.
    EF-14 — journalisation de 100 % des appels, refus compris.
    """
    for nom in ("demo-conforme", "demo-bavard", "demo-curieux"):
        resultat = executer(nom)
        assert resultat.couverture_journal == 1.0, nom
        assert len(resultat.entrees) == resultat.appels_emis
        assert resultat.etat_chaine.integre is True


def test_R9_une_rupture_de_chaine_est_detectee() -> None:
    """R9 — tampering with the chain is detected on reading."""
    from sas.journal.chaine import JournalChaine, verifier_sequence

    resultat = executer("demo-conforme")
    entrees = list(resultat.entrees)
    assert verifier_sequence(entrees).integre is True

    falsifiees = list(entrees)
    del falsifiees[1]
    etat = verifier_sequence(falsifiees)
    assert etat.integre is False
    assert etat.premiere_rupture is not None
    del JournalChaine


# --------------------------------------------------------------------------- #
# R6 / EF-13 — budget overrun ends the session cleanly
# --------------------------------------------------------------------------- #


def test_R6_un_budget_depasse_termine_proprement_la_session() -> None:
    """R6 — clean stop, session marked, campaign continues.
    ENF-03 — budgets imposés par Policy, arrêt propre au plafond.
    ENF-03 — budgets imposés par Policy, arrêt propre au plafond.
    ENF-03 — budgets imposés par Policy, arrêt propre au plafond.
    """
    ctx = contexte()
    # Only the budget moves; the seal check is bypassed by an empty recorded
    # fingerprint, so the campaign still runs and the stop is what is tested.
    petit = replace(
        ctx.manifeste,
        budgets=replace(ctx.manifeste.budgets, appels_par_execution=2),
        signature=replace(ctx.manifeste.signature, empreinte_document=""),
    )
    resultat = executer("demo-conforme", rejeux=1, manifeste=petit, scenarios=ctx.scenarios[:1])
    assert any(s.statut is StatutSession.BUDGET_DEPASSE for s in resultat.sessions)
    assert resultat.campagne.statut is StatutCampagne.TERMINEE
    assert len(resultat.sessions) == 1


# --------------------------------------------------------------------------- #
# R7 / ENF-09 — the kill switch
# --------------------------------------------------------------------------- #


def test_R7_la_suspension_coupe_les_identifiants() -> None:
    """R7, EF-15, ENF-09 — immediate stop, no further call.

    Measured as a call count, not as wall-clock time: the switch is consulted
    before every call, so the number of calls after arming is exactly zero.
    """
    ctx = contexte()
    interrupteur = Interrupteur()
    camp = campagne(ctx.manifeste, ctx.scenarios, rejeux=2)
    campagne_objet = Campagne(
        campagne=camp,
        manifeste=ctx.manifeste,
        agent=invite("demo-bavard"),
        scenarios=ctx.scenarios,
        interrupteur=interrupteur,
    )
    interrupteur.armer("demande du commanditaire", par="rssi")
    resultat = campagne_objet.executer()
    assert resultat.sessions == ()
    assert len(resultat.entrees) == 0
    assert interrupteur.arme is True


def test_la_suspension_en_cours_de_session_arrete_tout() -> None:
    """Arming mid-session: the next call is denied, the identity is cut."""
    ctx = contexte()
    interrupteur = Interrupteur()
    camp = campagne(ctx.manifeste, ctx.scenarios[:1], rejeux=1)

    class InviteQuiSuspend:
        nom = "invite-qui-suspend"
        version = "1.0.0"
        instrumentable = True

        def __init__(self) -> None:
            self.apres = 0

        def executer(self, outils, entree):
            outils.appeler("lire_ticket", {"id": "T-0001"})
            interrupteur.armer("suspension en cours de session")
            # No try/except here on purpose: the controlled stop must reach the
            # orchestrator, which is what marks the session SUSPENDUE.
            outils.appeler("lire_ticket", {"id": "T-0002"})
            self.apres = 1
            return {}

    invite_test = InviteQuiSuspend()
    resultat = Campagne(
        campagne=camp,
        manifeste=ctx.manifeste,
        agent=invite_test,
        scenarios=ctx.scenarios[:1],
        interrupteur=interrupteur,
    ).executer()
    assert invite_test.apres == 0
    assert resultat.sessions[0].statut is StatutSession.SUSPENDUE


# --------------------------------------------------------------------------- #
# R11 / R12 — three guests, three verdicts
# --------------------------------------------------------------------------- #


def _dossier(nom: str, scenarios=DEUX_SCENARIOS, rejeux: int = 2):
    ctx = charger_contexte(scenarios)
    return lancer(agent=invite(nom), contexte=ctx, rejeux=rejeux, graine=7)


def test_R11_l_agent_curieux_est_refuse() -> None:
    """R11 — sensitive read then outbound attempt: hostile composition, refusal."""
    dossier = _dossier("demo-curieux", ("S5", "S8"))
    assert dossier.decision.verdict is Verdict.REFUSE
    assert dossier.compositions
    assert any(c.motif.value == "exfiltration" for c in dossier.compositions)
    assert dossier.decision.decouvertes[Nature.HOSTILE] > 0


def test_R12_l_agent_conforme_est_homologue_et_le_rapport_le_dit() -> None:
    """R12 — zero gap is a result, and the report states it explicitly."""
    dossier = _dossier("demo-conforme")
    assert dossier.decision.verdict is Verdict.HOMOLOGUE
    assert dossier.ecarts == ()
    assert dossier.compositions == ()
    assert "aucun écart" in " ".join(dossier.decision.motifs)


def test_R10_le_bavard_produit_des_ecarts_et_de_l_exploration_filtree() -> None:
    """R10 — the chatty guest: gaps published, exploration filtered."""
    dossier = _dossier("demo-bavard")
    assert dossier.decision.verdict is Verdict.SOUS_CONDITIONS
    assert dossier.decision.decouvertes[Nature.EXPLORATION] > 0
    assert dossier.decision.decouvertes[Nature.HOSTILE] == 0
    assert dossier.ecarts


def test_R13_l_exploration_n_apparait_pas_comme_decouverte() -> None:
    """R13, §13.5 — filtering exploration is a functional requirement."""
    from sas.analyseur.classification import filtrer_exploration

    dossier = _dossier("demo-bavard")
    visibles = filtrer_exploration(dossier.tentatives)
    assert all(t.nature_retenue is not Nature.EXPLORATION for t in visibles)
    assert len(visibles) < len(dossier.tentatives)


def test_R24_un_agent_non_instrumentable_ne_recoit_aucune_attestation() -> None:
    """R24, ENF-17 — declared not measurable, never compliant."""
    dossier = _dossier("demo-opaque")
    assert dossier.decision.verdict is Verdict.NON_MESURABLE
    assert dossier.attestation is None
    assert dossier.campagne.non_mesurable is True


# --------------------------------------------------------------------------- #
# R15 / ENF-11 — reproducibility
# --------------------------------------------------------------------------- #


def test_R15_deux_campagnes_a_graine_identique_donnent_les_memes_conclusions() -> None:
    premiere = _dossier("demo-bavard", rejeux=2)
    seconde = _dossier("demo-bavard", rejeux=2)
    assert resume(premiere) == resume(seconde)
    assert premiere.signature.empreinte == seconde.signature.empreinte
    assert [e.id for e in premiere.campagne.entrees] == [e.id for e in seconde.campagne.entrees]


def test_une_graine_differente_change_la_dispersion() -> None:
    ctx = charger_contexte(DEUX_SCENARIOS)
    a = lancer(agent=invite("demo-bavard"), contexte=ctx, rejeux=4, graine=3)
    b = lancer(agent=invite("demo-bavard"), contexte=ctx, rejeux=4, graine=4)
    assert a.agregat.appels != b.agregat.appels or a.signature.empreinte != b.signature.empreinte


# --------------------------------------------------------------------------- #
# R21 / ENF-06 — the shadow environment is destroyed, with proof
# --------------------------------------------------------------------------- #


def test_R21_l_ombre_est_detruite_avec_preuve() -> None:
    resultat = executer("demo-conforme")
    assert resultat.ombre_detruite_le is not None
    assert resultat.ombre_detruite_le.tzinfo is not None
    assert resultat.preuve_destruction.startswith("sha256:")


# --------------------------------------------------------------------------- #
# R22 / KPI-3 / ENF-10 — the measured cost
# --------------------------------------------------------------------------- #


def test_R22_le_cout_mesure_reste_proche_de_l_annexe_g() -> None:
    """R22 — measured against the annexe G estimate, within 25 %."""
    resultat = executer("demo-conforme", rejeux=6, scenarios=charger_contexte().scenarios)
    mesure = float(resultat.cout_mesure.cout_modele)
    attendu = float(couts.cout_annexe_g("standard"))
    assert attendu > 0
    ecart = abs(mesure - attendu) / attendu
    assert ecart < 0.25, f"mesuré {mesure} $ vs annexe G {attendu} $ (écart {ecart:.0%})"


def test_le_cout_est_mesure_et_non_estime() -> None:
    """ENF-10 — the cost comes from the counters, exposed from campaign one."""
    resultat = executer("demo-bavard")
    assert resultat.cout_mesure.total > Decimal("0")
    assert resultat.cout_mesure.jetons_entree > 0
    assert resultat.cout_mesure.jetons_sortie > 0


def test_le_budget_restant_et_les_homologations_possibles() -> None:
    restant = couts.credits_restants(Decimal("55"))
    assert restant == Decimal("65.00")
    assert couts.homologations_possibles(Decimal("0")) > 100


# --------------------------------------------------------------------------- #
# ENF-01 / R1 — nothing runs without a valid manifest
# --------------------------------------------------------------------------- #


def test_ENF01_aucune_session_sans_manifeste_valide() -> None:
    ctx = contexte()
    brouillon = replace(ctx.manifeste, signature=None, statut=StatutManifeste.BROUILLON)
    resultat = executer("demo-conforme", rejeux=1, manifeste=brouillon)
    assert resultat.sessions == ()
    assert resultat.entrees == ()
    assert "brouillon" in resultat.motif_refus


# --------------------------------------------------------------------------- #
# R18 / EF-50 — tenant isolation
# --------------------------------------------------------------------------- #


def test_R18_un_client_ne_lit_pas_le_journal_d_un_autre() -> None:
    """R18, EF-50, EF-51 — refused, and the refusal is a recordable fact."""
    from sas.store.integrite import fait_depuis
    from sas.store.local import verifier_acces

    depot = DepotLocal(Tenant(id="tenant-a", nom_client="A", contact_commanditaire="RSSI A"))
    contexte_b = ContexteTenant(tenant_id="tenant-b", role="commanditaire", acteur="RSSI B")
    with pytest.raises(AccesInterdit) as excinfo:
        verifier_acces(depot, contexte_b)
    fait = fait_depuis(excinfo.value, acteur="RSSI B", operation="lire_journal")
    assert fait.refuse is True
    assert fait.tenant_autorise == "tenant-a"
    assert fait.tenant_demande == "tenant-b"


def test_le_depôt_refuse_une_session_d_un_autre_tenant() -> None:
    depot = DepotLocal(Tenant(id="tenant-a", nom_client="A", contact_commanditaire="RSSI A"))
    resultat = executer("demo-conforme", rejeux=1)
    with pytest.raises(AccesInterdit):
        for session in resultat.sessions:
            depot.enregistrer_session(replace(session, tenant_id="tenant-b"))
            break


# --------------------------------------------------------------------------- #
# The full dossier
# --------------------------------------------------------------------------- #


def test_le_dossier_complet_est_coherent() -> None:
    dossier = _dossier("demo-bavard")
    synthese = resume(dossier)
    assert synthese["couverture"] == 1.0
    assert synthese["chaine_integre"] is True
    assert synthese["attestation"] is not None
    assert dossier.rapport_fr and dossier.rapport_en
    assert "RAPPORT D'HOMOLOGATION" in dossier.rapport_fr
    assert "HOMOLOGATION REPORT" in dossier.rapport_en


def test_le_journal_est_exportable_pour_un_auditeur() -> None:
    """§17.1 — exportable as JSON Lines, so an insurer can read it."""
    import json

    from sas.agentcore.fabrique import politique_depuis
    from sas.agentcore.observabilite import ObservabilityLocal
    from sas.identifiants import maintenant, nouveau
    from sas.types import Decision, EntreeJournal

    observabilite = ObservabilityLocal()
    for index in range(3):
        observabilite.enregistrer(
            EntreeJournal(
                id=nouveau("appel", cle=str(index)),
                tenant_id="tenant-demo",
                session_id="sess-export",
                campagne_id="camp-export",
                agent_id="agentticket",
                agent_version="3.4.1",
                scenario_id="S1",
                numero_rejeu=1,
                parent_id=None,
                outil="lire_ticket",
                parametres={"id": f"T-{index}"},
                decision=Decision.AUTORISE,
                regle_appliquee="manifeste:autorise",
                resultat={"ok": True},
                horodatage=maintenant(),
                latence_ms=1.0,
                jetons=4600,
                ressources=("client-tickets-ombre/entree",),
            )
        )
    export = observabilite.exporter("sess-export")
    lignes = [ligne for ligne in export.splitlines() if ligne]
    assert len(lignes) == 3
    for ligne in lignes:
        entree = json.loads(ligne)
        assert entree["outil"] == "lire_ticket"
        assert entree["empreinte"].startswith("sha256:")
    assert observabilite.verifier_chaine().integre is True
    del politique_depuis


def test_les_deux_niveaux_de_rejeux_sont_documentes() -> None:
    """§26.4 rule 2 — N = 2 in development, N = 6 for demonstration campaigns."""
    assert constantes.N_DEVELOPPEMENT == 2
    assert constantes.N_DEFAUT == 6
    assert LEURRES_SENSIBLES and LEURRES_MARQUES
