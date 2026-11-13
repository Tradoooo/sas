"""Sas — the access log: who consulted what, and when (idea 85, §7).

An attestation is a document about an agent's behaviour. It is also a document
about **the organisation's** trust decisions, and those are exactly the accesses
an auditor wants to see: who read which attestation, under which role, from
which tenant. Nothing else about the platform is worth logging — the tool calls
are already in the chained journal — so the access log is deliberately narrow.

The record lives in the model layer, not in the HTTP layer, because the store
persists it: `sas.api.acces` is the facade the portal calls, `sas.store` writes
it with the journal's retention rule, and both speak this type. A record keeps
no payload — an access has none to keep — only the metadata that identifies it.

**What this does not claim.** The access log is *not* chained: a record carries
no predecessor fingerprint, so deleting a row is not detected by walking a hash
chain the way the agent journal is (spec §17.1). Its tamper-evidence rests on
the store's append-only table (DynamoDB point-in-time recovery in a real
deployment) and on the purge attestation, which names what a retention purge
removed. That is stated here rather than left to be assumed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sas.identifiants import canonique

# What is worth recording: the read, not the payload.
ACTIONS: tuple[str, ...] = ("lire", "telecharger", "lancer", "suspendre", "revoir")

PREFIXE = "acces"


@dataclass(frozen=True, slots=True)
class Acces:
    """One recorded access. Metadata only: actor, role, tenant, resource, action."""

    horodatage: datetime
    acteur: str
    role: str
    tenant_id: str
    ressource: str
    action: str
    id: str = ""

    def __post_init__(self) -> None:
        if self.action not in ACTIONS:
            raise ValueError(f"action inconnue : {self.action!r} (attendu : {', '.join(ACTIONS)})")
        if not self.id:
            # Deterministic: the same access recorded twice at the same instant is
            # the same row, so a retried request cannot invent a second identity.
            object.__setattr__(self, "id", f"{PREFIXE}-" + self.empreinte()[:16])

    def corps(self) -> dict[str, Any]:
        """The record itself — what identifies it, and nothing else."""
        return {
            "horodatage": self.horodatage.isoformat(),
            "acteur": self.acteur,
            "role": self.role,
            "tenant_id": self.tenant_id,
            "ressource": self.ressource,
            "action": self.action,
        }

    def empreinte(self) -> str:
        """A fingerprint of the record. There is no payload behind it to hash."""
        return hashlib.sha256(canonique(self.corps()).encode("utf-8")).hexdigest()

    def resume(self) -> dict[str, Any]:
        return {"id": self.id, **self.corps()}
