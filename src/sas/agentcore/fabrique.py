"""Choosing and assembling the AgentCore backend (lot 5).

No lot imports a backend directly: this module is the only door. It prefers the
real configurable policy engine of lot 6 when it is present, and the real AWS
backend when `SAS_BACKEND=aws` and the module exists — otherwise it assembles
the local one, which is what the tests, the demo and CI run on.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from sas.agentcore.local import IdentityLocal, MemoryLocal, RuntimeLocal
from sas.agentcore.observabilite import ObservabilityLocal
from sas.agentcore.passerelle import GatewayLocal
from sas.agentcore.politique_manifeste import PolicyLocale, deriver
from sas.agentcore.ports import Policy
from sas.journal.chaine import JournalChaine
from sas.ombre.support import SupportOmbre
from sas.types import Manifeste, Mode, Politique, StatutManifeste


@dataclass(frozen=True, slots=True)
class Backend:
    """The six components, assembled. Nothing here is decorative (§20.2)."""

    nom: str
    runtime: RuntimeLocal
    identite: IdentityLocal
    politique: Politique
    moteur: Policy
    passerelle: GatewayLocal
    memoire: MemoryLocal
    observabilite: ObservabilityLocal
    support: SupportOmbre
    journal: JournalChaine
    mode: Mode


def moteur_politique(politique: Politique) -> Policy:
    """Lot 6's configurable engine if it exists, else the manifest-derived one."""
    try:  # pragma: no cover - depends on lot 6 being merged
        from sas.politique.moteur import MoteurPolitique

        return MoteurPolitique(politique)  # type: ignore[return-value]
    except ImportError:
        return PolicyLocale(politique)


def politique_depuis(manifeste: Manifeste, mode: Mode = Mode.OMBRE) -> Politique:
    """EF-05 — the applied policy comes from the manifest, never from a hand."""
    return deriver(manifeste, mode)


def backend(
    *,
    politique: Politique,
    support: SupportOmbre,
    mode: Mode = Mode.OMBRE,
    tenant_id: str = "tenant-demo",
    memoires_persistantes: dict[str, bool] | None = None,
    manifeste_statut: StatutManifeste = StatutManifeste.VALIDE,
    version_courante: int = 1,
    journal: JournalChaine | None = None,
) -> Backend:
    chaine = journal or JournalChaine()
    moteur = moteur_politique(politique)
    identite = IdentityLocal()
    observabilite = ObservabilityLocal(chaine)
    passerelle = GatewayLocal(
        politique=politique,
        support=support,
        journal=chaine,
        identite_port=identite,
        moteur=moteur,
        manifeste_statut=manifeste_statut,
        version_courante=version_courante,
        mode=mode,
    )
    return Backend(
        nom=_nom_backend(),
        runtime=RuntimeLocal(tenant_id=tenant_id),
        identite=identite,
        politique=politique,
        passerelle=passerelle,
        memoire=MemoryLocal(memoires_persistantes),
        moteur=moteur,
        observabilite=observabilite,
        support=support,
        journal=chaine,
        mode=mode,
    )


def backend_aws() -> Any:
    """Real AgentCore. Raises an honest error when it cannot be used."""
    try:  # pragma: no cover - exercised only with credentials
        from sas.agentcore import aws
    except ImportError as exc:
        raise RuntimeError("SAS_BACKEND=aws demande le lot 17 (sas.agentcore.aws) et boto3 installé") from exc
    return aws.backend()  # pragma: no cover


def _nom_backend() -> str:
    demande = os.environ.get("SAS_BACKEND", "local").strip().lower()
    return demande or "local"
