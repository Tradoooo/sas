"""Budgets and the kill switch (EF-13, EF-15, ENF-03, ENF-09, R6, R7).

This module is deliberately outside `sas.orchestrateur`: the gateway consults
it on every call, and importing the orchestrator from the gateway would close a
cycle. `sas.orchestrateur` re-exports it, so callers keep one import path.

Two small mechanisms that the gateway consults on every call:

* `CompteursBudget` — a clean stop when the budget is exhausted. Annexe C ends
  the session at `budget x 1.2`, so a guest that loops does not burn the
  campaign's credits;
* `Interrupteur` — the kill switch. Arming it is immediate and cuts the
  identities, so the agent cannot be "in the middle of finishing" (§11.4).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from sas import constantes
from sas.identifiants import maintenant
from sas.types import Budgets


class BudgetEpuise(Exception):
    """Raised inside the guest's call: the session ends cleanly (R6)."""

    def __init__(self, session_id: str, motif: str) -> None:
        super().__init__(f"session {session_id} terminée proprement : {motif}")
        self.session_id = session_id
        self.motif = motif


class SessionSuspendue(Exception):
    """Raised inside the guest's call: the kill switch was armed (R7)."""

    def __init__(self, session_id: str, motif: str) -> None:
        super().__init__(f"session {session_id} suspendue : {motif}")
        self.session_id = session_id
        self.motif = motif


@dataclass(slots=True)
class CompteursBudget:
    """What is left of one session's budget."""

    appels: int
    jetons: int
    duree_maximale_secondes: int
    memoire_maximale_mio: int
    consommes_appels: int = 0
    consommes_jetons: int = 0

    @classmethod
    def depuis(cls, budgets: Budgets | None) -> CompteursBudget:
        source = budgets or _budgets_par_defaut()
        return cls(
            appels=source.appels_par_execution,
            jetons=source.jetons_par_execution,
            duree_maximale_secondes=source.duree_maximale_secondes,
            memoire_maximale_mio=source.memoire_maximale_mio,
        )

    @property
    def appels_restants(self) -> int:
        return max(0, self.appels - self.consommes_appels)

    @property
    def jetons_restants(self) -> int:
        return max(0, self.jetons - self.consommes_jetons)

    @property
    def plafond_arret(self) -> int:
        """Annexe C: the session ends cleanly at budget x 1.2."""
        return int(Decimal(self.appels) * constantes.FACTEUR_ARRET_BUDGET)

    def depasse(self) -> bool:
        return self.consommes_appels >= self.plafond_arret or self.jetons_restants <= 0

    def consommer(self, jetons: int = 0) -> None:
        self.consommes_appels += 1
        self.consommes_jetons += jetons


@dataclass(slots=True)
class Suspension:
    motif: str
    armee_le: datetime
    par: str = "systeme"


@dataclass(slots=True)
class Interrupteur:
    """The kill switch, shared between the campaign and every toolbox."""

    suspensions: list[Suspension] = field(default_factory=list)

    @property
    def arme(self) -> bool:
        return bool(self.suspensions)

    def armer(self, motif: str, par: str = "systeme") -> Suspension:
        suspension = Suspension(motif=motif, armee_le=maintenant(), par=par)
        self.suspensions.append(suspension)
        return suspension

    def derniere(self) -> Suspension | None:
        return self.suspensions[-1] if self.suspensions else None

    def desarmer(self) -> None:
        """Only a human decision re-arms production (§18): this exists for tests
        and for the observed mode's explicit resume, never automatically."""
        self.suspensions.clear()


def _budgets_par_defaut() -> Budgets:
    valeurs = constantes.BUDGETS_DEFAUT
    return Budgets(
        appels_par_execution=valeurs["appels_par_execution"],
        jetons_par_execution=valeurs["jetons_par_execution"],
        duree_maximale_secondes=valeurs["duree_maximale_secondes"],
        memoire_maximale_mio=valeurs["memoire_maximale_mio"],
    )
