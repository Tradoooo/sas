"""Local Observability: the raw material of the report (lot 5).

It delegates the chaining to `sas.journal.chaine` — one implementation, not two —
and adds what the port promises: per-session reading, chain verification over a
whole campaign, JSON-Lines export, and the **measured** cost.
"""

from __future__ import annotations

from collections.abc import Sequence

from sas import couts
from sas.journal.chaine import JournalChaine
from sas.types import CoutMesure, EntreeJournal, EtatChaine, Session


class ObservabilityLocal:
    def __init__(self, chaine: JournalChaine | None = None) -> None:
        self._chaine = JournalChaine() if chaine is None else chaine
        self._sessions: dict[str, Session] = {}

    @property
    def chaine(self) -> JournalChaine:
        return self._chaine

    # -- port Observability ------------------------------------------------ #
    def enregistrer(self, entree: EntreeJournal) -> EntreeJournal:
        return self._chaine.ajouter(entree)

    def journal(self, session_id: str) -> Sequence[EntreeJournal]:
        return self._chaine.entrees(session_id)

    def verifier_chaine(self, campagne_id: str | None = None) -> EtatChaine:
        """A campaign-wide check: one break anywhere and the proof is void."""
        if campagne_id is None:
            return self._chaine.verifier()
        entrees = [e for e in self._chaine.entrees() if e.campagne_id == campagne_id]
        integre = all(self._chaine.verifier(e.session_id).integre for e in entrees)
        premiere = next((e.id for e in entrees if not self._chaine.verifier(e.session_id).integre), None)
        return EtatChaine(
            integre=integre,
            entrees=len(entrees),
            premiere_rupture=premiere,
            empreinte_finale=self._chaine.derniere_empreinte(entrees[-1].session_id) if entrees else "",
        )

    def exporter(self, session_id: str) -> str:
        return self._chaine.exporter(session_id)

    def cout(self, campagne_id: str) -> CoutMesure:
        sessions = [s for s in self._sessions.values() if s.campagne_id == campagne_id]
        entrees = [e for e in self._chaine.entrees() if e.campagne_id == campagne_id]
        return couts.mesurer(sessions, entrees)

    # -- what the orchestrator adds ---------------------------------------- #
    def suivre_session(self, session: Session) -> None:
        self._sessions[session.id] = session

    def sessions(self, campagne_id: str | None = None) -> tuple[Session, ...]:
        if campagne_id is None:
            return tuple(self._sessions.values())
        return tuple(s for s in self._sessions.values() if s.campagne_id == campagne_id)

    def entrees(self, campagne_id: str | None = None) -> tuple[EntreeJournal, ...]:
        if campagne_id is None:
            return self._chaine.entrees()
        return tuple(e for e in self._chaine.entrees() if e.campagne_id == campagne_id)
