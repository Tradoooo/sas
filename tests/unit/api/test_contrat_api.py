"""The published API contract cannot drift from the running app."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sas import constantes

RACINE = Path(__file__).resolve().parents[3]
CONTRAT = RACINE / "docs" / "openapi.json"
GENERATEUR = RACINE / "scripts" / "genere_openapi.py"

pytest.importorskip("fastapi", reason="FastAPI est un extra optionnel")


def document() -> dict:
    return json.loads(CONTRAT.read_text(encoding="utf-8"))


def test_le_contrat_est_commite() -> None:
    assert CONTRAT.is_file(), "docs/openapi.json doit être publié"


def test_les_22_routes_de_l_inventaire_y_sont() -> None:
    """EF-51 / §23 — the frozen inventory and the published contract agree."""
    chemins = document()["paths"]
    manquantes = [
        f"{methode} {chemin}"
        for methode, chemin in constantes.ROUTES
        if chemin not in chemins or methode.lower() not in chemins[chemin]
    ]
    assert manquantes == []


def test_aucune_route_ne_prend_un_tenant_en_parametre() -> None:
    """EF-51, checked on the published contract rather than on the source."""
    for chemin, operations in document()["paths"].items():
        assert constantes.INTERDIT_PARAMETRE_TENANT not in chemin
        for methode, operation in operations.items():
            if not isinstance(operation, dict):
                continue
            for parametre in operation.get("parameters", []):
                assert parametre.get("name") != constantes.INTERDIT_PARAMETRE_TENANT, f"{methode} {chemin}"


def test_le_contrat_ne_contient_aucune_url_de_machine() -> None:
    """No server URL, no localhost: what is published describes the contract,
    not whoever generated it."""
    contenu = CONTRAT.read_text(encoding="utf-8")
    assert "servers" not in document()
    assert "127.0.0.1" not in contenu
    assert "localhost" not in contenu


def test_le_contrat_rappelle_la_regle_du_tenant() -> None:
    """The description states the invariant a reader must not miss."""
    assert "EF-51" in document()["info"]["description"]


@pytest.mark.slow
def test_le_contrat_est_a_jour() -> None:
    """Regenerate and compare: a route added without republishing fails here."""
    resultat = subprocess.run(
        [sys.executable, str(GENERATEUR), "--verifier"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(RACINE),
    )
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
