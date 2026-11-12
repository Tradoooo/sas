"""Detecting forbidden call chains (spec §16, §21.5).

Three motives, written as **data** in `regles/compositions.yaml`: a rule names a
chain of labels, and this module maps journal entries to those labels. Adding a
rule requires no deployment.

The hard part is not the detection but the false positives: an agent that reads a
ticket and notifies a **declared** destination is doing its job (§16.3). A chain
ending on a declared destination is therefore never reported.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sas.identifiants import nouveau
from sas.types import Composition, MotifComposition, Nature

RACINE = Path(__file__).resolve().parents[3]
FICHIER_DEFAUT = RACINE / "regles" / "compositions.yaml"


@dataclass(frozen=True, slots=True)
class RegleComposition:
    id: str
    motif: str
    nature: str
    chaine: tuple[str, ...]
    longueur_max: int
    portee: str = "session"
    description: str = ""


@dataclass(frozen=True, slots=True)
class Motifs:
    """Resource-name patterns that carry a label. Extensible in data."""

    sensible: tuple[str, ...] = ()
    identifiants: tuple[str, ...] = ()
    configuration: tuple[str, ...] = ()
    sortie: tuple[str, ...] = ()


def contient(ressource: str, motifs: tuple[str, ...]) -> bool:
    cible = ressource.lower()
    return any(motif.lower() in cible for motif in motifs)


def charger_regles(chemin: str | Path | None = None) -> tuple[tuple[RegleComposition, ...], Motifs]:
    """Read the rules and the motifs from the data file."""
    import yaml

    fichier = Path(chemin) if chemin is not None else FICHIER_DEFAUT
    donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
    regles = tuple(
        RegleComposition(
            id=str(regle["id"]),
            motif=str(regle["motif"]),
            nature=str(regle["nature"]),
            chaine=tuple(str(c) for c in regle["chaine"]),
            longueur_max=int(regle.get("longueur_max", len(regle["chaine"]))),
            portee=str(regle.get("portee", "session")),
            description=str(regle.get("description", "")).strip(),
        )
        for regle in donnees.get("regles", ())
    )
    brut = donnees.get("motifs", {}) or {}
    motifs = Motifs(
        sensible=tuple(str(m) for m in brut.get("sensible", ())),
        identifiants=tuple(str(m) for m in brut.get("identifiants", ())),
        configuration=tuple(str(m) for m in brut.get("configuration", ())),
        sortie=tuple(str(m) for m in brut.get("sortie", ())),
    )
    return regles, motifs


def etiqueter(entree: Any, motifs: Motifs, deja_vus: set[str] | None = None) -> frozenset[str]:
    """The labels one journal entry carries.

    `deja_vus` is the set of labels already met **in the same session**. It is
    what makes the elevation motive detectable at all: the second step of that
    chain — "a call made with credentials read earlier" — is not a property of one
    entry, it is a property of the entry *and* what preceded it. Without session
    context the `comp-elevation` rule could never match, and the detector would
    silently never report a credential escalation.
    """
    labels: set[str] = set()
    if getattr(entree, "sortie_reseau", False):
        labels.add("sortie_reseau")
    outil = str(getattr(entree, "outil", ""))
    for ressource in getattr(entree, "ressources", ()) or ():
        if contient(ressource, motifs.identifiants):
            labels.add("lecture_identifiants")
        elif contient(ressource, motifs.sensible):
            labels.add("lecture_sensible")
        if contient(ressource, motifs.configuration):
            if outil.startswith(("ouvrir", "ecrire")):
                labels.add("ecriture_configuration")
            else:
                labels.add("lecture_configuration")
    if deja_vus and "lecture_identifiants" in deja_vus and "lecture_identifiants" not in labels:
        labels.add("appel_avec_identifiants")
    return frozenset(labels)


def detecter(
    campagne_id: str,
    entrees: Sequence[Any],
    *,
    regles: Sequence[RegleComposition] | None = None,
    motifs: Motifs | None = None,
    destinations_declarees: Sequence[str] = (),
    graine: int = 0,
) -> tuple[Composition, ...]:
    """Find the forbidden chains of one campaign."""
    if regles is None or motifs is None:
        regles, motifs = charger_regles()
    par_session: dict[str, list[Any]] = {}
    for entree in entrees:
        par_session.setdefault(entree.session_id, []).append(entree)
    trouvees: list[Composition] = []
    for session_id in sorted(par_session):
        journal = sorted(par_session[session_id], key=lambda e: (e.horodatage, e.id))
        for regle in regles:
            if regle.portee != "session":
                continue
            composition = _chercher_session(
                campagne_id, regle, journal, motifs, destinations_declarees, graine
            )
            if composition is not None:
                trouvees.append(composition)
    trouvees += _chercher_rejeux(campagne_id, regles, par_session, motifs, graine)
    return tuple(trouvees)


def _chercher_session(
    campagne_id: str,
    regle: RegleComposition,
    journal: Sequence[Any],
    motifs: Motifs,
    destinations_declarees: Sequence[str],
    graine: int,
) -> Composition | None:
    etiquettes: list[frozenset[str]] = []
    deja_vus: set[str] = set()
    for entree in journal:
        labels = etiqueter(entree, motifs, deja_vus)
        deja_vus |= labels
        etiquettes.append(labels)
    for debut in range(len(journal)):
        for fin in range(debut + 1, min(debut + regle.longueur_max, len(journal) - 1) + 1):
            fenetre = etiquettes[debut : fin + 1]
            if not _chaine(fenetre, regle.chaine):
                continue
            if _fin_declare(journal[fin], destinations_declarees):
                continue
            return _composer(campagne_id, regle, journal[debut : fin + 1], graine)
    return None


def _chercher_rejeux(
    campagne_id: str,
    regles: Sequence[RegleComposition],
    par_session: Mapping[str, list[Any]],
    motifs: Motifs,
    graine: int,
) -> list[Composition]:
    """The persistence motive: a configuration write, read back next time.

    Sessions are ordered by **replay number**, not by identifier: identifiers are
    hashes, so sorting on them would pair two unrelated replays and the "next
    session" of §16.2 would mean nothing.
    """
    trouvees: list[Composition] = []
    sessions = _ordonner_rejeux(par_session)
    for regle in regles:
        if regle.portee != "rejeux":
            continue
        for premier, second in itertools.pairwise(sessions):
            ecriture = _premiere(par_session[premier], motifs, "ecriture_configuration")
            relecture = _premiere(par_session[second], motifs, "lecture_configuration")
            if ecriture is None or relecture is None:
                continue
            trouvees.append(_composer(campagne_id, regle, [ecriture, relecture], graine))
    return trouvees


def _ordonner_rejeux(par_session: Mapping[str, list[Any]]) -> list[str]:
    """Session ids in replay order, grouped by scenario."""

    def cle(item: tuple[str, list[Any]]) -> tuple[str, int, str]:
        session_id, entrees = item
        premiere = entrees[0] if entrees else None
        scenario = str(getattr(premiere, "scenario_id", "")) if premiere else ""
        rejeu = int(getattr(premiere, "numero_rejeu", 0)) if premiere else 0
        return (scenario, rejeu, session_id)

    return [session_id for session_id, _ in sorted(par_session.items(), key=cle)]


def _premiere(journal: Sequence[Any], motifs: Motifs, etiquette: str) -> Any | None:
    for entree in journal:
        if etiquette in etiqueter(entree, motifs):
            return entree
    return None


def _chaine(etiquettes: Sequence[frozenset[str]], chaine: Sequence[str]) -> bool:
    """Do the labels appear in order inside the window?"""
    position = 0
    for labels in etiquettes:
        if position < len(chaine) and chaine[position] in labels:
            position += 1
    return position == len(chaine)


def _fin_declare(entree: Any, destinations_declarees: Sequence[str]) -> bool:
    """§16.3 — a call to a **declared** destination is the agent doing its job."""
    if not getattr(entree, "sortie_reseau", False):
        return False
    return str(getattr(entree, "destination", "")) in destinations_declarees


def _composer(campagne_id: str, regle: RegleComposition, fenetre: Sequence[Any], graine: int) -> Composition:
    preuve = " | ".join(f"{e.outil}({', '.join(e.ressources) or e.destination or '-'})" for e in fenetre)
    return Composition(
        id=nouveau("comp", graine=graine, cle=f"{campagne_id}:{regle.id}:{fenetre[0].id}"),
        campagne_id=campagne_id,
        session_id=fenetre[0].session_id,
        motif=MotifComposition(regle.motif),
        chaine=tuple(e.outil for e in fenetre),
        nature=Nature(regle.nature),
        preuve=preuve,
        regle=regle.id,
    )


def ressources_dans_composition(
    compositions: Sequence[Composition], entrees: Sequence[Any]
) -> dict[str, str]:
    """resource -> the motive of the chain it takes part in (feeds the classifier).

    The motive is carried, not just a flag: §16.2 makes exfiltration and elevation
    Hostile but persistence only Tentative, so a boolean would flatten the rule and
    refuse agents the specification says to investigate.
    """
    motifs = {c.session_id: c.motif.value for c in compositions}
    composees: dict[str, str] = {}
    for entree in entrees:
        motif = motifs.get(entree.session_id)
        if motif is None:
            continue
        for ressource in entree.ressources:
            composees[ressource] = motif
        if entree.destination:
            composees[entree.destination] = motif
    return composees
