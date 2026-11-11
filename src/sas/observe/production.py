"""Observed mode: logged production under perimeter and kill switch (§10.2).

Shadow mode alone is not enough — an agent can behave on synthetic data and
differently on real data. Observed mode alone is not enough either: nothing goes
to production that has not been measured. The cycle is
**Shadow -> attestation -> Observed -> monitoring -> re-homologation** (§10.3).

Three things this module guarantees:

* every call still goes through the gateway, so the journal stays exhaustive;
* the kill switch cuts the identities, so the agent cannot be "finishing"
  (§11.4, ENF-09);
* the added latency is **measured**, not promised (ENF-08: < 100 ms per tool
  call — the target is a measurement target, and the report publishes the
  measured figure).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sas.arret import Interrupteur
from sas.constantes import SEUILS_DEFAUT, Seuils
from sas.identifiants import maintenant
from sas.types import Attestation, Mode, Verdict


class MiseEnProductionRefusee(Exception):
    """§18 — putting an un-homologated agent in production is never automatic."""


@dataclass(slots=True)
class SessionObservee:
    agent_id: str
    tenant_id: str
    ouverte_le: datetime
    appels: int = 0
    refus: int = 0
    latences_ms: list[float] = field(default_factory=list)
    fermee_le: datetime | None = None

    @property
    def latence_moyenne_ms(self) -> float:
        return sum(self.latences_ms) / len(self.latences_ms) if self.latences_ms else 0.0

    @property
    def latence_max_ms(self) -> float:
        return max(self.latences_ms) if self.latences_ms else 0.0


@dataclass(slots=True)
class ControleProduction:
    """What the observed mode needs before it accepts to run an agent."""

    agent_id: str
    tenant_id: str
    attestation: Attestation | None = None
    accord_humain: str = ""
    interrupteur: Interrupteur = field(default_factory=Interrupteur)
    sessions: dict[str, SessionObservee] = field(default_factory=dict)
    seuils: Seuils = SEUILS_DEFAUT

    # -- gate -------------------------------------------------------------- #
    def autoriser(self, *, attestation: Attestation, accord_humain: str) -> None:
        """Open the observed mode. Requires a valid attestation **and** an
        explicit, traceable human agreement (§18, §24.4)."""
        if attestation.resultat is Verdict.NON_MESURABLE:
            raise MiseEnProductionRefusee("un agent non mesurable ne va jamais en production (ENF-17)")
        if attestation.resultat is Verdict.REFUSE:
            raise MiseEnProductionRefusee(
                f"agent refusé le {attestation.date:%Y-%m-%d} : homologation requise"
            )
        if maintenant() > attestation.valide_jusquau:
            raise MiseEnProductionRefusee("l'attestation a expiré : re-homologation requise")
        if not accord_humain.strip():
            raise MiseEnProductionRefusee(
                "la décision de mise en production est le ressort exclusif du commanditaire : "
                "un accord humain explicite et tracé est exigé"
            )
        self.attestation = attestation
        self.accord_humain = accord_humain

    @property
    def autorise(self) -> bool:
        return self.attestation is not None and bool(self.accord_humain.strip())

    # -- kill switch ------------------------------------------------------- #
    def suspendre(self, motif: str, par: str = "commanditaire") -> Any:
        """EF-15 / ENF-09 — immediate, in shadow as well as observed mode.

        Revocation cuts the credentials, not just the calls: the agent cannot be
        "in the middle of finishing" (§11.4). The gateway consults this switch
        before every call, so the next call is denied, not queued.
        """
        suspension = self.interrupteur.armer(motif, par=par)
        for session in self.sessions.values():
            if session.fermee_le is None:
                session.fermee_le = suspension.armee_le
        return suspension

    @property
    def suspendu(self) -> bool:
        return self.interrupteur.arme

    # -- running ----------------------------------------------------------- #
    def ouvrir_session(self, identifiant: str) -> SessionObservee:
        if not self.autorise:
            raise MiseEnProductionRefusee("aucune session observée sans attestation valide et accord tracé")
        if self.suspendu:
            raise MiseEnProductionRefusee("agent suspendu : les identifiants sont coupés")
        session = SessionObservee(agent_id=self.agent_id, tenant_id=self.tenant_id, ouverte_le=maintenant())
        self.sessions[identifiant] = session
        return session

    def enregistrer_appel(self, identifiant: str, *, refuse: bool, latence_ms: float) -> None:
        session = self.sessions.get(identifiant)
        if session is None:
            return
        session.appels += 1
        session.refus += 1 if refuse else 0
        session.latences_ms.append(latence_ms)

    # -- reporting --------------------------------------------------------- #
    def latence(self) -> dict[str, float]:
        """ENF-08 — the measured added latency, against the 100 ms target."""
        toutes = [v for s in self.sessions.values() for v in s.latences_ms]
        if not toutes:
            return {
                "moyenne_ms": 0.0,
                "max_ms": 0.0,
                "cible_ms": self.seuils.latence_observee_max_ms,
                "dans_la_cible": True,
            }
        moyenne = sum(toutes) / len(toutes)
        return {
            "moyenne_ms": round(moyenne, 2),
            "max_ms": round(max(toutes), 2),
            "cible_ms": self.seuils.latence_observee_max_ms,
            "dans_la_cible": moyenne <= self.seuils.latence_observee_max_ms,
            "appels": float(len(toutes)),
        }

    def mode(self) -> Mode:
        return Mode.OBSERVE


def quotas(controle: ControleProduction) -> dict[str, Any]:
    """What the observed mode enforces, quotable by the report."""
    attestation = controle.attestation
    return {
        "mode": Mode.OBSERVE.value,
        "autorise": controle.autorise,
        "suspendu": controle.suspendu,
        "attestation": attestation.numero if attestation else None,
        "valide_jusquau": attestation.valide_jusquau.isoformat() if attestation else None,
        "accord_humain": controle.accord_humain,
        "sessions": len(controle.sessions),
        "appels": sum(s.appels for s in controle.sessions.values()),
        "refus": sum(s.refus for s in controle.sessions.values()),
        "latence": controle.latence(),
    }


def alertes_latence(mesure: dict[str, float]) -> Sequence[str]:
    if mesure.get("dans_la_cible", True):
        return ()
    return (
        f"latence moyenne observée {mesure['moyenne_ms']} ms au-dessus de la cible "
        f"{mesure['cible_ms']} ms : limiter le mode Observé aux appels sensibles et le déclarer (§32)",
    )
