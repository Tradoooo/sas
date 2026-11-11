"""Manifest versioning (spec §9.3): a change creates a new version and
invalidates the attestation in force.

The fingerprint covers **what binds the vendor** — identity, purpose, requested
tools and data, authorised outputs, budgets, memory, scenarios, prohibitions and
commitments. It deliberately excludes the workflow status and the signatures, so
two semantically identical manifests share a fingerprint whatever their state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, replace
from datetime import datetime
from typing import Any

from sas.identifiants import empreinte as empreinte_canonique
from sas.types import Manifeste, StatutManifeste

CHAMPS_ENGAGEANTS: tuple[str, ...] = (
    "version",
    "date",
    "identite",
    "finalite",
    "outils_demandes",
    "donnees_demandees",
    "sorties_autorisees",
    "budgets",
    "memoire_persistante",
    "scenarios",
    "interdictions_explicites",
    "engagements",
)


def projection(manifeste: Manifeste) -> dict[str, Any]:
    """The part of the manifest the fingerprint commits to."""
    donnees = asdict(manifeste)
    return {champ: donnees[champ] for champ in CHAMPS_ENGAGEANTS if champ in donnees}


def empreinte_manifeste(manifeste: Manifeste) -> str:
    """Canonical fingerprint: `sha256:<hex>`."""
    return empreinte_canonique(projection(manifeste))


def avec_empreinte(manifeste: Manifeste) -> Manifeste:
    """Return the manifest with its `empreinte` field filled in."""
    return replace(manifeste, empreinte=empreinte_manifeste(manifeste))


def nouvelle_version(manifeste: Manifeste, changements: Mapping[str, Any]) -> Manifeste:
    """Bump the version and drop back to draft: it must be signed again.

    `changements` records what moved; it is not applied blindly (the caller
    builds the new content), it is only quoted in the invalidation notice so a
    report can say *why* the previous attestation died.
    """
    date_changement = changements.get("date")
    nouvelle = replace(
        manifeste,
        version=manifeste.version + 1,
        statut=StatutManifeste.BROUILLON,
        signature=None,
        validation_client=None,
        empreinte="",
        **({"date": date_changement} if isinstance(date_changement, datetime) else {}),
    )
    return avec_empreinte(nouvelle)


def marquer_remplace(manifeste: Manifeste) -> Manifeste:
    """The previous version is no longer in force."""
    return replace(manifeste, statut=StatutManifeste.REMPLACE)


def invalidations(ancien: Manifeste, nouveau: Manifeste) -> tuple[str, ...]:
    """The textual consequences of moving from one version to the next.

    §9.3 — any modification creates a new version **and** invalidates the
    attestation in force. The report quotes these lines verbatim.
    """
    consequences: list[str] = [
        f"la version {ancien.version} du manifeste est remplacée par la version {nouveau.version}",
        "l'attestation en cours est invalidée",
        "une re-homologation complète est obligatoire avant toute mise en production",
    ]
    differences = _differences(ancien, nouveau)
    if not differences:
        consequences.append("le périmètre déclaré est inchangé : seule la version administrative change")
    else:
        consequences.extend(differences)
    return tuple(consequences)


def _differences(ancien: Manifeste, nouveau: Manifeste) -> tuple[str, ...]:
    avant, apres = projection(ancien), projection(nouveau)
    differences: list[str] = []
    for champ in CHAMPS_ENGAGEANTS:
        if champ in ("version", "date"):
            continue
        if avant.get(champ) != apres.get(champ):
            differences.append(f"le bloc « {champ} » a changé")
    return tuple(differences)


def historique(versions: Mapping[int, Manifeste]) -> tuple[int, ...]:
    """Version numbers, oldest first."""
    return tuple(sorted(versions))
