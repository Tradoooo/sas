"""The evaluation bench guests (spec annexe F.3).

Twenty faulty guests with one known fault each, twenty benign ones, and the
calibrated guest in `calibre.py` — 41 in all.

**The table is generated, not hand-written.** Annexe F.3 makes the
reproducibility of the bench an acceptance requirement, so `FAUTIFS` and
`BENINS` live in `_tableau.py`, emitted by `eval/genere-agents.mjs`. Edit the
generator, regenerate, commit both. `tests/unit/banc/test_generateur.py` fails
if the committed table is not what the generator produces.

This module is the public surface: the bench and the tests import from here.
"""

from __future__ import annotations

from collections.abc import Sequence

from eval.agents._tableau import BENINS, FAUTIFS
from eval.agents.modele import (
    DECLARATION,
    DOCUMENTATION,
    IDENTIFIANTS,
    LEURRE_CONFIG,
    LEURRE_SENSIBLE,
    NON_DECLAREE,
    SUIVI,
    TICKETS,
    AgentBanc,
    Etape,
    lire,
    nominatif,
    repeter,
    sortie,
)

__all__ = [
    "BENINS",
    "DECLARATION",
    "DOCUMENTATION",
    "FAUTIFS",
    "IDENTIFIANTS",
    "LEURRE_CONFIG",
    "LEURRE_SENSIBLE",
    "NON_DECLAREE",
    "SUIVI",
    "TICKETS",
    "AgentBanc",
    "Etape",
    "benins",
    "compter",
    "fautifs",
    "lire",
    "nominatif",
    "par_nom",
    "repeter",
    "sortie",
    "tous",
]


def tous() -> tuple[AgentBanc, ...]:
    return FAUTIFS + BENINS


def fautifs() -> Sequence[AgentBanc]:
    return FAUTIFS


def benins() -> Sequence[AgentBanc]:
    return BENINS


def par_nom(nom: str) -> AgentBanc | None:
    return next((a for a in tous() if a.nom == nom), None)


def compter() -> dict[str, int]:
    """The bench census. The calibrated guest is counted separately: it replays
    an existing guest at a known probability rather than adding a behaviour."""
    return {
        "fautifs": len(FAUTIFS),
        "benins": len(BENINS),
        "total": len(FAUTIFS) + len(BENINS),
        "avec_calibre": len(FAUTIFS) + len(BENINS) + 1,
        "avec_composition_attendue": sum(1 for a in FAUTIFS if a.composition_attendue),
    }
