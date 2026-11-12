"""Sas — identifiers and fingerprints (lot 0, frozen).

Identifiers are opaque strings and are never parsed. They are deterministic
when a seed is supplied (so a replayed campaign produces the same report) and
unique otherwise.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

PREFIXES: tuple[str, ...] = (
    "tenant",
    "editeur",
    "agent",
    "man",
    "camp",
    "sess",
    "appel",
    "tent",
    "comp",
    "ecart",
    "env",
    "drv",
    "att",
    "scn",
)


_HORLOGE_FIXE: datetime | None = None


def figer_horloge(instant: datetime | None) -> None:
    """Pin the clock, or release it with `None`.

    ENF-11 requires that the same scenarios and the same seed give the same
    conclusions. The conclusions always did; the **fingerprints** did not,
    because the wall clock leaked into the journal timestamps and therefore into
    the chain hash. Pinning the clock makes a whole campaign byte-for-byte
    reproducible, which is what lets the public portal dataset be regenerated and
    diffed in CI — a judge can re-run the generator and get identical bytes.

    Production never pins it. Tests and the dataset generator do.
    """
    global _HORLOGE_FIXE
    _HORLOGE_FIXE = instant


def maintenant() -> datetime:
    """The single clock entry point: timezone-aware UTC."""
    return _HORLOGE_FIXE or datetime.now(UTC)


def nouveau(prefixe: str, graine: int | None = None, cle: str = "") -> str:
    """Build an identifier. `graine` + `cle` make it reproducible."""
    if prefixe not in PREFIXES:
        raise ValueError(f"préfixe inconnu: {prefixe!r} (attendu: {', '.join(PREFIXES)})")
    if graine is None:
        return f"{prefixe}-{uuid.uuid4().hex[:16]}"
    empreinte = hashlib.sha256(f"{graine}:{cle}:{prefixe}".encode()).hexdigest()
    return f"{prefixe}-{empreinte[:16]}"


def empreinte(valeur: Any) -> str:
    """Canonical SHA-256 of any JSON-able value: `sha256:<hex>`.

    Used for the manifest fingerprint, the journal chain and the behavioural
    signature. Canonical means: sorted keys, no insignificant whitespace,
    numbers as strings when they are `Decimal`, datetimes in ISO-8601 UTC.
    """
    return f"sha256:{hashlib.sha256(canonique(valeur).encode('utf-8')).hexdigest()}"


def canonique(valeur: Any) -> str:
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), default=_serialise, ensure_ascii=False)


def _serialise(valeur: Any) -> Any:
    if isinstance(valeur, Decimal):
        return f"dec:{valeur}"
    if isinstance(valeur, datetime):
        return valeur.astimezone(UTC).isoformat()
    if isinstance(valeur, (set, frozenset, tuple)):
        return sorted(_serialise(v) if not isinstance(v, str) else v for v in valeur)
    if isinstance(valeur, bytes):
        return valeur.hex()
    return str(valeur)


def tronquer(empreinte_valeur: str, caracteres: int = 12) -> str:
    """Short display form used in reports: `sha256:c4d9…`."""
    if not empreinte_valeur.startswith("sha256:"):
        return empreinte_valeur[:caracteres]
    return f"sha256:{empreinte_valeur[7 : 7 + caracteres]}…"


def chainer(precedente: str, entree: Any) -> str:
    """Next link of the journal chain (spec §17.1)."""
    return empreinte({"prec": precedente, "entree": canonique(entree)})


def numero_attestation(date: datetime, rang: int) -> str:
    """`SAS-ATT-2026-0312` — year then the sequential number of the day."""
    return f"SAS-ATT-{date.astimezone(UTC):%Y}-{rang:04d}"
