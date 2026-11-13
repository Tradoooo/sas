"""Sas — writing a campaign's outcome into a store (lot 18).

The orchestrator writes the campaign and its sessions as it runs them. What it
does **not** write is the analysis: the journal entries, the findings and the
attestation. Those are produced afterwards by `sas.homologation`, and they are
the evidence the report quotes — so they belong in the store too, and the same
code serves the in-memory demo and the real DynamoDB.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from typing import Any

from sas.store.base import Depot


def persister(depot: Depot, dossier: Any) -> dict[str, int]:
    """Write what a campaign produced. Returns what was written.

    The counts come back so the caller can say what it did: a demo that claims
    "written in the real tables" must be able to prove it, line by line.
    """
    ecrits = {
        "journal": _ecrire(depot.ajouter_entree, dossier.campagne.entrees),
        "tentatives": _ecrire(depot.enregistrer_tentative, dossier.tentatives),
        "compositions": _ecrire(depot.enregistrer_composition, dossier.compositions),
        "ecarts": _ecrire(depot.enregistrer_ecart, dossier.ecarts),
    }
    if dossier.attestation is not None:
        depot.enregistrer_attestation(_avec_precedente(depot, dossier.attestation))
        ecrits["attestations"] = 1
    else:
        ecrits["attestations"] = 0
    return ecrits


def _ecrire(fonction: Any, elements: Iterable[Any]) -> int:
    nombre = 0
    for element in elements:
        fonction(element)
        nombre += 1
    return nombre


def _avec_precedente(depot: Depot, attestation: Any) -> Any:
    """§22.1 — the new dated attestation references the one it replaces.

    "An attestation is never corrected: it is replaced by a new dated one that
    references the old." The link is only known once the store has been asked
    what it already holds — which is exactly why it is made here, and not in
    the report.
    """
    if attestation.remplace:
        return attestation
    precedentes = sorted(depot.attestations(attestation.campagne_id), key=lambda a: a.date)
    if not precedentes:
        return attestation
    return replace(attestation, remplace=precedentes[-1].id)
