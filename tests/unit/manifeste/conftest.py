"""Shared helpers for the manifest lot.

Invalid manifests are **derived** from the reference fixture (annexe A) rather
than copied into eight near-identical files: one source, one truth.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from sas.types import Manifeste

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "manifeste-exemple.yaml"


def donnees_base() -> dict[str, Any]:
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def texte_base() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def poser(donnees: dict[str, Any], chemin: str, valeur: Any) -> dict[str, Any]:
    """Set a dotted path inside a nested dict or list. `None` deletes the key.

    A numeric step indexes a list, so `donnees_demandees.0.ressource` reaches
    the first declared resource.
    """
    cles = chemin.split(".")
    cible: Any = donnees
    for cle in cles[:-1]:
        cible = cible[int(cle)] if cle.isdigit() else cible.setdefault(cle, {})
    derniere = cles[-1]
    if derniere.isdigit():
        cible[int(derniere)] = valeur
    elif valeur is None:
        cible.pop(derniere, None)
    else:
        cible[derniere] = valeur
    return donnees


def variante(*modifications: tuple[str, Any]) -> str:
    """Reference manifest, with dotted-path edits, serialised back to YAML."""
    donnees = donnees_base()
    for chemin, valeur in modifications:
        poser(donnees, chemin, valeur)
    return yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False)


def manifeste_valide() -> Manifeste:
    from sas.manifeste import charger_manifeste

    return charger_manifeste(FIXTURE)
