"""Token -> tenant, never from free text (EF-51).

The API has no route that accepts a tenant as a parameter: the tenant is
derived from the bearer token. This module is the single place that does the
derivation, and it returns a `ContexteTenant` with the role, so the handlers
stay role-agnostic and the store stays tenant-scoped by construction.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from sas.store.integrite import AccesInterdit
from sas.types import ContexteTenant

Role = Literal["commanditaire", "architecte", "juridique", "analyste_msp", "responsable_compte", "editeur"]

# For the hackathon demo, tokens are deterministic HMACs over "<tenant>:<role>".
# A real deployment verifies Cognito JWTs; the derivation function is the same
# shape and is documented in infra/cdk/api.py (Cognito -> tenant via claim).
SECRET_DEMO = "sas-demo-secret-never-in-production"


def emettre(tenant_id: str, role: Role, acteur: str, editeur_id: str | None = None) -> str:
    """Issue a bearer token for the demo. Deterministic and verifiable."""
    message = "|".join([tenant_id, role, acteur, editeur_id or ""])
    sceau = hmac.new(SECRET_DEMO.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"sas.{message}.{sceau[:24]}"


def deriver(jeton: str) -> ContexteTenant:
    """Derive the tenant and role from a token. Nothing else is trusted."""
    if not jeton.startswith("sas."):
        raise AccesInterdit("", "jeton illisible")
    parties = jeton.split(".")
    if len(parties) != 3:
        raise AccesInterdit("", "jeton malformé")
    message = parties[1]
    champs = message.split("|")
    if len(champs) < 3:
        raise AccesInterdit("", "jeton incomplet")
    tenant_id, role, acteur = champs[0], champs[1], champs[2]
    editeur_id = champs[3] if len(champs) > 3 else None
    retour = ContexteTenant(tenant_id=tenant_id, role=role, acteur=acteur, editeur_id=editeur_id, jeton=jeton)  # type: ignore[arg-type]
    if _verifier(jeton, retour) is False:
        raise AccesInterdit("", "sceau invalide")
    return retour


def _verifier(jeton: str, contexte: ContexteTenant) -> bool:
    attendu = emettre(
        contexte.tenant_id,
        contexte.role,
        contexte.acteur,
        contexte.editeur_id,  # type: ignore[arg-type]
    )
    return hmac.compare_digest(jeton.encode("utf-8"), attendu.encode("utf-8"))


@dataclass(frozen=True, slots=True)
class Portee:
    """What a role may read and do — the table of §7."""

    lecture: tuple[str, ...]


PORTEES: Mapping[str, Portee] = {
    "commanditaire": Portee(("manifeste", "campagne", "attestation", "registre")),
    "architecte": Portee(("manifeste",)),
    "juridique": Portee(("attestation",)),
    "analyste_msp": Portee(("campagne", "tentative", "composition", "ecart", "registre", "budget")),
    "responsable_compte": Portee(("registre", "budget")),
    "editeur": Portee(("rapport-ecart",)),
}


def autoriser(contexte: ContexteTenant, ressource: str) -> None:
    """EF-53 — an editor sees only their own gap report, nothing else."""
    portee = PORTEES.get(contexte.role)
    if portee is None:
        raise AccesInterdit(contexte.tenant_id, f"rôle inconnu {contexte.role}")
    if ressource not in portee.lecture:
        raise AccesInterdit(contexte.tenant_id, f"le rôle {contexte.role} ne lit pas {ressource}")
