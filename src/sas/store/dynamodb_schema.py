"""Sas — the DynamoDB schema, and how the deployed stack is read (lot 18).

The table definitions live in `sas.store.ddl`; this module holds the two things
the adapter needs on top of them:

* the correspondence between a logical table and the dataclass it holds, and
  the key/index attributes the DDL names (`agent_id`, `session_id`…) — the
  adapter writes those names, never the dataclass's own;
* the reading of the deployed stack's outputs, so the physical names come from
  CloudFormation and not from a guess.

The two tables the port does not use are absent on purpose: `scenarios` lives
in YAML files, and the tool calls are the journal.
"""

from __future__ import annotations

import json

from sas.types import (
    Acces,
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

# Logical table -> dataclass it holds. `scenarios` and `appels` are absent on
# purpose: scenarios live in YAML files, and the tool calls are the journal.
ENTITES: dict[str, type] = {
    "tenants": Tenant,
    "editeurs": Editeur,
    "agents": Agent,
    "manifestes": Manifeste,
    "campagnes": Campagne,
    "sessions": Session,
    "journal": EntreeJournal,
    "tentatives": Tentative,
    "compositions": Composition,
    "ecarts": Ecart,
    "enveloppes": Enveloppe,
    "derives": Derive,
    "attestations": Attestation,
    "acces": Acces,
}

# DDL key attribute -> dataclass field that feeds it.
CLES: dict[str, dict[str, str]] = {
    "tenants": {"tenant_id": "id"},
    "editeurs": {"editeur_id": "id"},
    "agents": {"agent_id": "id"},
    "manifestes": {"agent_id": "agent_id", "version": "version"},
    "campagnes": {"campagne_id": "id"},
    "sessions": {"session_id": "id"},
    "journal": {"id": "id"},
    "tentatives": {"tentative_id": "id"},
    "compositions": {"composition_id": "id"},
    "ecarts": {"ecart_id": "id"},
    "enveloppes": {"enveloppe_id": "id"},
    "derives": {"derive_id": "id"},
    "attestations": {"attestation_id": "id"},
    "acces": {"id": "id"},
}

# Global secondary index -> dataclass field (identity everywhere, stated so it
# cannot drift). `tenant_id` is written on every row regardless of the index.
INDEX_CHAMPS: dict[str, dict[str, str]] = {
    "agents": {"tenant_id": "tenant_id"},
    "manifestes": {"agent_id": "agent_id"},
    "campagnes": {"agent_id": "agent_id"},
    "sessions": {"campagne_id": "campagne_id"},
    "journal": {"session_id": "session_id", "campagne_id": "campagne_id"},
    "tentatives": {"campagne_id": "campagne_id"},
    "compositions": {"campagne_id": "campagne_id"},
    "ecarts": {"campagne_id": "campagne_id"},
    "enveloppes": {"agent_id": "agent_id"},
    "derives": {"agent_id": "agent_id"},
    "attestations": {"campagne_id": "campagne_id"},
    "acces": {"tenant_id": "tenant_id", "acteur": "acteur"},
}

# Tables whose key attribute is a bare `id`: the identifier is deterministic, so
# the same evidence (the same campaign replayed) carries the same id for every
# tenant. The stored key is prefixed with the tenant, or two tenants would fight
# over one row (§22.1, EF-51).
CLES_PORTEES_PAR_LE_TENANT: dict[str, tuple[str, ...]] = {
    "journal": ("id",),
}

# The same applies to the index attributes: the identifiers are deterministic,
# so two tenants hold the same `session_id`. An index partition that is not
# tenant-scoped would let one tenant *read* another's rows through a query —
# the exact leak EF-51 forbids. `tenant_id` itself is not prefixed: it is the
# raw value a scan filters on.
INDEX_PORTEES_PAR_LE_TENANT: dict[str, tuple[str, ...]] = {
    "journal": ("session_id", "campagne_id"),
    "sessions": ("campagne_id",),
    "tentatives": ("campagne_id",),
    "compositions": ("campagne_id",),
    "ecarts": ("campagne_id",),
    "attestations": ("campagne_id",),
    "campagnes": ("agent_id",),
    "manifestes": ("agent_id",),
    "enveloppes": ("agent_id",),
    "derives": ("agent_id",),
    "acces": ("acteur",),
}

# Tables whose rows expire by DynamoDB TTL and carry an `expire_le` epoch.
TABLE_TTL: tuple[str, ...] = ("journal", "acces")


class ErreurStoreAbsent(RuntimeError):
    """The deployed store is not reachable: no stack, no credentials.

    Raised instead of a stack trace of boto3: a missing account is a fact
    about the environment, not a bug in the adapter.
    """


def lire_tables(region: str = "eu-west-3", pile: str = "sas-donnees-dev") -> dict[str, str]:
    """Read the physical table names from the deployed CloudFormation stack.

    The names are what the stack actually deployed, so the code cannot drift
    from the infrastructure — the adapter is built from the outputs, not guesses.
    """
    import boto3  # local import: the adapter is the only module that needs it

    client = boto3.client("cloudformation", region_name=region)
    try:
        stack = client.describe_stacks(StackName=pile)["Stacks"][0]
    except Exception as exc:  # botocore raises several shapes of "not there"
        raise ErreurStoreAbsent(f"la pile {pile} ({region}) n'est pas déployée : {exc}") from exc
    sorties = {sortie["OutputKey"]: sortie["OutputValue"] for sortie in stack["Outputs"]}
    return json.loads(sorties["TablesJson"])


def lire_seau_preuves(region: str = "eu-west-3", pile: str = "sas-donnees-dev") -> str:
    """The evidence bucket's real name, read from the stack's outputs."""
    import boto3

    client = boto3.client("cloudformation", region_name=region)
    try:
        stack = client.describe_stacks(StackName=pile)["Stacks"][0]
    except Exception as exc:
        raise ErreurStoreAbsent(f"la pile {pile} ({region}) n'est pas déployée : {exc}") from exc
    sorties = {sortie["OutputKey"]: sortie["OutputValue"] for sortie in stack["Outputs"]}
    return sorties.get("BucketPreuves", "")
