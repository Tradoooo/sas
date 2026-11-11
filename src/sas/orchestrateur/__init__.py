"""Lot 5 — the replay orchestrator (spec §21.3).

Public surface: `Campagne`, `ResultatCampagne`, `nouvelle_campagne`,
`Interrupteur`, `CompteursBudget` and the two controlled stops.
"""

from __future__ import annotations

from sas.arret import (
    BudgetEpuise,
    CompteursBudget,
    Interrupteur,
    SessionSuspendue,
    Suspension,
)
from sas.orchestrateur.campagne import Campagne, ResultatCampagne, nouvelle_campagne
from sas.orchestrateur.sessions import executer_rejeu

__all__ = [
    "BudgetEpuise",
    "Campagne",
    "CompteursBudget",
    "Interrupteur",
    "ResultatCampagne",
    "SessionSuspendue",
    "Suspension",
    "executer_rejeu",
    "nouvelle_campagne",
]
