"""Publish the API contract: `docs/openapi.json`, generated not hand-written.

The route inventory is frozen in `constantes.ROUTES` and a test asserts the app
registers all 22 of them. This script exports what FastAPI itself declares, so a
third party can read the contract without reading the code — and so the published
contract cannot drift from the running app.

Deterministic: keys sorted, no timestamp, no server URL from the local machine.
Running it twice produces identical bytes, which a test checks.

Usage:
    PYTHONPATH=src python3 scripts/genere_openapi.py [--sortie docs/openapi.json] [--verifier]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE))

SORTIE_DEFAUT = RACINE / "docs" / "openapi.json"


def schema() -> dict:
    """The OpenAPI document of the running app, with nothing machine-specific."""
    from sas import constantes
    from sas.api.app import creer_app

    application = creer_app()
    document = application.openapi()
    document.pop("servers", None)
    document["info"] = {
        "title": "Sas",
        "version": "0.1.0",
        "description": (
            "Homologation and controlled execution of third-party AI agents. "
            "No route accepts a tenant as a parameter (EF-51): the tenant is "
            "derived from the bearer token."
        ),
        "x-route-inventory": [f"{methode} {chemin}" for methode, chemin in constantes.ROUTES],
    }
    return document


def ecrire(document: dict, sortie: Path) -> None:
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def verifier(document: dict, sortie: Path) -> int:
    """Compare against the committed file: a stale contract fails the build."""
    if not sortie.is_file():
        print(f"contrat absent : {sortie}")
        return 1
    attendu = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if sortie.read_text(encoding="utf-8") != attendu:
        print(f"CONTRAT PÉRIMÉ : régénérer {sortie.relative_to(RACINE)}")
        return 1
    print(f"contrat à jour : {sortie.relative_to(RACINE)}")
    return 0


def compter_routes(document: dict) -> tuple[int, list[str]]:
    """Every declared route must appear in the exported contract."""
    from sas import constantes

    chemins = document.get("paths", {})
    manquantes = []
    for methode, chemin in constantes.ROUTES:
        if chemin not in chemins or methode.lower() not in chemins[chemin]:
            manquantes.append(f"{methode} {chemin}")
    return len(constantes.ROUTES), manquantes


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    parseur.add_argument("--verifier", action="store_true", help="compare au fichier committé sans écrire")
    args = parseur.parse_args()

    document = schema()
    total, manquantes = compter_routes(document)
    if manquantes:
        print(f"ERREUR: {len(manquantes)} route(s) de l'inventaire absente(s) du contrat :")
        for manquante in manquantes:
            print(f"  - {manquante}")
        return 1
    print(f"{total} routes de l'inventaire présentes dans le contrat")

    if args.verifier:
        return verifier(document, args.sortie)
    ecrire(document, args.sortie)
    print(f"écrit {args.sortie} ({args.sortie.stat().st_size} octets)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
