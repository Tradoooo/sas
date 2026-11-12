"""The attestation as a printable, signable artefact (spec §17.2, EF-41).

Two outputs from one source:

* an HTML fragment for the portal's print view — the browser's own print dialog
  produces the PDF, so nothing is invented about signatures;
* a **one-page PDF written here**, in pure standard library, so `sas attestation
  --pdf` produces a real file with no dependency and no network. It is a text
  PDF: it carries the document, not a cryptographic signature. Saying so is part
  of the honesty of the deliverable — the seal lives in `sas.manifeste.signature`
  and a real deployment swaps it for KMS (lot 17).

The attestation is deliberately poor in details (§17.2): this module renders
what `sas.rapports.attestation` already decided to expose, and adds nothing.
"""

from __future__ import annotations

import zlib
from collections.abc import Sequence
from dataclasses import dataclass

from sas.rapports import attestation as module_attestation
from sas.types import Attestation, Langue

ENCODAGE = "cp1252"  # WinAnsiEncoding: covers French accents, « », and em dashes
MARGE_GAUCHE = 56
MARGE_HAUTE = 760
INTERLIGNE = 13
TAILLE_POLICE = 9


@dataclass(frozen=True, slots=True)
class Document:
    """A rendered document: bytes for a file, text for a diff or a test."""

    nom: str
    contenu: bytes
    texte: str
    pages: int
    format: str
    lignes_rendues: int = 0


def texte_attestation(attestation_objet: Attestation, langue: Langue = Langue.FR) -> str:
    """One source: the text the report module already produces."""
    return module_attestation.texte(attestation_objet, "fr" if langue is Langue.FR else "en")


def html_impression(attestation_objet: Attestation, langue: Langue = Langue.FR) -> str:
    """A self-contained print view. No script, no external resource."""
    texte = texte_attestation(attestation_objet, langue)
    echappe = texte.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    titre = "Attestation d'homologation" if langue is Langue.FR else "Homologation attestation"
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{"fr" if langue is Langue.FR else "en"}"><head><meta charset="utf-8">'
        f"<title>{titre} {attestation_objet.numero}</title>"
        "<style>"
        "@page { size: A4; margin: 18mm; }"
        "body { font: 10.5pt/1.45 ui-monospace, Menlo, Consolas, monospace; color: #000; }"
        "pre { white-space: pre-wrap; word-break: break-word; margin: 0; }"
        ".pied { margin-top: 14mm; font: 8.5pt/1.4 sans-serif; color: #444; }"
        "@media print { .pied { position: fixed; bottom: 0; } }"
        "</style></head><body>"
        f"<pre>{echappe}</pre>"
        '<p class="pied">Document généré par Sas. Le scellement de ce document est un sceau '
        "à clé partagée (HMAC-SHA256) ; un déploiement réel le remplace par une signature "
        "KMS. Ce fichier n'est pas une signature électronique au sens du règlement eIDAS.</p>"
        "</body></html>\n"
    )


def pdf(attestation_objet: Attestation, langue: Langue = Langue.FR) -> Document:
    """Render the attestation as a one-page PDF, stdlib only."""
    texte = texte_attestation(attestation_objet, langue)
    lignes = _tronquer_par_page(texte.splitlines())[0]
    return Document(
        nom=f"{attestation_objet.numero}.pdf",
        contenu=_construire(lignes),
        texte=texte,
        pages=1,
        format="pdf",
        lignes_rendues=len(lignes),
    )


def _tronquer_par_page(lignes: Sequence[str]) -> tuple[list[str], ...]:
    """The attestation is one page by design (§17.2); anything past the fold is
    dropped rather than silently spilling onto a second page."""
    capacite = int((MARGE_HAUTE - 40) // INTERLIGNE)
    return (list(lignes[:capacite]),)


def _construire(lignes: Sequence[str]) -> bytes:
    """Assemble a minimal PDF 1.4: catalog, one page, Helvetica, one content stream."""
    flux = _flux_contenu(lignes)
    comprime = zlib.compress(flux.encode(ENCODAGE, "replace"))
    objets = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources "
        b"<< /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(comprime)} /Filter /FlateDecode >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, objet in enumerate(objets, start=1):
        offsets.append(len(sortie))
        sortie += f"{index} 0 obj\n".encode("ascii") + objet + b"\nendobj\n"
    offsets.append(len(sortie))
    sortie += b"6 0 obj\n<< /Length " + str(len(comprime)).encode("ascii") + b" >>\nstream\n"
    sortie += comprime + b"\nendstream\nendobj\n"
    debut_xref = len(sortie)
    sortie += "xref\n0 7\n0000000000 65535 f \n".encode("ascii")
    for decalage in offsets[1:]:
        sortie += f"{decalage:010d} 00000 n \n".encode("ascii")
    sortie += f"trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{debut_xref}\n%%EOF\n".encode("ascii")
    return bytes(sortie)


def _flux_contenu(lignes: Sequence[str]) -> str:
    """The PDF content stream: fixed-pitch text, one Tj per line."""
    commandes = [
        "BT",
        f"/F1 {TAILLE_POLICE} Tf",
        f"{INTERLIGNE} TL",
        f"1 0 0 1 {MARGE_GAUCHE} {MARGE_HAUTE} Tm",
    ]
    for ligne in lignes:
        commandes.append(f"({_echapper(ligne)}) Tj T*")
    commandes.append("ET")
    return "\n".join(commandes)


def _echapper(texte: str) -> str:
    """Escape the PDF string delimiters, then drop what WinAnsi cannot encode."""
    return (
        texte.replace("\\", r"\\")
        .replace("(", r"\(")
        .replace(")", r"\)")
        .encode(ENCODAGE, "replace")
        .decode(ENCODAGE)
    )


def verifiable(contenu: bytes) -> tuple[bool, str]:
    """A minimal structural check, so a test can assert the file is a PDF and not
    a renamed text blob. Not a full parser: it checks the header, the trailer and
    that every declared object is present."""
    if not contenu.startswith(b"%PDF-1.4"):
        return False, "en-tête absent"
    if b"%%EOF" not in contenu[-32:]:
        return False, "marqueur de fin absent"
    if b"startxref" not in contenu:
        return False, "table de références croisées absente"
    for index in range(1, 7):
        if f"{index} 0 obj".encode("ascii") not in contenu:
            return False, f"objet {index} absent"
    return True, "structure valide"
