"""Sealing a manifest: editor signature then sponsor validation (EF-03).

**Honesty note.** This is a keyed-hash seal over the canonical fingerprint, not
a PKI signature: it proves that whoever holds the shared key approved exactly
this document, and it detects any later edit. It is enough for the airlock's own
chain of custody and for the demo. A real deployment replaces it with AWS KMS
asymmetric signing (lot 17 does the swap behind the same four functions), and
the report never claims more than what is implemented.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import replace
from datetime import datetime

from sas.manifeste.versions import avec_empreinte, empreinte_manifeste
from sas.types import Manifeste, Mode, SignatureEditeur, StatutManifeste, ValidationClient

ALGORITHME = "hmac-sha256"


def sceller(manifeste: Manifeste, cle: str) -> str:
    """Seal of the canonical fingerprint: `hmac-sha256:<hex>`."""
    if not cle:
        raise ValueError("une clé de scellement vide ne scelle rien")
    cible = empreinte_manifeste(manifeste)
    digest = hmac.new(cle.encode("utf-8"), cible.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{ALGORITHME}:{digest}"


def signer_editeur(
    manifeste: Manifeste,
    *,
    signataire: str,
    qualite: str,
    date: datetime,
    cle: str,
) -> Manifeste:
    """The vendor signs: status becomes SIGNE_EDITEUR, the seal is recorded."""
    if not signataire.strip() or not qualite.strip():
        raise ValueError("le signataire et sa qualité sont obligatoires")
    if not cle:
        raise ValueError("une clé de scellement est exigée pour signer")
    scelle = avec_empreinte(manifeste)
    signature = SignatureEditeur(
        signataire=signataire,
        qualite=qualite,
        date=date,
        empreinte_document=empreinte_manifeste(scelle),
    )
    return replace(scelle, signature=signature, statut=StatutManifeste.SIGNE_EDITEUR)


def valider_commanditaire(
    manifeste: Manifeste,
    *,
    commanditaire: str,
    date: datetime,
    perimetre_approuve: str,
    mode: Mode = Mode.OMBRE,
    homologation_precedente: bool = False,
    cle: str = "",
) -> Manifeste:
    """The sponsor validates the perimeter: status becomes VALIDE.

    A first homologation is authorised in shadow mode only (§10.1). The
    observed mode requires a previous, attested shadow homologation, which the
    caller must state explicitly: nothing is ever produced on trust.
    """
    if manifeste.signature is None:
        raise ValueError("le manifeste doit être signé par l'éditeur avant validation")
    if not commanditaire.strip():
        raise ValueError("le commanditaire est obligatoire")
    if not cle:
        raise ValueError("une clé de scellement est exigée pour valider")
    if mode is Mode.OBSERVE and not homologation_precedente:
        raise ValueError("le mode Observé exige une première homologation en Ombre attestée (§10.1)")
    validation = ValidationClient(
        commanditaire=commanditaire,
        date=date,
        perimetre_approuve=perimetre_approuve,
        mode_autorise=mode,
    )
    return replace(manifeste, validation_client=validation, statut=StatutManifeste.VALIDE)


def verifier(manifeste: Manifeste, cle: str = "", sceau: str = "") -> tuple[bool, str]:
    """Re-check the document fingerprint and, when a seal is supplied, the seal.

    A manifest edited after signature does not verify — that is test R3. The
    seal is not stored inside the manifest (the frozen types have no field for
    it): the store keeps it next to the manifest, and it is passed here.
    """
    if manifeste.signature is None:
        return False, "manifeste non signé"
    attendue = manifeste.signature.empreinte_document
    calculee = empreinte_manifeste(manifeste)
    if attendue and attendue != calculee:
        return False, (
            f"le document signé portait l'empreinte {attendue[:19]}…, "
            f"le document courant porte {calculee[:19]}…"
        )
    if manifeste.empreinte and manifeste.empreinte != calculee:
        return False, "l'empreinte enregistrée ne correspond plus au contenu"
    if manifeste.statut is StatutManifeste.BROUILLON:
        return False, "manifeste encore au statut brouillon"
    if sceau and cle and sceller(manifeste, cle) != sceau:
        return False, "le sceau ne correspond pas à la clé fournie"
    return True, "signature vérifiée"
