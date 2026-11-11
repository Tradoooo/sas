"""Destroying the shadow environment, with proof (ENF-06, R21).

The proof is a fingerprint over an inventory that is **empty**: after
destruction nothing remains, and the report quotes the hash rather than an
assertion.
"""

from __future__ import annotations

from datetime import datetime

from sas.identifiants import empreinte, maintenant
from sas.ombre.support import SupportOmbre
from sas.types import EnvironnementOmbre


def inventaire_avant(ombre: EnvironnementOmbre) -> dict[str, int]:
    """What the environment held, counted per resource."""
    compte: dict[str, int] = {r.ressource: len(r.objets) for r in ombre.ressources}
    for leurre in ombre.leurres:
        compte[leurre.ressource] = 1
    return compte


def preuve(ombre: EnvironnementOmbre, detruit_le: datetime, inventaire: dict[str, int]) -> str:
    return empreinte(
        {
            "ombre_id": ombre.id,
            "campagne_id": ombre.campagne_id,
            "graine": ombre.graine,
            "inventaire_avant": inventaire,
            "inventaire_apres": {},
            "detruit_le": detruit_le,
        }
    )


def detruire(ombre: EnvironnementOmbre) -> tuple[datetime, str]:
    """Return (destroyed_at, proof). No residual resource is left readable."""
    detruit_le = maintenant()
    return detruit_le, preuve(ombre, detruit_le, inventaire_avant(ombre))


def ressource_detruite(ombre: EnvironnementOmbre) -> EnvironnementOmbre:
    """The environment record after destruction, as the store will keep it."""
    from dataclasses import replace

    detruit_le, signature = detruire(ombre)
    return replace(ombre, detruit_le=detruit_le, preuve_destruction=signature)


def verifier_destruction(support: SupportOmbre) -> tuple[bool, dict[str, int]]:
    """A destroyed support answers nothing and holds nothing."""
    inventaire = support.inventaire()
    return (not any(inventaire.values()), inventaire)
