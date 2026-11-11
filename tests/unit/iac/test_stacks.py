"""IaC stack metadata: tables, routes, components, budget, no module-level CDK.

None of these tests import ``aws_cdk`` — they exercise the pure data surface of
``infra.cdk``, which is exactly what the CI can afford (offline, ≤ 5 minutes).
"""

from __future__ import annotations

import re
from pathlib import Path

from infra.cdk import agentcore, api, common, data, observability, orchestration

from sas import constantes

CDK = Path(__file__).resolve().parents[3] / "infra" / "cdk"


def test_15_tables_alignees_constantes() -> None:
    assert data.noms_tables() == constantes.TABLES


def test_index_journal_et_appels() -> None:
    tables = {t["nom"]: t for t in data.tables_depuis_ddl()}
    for nom in ("journal", "appels"):
        index = {i["cle"] for i in tables[nom]["index"]}
        assert {"session_id", "campagne_id"} <= index


def test_chaque_route_a_un_handler() -> None:
    chemins = {(h["methode"], h["chemin"]) for h in api.handlers()}
    assert chemins == set(constantes.ROUTES)


def test_aucune_route_ne_prend_un_tenant() -> None:
    for chemin in (chemin for _, chemin in constantes.ROUTES):
        assert constantes.INTERDIT_PARAMETRE_TENANT not in chemin


def test_six_composants_agentcore_nommes() -> None:
    assert agentcore.composants_agentcore() == (
        "Runtime",
        "Gateway",
        "Identity",
        "Policy",
        "Memory",
        "Observability",
    )


def test_reseau_ombre_sans_egress() -> None:
    assert "aucune route sortante sauf la passerelle" in agentcore.reseau_ombre()["egress"]


def test_etapes_rejeu_dans_l_ordre() -> None:
    assert orchestration.etapes_rejeu() == (
        "creer_session",
        "armer_identite",
        "reinitialiser_ombre",
        "executer",
        "collecter_journal",
        "detruire",
    )


def test_definition_sfn_couvre_les_etapes() -> None:
    itineraire = orchestration.definition_sfn()["States"]["ParScenario"]["Iterator"]["States"]
    etats = itineraire["ParRejeu"]["Iterator"]["States"]
    assert set(orchestration.etapes_rejeu()) <= set(etats)


def test_alarme_disponibilite_et_budget() -> None:
    noms = {a["nom"] for a in observability.alarmes()}
    assert {"disponibilite-api", "budget-200"} <= noms


def test_six_regles_de_budget() -> None:
    assert len(observability.regles_budget()) == 6


def test_pas_d_import_cdk_niveau_module() -> None:
    for fichier in CDK.glob("*.py"):
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            assert not re.match(r"^(import|from) aws_cdk", ligne), f"{fichier.name}: {ligne}"


def test_sept_domaines_etiquetes() -> None:
    assert common.domaines() == common.DOMAINES
    assert len(common.domaines()) == 7
