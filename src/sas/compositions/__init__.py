"""Lot 9 — forbidden call chains, rules as data (spec §16).

Public surface: `charger_regles`, `detecter`, `etiqueter`,
`ressources_dans_composition`.
"""

from __future__ import annotations

from sas.compositions.detecteur import (
    Motifs,
    RegleComposition,
    charger_regles,
    contient,
    detecter,
    etiqueter,
    ressources_dans_composition,
)

__all__ = [
    "Motifs",
    "RegleComposition",
    "charger_regles",
    "contient",
    "detecter",
    "etiqueter",
    "ressources_dans_composition",
]
