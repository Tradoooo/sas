"""Lot 8 — the analyser: aggregate, propose, decide (spec §21.4).

Pass 1 (`agregation`) and pass 3 (`classification`) are pure code. Pass 2 — the
model's proposal — is injected: `sas.modeles` provides the Bedrock adapter and a
deterministic fake. Nothing here ever lets a model set a nature (EF-25).
"""

from __future__ import annotations

from sas.analyseur.agregation import Agregat, TentativeBrute, agreger
from sas.analyseur.classification import (
    calculer_signaux,
    classer,
    compter_par_nature,
    decider,
    filtrer_exploration,
    grouper,
    trancher,
)

__all__ = [
    "Agregat",
    "TentativeBrute",
    "agreger",
    "calculer_signaux",
    "classer",
    "compter_par_nature",
    "decider",
    "filtrer_exploration",
    "grouper",
    "trancher",
]
