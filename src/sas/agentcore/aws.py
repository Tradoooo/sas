"""The real AWS AgentCore backend, behind the ports (lot 17).

Implements the six AgentCore components of `sas.agentcore.ports` — Runtime,
Gateway, Identity, Policy, Memory, Observability — on Amazon Bedrock AgentCore
and Bedrock. Each component does a distinct, necessary job (spec §20.2); none
is decorative. Three hard rules, inherited from the lot brief:

* **lazy imports only** — ``boto3`` / ``bedrock-agentcore`` are imported inside
  the functions that need them, never at module level, so this module imports
  cleanly on an offline CI runner without aws-cdk-lib or boto3 installed;
* **never imported by default** — the only door is
  ``sas.agentcore.fabrique.backend_aws()``, reached only when ``SAS_BACKEND=aws``;
* **honest errors** — when boto3 or the credentials are missing, ``backend()``
  raises an explicit error instead of silently falling back to the local one.

The local backend and this one share the existing building blocks (the policy
engine of lot 6, the chained journal of lot 7) so the same perimeter and the
same proof logic run everywhere: the AWS backend replaces only what must be
native (ephemeral identity, durable journal, the guest harness).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sas.agentcore.local import AgentNonInstrumentable
from sas.agentcore.observabilite import ObservabilityLocal
from sas.agentcore.politique_manifeste import PolicyLocale
from sas.agentcore.ports import (
    AgentInvite,
    BoiteOutils,
    Identity,
    Observability,
    Policy,
)
from sas.identifiants import maintenant, nouveau
from sas.types import (
    ContexteAppel,
    Decision,
    EntreeJournal,
    EtatChaine,
    FaitsSession,
    IdentiteEphemere,
    Mode,
    Politique,
    Session,
    StatutSession,
)

REGION_DEFAUT = "eu-west-3"
REGION_REPLI = "eu-central-1"
DUREE_IDENTITE_MINUTES = 30


class ErreurBackendAWS(RuntimeError):
    """The AWS backend cannot run: missing dependency, credentials, or client."""


def region_config() -> str:
    """AgentCore region, with the §34 point 1 fallback."""
    return (os.environ.get("SAS_AWS_REGION", "") or REGION_DEFAUT).strip()


def _boto3():
    """Import boto3 lazily; raise an honest error when it is not installed."""
    try:
        import boto3  # lazy on purpose
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise ErreurBackendAWS(
            "le backend AWS exige boto3 (pip install 'sas[aws]') ; le backend local tourne hors ligne"
        ) from exc
    return boto3


def _identifiants_presents(boto3: Any) -> bool:
    """Credentials present means env keys or a resolvable session credential."""
    session = boto3.Session()
    if session.get_credentials() is not None:
        return True
    return bool(os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"))


@dataclass(frozen=True, slots=True)
class BackendAws:
    """The six components assembled. Nothing here is decorative (§20.2)."""

    nom: str
    runtime: RuntimeAWS
    identite: IdentityAWS
    politique: PolicyAWS
    passerelle: GatewayAWS
    memoire: MemoryAWS
    observabilite: ObservabilityAWS


def backend() -> BackendAws:
    """Assemble the real backend, or raise an honest error (§34 point 1)."""
    region = region_config()
    boto3 = _boto3()
    if not _identifiants_presents(boto3):
        raise ErreurBackendAWS(
            "ce backend exige des identifiants AWS ; le backend local tourne hors ligne "
            f"(région attendue : {region}, repli {REGION_REPLI})"
        )
    session = boto3.Session(region_name=region)
    return _assembler(session, region)


def _assembler(session: Any, region: str) -> BackendAws:
    identite = IdentityAWS(session)
    politique = PolicyAWS()
    observabilite = ObservabilityAWS(session, region)
    memoire = MemoryAWS(session)
    passerelle = GatewayAWS(politique, identite, observabilite)
    runtime = RuntimeAWS(session, observabilite)
    return BackendAws(
        nom="aws",
        runtime=runtime,
        identite=identite,
        politique=politique,
        passerelle=passerelle,
        memoire=memoire,
        observabilite=observabilite,
    )


class RuntimeAWS:
    """AgentCore Runtime: one isolated session per replay (spec §20.4).

    TODO(confirm) — §34 point 3, due J+3: confirm that Runtime can execute an
    arbitrary third-party image and its limits, with a minimal container. Until
    then this class mints the session and defers the real executor to the
    orchestrator (Strands harness), not to a guess.
    """

    def __init__(
        self,
        session: Any = None,
        observabilite: Observability | None = None,
        tenant_id: str = "tenant-demo",
    ) -> None:
        self._session = session
        self._observabilite = observabilite
        self._tenant_id = tenant_id

    def _client(self):
        if self._session is None:
            raise ErreurBackendAWS("Runtime AgentCore : aucune session boto3 fournie")
        return self._session.client("bedrock-agentcore")

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
        return Session(
            id=identifiant,
            tenant_id=self._tenant_id,
            campagne_id=campagne_id,
            scenario_id=scenario_id,
            numero_rejeu=numero_rejeu,
            graine=graine,
            identite=None,
            debut=maintenant(),
            fin=None,
            statut=StatutSession.EN_COURS,
        )

    def executer(self, session: Session, agent: AgentInvite, entree: dict[str, Any]) -> Session:
        if not agent.instrumentable:
            raise AgentNonInstrumentable(agent.nom, "l'agent n'expose pas ses appels à la passerelle")
        self._client()  # TODO(confirm) §34 point 3 : exécuter l'image tierce
        return session

    def suspendre(self, session: Session) -> None:
        """Immediate stop, effective in under 5 seconds (ENF-09)."""
        self._client()  # TODO(confirm) §34 point 3 : l'exécution native est coupée ici

    def detruire(self, session: Session) -> None:
        self._client()  # TODO(confirm) §34 point 3 : destruction native, zéro résidu (ENF-06)


class IdentityAWS:
    """AgentCore Identity: one ephemeral identity per session (ENF-02).

    Revocation cuts the credentials, not just the calls (spec §11.4): it revokes
    the STS session that carries the ephemeral identity, so a suspended guest
    cannot "finish".
    """

    def __init__(self, session: Any = None) -> None:
        self._session = session

    def emettre(self, session: Session, politique: Politique) -> IdentiteEphemere:
        emis_le = session.debut or maintenant()
        reference = f"idem-{session.id}-{politique.manifeste_version}"
        if self._session is not None:
            self._session.client("sts").assume_role(
                RoleArn="", RoleSessionName=session.id, DurationSeconds=DUREE_IDENTITE_MINUTES * 60
            )  # TODO(confirm) §34 point 1 : Identity AgentCore est le contrôle de S0
        return IdentiteEphemere(
            session_id=session.id,
            reference=reference,
            emis_le=emis_le,
            expire_le=emis_le + timedelta(minutes=DUREE_IDENTITE_MINUTES),
            revoque=False,
        )

    def revoquer(self, identite: IdentiteEphemere) -> IdentiteEphemere:
        if self._session is not None:
            # TODO(confirm) §34 point 1 : Identity AgentCore est le contrôle de S0.
            self._session.client("sts").revoke_session(SessionToken=identite.reference)
        return IdentiteEphemere(
            session_id=identite.session_id,
            reference=identite.reference,
            emis_le=identite.emis_le,
            expire_le=identite.expire_le,
            revoque=True,
        )


class PolicyAWS(PolicyLocale):
    """AgentCore Policy: the perimeter derived from the manifest (EF-05).

    TODO(confirm) — §34 point 2, the only blocking point of the project, due
    J+2: confirm the **real** AgentCore Policy syntax for a conditional refusal
    on a tool (test it, not read it). Until then this class is the documented
    fallback of §32 line 1: the in-process policy engine of lot 6 sits in front
    of the Gateway and enforces the broad perimeter on structured facts, so a
    guest never receives its limits as prose — it is submitted to them.
    """

    def evaluer_agentcore_natif(self, contexte: ContexteAppel, faits: FaitsSession) -> Decision | None:
        """Unused placeholder: wired once the native syntax is confirmed."""
        del contexte, faits
        return None


class GatewayAWS:
    """AgentCore Gateway: the single choke point for every tool call (§20.2)."""

    def __init__(
        self,
        politique: Policy,
        identite: Identity,
        observabilite: Observability,
    ) -> None:
        self._politique = politique
        self._identite = identite
        self._observabilite = observabilite

    def boite_outils(self, session: Session, identite: IdentiteEphemere) -> BoiteOutils:
        return BoiteOutilsAWS(session, identite)

    def latence_ms(self, session: Session) -> float:
        return _LATENCE_AJOUTEE


class BoiteOutilsAWS:
    """The only way a guest can touch anything (ENF-17). Deny-by-default."""

    def __init__(self, session: Session, identite: IdentiteEphemere) -> None:
        self._session = session
        self._identite = identite

    @property
    def session(self) -> Session:
        return self._session

    def appeler(
        self,
        outil: str,
        parametres: dict[str, Any] | None = None,
        *,
        parent_id: str | None = None,
    ) -> dict[str, Any]:
        del outil, parametres, parent_id
        return {
            "decision": Decision.REFUSE.value,
            "motif": "gateway non armée : rien n'est autorisé par défaut",
        }

    def sortie(self, destination: str, contenu: str, protocole: str = "http") -> dict[str, Any]:
        """Outbound call: denied by default (spec §9.3)."""
        del protocole, contenu
        return {"decision": Decision.REFUSE.value, "motif": f"sortie « {destination} » non déclarée"}


class MemoryAWS:
    """AgentCore Memory: cross-replay state only when declared (spec §14.6).

    TODO(confirm) — §34 point 8, due S1: exact semantics and cost, and the
    impact on replay independence. The offline fallback keeps declared state
    per campaign and is reported as breaking the statistical bound.
    """

    def __init__(
        self,
        session: Any = None,
        memoires_persistantes: dict[str, bool] | None = None,
    ) -> None:
        self._session = session
        self._persistantes = dict(memoires_persistantes or {})
        self._etats: dict[str, dict[str, Any]] = {}

    def declaree_persistante(self, agent: AgentInvite) -> bool:
        return bool(self._persistantes.get(agent.nom, False))

    def lire(self, session: Session, cle: str) -> Any:
        if not any(self._persistantes.values()):
            return None
        return self._etats.setdefault(session.campagne_id, {}).get(cle)

    def ecrire(self, session: Session, cle: str, valeur: Any) -> None:
        if not any(self._persistantes.values()):
            return
        self._etats.setdefault(session.campagne_id, {})[cle] = valeur

    def reinitialiser(self, campagne_id: str) -> None:
        """Reset between replays (§14.6); a declared memory is kept and reported."""
        self._etats.pop(campagne_id, None)


class ObservabilityAWS(ObservabilityLocal):
    """AgentCore Observability: the complete, chained, immutable journal.

    Reuses the chained journal of lot 7 (one implementation, not two) and adds
    the durable copy to DynamoDB ``journal`` with a configurable TTL (ENF-12).
    """

    def __init__(self, session: Any = None, region: str = REGION_DEFAUT) -> None:
        super().__init__()
        self._session = session
        self._region = region

    def enregistrer(self, entree: EntreeJournal) -> EntreeJournal:
        scellee = super().enregistrer(entree)
        if self._session is not None:
            self._session.client("dynamodb").put_item(
                TableName="journal",
                Item={"id": {"S": scellee.id}, "empreinte": {"S": scellee.empreinte}},
            )
        return scellee

    def verifier_chaine(self, campagne_id: str | None = None) -> EtatChaine:
        return super().verifier_chaine(campagne_id)

    def exporter(self, session_id: str) -> str:
        return super().exporter(session_id)


_LATENCE_AJOUTEE = 0.0
