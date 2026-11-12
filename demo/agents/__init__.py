"""The synthetic guest agents of the demonstration (annexe F.1).

All three are **synthetic and labelled as such**: no real vendor agent is used,
because that would require the vendor's agreement (§28.1). Saying so plainly is
part of the honesty of the submission.

A fourth guest, `demo-opaque`, does not go through the toolbox at all: it exists
to prove ENF-17 — an agent that refuses instrumentation is declared **not
measurable**, never compliant.
"""

from __future__ import annotations

from typing import Any

from demo.agents.bavard import DemoBavard
from demo.agents.conforme import DemoConforme
from demo.agents.curieux import DemoCurieux
from demo.agents.evasion import DemoEvasion
from demo.agents.opaque import AgentNonInstrumentable, DemoOpaque
from sas.agentcore.ports import AgentInvite

AGENTS: dict[str, type] = {
    "demo-conforme": DemoConforme,
    "demo-bavard": DemoBavard,
    "demo-curieux": DemoCurieux,
    "demo-evasion": DemoEvasion,
    "demo-opaque": DemoOpaque,
}


def construire(nom: str, **parametres: Any) -> AgentInvite:
    """Build a demo guest by name. An unknown name is refused, never guessed."""
    try:
        classe = AGENTS[nom]
    except KeyError:
        disponibles = ", ".join(sorted(AGENTS))
        raise ValueError(f"agent de démonstration inconnu: {nom!r} (disponibles: {disponibles})") from None
    return classe(**parametres)


def noms() -> tuple[str, ...]:
    return tuple(sorted(AGENTS))


__all__ = [
    "AGENTS",
    "AgentNonInstrumentable",
    "DemoBavard",
    "DemoConforme",
    "DemoCurieux",
    "DemoOpaque",
    "construire",
    "noms",
]
