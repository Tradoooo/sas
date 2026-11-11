"""Sas — deterministic randomness (lot 0, frozen).

Everything random in the product goes through here: shadow data generation,
guest-agent dispersion, model fakes. Two campaigns with the same seed produce
the same conclusions (ENF-11, R15). Calling `random` directly is a defect.
"""

from __future__ import annotations

import hashlib
import random
from collections.abc import Iterable, Sequence
from typing import Any

GRAPPE_DEFAUT = 0


def genereur(graine: int, flux: str = "") -> random.Random:
    """A `random.Random` seeded deterministically from (seed, stream name).

    The stream name keeps two consumers of the same seed independent: the
    shadow generator and a guest agent never draw from the same sequence.
    """
    digest = hashlib.sha256(f"{graine}:{flux}".encode()).digest()
    return random.Random(int.from_bytes(digest[:8], "big"))


def melange(graine: int, flux: str, elements: Sequence[Any]) -> list[Any]:
    copie = list(elements)
    genereur(graine, flux).shuffle(copie)
    return copie


def choix(graine: int, flux: str, elements: Sequence[Any]) -> Any:
    if not elements:
        raise ValueError("choix sur une séquence vide")
    return genereur(graine, flux).choice(list(elements))


def probabilite(graine: int, flux: str) -> float:
    """A stable draw in [0, 1) for a given (seed, stream)."""
    return genereur(graine, flux).random()


def echantillon(graine: int, flux: str, elements: Sequence[Any], k: int) -> list[Any]:
    if k >= len(elements):
        return list(elements)
    return genereur(graine, flux).sample(list(elements), k)


def entier(graine: int, flux: str, borne_inferieure: int, borne_superieure: int) -> int:
    return genereur(graine, flux).randint(borne_inferieure, borne_superieure)


def graine_derivee(graine: int, *etiquettes: Any) -> int:
    """Derive a sub-seed so a replay can have its own stream without the
    caller having to invent one."""
    cle = "|".join(str(e) for e in (graine, *etiquettes))
    return int.from_bytes(hashlib.sha256(cle.encode("utf-8")).digest()[:8], "big")


def disperser(graine: int, flux: str, valeurs: Iterable[Any]) -> list[Any]:
    """Shuffle a stable iterable into a reproducible random order."""
    return melange(graine, flux, list(valeurs))
