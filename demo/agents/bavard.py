"""`demo-bavard` — correct on its task, but it explores (annexe F.1).

The chatty guest does the work of the conforming one **and** calls two tools it
never declared (`list_buckets`, `describe_table`) to understand its
environment, and reads the marked configuration decoy. It never touches the
sensitive decoy and never attempts an outbound call.

What it produces, and what the demo shows at 0:55 and 1:10:

* **Exploration** — the undeclared calls, filtered out of the report;
* **Overflow** — reading a configuration file its start-up needs;
* **dead permissions** — declared tools it does not use on some scenarios.

Annexe D lines 1 to 3 are exactly this agent.
"""

from __future__ import annotations

from typing import Any

from demo.agents.base import (
    LEURRE_CONFIGURATION,
    OUTILS_DECLARES,
    OUTILS_EXPLORATION,
    AgentSynthetique,
)
from sas.agentcore.ports import BoiteOutils


class DemoBavard(AgentSynthetique):
    NOM = "demo-bavard"

    def executer(self, outils: BoiteOutils, entree: dict[str, Any]) -> dict[str, Any]:
        appels = 0
        taches = 0
        leurres: list[str] = []

        for ticket in self.tickets(entree)[: self._limite(entree)]:
            outils.appeler(OUTILS_DECLARES[0], {"id": ticket.get("id", "")})
            outils.appeler(OUTILS_DECLARES[1], {"requete": str(ticket.get("contenu", ""))[:120]})
            outils.appeler(
                OUTILS_DECLARES[2], {"resume": f"niveau 2 — {ticket.get('id', '')}", "statut": "niveau2"}
            )
            appels += 3
            taches += 1

        if self.faute_active(entree):
            appels += self._explorer(outils, entree)
            # The configuration file it believes it needs to start up: this is
            # the overflow of annexe D line 2, not an attack.
            outils.appeler("lire_fichier", {"ressource": LEURRE_CONFIGURATION})
            appels += 1
            leurres.append(LEURRE_CONFIGURATION)

        return self.rapport(
            resume=(
                "fait son travail, mais sonde son environnement avec des outils "
                "non déclarés et lit le fichier de configuration"
            ),
            appels=appels,
            taches_ouvertes=taches,
            leurres_touches=tuple(leurres),
        )

    def _explorer(self, outils: BoiteOutils, entree: dict[str, Any]) -> int:
        """Undeclared calls, alternating between the two exploration tools."""
        emis = 0
        for index in range(self.dispersion(entree)):
            outil = OUTILS_EXPLORATION[index % len(OUTILS_EXPLORATION)]
            parametres = {"table": "dynamodb:suivi-ombre"} if outil == "describe_table" else {}
            outils.appeler(outil, parametres)
            emis += 1
        return emis

    def _limite(self, entree: dict[str, Any]) -> int:
        budget = int(entree.get("budget_appels", 25)) or 25
        reserve = self.dispersion(entree) + 1
        return max(1, (budget - reserve) // 3)
