"""Lot 7 — the journal export and the audit a third party can run.

The fixtures build a journal that is **healthy**: the chain is intact, the
entries are deterministic, and nothing depends on the wall clock. A broken
journal is *derived* from this one by editing the exported text — the same way
an attacker would, byte for byte — never by rebuilding the chain.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sas.journal.chaine import JournalChaine
from sas.types import Decision, EntreeJournal

HORODATAGE = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)

#: The export date used by the tests: pinned, so the bytes are stable.
INSTANT = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def entree(
    index: int,
    *,
    session_id: str = "sess-a",
    decision: Decision = Decision.AUTORISE,
    outil: str = "lire_ticket",
) -> EntreeJournal:
    """One journal entry, deterministic down to its timestamp."""
    return EntreeJournal(
        id=f"appel-{index}",
        tenant_id="tenant-a",
        session_id=session_id,
        campagne_id="camp-1",
        agent_id="agent-1",
        agent_version="3.4.1",
        scenario_id="S1",
        numero_rejeu=1,
        parent_id=None,
        outil=outil,
        parametres={"id": f"T-{index:04d}"},
        decision=decision,
        regle_appliquee="manifeste:autorise",
        resultat={"ok": True, "lignes": index},
        horodatage=HORODATAGE,
        latence_ms=3.5,
        jetons=460,
        ressources=("client-tickets/entree",),
    )


def journal_sain(nb_entrees: int = 3, *, sessions: tuple[str, ...] = ("sess-a",)) -> JournalChaine:
    """A healthy journal: `nb_entrees` entries spread over `sessions`."""
    chaine = JournalChaine()
    for index in range(nb_entrees):
        session = sessions[index % len(sessions)]
        chaine.ajouter(
            entree(
                index,
                session_id=session,
                decision=Decision.REFUSE if index == nb_entrees - 1 else Decision.AUTORISE,
            )
        )
    return chaine


def lignes_export(texte: str) -> list[str]:
    """The export split into its lines, blanks removed."""
    return [ligne for ligne in texte.splitlines() if ligne.strip()]


def modifier_entree(texte: str, index: int, **champs: Any) -> str:
    """Rewrite one entry of an export, the way a text editor would.

    The rest of the file is left untouched — byte for byte — so the audit
    sees exactly what an attacker would leave behind.
    """
    lignes = lignes_export(texte)
    entree_objet = json.loads(lignes[index + 1])
    entree_objet.update(champs)
    lignes[index + 1] = json.dumps(entree_objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "\n".join(lignes) + "\n"


def supprimer_entree(texte: str, index: int) -> str:
    """Delete one entry line from an export."""
    lignes = lignes_export(texte)
    del lignes[index + 1]
    return "\n".join(lignes) + "\n"
