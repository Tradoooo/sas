"""Amazon Quick datasets and RLS (lot 16): deterministic and multi-tenant."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from sas import quicksight
from sas.store import ddl

RACINE = Path(__file__).resolve().parents[3]


def test_trois_datasets() -> None:
    identifiants = {d.identifiant for d in quicksight.datasets()}
    assert identifiants == {"registre_flotte", "tendances_derive", "cout_par_tenant"}


def test_sources_lisent_le_ddl() -> None:
    for dataset in quicksight.datasets():
        assert dataset.source in ddl.DEFINITIONS


def test_un_client_ne_voit_que_ses_agents() -> None:
    regle = next(r for r in quicksight.regles_rls() if r.role == "tenant" and r.dataset == "registre_flotte")
    assert regle.colonne == "tenant_id"


def test_un_editeur_ne_voit_que_ses_agents() -> None:
    regles_editeur = [r for r in quicksight.regles_rls() if r.role == "editeur"]
    assert regles_editeur
    assert all(r.colonne == "editeur_id" for r in regles_editeur)
    assert all(r.dataset == "registre_flotte" for r in regles_editeur)


def test_un_editeur_n_accede_pas_au_cout() -> None:
    assert "editeur" not in quicksight.ACCES_PAR_DATASET["cout_par_tenant"]


def test_bundle_deterministe() -> None:
    premier = json.dumps(quicksight.bundle(), sort_keys=True)
    second = json.dumps(quicksight.bundle(), sort_keys=True)
    assert premier == second


def test_script_regénère_le_meme_fichier() -> None:
    chemin_script = RACINE / "scripts" / "genere_assets_quick.py"
    spec = importlib.util.spec_from_file_location("genere_assets_quick", chemin_script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    attendu = json.dumps(quicksight.bundle(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    assert module.contenu() == attendu


def test_fichier_sur_disque_stable() -> None:
    chemin = RACINE / "infra" / "quick" / "datasets.json"
    attendu = json.dumps(quicksight.bundle(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    assert chemin.read_text(encoding="utf-8") == attendu
