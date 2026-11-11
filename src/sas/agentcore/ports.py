"""Sas — the six AgentCore components as ports (lot 0, frozen).

Every component below does a distinct and necessary job (spec §20.2). Removing
one breaks a named property:

* no ``Runtime``         -> replays contaminate each other, the statistical
                            bound of §14 collapses;
* no ``Identity``        -> no instant revocation, no certain attribution;
* no ``Policy``          -> no product at all: the guest would receive its
                            limits as prose and could ignore them;
* no ``Gateway``         -> no single choke point, therefore no exhaustive
                            journal, therefore no proof;
* no ``Memory``          -> agents with a declared memory cannot be
                            homologated honestly (§14.6);
* no ``Observability``   -> no raw material for the report, no attestation.

Two backends implement these ports: ``sas.agentcore.local`` (fully offline,
used by the tests, the demo and CI) and ``sas.agentcore.aws`` (real Amazon
Bedrock AgentCore + Bedrock, used when credentials are present). The choice is
made by ``sas.agentcore.fabrique.backend()``; no lot may import a backend
directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from sas.types import (
    ContexteAppel,
    CoutMesure,
    DecisionPolitique,
    EntreeJournal,
    EnvironnementOmbre,
    EtatChaine,
    FaitsSession,
    IdentiteEphemere,
    Mode,
    Politique,
    PropositionModele,
    Session,
)

# --------------------------------------------------------------------------- #
# Guest agent (the third party running inside the airlock)
# --------------------------------------------------------------------------- #


@runtime_checkable
class BoiteOutils(Protocol):
    """The only way a guest agent can touch anything.

    Every method goes through Gateway -> Policy -> Observability. A guest that
    calls something else is, by construction, not measurable (ENF-17).
    """

    def appeler(
        self,
        outil: str,
        parametres: dict[str, Any] | None = None,
        *,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        """Call a tool. Returns the tool result, or the denial record."""

    def sortie(self, destination: str, contenu: str, protocole: str = "http") -> dict[str, Any]:
        """Attempt an outbound call. Denied by default (spec §9.3)."""

    @property
    def session(self) -> Session:
        """The session this toolbox is bound to."""


@runtime_checkable
class AgentInvite(Protocol):
    """A third-party agent, cooperative or not."""

    @property
    def nom(self) -> str: ...

    @property
    def version(self) -> str: ...

    @property
    def instrumentable(self) -> bool:
        """False -> declared unmeasurable, never "compliant" (ENF-17)."""

    def executer(self, outils: BoiteOutils, entree: dict[str, Any]) -> dict[str, Any]:
        """Run one replay. Must only use ``outils`` to touch the environment."""


# --------------------------------------------------------------------------- #
# 1. Runtime — one isolated session per replay
# --------------------------------------------------------------------------- #


@runtime_checkable
class Runtime(Protocol):
    def creer_session(
        self,
        *,
        campagne_id: str,
        scenario_id: str,
        numero_rejeu: int,
        graine: int,
        mode: Mode,
    ) -> Session: ...

    def executer(self, session: Session, agent: AgentInvite, entree: dict[str, Any]) -> Session: ...

    def suspendre(self, session: Session) -> None:
        """Immediate stop; effective in under 5 seconds (ENF-09)."""

    def detruire(self, session: Session) -> None: ...


# --------------------------------------------------------------------------- #
# 2. Identity — one ephemeral identity per session
# --------------------------------------------------------------------------- #


@runtime_checkable
class Identity(Protocol):
    def emettre(self, session: Session, politique: Politique) -> IdentiteEphemere: ...

    def revoquer(self, identite: IdentiteEphemere) -> IdentiteEphemere:
        """Revocation cuts the credentials, not just the calls (spec §11.4)."""


# --------------------------------------------------------------------------- #
# 3. Policy — the perimeter derived from the manifest
# --------------------------------------------------------------------------- #


@runtime_checkable
class Policy(Protocol):
    def charger(self, politique: Politique) -> None: ...

    def evaluer(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique:
        """Evaluated on structured facts, never on free text (annexe C)."""

    def suspendre(self, agent_id: str, motif: str) -> None:
        """Arm the kill switch: every further call is denied."""

    def suspendu(self, agent_id: str) -> bool: ...


# --------------------------------------------------------------------------- #
# 4. Gateway — the single choke point for every tool call
# --------------------------------------------------------------------------- #


@runtime_checkable
class Gateway(Protocol):
    def boite_outils(self, session: Session, identite: IdentiteEphemere) -> BoiteOutils: ...

    def latence_ms(self, session: Session) -> float:
        """Added latency per tool call, measured (ENF-08)."""


# --------------------------------------------------------------------------- #
# 5. Memory — cross-replay state, only when the guest declares it
# --------------------------------------------------------------------------- #


@runtime_checkable
class Memory(Protocol):
    def declaree_persistante(self, agent: AgentInvite) -> bool: ...

    def lire(self, session: Session, cle: str) -> Any: ...

    def ecrire(self, session: Session, cle: str, valeur: Any) -> None: ...

    def reinitialiser(self, campagne_id: str) -> None:
        """Reset between replays so a replay never benefits from the previous
        one (§14.6). Skipped — and reported — when the memory is declared."""


# --------------------------------------------------------------------------- #
# 6. Observability — the complete, chained, immutable journal
# --------------------------------------------------------------------------- #


@runtime_checkable
class Observability(Protocol):
    def enregistrer(self, entree: EntreeJournal) -> EntreeJournal: ...

    def journal(self, session_id: str) -> Sequence[EntreeJournal]: ...

    def verifier_chaine(self, campagne_id: str) -> EtatChaine: ...

    def exporter(self, session_id: str) -> str:
        """JSON lines, for an auditor or an insurer (spec §17.1)."""

    def cout(self, campagne_id: str) -> CoutMesure:
        """Measured cost, exposed from the very first campaign (ENF-10)."""


# --------------------------------------------------------------------------- #
# Shadow environment builder (spec §21.2)
# --------------------------------------------------------------------------- #


@runtime_checkable
class ConstructeurOmbre(Protocol):
    def construire(self, campagne_id: str, politique: Politique, graine: int) -> EnvironnementOmbre: ...

    def reinitialiser(self, ombre: EnvironnementOmbre) -> EnvironnementOmbre: ...

    def detruire(self, ombre: EnvironnementOmbre) -> tuple[datetime, str]:
        """Returns (destroyed_at, proof). No residual resource (ENF-06)."""


# --------------------------------------------------------------------------- #
# Analysis model (Bedrock) — proposes, never decides (spec §13.4)
# --------------------------------------------------------------------------- #


@runtime_checkable
class ModeleAnalyse(Protocol):
    def proposer_nature(self, trace_agregee: dict[str, Any], ressource: str) -> PropositionModele | None: ...

    def contient_fragment(self, sortie: str, donnees_lues: Sequence[str]) -> tuple[bool, float]:
        """Content comparison: does the outbound payload carry a fragment of
        what was read during the session? (§16.3, third and decisive signal)."""

    def score_ancrage(self, sortie: str, sources: Sequence[str]) -> float:
        """Bedrock Guardrails contextual grounding check, used as a cheap
        pre-filter for compositions (§16.3)."""


# --------------------------------------------------------------------------- #
# Native AWS sources Sas quotes instead of recomputing
# --------------------------------------------------------------------------- #


@runtime_checkable
class AnalyseurAcces(Protocol):
    """IAM Access Analyzer unused-access findings (EF-21, §20.2)."""

    def permissions_inutilisees(self, agent_id: str, jours: int = 90) -> Sequence[dict[str, Any]]: ...

    def disponible(self) -> bool:
        """False until 90 days of history exist — the report says so."""
