"""`sas attestation` — print or export the attestation of the last campaign.

The CLI has no persistent store (a campaign lives in memory), so this command
runs a campaign with the parameters given, then renders its attestation: to the
terminal, as an HTML print view, or as a one-page PDF. That makes `make attest`
reproduce a real deliverable rather than reading a fixture.
"""

from __future__ import annotations

import sys
from pathlib import Path

from sas.cli_partage import charger_contexte, invite, lancer
from sas.rapports import impression
from sas.types import Langue


def executer_attestation(
    *,
    agent: str = "demo-conforme",
    scenarios: tuple[str, ...] = ("S1", "S4"),
    rejeux: int = 2,
    graine: int = 7,
    langue: str = "fr",
    sortie: str = "",
    fmt: str = "texte",
) -> int:
    contexte = charger_contexte(scenarios)
    dossier = lancer(agent=invite(agent), contexte=contexte, rejeux=rejeux, graine=graine)
    if dossier.attestation is None:
        print(
            "Aucune attestation : cet agent est déclaré NON MESURABLE (ENF-17). "
            "Un agent qui ne passe pas par la passerelle n'est jamais « conforme ».",
            file=sys.stderr,
        )
        return 3

    code_langue = Langue.EN if langue.lower().startswith("en") else Langue.FR
    if fmt == "pdf":
        return _ecrire_pdf(dossier, code_langue, sortie)
    if fmt == "html":
        return _ecrire_html(dossier, code_langue, sortie)
    print(impression.texte_attestation(dossier.attestation, code_langue))
    return 0


def _ecrire_pdf(dossier: object, langue: Langue, sortie: str) -> int:
    document = impression.pdf(dossier.attestation, langue)  # type: ignore[attr-defined]
    chemin = Path(sortie) if sortie else Path(document.nom)
    chemin.write_bytes(document.contenu)
    print(f"écrit {chemin} ({len(document.contenu)} octets, {document.pages} page)")
    print(
        "Scellement : HMAC-SHA256 à clé partagée — pas une signature électronique "
        "eIDAS. Un déploiement réel signe via KMS (lot 17)."
    )
    return 0


def _ecrire_html(dossier: object, langue: Langue, sortie: str) -> int:
    attestation = dossier.attestation  # type: ignore[attr-defined]
    chemin = Path(sortie) if sortie else Path(f"{attestation.numero}.html")
    chemin.write_text(impression.html_impression(attestation, langue), encoding="utf-8")
    print(f"écrit {chemin} — ouvrir puis imprimer pour obtenir un PDF")
    return 0
