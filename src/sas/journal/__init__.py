"""The journal: complete, chained, immutable, exportable (spec §17.1).

Lot 5 owns `chaine.py` (the chain itself). Lot 7 adds `export.py` and `audit.py`
on top of it and must not re-implement the chaining.
"""

from __future__ import annotations

from sas.journal.chaine import JournalChaine, fusionner, verifier_sequence

__all__ = ["JournalChaine", "fusionner", "verifier_sequence"]
