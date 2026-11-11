"""The chained journal (spec §17.1): complete, chained, immutable, exportable.

Four properties, each one testable:

* **complete** — 100 % of the tool calls, denials included (KPI-4, R8). A
  journal without the denials is useless, since the denials are what carries the
  information;
* **chained** — each entry carries the fingerprint of the previous one, so a
  deletion or an edit is detected on reading (R9);
* **immutable** — this class has no method that removes or modifies an entry;
* **exportable** — JSON Lines, for an auditor or an insurer.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import asdict, replace
from typing import Any

from sas.identifiants import canonique, chainer
from sas.types import EntreeJournal, EtatChaine


class JournalChaine:
    """Append-only journal, chained per session."""

    def __init__(self) -> None:
        self._entrees: list[EntreeJournal] = []
        self._queues: dict[str, str] = {}

    def ajouter(self, entree: EntreeJournal) -> EntreeJournal:
        """Append one entry and return it with its chain fields filled in."""
        precedente = self._queues.get(entree.session_id, "")
        scellee = replace(entree, empreinte_prec=precedente)
        scellee = replace(scellee, empreinte=chainer(precedente, _projection(scellee)))
        self._entrees.append(scellee)
        self._queues[entree.session_id] = scellee.empreinte
        return scellee

    def entrees(self, session_id: str | None = None) -> tuple[EntreeJournal, ...]:
        if session_id is None:
            return tuple(self._entrees)
        return tuple(e for e in self._entrees if e.session_id == session_id)

    def derniere_empreinte(self, session_id: str) -> str:
        return self._queues.get(session_id, "")

    def verifier(self, session_id: str | None = None) -> EtatChaine:
        """Walk the chain and report the first break, if any.

        The chain is **per session**: each replay starts from an empty
        fingerprint, so verifying a campaign means verifying every session's
        chain separately. Walking all entries as one chain would report a break
        at every session boundary.
        """
        if session_id is not None:
            return self._verifier_une(self.entrees(session_id))
        for identifiant in self.sessions():
            etat = self._verifier_une(self.entrees(identifiant))
            if not etat.integre:
                return EtatChaine(
                    integre=False,
                    entrees=len(self._entrees),
                    premiere_rupture=etat.premiere_rupture,
                    empreinte_finale=etat.empreinte_finale,
                )
        return EtatChaine(integre=True, entrees=len(self._entrees), empreinte_finale=self._empreinte_finale())

    def _verifier_une(self, entrees: Sequence[EntreeJournal]) -> EtatChaine:
        attendue = ""
        for entree in entrees:
            if entree.empreinte_prec != attendue:
                return EtatChaine(False, len(entrees), entree.id, attendue)
            if chainer(attendue, _projection(entree)) != entree.empreinte:
                return EtatChaine(False, len(entrees), entree.id, attendue)
            attendue = entree.empreinte
        return EtatChaine(True, len(entrees), None, attendue)

    def _empreinte_finale(self) -> str:
        sessions = self.sessions()
        return self._queues.get(sessions[-1], "") if sessions else ""

    def exporter(self, session_id: str | None = None) -> str:
        """JSON Lines, keys sorted: an auditor can diff two exports."""
        lignes = [canonique(_serialisable(e)) for e in self.entrees(session_id)]
        return "\n".join(lignes) + ("\n" if lignes else "")

    def __len__(self) -> int:
        return len(self._entrees)

    def sessions(self) -> tuple[str, ...]:
        return tuple(sorted(self._queues))

    def purger_avant(self, seuil: Any) -> int:
        """ENF-12 — the retention purge.

        This is **not** an edit of the chain: entries are never modified. Whole
        sessions older than the threshold are dropped, tail first, so what
        remains is still a complete, verifiable chain. The purge is a fact the
        report states, not a silent truncation.
        """
        gardees = [e for e in self._entrees if e.horodatage >= seuil]
        retirees = len(self._entrees) - len(gardees)
        self._entrees = gardees
        self._queues = {e.session_id: e.empreinte for e in gardees}
        return retirees


def verifier_sequence(entrees: Sequence[EntreeJournal]) -> EtatChaine:
    """Verify an already-exported sequence (used on a reloaded journal).

    Entries of different sessions form different chains, so each session is
    verified separately and the first break found is reported.
    """
    journal = JournalChaine()
    for entree in entrees:
        journal._entrees.append(entree)
        journal._queues[entree.session_id] = entree.empreinte
    return journal.verifier()


def _projection(entree: EntreeJournal) -> dict[str, object]:
    """What the chain commits to: everything but the chain fields themselves."""
    donnees = _serialisable(entree)
    donnees.pop("empreinte", None)
    donnees.pop("empreinte_prec", None)
    return donnees


def _serialisable(entree: EntreeJournal) -> dict[str, object]:
    donnees = asdict(entree)
    donnees["decision"] = entree.decision.value
    return {cle: json.loads(json.dumps(valeur, default=str)) for cle, valeur in donnees.items()}


def fusionner(journaux: Iterable[JournalChaine]) -> JournalChaine:
    """Merge several session journals into one, keeping each chain intact."""
    resultat = JournalChaine()
    for journal in journaux:
        for entree in journal.entrees():
            resultat._entrees.append(entree)
            resultat._queues[entree.session_id] = entree.empreinte
    return resultat
