"""Lot 11 — behavioural signature and drift detection (spec §15).

Public surface: `calculer`, `sceller`, `distance`, `detail`, `comparer`,
`action_pour`, `alertes_supplementaires`.
"""

from __future__ import annotations

from sas.signature.moteur import (
    Alerte,
    action_pour,
    alertes_supplementaires,
    calculer,
    comparer,
    detail,
    distance,
    sceller,
)

__all__ = [
    "Alerte",
    "action_pour",
    "alertes_supplementaires",
    "calculer",
    "comparer",
    "detail",
    "distance",
    "sceller",
]
