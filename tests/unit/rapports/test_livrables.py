"""Acceptance tests R14, R16, R19, R20 — deliverables, drift and honesty.

These four close the traceability matrix of §33.2: dead permissions published,
an undeclared model change detected, an attestation poor in details, and a
vendor report carrying no client data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sas import statistiques
from sas.cli_partage import charger_contexte, invite, lancer
from sas.homologation import enveloppe
from sas.rapports import editeur as module_editeur
from sas.signature import calculer, comparer, distance, sceller
from sas.types import ActionDerive, Langue, Mode, Nature, Verdict

DATE = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


def _dossier(agent: str, scenarios=("S1", "S4", "S5"), rejeux: int = 2):
    contexte = charger_contexte(scenarios)
    return lancer(agent=invite(agent), contexte=contexte, rejeux=rejeux, graine=7)


# --------------------------------------------------------------------------- #
# R14 — declared but never used permissions are published
# --------------------------------------------------------------------------- #


def test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees() -> None:
    """R14, EF-21 — a dead permission is a finding, not a silence.

    The reference manifest declares three resources and the conforming guest
    uses all three, so a fourth declaration is added here: an archive the agent
    never touches. That is exactly the case a CISO fears — access granted and
    never exercised (§4, what IAM Access Analyzer reports natively).
    """
    from dataclasses import replace

    from sas import ecarts as module_ecarts
    from sas.analyseur.agregation import agreger
    from sas.orchestrateur import Campagne, nouvelle_campagne
    from sas.types import DonneeDemandee, TypeEcart

    contexte = charger_contexte(("S1",))
    archive = DonneeDemandee(
        type="index", ressource="archive-2019-client", justification="historique des dossiers clos"
    )
    manifeste = replace(
        contexte.manifeste, donnees_demandees=(*contexte.manifeste.donnees_demandees, archive)
    )
    campagne = nouvelle_campagne(
        tenant_id="tenant-demo",
        agent_id=manifeste.agent_id,
        manifeste=manifeste,
        n_rejeux=1,
        graine=7,
        scenarios=["S1"],
    )
    resultat = Campagne(
        campagne=campagne,
        manifeste=manifeste,
        agent=invite("demo-conforme"),
        scenarios=contexte.scenarios,
    ).executer()
    agregat = agreger(resultat.entrees)
    calcules = module_ecarts.calculer(
        campagne.id,
        agregat,
        declarees=module_ecarts.ressources_declarees_depuis(manifeste, Mode.OMBRE),
        graine=7,
    )
    mortes = [e for e in calcules if e.type is TypeEcart.PERMISSION_MORTE]
    assert "archive-2019-ombre" in [e.ressource for e in mortes]
    assert all(e.declare is True and e.observe is False for e in mortes)


def test_EF21_la_source_native_est_citee_quand_elle_existe() -> None:
    """EF-21 — IAM Access Analyzer findings are quoted, not recomputed."""
    from sas import ecarts as module_ecarts
    from sas.analyseur.agregation import Agregat
    from sas.types import TypeEcart

    ecart = module_ecarts.calculer(
        "camp-1",
        Agregat(),
        declarees=("kb-documentation-ombre", "dynamodb:suivi-ombre"),
        graine=1,
    )
    mortes = [e for e in ecart if e.type is TypeEcart.PERMISSION_MORTE]
    assert mortes
    enrichi = module_ecarts.croiser_acces_inutilises(
        "camp-1",
        ecart,
        [{"ressource": mortes[0].ressource}],
        disponible=True,
    )
    assert any(e.source == "iam-access-analyzer" for e in enrichi)
    # When the native source has no history yet, the report says so.
    inchanges = module_ecarts.croiser_acces_inutilises("camp-1", ecart, [], disponible=False)
    assert all(e.source == "journal" for e in inchanges)


# --------------------------------------------------------------------------- #
# R16 — a model change without a version change is detected
# --------------------------------------------------------------------------- #


def test_R16_un_changement_de_modele_non_declare_est_detecte() -> None:
    """R16, EF-33 — the behavioural signature differs, the alert fires."""
    reference = _dossier("demo-conforme")
    courante = _dossier("demo-bavard")

    mesure = distance(reference.signature, courante.signature)
    assert mesure > 0.0
    ecart = comparer(
        agent_id="agentticket",
        tenant_id="tenant-demo",
        reference=enveloppe(
            reference,
            agent_id="agentticket",
            tenant_id="tenant-demo",
            version="3.4.1",
            reference=True,
            date=DATE,
        ),
        courante=enveloppe(
            courante,
            agent_id="agentticket",
            tenant_id="tenant-demo",
            version="3.4.1",
            date=DATE + timedelta(days=7),
        ),
        changement_non_declare=True,
        alerte_le=DATE + timedelta(days=7),
    )
    assert ecart.distance == mesure
    assert ecart.changement_non_declare is True
    assert ecart.action in (ActionDerive.ALERTE, ActionDerive.REHOMOLOGATION, ActionDerive.SUSPENSION)
    assert ecart.detail, "l'alerte doit dire ce qui a changé"


def test_la_signature_est_stable_pour_un_meme_comportement() -> None:
    """ENF-11 — the same behaviour gives the same signature."""
    premier = _dossier("demo-conforme")
    second = _dossier("demo-conforme")
    assert premier.signature.empreinte == second.signature.empreinte
    assert distance(premier.signature, second.signature) == 0.0


def test_les_seuils_de_derive_sont_en_configuration() -> None:
    """§15.3 — thresholds live in configuration, versioned with the manifest."""
    from sas.constantes import SEUILS_DEFAUT

    assert SEUILS_DEFAUT.distance_derive_alerte < SEUILS_DEFAUT.distance_derive_suspension
    assert calculer is not None and sceller is not None


# --------------------------------------------------------------------------- #
# R19 — the attestation is deliberately poor in details
# --------------------------------------------------------------------------- #


def test_R19_l_attestation_est_pauvre_en_details_et_porte_sa_portee() -> None:
    """R19, §17.2 — no client data, no reproducible detail, but the bound."""
    dossier = _dossier("demo-bavard")
    attestation = dossier.attestation
    assert attestation is not None
    texte = __import__("sas.rapports.attestation", fromlist=["texte"]).texte(attestation, "fr")

    # The statistical scope is printed (KPI-7).
    assert "PORTÉE STATISTIQUE" in texte
    assert "rejeux" in texte
    assert "rare" in texte.lower()

    # Deliberately poor: no tool parameter, no ticket content, no resource path.
    for interdit in ("T-0001", "SYNTHETIQUE", "client-tickets", "grille des salaires", "parametres"):
        assert interdit not in texte, interdit

    # It states whose decision the go-live is.
    assert "commanditaire" in texte


def test_l_attestation_anglaise_existe_aussi() -> None:
    """ENF-13 — the deliverable exists in both languages."""
    dossier = _dossier("demo-conforme")
    attestation = dossier.attestation
    assert attestation is not None
    module = __import__("sas.rapports.attestation", fromlist=["texte"])
    anglais = module.texte(attestation, "en")
    assert "HOMOLOGATION ATTESTATION" in anglais
    assert "STATISTICAL SCOPE" in anglais


def test_la_borne_publiee_est_celle_du_chapitre_14() -> None:
    """§14.2 — the published numbers are the specification's, to the digit."""
    assert statistiques.probabilite_detection(0.50, 6) == 0.9844
    assert statistiques.probabilite_detection(0.25, 6) == 0.8220
    assert statistiques.probabilite_detection(0.25, 12) == 0.9683
    assert statistiques.rejeux_necessaires(0.50) == 5
    assert statistiques.rejeux_necessaires(0.25) == 11
    assert statistiques.rejeux_necessaires(0.10) == 29


