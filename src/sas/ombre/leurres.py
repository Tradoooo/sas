"""Marked decoys (spec §21.2, annexe F.2).

A decoy turns a fuzzy question — "was it allowed to?" — into a binary one —
"did it touch the decoy?". The decoys are declared in `constantes.LEURRES_DEFAUT`
so adding one is a data change, not a code change.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from sas import constantes
from sas.types import Leurre


def leurres_par_defaut() -> tuple[Leurre, ...]:
    """The decoys of the demonstration shadow environment."""
    return tuple(_depuis(declaration) for declaration in constantes.LEURRES_DEFAUT)


def _depuis(declaration: Mapping[str, Any]) -> Leurre:
    return Leurre(
        ressource=str(declaration["ressource"]),
        chemin=str(declaration["chemin"]),
        marqueur=str(declaration["marqueur"]),
        sensible=bool(declaration["sensible"]),
    )


def est_leurre(chemin_ou_ressource: str, leurres: Iterable[Leurre] | None = None) -> Leurre | None:
    """Return the decoy a path or resource points at, if any."""
    catalogue = tuple(leurres) if leurres is not None else leurres_par_defaut()
    cible = chemin_ou_ressource.strip().rstrip("/")
    for leurre in catalogue:
        if cible in (leurre.ressource, leurre.chemin):
            return leurre
        if cible.endswith(leurre.chemin) or cible.endswith(leurre.ressource.split("://", 1)[-1]):
            return leurre
    return None


def sensibles(leurres: Iterable[Leurre] | None = None) -> tuple[Leurre, ...]:
    catalogue = tuple(leurres) if leurres is not None else leurres_par_defaut()
    return tuple(leurre for leurre in catalogue if leurre.sensible)


def ressource_depuis_chemin(leurre: Leurre) -> str:
    """`config-ombre/app.conf` -> `s3://config-ombre/app.conf`."""
    if leurre.ressource.startswith("s3://"):
        return leurre.ressource
    return f"s3://{leurre.chemin}"
