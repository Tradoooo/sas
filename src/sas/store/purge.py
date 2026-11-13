"""A retention purge that PROVES what it removed (ENF-12).

The specification asks for a purge that is "effective and provable". Effective:
the entries are gone. Provable: a signed record says **which** entries were
removed, when, by whom, and what the journal's chain root was before and after —
so a third party can check that the purge removed exactly the expired entries and
nothing else.

The seal is a keyed HMAC, the same honesty as the manifest seal: it proves the
record was produced by the holder of the key and has not been altered. It is not
an eIDAS signature; a real deployment replaces it with KMS (lot 17).

**Confidentiality is not claimed here.** The attestation names the *identifiers*
of what was purged and their fingerprints — not their content. A purge record
that quoted the data it deleted would leak the very thing it was supposed to
remove.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sas.identifiants import canonique, maintenant
from sas.types import Acces, EtatChaine

ALGORITHME = "hmac-sha256"


@dataclass(frozen=True, slots=True)
class LignePurge:
    """One purged item: its identifier and its fingerprint, never its content."""

    identifiant: str
    empreinte: str
    age_jours: int


@dataclass(frozen=True, slots=True)
class AttestationPurge:
    """The proof that a retention purge happened, and what it removed."""

    id: str
    horodatage: datetime
    tenant_id: str
    jours_retenus: int
    purges: tuple[LignePurge, ...]
    racine_avant: str
    racine_apres: str
    signature: str
    signataire: str
    nombre_total: int
    tables: tuple[str, ...] = ()

    @property
    def nombre_purge(self) -> int:
        return len(self.purges)

    def resume(self) -> dict[str, Any]:
        """A JSON-able summary: what was purged, never what it contained."""
        return {
            "id": self.id,
            "horodatage": self.horodatage.isoformat(),
            "tenant_id": self.tenant_id,
            "jours_retenus": self.jours_retenus,
            "nombre_purge": self.nombre_purge,
            "racine_avant": self.racine_avant,
            "racine_apres": self.racine_apres,
            "signature": self.signature,
            "signataire": self.signataire,
            "tables": list(self.tables),
        }


def purger_attestee(
    depot: Any,
    jours: int,
    *,
    signataire: str,
    cle: str,
    instant: datetime | None = None,
) -> AttestationPurge:
    """Purge what expired, and return the proof.

    `depot` is anything exposing `purger(jours) -> int` and its journal entries;
    the concrete store is `sas.store.local.DepotLocal`. The dependency is
    deliberate: the attestation logic must not depend on the storage engine.
    """
    if not signataire.strip():
        raise ValueError("une purge sans auteur n'est pas une purge prouvée")
    if not cle:
        raise ValueError("une clé de scellement est exigée pour attester la purge")
    instant = instant or maintenant()
    avant = _racine(depot)
    candidats = _candidats(depot, jours, instant)
    nombre = depot.purger(jours)
    apres = _racine(depot)
    purges = tuple(
        LignePurge(
            identifiant=str(identifiant),
            empreinte=_empreinte(contenu),
            age_jours=_age(contenu, instant),
        )
        for identifiant, contenu in candidats
    )
    corps = _corps(avant, apres, purges, jours, depot, instant)
    return AttestationPurge(
        id="purge-" + hashlib.sha256(canonique(corps).encode()).hexdigest()[:16],
        horodatage=instant,
        tenant_id=getattr(depot, "tenant_id", ""),
        jours_retenus=jours,
        purges=purges,
        racine_avant=avant,
        racine_apres=apres,
        signature=_sceller(corps, cle),
        signataire=signataire,
        nombre_total=nombre,
        tables=("journal", "sessions", "acces"),
    )


def _corps(
    avant: str,
    apres: str,
    purges: tuple[LignePurge, ...],
    jours: int,
    depot: Any,
    instant: datetime,
) -> dict[str, Any]:
    """What the seal covers: the chain roots, the purged identifiers, the
    retention and the moment."""
    return {
        "avant": avant,
        "apres": apres,
        "purges": [(ligne.identifiant, ligne.empreinte) for ligne in purges],
        "jours": jours,
        "tenant": getattr(depot, "tenant_id", ""),
        "horodatage": instant.isoformat(),
    }


def _sceller(corps: dict[str, Any], cle: str) -> str:
    digest = hmac.new(cle.encode("utf-8"), canonique(corps).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{ALGORITHME}:{digest}"


def _candidats(depot: Any, jours: int, instant: datetime) -> list[tuple[str, Any]]:
    """What the purge is about to remove: the expired journal entries **and**
    the expired access records — one retention rule, not two."""
    seuil = instant - timedelta(days=jours)
    candidats: list[tuple[str, Any]] = []
    expirees = getattr(depot, "entrees_expirees", None)
    if expirees is not None:
        candidats += [(str(getattr(e, "id", i)), e) for i, e in enumerate(expirees(seuil))]
    acces_expires = getattr(depot, "acces_expires", None)
    if acces_expires is not None:
        candidats += [(acces.id, acces) for acces in acces_expires(seuil)]
    return candidats


def _age(contenu: Any, instant: datetime) -> int:
    horodatage = getattr(contenu, "horodatage", None)
    if isinstance(horodatage, datetime):
        return max(0, (instant - horodatage).days)
    return 0


def _empreinte(contenu: Any) -> str:
    return hashlib.sha256(canonique(_projetable(contenu)).encode("utf-8")).hexdigest()[:32]


def _projetable(contenu: Any) -> Any:
    """Only the non-content part of an entry: what it was, not what it said."""
    if isinstance(contenu, Acces):
        # An access record keeps no payload: its metadata is its whole identity.
        return contenu.resume()
    if isinstance(contenu, dict):
        return {cle: contenu.get(cle) for cle in ("id", "session_id", "horodatage", "outil")}
    return {
        "id": getattr(contenu, "id", ""),
        "session_id": getattr(contenu, "session_id", ""),
        "horodatage": str(getattr(contenu, "horodatage", "")),
        "outil": getattr(contenu, "outil", ""),
    }


def _racine(depot: Any) -> str:
    """The chain root of what remains: the fingerprint of the last entry."""
    journal = getattr(depot, "journal", None)
    if journal is None:
        return ""
    try:
        etat: EtatChaine = journal.verifier()
    except Exception:
        return ""
    return etat.empreinte_finale


def verifier(attestation: AttestationPurge, cle: str) -> tuple[bool, str]:
    """Check the seal of a purge attestation."""
    corps = {
        "avant": attestation.racine_avant,
        "apres": attestation.racine_apres,
        "purges": [(ligne.identifiant, ligne.empreinte) for ligne in attestation.purges],
        "jours": attestation.jours_retenus,
        "tenant": attestation.tenant_id,
        "horodatage": attestation.horodatage.isoformat(),
    }
    attendu = _sceller(corps, cle)
    if not hmac.compare_digest(attendu.encode(), attestation.signature.encode()):
        return False, "le sceau ne correspond pas à la clé fournie"
    return True, "sceau vérifié"
