"""Replaying one scenario from a finding (EF-44).

§12.5 lists it among the functional requirements: « Permettre le rejeu d'un
scénario précis depuis un finding ». A finding is not an end in itself — it is a
question, and the cheapest way to answer it is to run the scenario that produced
it again, with the same seed, and look at what changed.

The replay is **deterministic**: the seed and the replay number of the finding
are reused, so the same session comes back. That is the point — a finding you
cannot reproduce is a hypothesis, not a measurement.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sas.types import Tentative


@dataclass(frozen=True, slots=True)
class Rejeu:
    """What a replay from a finding produced."""

    tentative_id: str
    scenario_id: str
    graine: int
    numero_rejeu: int
    sessions: tuple[str, ...]
    entrees: int
    refus: int
    reprise_identique: bool

    def resume(self) -> dict[str, Any]:
        return {
            "tentative_id": self.tentative_id,
            "scenario_id": self.scenario_id,
            "graine": self.graine,
            "numero_rejeu": self.numero_rejeu,
            "sessions": list(self.sessions),
            "entrees": self.entrees,
            "refus": self.refus,
            "reprise_identique": self.reprise_identique,
        }


def rejouer(
    tentative: Tentative,
    *,
    scenario_id: str,
    graine: int,
    numero_rejeu: int,
    agent: Any,
    scenarios: Sequence[Any],
    contexte: Any,
    reference_refus: int | None = None,
) -> Rejeu:
    """Re-run the scenario that produced the finding, with the same seed.

    `agent`, `scenarios` and `contexte` are injected so this module stays
    independent of the orchestrator's internals. `reference_refus` is the number
    of refusals the finding was based on: when the replay refuses exactly as
    much, the finding reproduces.
    """
    from sas.orchestrateur import Campagne, nouvelle_campagne

    campagne = nouvelle_campagne(
        tenant_id=tentative.tenant_id,
        agent_id=tentative.campagne_id,
        manifeste=contexte.manifeste,
        n_rejeux=1,
        graine=graine,
        scenarios=(scenario_id,),
    )
    resultat = Campagne(
        campagne=campagne,
        manifeste=contexte.manifeste,
        agent=agent,
        scenarios=scenarios,
    ).executer()
    sessions = tuple(s.id for s in resultat.sessions)
    refus = sum(1 for e in resultat.entrees if e.decision.value == "refuse")
    return Rejeu(
        tentative_id=tentative.id,
        scenario_id=scenario_id,
        graine=graine,
        numero_rejeu=numero_rejeu,
        sessions=sessions,
        entrees=len(resultat.entrees),
        refus=refus,
        reprise_identique=reference_refus is None or refus == reference_refus,
    )


def scenario_d_une_tentative(tentative: Tentative, journal: Sequence[Any]) -> str:
    """Which scenario produced this finding, read back from the journal."""
    for entree in journal:
        if entree.id in tentative.entrees:
            return str(entree.scenario_id)
    return ""


def graine_d_une_session(session: Any) -> int:
    return int(getattr(session, "graine", 0))
