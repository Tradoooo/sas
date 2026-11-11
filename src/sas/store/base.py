"""Sas — the storage port (lot 0, frozen).

The store is tenant-scoped by construction: a `Depot` is always bound to one
tenant, and there is no method that takes a tenant as an argument (EF-51).
The DynamoDB table definitions live in `sas.store.ddl`; the local backend
(`sas.store.local`) mirrors them with in-memory structures so the whole
product runs offline.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from sas.types import (
    Agent,
    Attestation,
    Campagne,
    Composition,
    Derive,
    Ecart,
    Editeur,
    EntreeJournal,
    Enveloppe,
    Manifeste,
    Session,
    Tenant,
    Tentative,
)


@runtime_checkable
class Depot(Protocol):
    """Everything the product persists. One instance == one tenant."""

    @property
    def tenant_id(self) -> str: ...

    # -- registry ---------------------------------------------------------- #
    def enregistrer_tenant(self, tenant: Tenant) -> None: ...

    def enregistrer_editeur(self, editeur: Editeur) -> None: ...

    def enregistrer_agent(self, agent: Agent) -> None: ...

    def agent(self, agent_id: str) -> Agent | None: ...

    def agents(self) -> Sequence[Agent]: ...

    def editeur(self, editeur_id: str) -> Editeur | None: ...

    def tenant(self, tenant_id: str) -> Tenant | None: ...

    # -- manifests --------------------------------------------------------- #
    def enregistrer_manifeste(self, manifeste: Manifeste) -> None: ...

    def manifeste(self, manifeste_id: str, version: int | None = None) -> Manifeste | None: ...

    def manifeste_courant(self, agent_id: str) -> Manifeste | None: ...

    def versions_manifeste(self, agent_id: str) -> Sequence[int]: ...

    def remplacer_manifeste(self, agent_id: str) -> None:
        """Mark the previous version as replaced: the attestation in force is
        invalidated (R3)."""

    # -- campaigns --------------------------------------------------------- #
    def enregistrer_campagne(self, campagne: Campagne) -> None: ...

    def campagne(self, campagne_id: str) -> Campagne | None: ...

    def campagnes(self, agent_id: str | None = None) -> Sequence[Campagne]: ...

    def enregistrer_session(self, session: Session) -> None: ...

    def session(self, session_id: str) -> Session | None: ...

    def sessions(self, campagne_id: str) -> Sequence[Session]: ...

    # -- journal ----------------------------------------------------------- #
    def ajouter_entree(self, entree: EntreeJournal) -> EntreeJournal: ...

    def entrees(self, campagne_id: str) -> Sequence[EntreeJournal]: ...

    def entrees_session(self, session_id: str) -> Sequence[EntreeJournal]: ...

    # -- measurements ------------------------------------------------------ #
    def enregistrer_tentative(self, tentative: Tentative) -> None: ...

    def tentatives(self, campagne_id: str) -> Sequence[Tentative]: ...

    def tentative(self, tentative_id: str) -> Tentative | None: ...

    def enregistrer_composition(self, composition: Composition) -> None: ...

    def compositions(self, campagne_id: str) -> Sequence[Composition]: ...

    def enregistrer_ecart(self, ecart: Ecart) -> None: ...

    def ecarts(self, campagne_id: str) -> Sequence[Ecart]: ...

    def enregistrer_enveloppe(self, enveloppe: Enveloppe) -> None: ...

    def enveloppes(self, agent_id: str) -> Sequence[Enveloppe]: ...

    def enveloppe_reference(self, agent_id: str) -> Enveloppe | None: ...

    def enregistrer_derive(self, derive: Derive) -> None: ...

    def derives(self, agent_id: str | None = None) -> Sequence[Derive]: ...

    # -- deliverables ------------------------------------------------------ #
    def enregistrer_attestation(self, attestation: Attestation) -> None: ...

    def attestation(self, attestation_id: str) -> Attestation | None: ...

    def attestations(self, campagne_id: str | None = None) -> Sequence[Attestation]: ...

    # -- housekeeping ------------------------------------------------------ #
    def purger(self, jours: int) -> int:
        """Retention purge, effective and provable (ENF-12)."""

    def cout_cumule(self) -> dict[str, float]:
        """Measured cost per campaign and per tenant (EF-52)."""
