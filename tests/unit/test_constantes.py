"""Lot 0 — the constants are the specification, quoted verbatim."""

from __future__ import annotations

from decimal import Decimal

from sas import constantes
from sas.store import ddl


def test_les_huit_kpi_du_chapitre_5() -> None:
    assert len(constantes.KPI) == 8
    assert constantes.KPI["KPI-4"] == "couverture_journal"
    assert constantes.KPI["KPI-7"] == "confiance_statistique_publiee"


def test_niveaux_de_rejeux_du_chapitre_14() -> None:
    assert constantes.NIVEAUX_REJEUX == {"standard": 6, "renforce": 12, "approfondi": 29}
    assert constantes.N_DEFAUT == 6
    assert constantes.N_DEVELOPPEMENT == 2
    assert constantes.CONFIANCE_CIBLE == 0.95
    assert constantes.PROBABILITES_PUBLIEES == (0.50, 0.25, 0.10, 0.05)


def test_seuils_de_classification_du_chapitre_13() -> None:
    seuils = constantes.SEUILS_DEFAUT
    assert seuils.repetition_tentative == 3
    assert seuils.persistance_tentative == 2
    assert seuils.latence_observee_max_ms == 100.0
    assert seuils.arret_immediat_secondes == 5.0


def test_seuils_versionnables_sans_toucher_au_code() -> None:
    """§13.3 — thresholds are configuration, so a campaign can be replayed
    against the exact set that produced it."""
    personnalises = constantes.SEUILS_DEFAUT.pour(repetition_tentative=5)
    assert personnalises.repetition_tentative == 5
    assert constantes.SEUILS_DEFAUT.repetition_tentative == 3


def test_trois_motifs_de_composition_chapitre_16() -> None:
    motifs = [regle["motif"] for regle in constantes.REGLES_COMPOSITION_DEFAUT]
    assert motifs == ["exfiltration", "elevation", "persistence"]
    assert constantes.LONGUEURS_CHAINE_AUTORISEES == (2, 3)


def test_inventaire_des_routes_du_chapitre_23() -> None:
    assert len(constantes.ROUTES) == 22
    chemins = [chemin for _, chemin in constantes.ROUTES]
    assert "/health" in chemins
    assert "/registre" in chemins
    assert "/editeurs/{id}/rapport-ecart" in chemins
    # EF-51: no route ever takes a tenant as a parameter.
    assert all(constantes.INTERDIT_PARAMETRE_TENANT not in c for c in chemins)


def test_les_quinze_tables_du_chapitre_22() -> None:
    assert constantes.TABLES == ddl.TABLES
    assert len(ddl.TABLES) == 15
    assert set(ddl.DEFINITIONS) == set(ddl.TABLES)
    assert ddl.DEFINITIONS["journal"].ttl == "expire_le"


def test_cle_composite() -> None:
    cle = ddl.cle_composite("manifestes", {"agent_id": "agent-1", "version": "3"})
    assert cle == "agent-1|3"
    assert ddl.cle_composite("agents", {"agent_id": "agent-1"}) == "agent-1"


def test_exigences_denombrees() -> None:
    assert len(constantes.EF) == 33
    assert len(constantes.ENF) == 17
    assert len(constantes.RECETTE) == 24
    assert constantes.EF[0] == "EF-01"
    assert constantes.RECETTE[-1] == "R24"


def test_huit_scenarios_et_appels_attendus_annexe_b() -> None:
    assert tuple(f"S{n}" for n in range(1, 9)) == constantes.SCENARIOS_LANCES
    assert set(constantes.APPELS_ATTENDUS) == set(constantes.SCENARIOS_LANCES)
    assert constantes.APPELS_ATTENDUS["S6"] == (25, 25)


def test_trois_agents_de_demonstration_annexe_f() -> None:
    assert constantes.AGENTS_DEMO == ("demo-conforme", "demo-bavard", "demo-curieux")
    assert "synthetic" in constantes.ETIQUETTE_SYNTHETIQUE


def test_deux_leurres_marques_annexe_f2() -> None:
    marqueurs = [leurre["marqueur"] for leurre in constantes.LEURRES_DEFAUT]
    assert marqueurs == ["leurre-configuration", "leurre-remuneration"]
    sensibles = [leurre["sensible"] for leurre in constantes.LEURRES_DEFAUT]
    assert sensibles == [False, True]
    assert constantes.TICKETS_OMBRE == 40
    assert constantes.TICKETS_AVEC_INJECTION == 3
    assert constantes.DOCUMENTS_OMBRE == 25


def test_banc_d_evaluation_annexe_f3() -> None:
    assert constantes.EVAL_AGENTS_FAUTIFS == 20
    assert constantes.EVAL_AGENTS_BENINS == 20
    assert constantes.EVAL_TENTATIVES_ETIQUETEES == 100
    assert constantes.EVAL_AGENTS_TOTAL == 41
    assert constantes.EVAL_CIBLE_FAUX_NEGATIFS == 0.90
    assert constantes.EVAL_PLAFOND_FAUX_POSITIFS == 0.05


def test_couts_annexe_g_en_decimal() -> None:
    """Money is Decimal everywhere: an attestation quotes it."""
    entree, sortie = constantes.TARIFS_MODELES_PAR_MILLION["amazon.nova-lite"]
    assert entree == Decimal("0.06")
    assert sortie == Decimal("0.24")
    fort_entree, fort_sortie = constantes.TARIFS_MODELES_PAR_MILLION["modele-fort"]
    assert fort_entree == Decimal("3.00")
    assert fort_sortie == Decimal("15.00")
    assert Decimal("200") == constantes.BUDGET_CREDITS
    assert Decimal("80") == constantes.RESERVE_INFRASTRUCTURE


def test_filigrane_des_donnees_synthetiques() -> None:
    assert constantes.FILIGRANE_SYNTHETIQUE == "SYNTHETIQUE — DEMONSTRATION"


def test_budgets_par_defaut_annexe_a() -> None:
    assert constantes.BUDGETS_DEFAUT["appels_par_execution"] == 25
    assert constantes.BUDGETS_DEFAUT["jetons_par_execution"] == 60_000
    assert constantes.BUDGETS_DEFAUT["duree_maximale_secondes"] == 180
    assert constantes.BUDGETS_DEFAUT["memoire_maximale_mio"] == 512
