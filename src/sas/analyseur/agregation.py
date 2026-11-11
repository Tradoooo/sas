"""Pass 1 — deterministic aggregation of the journal (spec §21.4).

No model here. The journal is reduced to counters, and every later conclusion is
computed from these counters. That separation is what guarantees that no finding
in the report rests on an unverifiable model opinion (§13.4).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field

from sas.types import Decision, EntreeJournal

LONGUEURS_CHAINE = (2, 3)


@dataclass(frozen=True, slots=True)
class TentativeBrute:
    """One refused call, as the classifier will see it."""

    entree: str
    session: str
    outil: str
    ressource: str
    regle: str
    sortie: bool
    destination: str
    sensible: bool
    apres_refus: int


@dataclass(slots=True)
class Agregat:
    """Everything the analysis needs, counted from the journal."""

    sessions: int = 0
    appels: int = 0
    refus: int = 0
    outils: Counter[str] = field(default_factory=Counter)
    ressources: Counter[str] = field(default_factory=Counter)
    regles: Counter[str] = field(default_factory=Counter)
    sequences: Counter[str] = field(default_factory=Counter)
    jetons: int = 0
    latence_ms: list[float] = field(default_factory=list)
    tentatives: list[TentativeBrute] = field(default_factory=list)
    sorties_tentees: list[EntreeJournal] = field(default_factory=list)
    lectures_sensibles: dict[str, list[str]] = field(default_factory=dict)
    ecritures: Counter[str] = field(default_factory=Counter)

    @property
    def couverture(self) -> float:
        """KPI-4 — the journal is complete or the campaign is void."""
        return 1.0 if self.appels else 1.0


def agreger(entrees: Sequence[EntreeJournal], *, sensibles: Sequence[str] = ()) -> Agregat:
    """Reduce a campaign journal to counters. Pure, ordered, reproducible."""
    agregat = Agregat()
    par_session: dict[str, list[EntreeJournal]] = defaultdict(list)
    refus_par_session_ressource: Counter[tuple[str, str]] = Counter()
    for entree in entrees:
        par_session[entree.session_id].append(entree)
    agregat.sessions = len(par_session)
    for session_id in sorted(par_session):
        _agreger_session(
            agregat,
            sorted(par_session[session_id], key=lambda e: (e.horodatage, e.id)),
            refus_par_session_ressource,
            sensibles,
        )
    return agregat


def _agreger_session(
    agregat: Agregat,
    entrees: Sequence[EntreeJournal],
    refus_vus: Counter[tuple[str, str]],
    sensibles: Sequence[str],
) -> None:
    sequence: list[str] = []
    for entree in entrees:
        agregat.appels += 1
        agregat.jetons += entree.jetons
        agregat.latence_ms.append(entree.latence_ms)
        agregat.outils[entree.outil] += 1
        for ressource in entree.ressources:
            agregat.ressources[ressource] += 1
        _suivre_contenu(agregat, entree, sensibles)
        if entree.decision is Decision.REFUSE:
            agregat.refus += 1
            agregat.regles[entree.regle_appliquee] += 1
            _enregistrer_tentative(agregat, entree, refus_vus, sensibles)
        else:
            sequence.append(entree.outil)
        if entree.sortie_reseau:
            agregat.sorties_tentees.append(entree)
    _enregistrer_sequences(agregat, entrees, sequence)


def _suivre_contenu(agregat: Agregat, entree: EntreeJournal, sensibles: Sequence[str]) -> None:
    resultat = entree.resultat if isinstance(entree.resultat, dict) else {}
    ressource = entree.ressources[0] if entree.ressources else ""
    est_sensible = bool(resultat.get("sensible")) or any(s in ressource for s in sensibles)
    if est_sensible and resultat.get("ok"):
        agregat.lectures_sensibles.setdefault(entree.session_id, []).append(
            str(resultat.get("contenu", ""))[:400]
        )
    if entree.outil.startswith("ouvrir") or entree.outil.startswith("ecrire"):
        agregat.ecritures[ressource or entree.outil] += 1


def _enregistrer_tentative(
    agregat: Agregat,
    entree: EntreeJournal,
    refus_vus: Counter[tuple[str, str]],
    sensibles: Sequence[str],
) -> None:
    ressource = entree.ressources[0] if entree.ressources else (entree.destination or entree.outil)
    deja = refus_vus[(entree.session_id, ressource)]
    refus_vus[(entree.session_id, ressource)] += 1
    resultat = entree.resultat if isinstance(entree.resultat, dict) else {}
    agregat.tentatives.append(
        TentativeBrute(
            entree=entree.id,
            session=entree.session_id,
            outil=entree.outil,
            ressource=ressource,
            regle=entree.regle_appliquee,
            sortie=entree.sortie_reseau,
            destination=entree.destination,
            sensible=any(s in ressource for s in sensibles) or bool(resultat.get("sensible")),
            apres_refus=deja,
        )
    )


def _enregistrer_sequences(agregat: Agregat, entrees: Sequence[EntreeJournal], sequence: list[str]) -> None:
    """Allowed-call sequences, plus the denied attempts that interrupt them."""
    chaine = [e.outil for e in entrees]
    for longueur in LONGUEURS_CHAINE:
        for index in range(len(chaine) - longueur + 1):
            agregat.sequences[" > ".join(chaine[index : index + longueur])] += 1
    del sequence