def test_une_memoire_persistante_annule_la_borne() -> None:
    """§14.6 — the report says so rather than publishing a false number."""
    borne = statistiques.borne(6, memoire_persistante=True)
    assert borne.rejeux_independants is False
    assert borne.lignes == ()
    assert "persistante" in statistiques.phrase_portee(borne, "fr")


# --------------------------------------------------------------------------- #
# R20 — the vendor report carries no client data
# --------------------------------------------------------------------------- #


def test_R20_le_rapport_editeur_ne_contient_aucune_donnee_client() -> None:
    """R20, EF-42, §24.5 — without this the vendor will not sign the manifest."""
    dossier = _dossier("demo-bavard", scenarios=("S1", "S4", "S5", "S8"))
    texte = dossier.rapport_editeur
    assert "RAPPORT D'ÉCART DESTINÉ À L'ÉDITEUR" in texte
    assert module_editeur.sans_donnee_client(texte) is True
    # It is actionable: the vendor receives a list of corrections.
    assert "Corrections demandées" in texte


def test_le_rapport_editeur_existe_en_anglais() -> None:
    dossier = _dossier("demo-curieux", scenarios=("S5", "S8"))
    construit = module_editeur.construire(
        manifeste=charger_contexte(("S5", "S8")).manifeste,
        verdict=dossier.decision.verdict,
        tentatives=dossier.tentatives,
        compositions=dossier.compositions,
        ecarts=dossier.ecarts,
    )
    anglais = module_editeur.texte(construit, Langue.EN)
    assert "GAP REPORT FOR THE VENDOR" in anglais
    assert module_editeur.sans_donnee_client(anglais) is True


def test_le_rapport_complet_existe_dans_les_deux_langues() -> None:
    """EF-40 — the homologation report exists in French and in English."""
    dossier = _dossier("demo-bavard")
    assert "RAPPORT D'HOMOLOGATION" in dossier.rapport_fr
    assert "HOMOLOGATION REPORT" in dossier.rapport_en
    assert "10. Ce que ce rapport ne garantit pas" in dossier.rapport_fr
    assert "10. What this report does not guarantee" in dossier.rapport_en


def test_un_agent_non_mesurable_ne_produit_aucun_rapport_de_conformite() -> None:
    """ENF-17 — declared not measurable, never compliant."""
    dossier = _dossier("demo-opaque")
    assert dossier.decision.verdict is Verdict.NON_MESURABLE
    assert dossier.attestation is None
    assert dossier.decision.decouvertes[Nature.HOSTILE] == 0
