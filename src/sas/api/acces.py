"""Who consulted what, and when.

An attestation is a document about an agent's behaviour. It is also a document
about **the organisation's** trust decisions, and those are exactly the accesses
an auditor wants to see: who read which attestation, under which role, from which
tenant. Nothing else about the platform is worth logging — the tool calls are
already in the chained journal — so the access log is deliberately narrow.

It is also the basis of the least-privilege story of §7: the role decides what
is readable, and the log proves the rule was applied.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sas.identifiants import maintenant
from sas.types import ContexteTenant

# What is worth recording: the read, not the payload.
ACTIONS: tuple[str, ...] = ("lire", "telecharger", "lancer", "suspendre", "revoir")


@dataclass(frozen=True, slots=True)
class Acces:
    """One recorded access."""

    horodatage: datetime
    acteur: str
    role: str
    tenant_id: str
    ressource: str
    action: str

    def resume(self) -> dict[str, Any]:
        return {
            "horodatage": self.horodatage.isoformat(),
            "acteur": self.acteur,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "ressource": self.ressource,
            "action": self.action,
        }


@dataclass(slots=True)
class JournalAcces:
    """The access log. In memory here; a real deployment writes it to the store
    with the same retention rules as the journal."""

    acces: list[Acces] = field(default_factory=list)

    def enregistrer(
        self,
        contexte: ContexteTenant,
        ressource: str,
        action: str = "lire",
        *,
        horodatage: datetime | None = None,
    ) -> Acces:
        if action not in ACTIONS:
            raise ValueError(f"action inconnue : {action!r} (attendu : {', '.join(ACTIONS)})")
        entree = Acces(
            horodatage=horodatage or maintenant(),
            acteur=contexte.acteur,
            role=contexte.role,
            tenant_id=contexte.tenant_id,
            ressource=ressource,
            action=action,
        )
        self.acces.append(entree)
        return entree

    def pour_tenant(self, tenant_id: str) -> tuple[Acces, ...]:
        return tuple(a for a in self.acces if a.tenant_id == tenant_id)

    def pour_acteur(self, acteur: str) -> tuple[Acces, ...]:
        return tuple(a for a in self.acces if a.acteur == acteur)

    def sur_ressource(self, ressource: str) -> tuple[Acces, ...]:
        return tuple(a for a in self.acces if a.ressource == ressource)

    def resume(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        acces = self.acces if tenant_id is None else self.pour_tenant(tenant_id)
        return [a.resume() for a in acces]

    def __len__(self) -> int:
        return len(self.acces)


def ressources_lues(journal: JournalAcces, acteur: str) -> Sequence[str]:
    """The distinct resources an actor has consulted."""
    vus: list[str] = []
    for acces in journal.pour_acteur(acteur):
        if acces.ressource not in vus:
            vus.append(acces.ressource)
    return tuple(vus)
