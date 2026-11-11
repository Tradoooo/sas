"""Sas — DynamoDB table definitions (lot 0, frozen).

One table per entity of the data model (spec §22). The definitions are the
single source of truth: the CDK stack (`infra/cdk`) and the local backend
(`sas.store.local`) both read them, so a schema change cannot drift between
the infrastructure and the code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

TABLES: tuple[str, ...] = (
    "tenants",
    "editeurs",
    "agents",
    "manifestes",
    "scenarios",
    "campagnes",
    "sessions",
    "appels",
    "tentatives",
    "compositions",
    "ecarts",
    "enveloppes",
    "derives",
    "attestations",
    "journal",
)


@dataclass(frozen=True, slots=True)
class DefinitionTable:
    nom: str
    cle: str
    attributs_cles: tuple[str, ...]
    index: tuple[tuple[str, str], ...] = ()
    ttl: str | None = None
    notes: str = ""


DEFINITIONS: Mapping[str, DefinitionTable] = {
    "tenants": DefinitionTable(
        nom="tenants",
        cle="tenant_id",
        attributs_cles=("tenant_id",),
        notes="One row per customer. Retention days live here.",
    ),
    "editeurs": DefinitionTable(
        nom="editeurs",
        cle="editeur_id",
        attributs_cles=("editeur_id",),
        notes="Third-party vendors; an editor only ever sees their own gap report.",
    ),
    "agents": DefinitionTable(
        nom="agents",
        cle="agent_id",
        attributs_cles=("agent_id",),
        index=(("tenant_id", "tenant_id"),),
        notes="The fleet registry: one row per third-party agent.",
    ),
    "manifestes": DefinitionTable(
        nom="manifestes",
        cle="agent_id",
        attributs_cles=("agent_id", "version"),
        index=(("agent_id", "agent_id"),),
        notes="Sorted by version; the previous version is flagged replaced.",
    ),
    "scenarios": DefinitionTable(
        nom="scenarios",
        cle="scenario_id",
        attributs_cles=("scenario_id",),
        notes="Homologation scenarios, stored as data (spec annexe B).",
    ),
    "campagnes": DefinitionTable(
        nom="campagnes",
        cle="campagne_id",
        attributs_cles=("campagne_id",),
        index=(("agent_id", "agent_id"),),
        notes="One campaign = one homologation run in one mode.",
    ),
    "sessions": DefinitionTable(
        nom="sessions",
        cle="session_id",
        attributs_cles=("session_id",),
        index=(("campagne_id", "campagne_id"),),
        notes="One session per replay, with its ephemeral identity.",
    ),
    "appels": DefinitionTable(
        nom="appels",
        cle="id",
        attributs_cles=("id",),
        index=(("session_id", "session_id"), ("campagne_id", "campagne_id")),
        notes="Tool calls, denials included. Append-only.",
    ),
    "tentatives": DefinitionTable(
        nom="tentatives",
        cle="tentative_id",
        attributs_cles=("tentative_id",),
        index=(("campagne_id", "campagne_id"),),
        notes="Out-of-scope attempts, with the nature retained by code.",
    ),
    "compositions": DefinitionTable(
        nom="compositions",
        cle="composition_id",
        attributs_cles=("composition_id",),
        index=(("campagne_id", "campagne_id"),),
        notes="Forbidden call chains detected on the session call graph.",
    ),
    "ecarts": DefinitionTable(
        nom="ecarts",
        cle="ecart_id",
        attributs_cles=("ecart_id",),
        index=(("campagne_id", "campagne_id"),),
        notes="Declared vs observed, in both directions.",
    ),
    "enveloppes": DefinitionTable(
        nom="enveloppes",
        cle="enveloppe_id",
        attributs_cles=("enveloppe_id",),
        index=(("agent_id", "agent_id"),),
        notes="Behaviour envelopes; one is flagged as the reference.",
    ),
    "derives": DefinitionTable(
        nom="derives",
        cle="derive_id",
        attributs_cles=("derive_id",),
        index=(("agent_id", "agent_id"),),
        notes="Drift alerts, with the distance and the detail of the change.",
    ),
    "attestations": DefinitionTable(
        nom="attestations",
        cle="attestation_id",
        attributs_cles=("attestation_id",),
        index=(("campagne_id", "campagne_id"),),
        notes="Immutable. A correction is a new dated attestation.",
    ),
    "journal": DefinitionTable(
        nom="journal",
        cle="id",
        attributs_cles=("id",),
        index=(("session_id", "session_id"), ("campagne_id", "campagne_id")),
        ttl="expire_le",
        notes="Append-only, chained by hash. The evidence itself.",
    ),
}


def cle_composite(table: str, parts: Mapping[str, str]) -> str:
    """Build the composite sort key value of a row."""
    definition = DEFINITIONS[table]
    if len(definition.attributs_cles) == 1:
        return parts[definition.attributs_cles[0]]
    return "|".join(parts[attribut] for attribut in definition.attributs_cles)
