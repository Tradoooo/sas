"""Store integrity errors (§22.1).

Two families, deliberately distinct:

* `IntegriteRefusee` — a write that would break a rule of the data model
  (a session without a valid manifest, an attestation being rewritten, a nature
  accepted from outside instead of computed);
* `AccesInterdit` — a read or write that crosses a tenant boundary (EF-50,
  EF-51). The refusal is itself a fact worth recording.
"""

from __future__ import annotations

from dataclasses import dataclass


class IntegriteRefusee(Exception):
    """A write refused by the integrity rules of §22.1."""


class AccesInterdit(Exception):
    """A tenant boundary was crossed. Never a silent empty result."""

    def __init__(self, tenant_autorise: str, tenant_demande: str) -> None:
        super().__init__(
            f"accès refusé : le dépôt est lié au tenant « {tenant_autorise} », "
            f"la demande porte sur « {tenant_demande} »"
        )
        self.tenant_autorise = tenant_autorise
        self.tenant_demande = tenant_demande


@dataclass(frozen=True, slots=True)
class FaitAcces:
    """The structured record of a refused access, so the API can journal it."""

    tenant_autorise: str
    tenant_demande: str
    acteur: str
    operation: str
    refuse: bool = True


def fait_depuis(exc: AccesInterdit, *, acteur: str, operation: str) -> FaitAcces:
    return FaitAcces(
        tenant_autorise=exc.tenant_autorise,
        tenant_demande=exc.tenant_demande,
        acteur=acteur,
        operation=operation,
    )
