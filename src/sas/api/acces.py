"""Who consulted what, and when.

An attestation is a document about an agent's behaviour. It is also a document
about **the organisation's** trust decisions, and those are exactly the accesses
an auditor wants to see: who read which attestation, under which role, from which
tenant. Nothing else about the platform is worth logging — the tool calls are
already in the chained journal — so the access log is deliberately narrow.

It is also the basis of the least-privilege story of §7: the role decides what
is readable, and the log proves the rule was applied.

The record type lives in `sas.modele.journal_acces` (the store persists it too);
this module is the facade the portal calls. Bound to a depot (`depot=`), every
record is written to the tenant's store, where the retention purge removes it
with the journal's own rule and the purge attestation names it (ENF-12). Left
unbound — the offline demo — it stays in memory.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sas.identifiants import maintenant
from sas.modele.journal_acces import ACTIONS, Acces
from sas.store.base import Depot
from sas.types import ContexteTenant

__all__ = ["ACTIONS", "Acces", "JournalAcces", "ressources_lues"]


@dataclass(slots=True)
class JournalAcces:
    """The access log: in memory, and in the store when one is bound."""

    depot: Depot | None = None
    acces: list[Acces] = field(default_factory=list)

    def enregistrer(
        self,
        contexte: ContexteTenant,
        ressource: str,
        action: str = "lire",
        *,
        horodatage: datetime | None = None,
    ) -> Acces:
        entree = Acces(
            horodatage=horodatage or maintenant(),
            acteur=contexte.acteur,
            role=contexte.role,
            tenant_id=contexte.tenant_id,
            ressource=ressource,
            action=action,
        )
        if self.depot is not None:
            self.depot.enregistrer_acces(entree)
        self.acces.append(entree)
        return entree

    def _source(self) -> Sequence[Acces]:
        """The store is authoritative when one is bound: reading the log after a
        restart must return what was journalled, not what this process happens to
        remember."""
        return self.depot.acces() if self.depot is not None else tuple(self.acces)

    def pour_tenant(self, tenant_id: str) -> tuple[Acces, ...]:
        return tuple(a for a in self._source() if a.tenant_id == tenant_id)

    def pour_acteur(self, acteur: str) -> tuple[Acces, ...]:
        return tuple(a for a in self._source() if a.acteur == acteur)

    def sur_ressource(self, ressource: str) -> tuple[Acces, ...]:
        return tuple(a for a in self._source() if a.ressource == ressource)

    def resume(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        acces = self._source() if tenant_id is None else self.pour_tenant(tenant_id)
        return [a.resume() for a in acces]

    def __len__(self) -> int:
        return len(self._source())


def ressources_lues(journal: JournalAcces, acteur: str) -> Sequence[str]:
    """The distinct resources an actor has consulted."""
    vus: list[str] = []
    for acces in journal.pour_acteur(acteur):
        if acces.ressource not in vus:
            vus.append(acces.ressource)
    return tuple(vus)
