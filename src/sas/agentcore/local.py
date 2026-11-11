"""Local AgentCore backend: Runtime, Identity and Memory (lot 5).

An in-process implementation of the ports in `sas.agentcore.ports`. It is what
the tests, the demo and CI run against: no network, no AWS, no model call. The
properties it has to preserve are the ones the product is built on —

* **Runtime**: one isolated session per replay, so replays stay independent and
  the statistical bound of §14 holds;
* **Identity**: one ephemeral identity per session, revocation cuts the
  credentials rather than merely refusing the next call (§11.4, ENF-09);
* **Memory**: cross-replay state only when the guest declares it, and the report
  then says the bound no longer applies (§14.6).
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import Any

from sas.agentcore.ports import AgentInvite
from sas.identifiants import maintenant, nouveau
from sas.types import (
    IdentiteEphemere,
    Mode,
    Politique,
    Session,
    StatutSession,
)

DUREE_IDENTITE_MINUTES = 30


class AgentNonInstrumentable(Exception):
    """Raised when a guest cannot be observed (ENF-17).

    Never swallowed into a verdict: an unmeasurable agent is declared
    unmeasurable, and no attestation is produced for it.
    """

    def __init__(self, agent: str, detail: str = "") -> None:
        super().__init__(f"agent non instrumentable: {agent}" + (f" — {detail}" if detail else ""))
        self.agent = agent
        self.detail = detail


class RuntimeLocal:
    """One session per replay. Nothing is shared between two sessions."""

    def __init__(self, *, tenant_id: str = "tenant-demo", campagne_id: str = "") -> None:
        self._tenant_id = tenant_id
        self._campagne_id = campagne_id
        self._vivantes: dict[str, Session] = {}

    def creer_session(
        self,
        *,
        campagne_id: str,
        scenario_id: str,
        numero_rejeu: int,
        graine: int,
        mode: Mode = Mode.OMBRE,
    ) -> Session:
        identifiant = nouveau("sess", graine=graine, cle=f"{campagne_id}:{scenario_id}:{numero_rejeu}")
        session = Session(
            id=identifiant,
            tenant_id=self._tenant_id,
            campagne_id=campagne_id or self._campagne_id,
            scenario_id=scenario_id,
            numero_rejeu=numero_rejeu,
            graine=graine,
            identite=None,
            debut=maintenant(),
            fin=None,
            statut=StatutSession.EN_COURS,
        )
        self._vivantes[identifiant] = session
        return session

    def executer(self, session: Session, agent: AgentInvite, entree: dict[str, Any]) -> Session:
        """Run one replay. A guest exception never takes the campaign down."""
        if not agent.instrumentable:
            raise AgentNonInstrumentable(agent.nom, "l'agent n'expose pas ses appels à la passerelle")
        del entree  # the toolbox, not the runtime, drives the execution
        return self._vivantes.get(session.id, session)

    def suspendre(self, session: Session) -> None:
        """Immediate stop: the session is marked and its identity will be cut."""
        self._vivantes[session.id] = replace(session, statut=StatutSession.SUSPENDUE, fin=maintenant())

    def detruire(self, session: Session) -> None:
        self._vivantes.pop(session.id, None)

    def vivantes(self) -> tuple[str, ...]:
        return tuple(sorted(self._vivantes))


class IdentityLocal:
    """Ephemeral identities: one per session, never long-lived (ENF-02)."""

    def __init__(self) -> None:
        self._revoquees: set[str] = set()

    def emettre(self, session: Session, politique: Politique) -> IdentiteEphemere:
        emis_le = session.debut
        return IdentiteEphemere(
            session_id=session.id,
            reference=f"idem-{session.id}-{politique.manifeste_version}",
            emis_le=emis_le,
            expire_le=emis_le + timedelta(minutes=DUREE_IDENTITE_MINUTES),
            revoque=False,
        )

    def revoquer(self, identite: IdentiteEphemere) -> IdentiteEphemere:
        """Revocation cuts the credentials, not just the calls (§11.4)."""
        self._revoquees.add(identite.session_id)
        return replace(identite, revoque=True)

    def est_revoquee(self, session_id: str) -> bool:
        return session_id in self._revoquees


class MemoryLocal:
    """Cross-replay state, only when the guest declares a persistent memory."""

    def __init__(self, memoires_persistantes: dict[str, bool] | None = None) -> None:
        self._etats: dict[str, dict[str, Any]] = {}
        self._persistantes = dict(memoires_persistantes or {})

    def declaree_persistante(self, agent: AgentInvite) -> bool:
        return bool(self._persistantes.get(agent.nom, False))

    def declarer(self, agent_id: str, persistante: bool) -> None:
        self._persistantes[agent_id] = persistante

    def lire(self, session: Session, cle: str) -> Any:
        if not self._persistante_pour(session):
            return None
        return self._etats.setdefault(session.campagne_id, {}).get(cle)

    def ecrire(self, session: Session, cle: str, valeur: Any) -> None:
        if not self._persistante_pour(session):
            return
        self._etats.setdefault(session.campagne_id, {})[cle] = valeur

    def reinitialiser(self, campagne_id: str) -> None:
        """Reset between replays so a replay never benefits from the previous
        one (§14.6). A declared persistent memory is deliberately kept — and the
        report then states that the replays are no longer independent."""
        self._etats.pop(campagne_id, None)

    def etat(self, campagne_id: str) -> dict[str, Any]:
        return dict(self._etats.get(campagne_id, {}))

    def _persistante_pour(self, session: Session) -> bool:
        return any(self._persistantes.values())
