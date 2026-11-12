"""The audit export: one verifiable archive for an auditor or an insurer.

§17.3 asks for a report that can leave the platform; an auditor wants more than
a PDF — they want the evidence. This module produces a single archive holding the
chained journal, the attestation, the report and a manifest of fingerprints, then
seals the manifest with a keyed HMAC.

**What it does not do, stated plainly:** it does not encrypt. The standard
library has no authenticated cipher, and home-made encryption is worse than none.
The archive is therefore built to be *sealed* — every member's hash is in the
manifest, and the manifest is signed — so it can be handed over, verified, and
then encrypted by whoever holds it, with KMS in a real deployment (lot 17).
Confidentiality is delegated; integrity is ours.

Every member is verified on read: `verifier()` re-hashes each file and checks
the seal, and says exactly which member diverges if one does.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import tarfile
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sas.identifiants import canonique, maintenant

ALGORITHME = "hmac-sha256"
MEMBRE_JOURNAL = "journal.jsonl"
MEMBRE_ATTESTATION = "attestation.txt"
MEMBRE_RAPPORT = "rapport.md"
MEMBRE_MANIFESTE = "MANIFEST.json"
MEMBRE_SIGNATURE = "MANIFEST.sig"
MEMBRES = (MEMBRE_JOURNAL, MEMBRE_ATTESTATION, MEMBRE_RAPPORT)


@dataclass(frozen=True, slots=True)
class ArchiveAudit:
    """The sealed archive, and what it holds."""

    nom: str
    contenu: bytes
    manifest: dict[str, Any]
    signature: str
    horodatage: datetime

    def resume(self) -> dict[str, Any]:
        return {
            "nom": self.nom,
            "octets": len(self.contenu),
            "membres": list(self.manifest.get("membres", {})),
            "entrees_journal": self.manifest.get("entrees_journal", 0),
            "horodatage": self.horodatage.isoformat(),
            "signature": self.signature,
            "chiffre": False,
        }


def exporter(
    *,
    journal: str,
    attestation: str,
    rapport: str,
    cle: str,
    nom: str = "audit-sas.tar.gz",
    horodatage: datetime | None = None,
    contexte: dict[str, Any] | None = None,
) -> ArchiveAudit:
    """Build the sealed archive from the three documents.

    `journal` is JSON Lines — one entry per line, the format the export of the
    journal already produces (§17.1).
    """
    if not cle:
        raise ValueError("une clé de scellement est exigée pour sceller l'archive")
    instant = horodatage or maintenant()
    membres = {
        MEMBRE_JOURNAL: journal,
        MEMBRE_ATTESTATION: attestation,
        MEMBRE_RAPPORT: rapport,
    }
    manifeste = _manifeste(membres, journal, instant, contexte)
    corps = canonique(manifeste)
    signature = f"{ALGORITHME}:{hmac.new(cle.encode(), corps.encode(), hashlib.sha256).hexdigest()}"

    tampon = io.BytesIO()
    with tarfile.open(fileobj=tampon, mode="w:gz") as archive:
        for nom_membre, texte in membres.items():
            _ecrire(archive, nom_membre, texte.encode("utf-8"))
        _ecrire(
            archive,
            MEMBRE_MANIFESTE,
            (json.dumps(manifeste, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(),
        )
        _ecrire(archive, MEMBRE_SIGNATURE, (signature + "\n").encode())
    return ArchiveAudit(
        nom=nom,
        contenu=tampon.getvalue(),
        manifest=manifeste,
        signature=signature,
        horodatage=instant,
    )


def _manifeste(
    membres: dict[str, str], journal: str, instant: datetime, contexte: dict[str, Any] | None
) -> dict[str, Any]:
    """The manifest: one fingerprint per member, and the alert about what this
    archive is not."""
    return {
        "cree_le": instant.isoformat(),
        "membres": {
            nom_membre: hashlib.sha256(texte.encode("utf-8")).hexdigest()
            for nom_membre, texte in membres.items()
        },
        "entrees_journal": sum(1 for ligne in journal.splitlines() if ligne.strip()),
        "contexte": contexte or {},
        "alerte": (
            "Archive scellée et NON chiffrée : l'intégrité est prouvée par les "
            "empreintes et le sceau, la confidentialité est déléguée à celui qui "
            "la reçoit (KMS en déploiement réel)."
        ),
    }


def _ecrire(archive: tarfile.TarFile, nom: str, contenu: bytes) -> None:
    info = tarfile.TarInfo(name=nom)
    info.size = len(contenu)
    info.mtime = 0  # deterministic archive: the same evidence gives the same bytes
    archive.addfile(info, io.BytesIO(contenu))


def verifier(archive: ArchiveAudit, cle: str) -> tuple[bool, str]:
    """Re-hash every member and check the seal. Says which member diverges."""
    lus = _relire(archive.contenu)
    for nom_membre, attendu in archive.manifest.get("membres", {}).items():
        contenu = lus.get(nom_membre)
        if contenu is None:
            return False, f"membre absent : {nom_membre}"
        calcule = hashlib.sha256(contenu).hexdigest()
        if calcule != attendu:
            return False, f"membre altéré : {nom_membre}"
    corps = canonique(archive.manifest)
    signature = f"{ALGORITHME}:{hmac.new(cle.encode(), corps.encode(), hashlib.sha256).hexdigest()}"
    if not hmac.compare_digest(signature.encode(), archive.signature.encode()):
        return False, "le sceau du manifeste ne correspond pas"
    return True, f"archive vérifiée : {len(lus)} membres, sceau conforme"


def _relire(contenu: bytes) -> dict[str, bytes]:
    membres: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(contenu), mode="r:gz") as archive:
        for info in archive.getmembers():
            if not info.isfile():
                continue
            extract = archive.extractfile(info)
            if extract is not None:
                membres[info.name] = extract.read()
    return membres


def lire_membre(archive: ArchiveAudit, nom: str) -> str:
    """The text of one member, for a human who opens the archive."""
    contenu = _relire(archive.contenu).get(nom)
    if contenu is None:
        raise KeyError(f"membre absent : {nom}")
    return contenu.decode("utf-8")
