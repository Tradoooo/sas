"""One replay: create, arm, run, collect, destroy (spec §11.1 step 5, §21.3).

Kept apart from the campaign so the isolation property is visible in one place:
a replay owns its session, its ephemeral identity and its counters, and nothing
survives it except the journal.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from sas.agentcore.fabrique import Backend
from sas.agentcore.local import AgentNonInstrumentable
from sas.agentcore.ports import AgentInvite
from sas.arret import BudgetEpuise, SessionSuspendue
from sas.identifiants import maintenant
from sas.types import Session, StatutSession


def executer_rejeu(
    *,
    backend: Backend,
    agent: AgentInvite,
    scenario_id: str,
    numero_rejeu: int,
    graine: int,
    campagne_id: str,
    entree: dict[str, Any],
    interrupteur: Any | None = None,
    erreurs: list[str] | None = None,
) -> Session:
    """Run one replay inside its own isolated session."""
    runtime = backend.runtime
    session = runtime.creer_session(
        campagne_id=campagne_id,
        scenario_id=scenario_id,
        numero_rejeu=numero_rejeu,
        graine=graine,
        mode=backend.mode,
    )
    identite = backend.identite.emettre(session, backend.politique)
    cadre = backend.passerelle.ouvrir_session(session, identite)
    cadre.interrupteur = interrupteur
    backend.support.reinitialiser()
    backend.observabilite.suivre_session(session)

    session = replace(session, identite=identite)
    statut, depasse = _jouer(backend, agent, session, entree, erreurs)
    return _clore(backend, session, cadre, statut, depasse)


def _jouer(
    backend: Backend,
    agent: AgentInvite,
    session: Session,
    entree: dict[str, Any],
    erreurs: list[str] | None = None,
) -> tuple[StatutSession, bool]:
    """Run the guest. A guest crash never takes the campaign down, but it is
    **recorded**: a silent empty session would be worse than an error."""
    boite = backend.passerelle.boite_outils(session, session.identite)  # type: ignore[arg-type]
    try:
        agent.executer(boite, entree)
    except BudgetEpuise:
        return StatutSession.BUDGET_DEPASSE, True
    except SessionSuspendue:
        return StatutSession.SUSPENDUE, False
    except AgentNonInstrumentable as exc:
        _noter(erreurs, session, f"non instrumentable: {exc}")
        return StatutSession.ERREUR, False
    except Exception as exc:
        _noter(erreurs, session, f"{type(exc).__name__}: {exc}")
        return StatutSession.ERREUR, False
    return StatutSession.TERMINEE, False


def _noter(erreurs: list[str] | None, session: Session, message: str) -> None:
    if erreurs is not None:
        erreurs.append(f"{session.scenario_id}#{session.numero_rejeu}: {message}")


def _clore(backend: Backend, session: Session, cadre: Any, statut: StatutSession, depasse: bool) -> Session:
    """Revoke the identity, record the counters, destroy the session."""
    backend.identite.revoquer(session.identite)  # type: ignore[arg-type]
    close = replace(
        session,
        fin=maintenant(),
        statut=statut,
        appels=cadre.appels,
        appels_refuses=cadre.refus,
        jetons=cadre.jetons,
        budget_depasse=depasse,
    )
    backend.runtime.detruire(close)
    return close
