"""The export format of the journal (lot 7): a versioned envelope around the entries.

A third party — an auditor, an insurer, another agent — must be able to check
the integrity of an exported journal **without running Sas**. That is only
possible if the export says, *in data*, how its fingerprints are computed: this
module writes that description next to the entries.

The format (`sas-journal-export/1`) is published in `docs/FORMAT-JOURNAL.en.md`
(and `.fr.md`):

* line 1 — the **envelope**: one JSON object, canonical form, carrying the
  format version, the export date, the algorithm, and what the file must
  contain (the sessions, the entry count, the fingerprint of the whole file);
* lines 2..n — the **entries**, JSON Lines, in the journal's order, verbatim.

The auditor that implements this format is `sas.journal.audit`. It shares no
code with the producer on purpose: an audit that reuses the producer's own
fingerprinting proves only that the producer is consistent with itself.

The chain itself is **not** re-implemented here — `JournalChaine` remains the
only thing that computes fingerprints. This module only describes them, and
carries them.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sas.identifiants import canonique, maintenant
from sas.journal.chaine import JournalChaine
from sas.types import EntreeJournal

FORMAT_VERSION = "sas-journal-export/1"

#: The algorithm, described as data. A third party reads it and recomputes: it
#: is not documentation hidden in the prose, it is a field of the export.
ALGORITHME: dict[str, Any] = {
    "empreinte": "sha256",
    "prefixe": "sha256:",
    "canonique": {
        "cles_triees": True,
        "separateurs": [",", ":"],
        "ensure_ascii": False,
        "encodage": "utf-8",
    },
    "projection": {
        "champs_exclus": ["empreinte", "empreinte_prec"],
        "portee": "l'entrée entière moins les deux champs de chaîne",
    },
    "liaison": {
        "graine": "",
        "portee": "une chaîne par session ; la première entrée d'une session repart de la graine",
        "forme": (
            "empreinte = prefixe + sha256(canonique("
            "{entree: projection canonique, prec: empreinte précédente}))"
        ),
    },
    "empreinte_export": {
        "portee": "toutes les entrées du fichier, dans l'ordre du fichier",
        "forme": "empreinte_export = prefixe + sha256(canonique([empreinte de chaque entrée]))",
    },
}


def exporter(
    journal: JournalChaine,
    *,
    session_id: str | None = None,
    exporte_le: datetime | None = None,
) -> str:
    """The export as text: the envelope on the first line, the entries below.

    The entries are the ones the chain already produced, byte for byte: an
    export never re-writes an entry, it only carries it. Two exports of the
    same journal give the same bytes, down to the export date.
    """
    entete = canonique(enveloppe(journal, session_id=session_id, exporte_le=exporte_le))
    return entete + "\n" + journal.exporter(session_id)


def enveloppe(
    journal: JournalChaine,
    *,
    session_id: str | None = None,
    exporte_le: datetime | None = None,
) -> dict[str, Any]:
    """The envelope alone: what a third party needs, the algorithm included."""
    sessions = [
        _session(journal, identifiant)
        for identifiant in journal.sessions()
        if session_id is None or identifiant == session_id
    ]
    entrees = journal.entrees(session_id)
    return {
        "format_version": FORMAT_VERSION,
        "exporte_le": (exporte_le or maintenant()).isoformat(),
        "producteur": "sas",
        "algorithme": ALGORITHME,
        "sessions": sessions,
        "entrees": len(entrees),
        "empreinte_export": _empreinte_export(entrees),
    }


def _session(journal: JournalChaine, identifiant: str) -> dict[str, Any]:
    """What the envelope says about one session: size, tip, integrity state."""
    etat = journal.verifier(identifiant)
    return {
        "session_id": identifiant,
        "entrees": len(journal.entrees(identifiant)),
        "empreinte_finale": journal.derniere_empreinte(identifiant),
        "integrite": etat.integre,
        "premiere_rupture": etat.premiere_rupture,
    }


def _empreinte_export(entrees: Sequence[EntreeJournal]) -> str:
    """The fingerprint of the whole file: the ordered list of entry fingerprints.

    It is what makes the export *complete*: a missing, added or reordered
    entry changes this value, and the auditor compares it with the declared one.
    """
    empreintes = [entree.empreinte for entree in entrees]
    return "sha256:" + hashlib.sha256(canonique(empreintes).encode("utf-8")).hexdigest()
