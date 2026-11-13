"""Amazon Quick datasets and multi-tenant row-level security (lot 16).

Pure Python and deterministic so it can be tested offline and its generated
bundle (`infra/quick/datasets.json`) can be reproduced bit-for-bit.

Three datasets mirror the data model of spec §22 and are read by the CDK stack
`infra/cdk/quick.py` — the QuickSight side does not reinvent the schema, it
consumes the same tables defined once in `sas.store.ddl`:

* ``registre_flotte``  — the fleet registry, one row per third-party agent;
* ``tendances_derive`` — drift alerts with the distance and the action taken;
* ``cout_par_tenant``  — measured cost per campaign and per tenant (ENF-10).

Row-level security enforces the two isolation requirements of §25 and EF-42/
EF-53: a customer sees only its own agents and costs, an editor sees only its
own agents — never another tenant's data, never another editor's gap report.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Any

SCHEMA_VERSION = 1

ROLES: tuple[str, ...] = ("tenant", "editeur")


@dataclass(frozen=True, slots=True)
class Dataset:
    """One Amazon Quick dataset.

    ``source`` names a table of ``sas.store.ddl`` — never a hand-made copy.
    ``dimensions`` group rows, ``faits`` are the measures to aggregate.
    """

    identifiant: str
    nom: str
    source: str
    colonnes: tuple[str, ...]
    dimensions: tuple[str, ...] = ()
    faits: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RegleRls:
    """One row-level security rule.

    ``colonne`` is the dataset column filtered against the identity carried by
    the user's token (the tenant id or the editor id — EF-51: the tenant never
    comes from the request, always from the token).
    """

    role: str
    dataset: str
    colonne: str
    description: str


# Which role may open which dataset. An editor never sees a tenant's measured
# cost nor the drift of agents that are not its own (EF-42, EF-53).
ACCES_PAR_DATASET: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "registre_flotte": ("tenant", "editeur"),
        "tendances_derive": ("tenant",),
        "cout_par_tenant": ("tenant",),
    }
)


def datasets() -> tuple[Dataset, ...]:
    """The three datasets, sorted so the generated bundle is deterministic."""
    return tuple(
        sorted(
            (
                Dataset(
                    identifiant="registre_flotte",
                    nom="Fleet registry",
                    source="agents",
                    colonnes=(
                        "agent_id",
                        "tenant_id",
                        "editeur_id",
                        "nom",
                        "version_courante",
                        "empreinte",
                        "statut",
                    ),
                    dimensions=("tenant_id", "editeur_id", "statut"),
                ),
                Dataset(
                    identifiant="tendances_derive",
                    nom="Drift trends",
                    source="derives",
                    colonnes=("derive_id", "agent_id", "distance", "alerte_le", "action"),
                    dimensions=("agent_id", "action"),
                    faits=("distance",),
                ),
                Dataset(
                    identifiant="cout_par_tenant",
                    nom="Measured cost per tenant",
                    source="campagnes",
                    colonnes=(
                        "campagne_id",
                        "tenant_id",
                        "agent_id",
                        "manifeste_id",
                        "mode",
                        "n_rejeux",
                        "statut",
                        "debutee_le",
                        "cout_mesure",
                    ),
                    dimensions=("tenant_id", "agent_id", "mode"),
                    faits=("cout_mesure",),
                ),
            ),
            key=lambda d: d.identifiant,
        )
    )


def regles_rls() -> tuple[RegleRls, ...]:
    """The row-level security rules, sorted by (dataset, role)."""
    return tuple(
        sorted(
            (
                RegleRls(
                    role="tenant",
                    dataset="registre_flotte",
                    colonne="tenant_id",
                    description="A customer sees only its own agents (EF-53).",
                ),
                RegleRls(
                    role="tenant",
                    dataset="tendances_derive",
                    colonne="agent_id",
                    description="A customer sees the drift of its own agents only (EF-53).",
                ),
                RegleRls(
                    role="tenant",
                    dataset="cout_par_tenant",
                    colonne="tenant_id",
                    description="A customer sees only its own measured cost (EF-53).",
                ),
                RegleRls(
                    role="editeur",
                    dataset="registre_flotte",
                    colonne="editeur_id",
                    description="An editor sees only the agents it publishes (EF-53).",
                ),
            ),
            key=lambda r: (r.dataset, r.role),
        )
    )


def bundle() -> dict[str, Any]:
    """Deterministic JSON-able bundle written to ``infra/quick/datasets.json``."""
    return {
        "schema_version": SCHEMA_VERSION,
        "datasets": [asdict(d) for d in datasets()],
        "acces": {d: list(roles) for d, roles in sorted(ACCES_PAR_DATASET.items())},
        "rls": [asdict(r) for r in regles_rls()],
    }
