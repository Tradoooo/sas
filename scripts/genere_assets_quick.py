#!/usr/bin/env python3
"""Write ``infra/quick/datasets.json`` from the code (lot 16).

The bundle is generated from ``sas.quicksight`` — the single source of truth —
so the asset on disk can never drift from the code: ``scripts/check_limits.py``
and the tests just regenerate and compare. Deterministic on purpose (sorted
keys, no timestamps, no network).

Run with ``PYTHONPATH=src python3 scripts/genere_assets_quick.py``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sas.quicksight import bundle

RACINE = Path(__file__).resolve().parent.parent
CIBLE = RACINE / "infra" / "quick" / "datasets.json"


def contenu() -> str:
    """The bundle as stable text: sorted keys, ASCII-safe, final newline."""
    return json.dumps(bundle(), ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def ecrire(chemin: Path = CIBLE) -> Path:
    """Write the bundle if it changed, so reruns are a no-op off the filesystem."""
    texte = contenu()
    if chemin.exists() and chemin.read_text(encoding="utf-8") == texte:
        return chemin
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    return chemin


def main() -> int:
    chemin = ecrire()
    print(f"quick: {chemin.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
