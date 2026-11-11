"""`demo-opaque` — the guest that does not go through the gateway (ENF-17).

Some vendor agents call their own tools directly. Sas cannot journal what does
not pass through the gateway, and it says so rather than producing an empty
report: the agent is declared **not measurable**, never "compliant".

This guest exists to prove that refusal end to end (R24): it bypasses the
toolbox, and the airlock raises instead of inventing a verdict.
"""

from __future__ import annotations

from typing import Any

from demo.agents.base import AgentSynthetique
from sas.agentcore.ports import BoiteOutils


class AgentNonInstrumentable(Exception):
    """Raised when a guest cannot be measured. Never swallowed into a verdict."""

    def __init__(self, agent: str, detail: str = "") -> None:
        super().__init__(f"agent non instrumentable: {agent}" + (f" — {detail}" if detail else ""))
        self.agent = agent
        self.detail = detail


class DemoOpaque(AgentSynthetique):
    NOM = "demo-opaque"

    @property
    def instrumentable(self) -> bool:
        """The honest answer: this guest cannot be observed."""
        return False

    def executer(self, outils: BoiteOutils, entree: dict[str, Any]) -> dict[str, Any]:
        """Call its own tools, outside the gateway — then be declared unmeasurable."""
        del outils, entree  # the whole point: the toolbox is never used
        raise AgentNonInstrumentable(
            self.nom,
            "l'agent appelle ses propres outils sans passer par la passerelle : "
            "aucun journal exhaustif n'est possible",
        )
