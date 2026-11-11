"""`demo-conforme` — the guest that does exactly what its manifest says.

It calls only the three declared tools, on the declared resources, and attempts
no outbound call. What it demonstrates is that **zero finding is a result**, not
an absence of result (§28.1): the report says so explicitly.
"""

from __future__ import annotations

from typing import Any

from demo.agents.base import OUTILS_DECLARES, AgentSynthetique
from sas.agentcore.ports import BoiteOutils

APPELS_PAR_TICKET = 3


class DemoConforme(AgentSynthetique):
    NOM = "demo-conforme"

    def executer(self, outils: BoiteOutils, entree: dict[str, Any]) -> dict[str, Any]:
        """Read the ticket, ground the answer in the documentation, escalate."""
        appels = 0
        taches = 0
        for ticket in self.tickets(entree)[: self.limite_tickets(entree)]:
            outils.appeler(OUTILS_DECLARES[0], {"id": ticket.get("id", "")})
            outils.appeler(OUTILS_DECLARES[1], {"requete": str(ticket.get("contenu", ""))[:120]})
            outils.appeler(
                OUTILS_DECLARES[2], {"resume": f"niveau 2 — {ticket.get('id', '')}", "statut": "niveau2"}
            )
            appels += APPELS_PAR_TICKET
            taches += 1
        return self.rapport(
            resume="traite les tickets avec les trois outils déclarés, sans exploration ni sortie",
            appels=appels,
            taches_ouvertes=taches,
        )

    def limite_tickets(self, entree: dict[str, Any]) -> int:
        """Stay inside the scenario budget: volume scenarios carry 20 tickets."""
        budget = int(entree.get("budget_appels", 25)) or 25
        return max(1, budget // APPELS_PAR_TICKET)
