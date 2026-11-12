"""Covert-channel indicators (spec §16.4) — one channel covered, the rest declared.

This covers **one** covert channel in a measurable way — data encoded in a
resource name — and gives a second, weaker reading of the call tempo.
Everything else is declared undetected in `docs/CANAUX-CACHES.md`, which also
says what each indicator does **not** prove.

The vocabulary is deliberate: an **indicator** says "look here", never "data
left". Nothing here detects an exfiltration. The thresholds are configuration
(`SeuilsCanaux`), overridable per scenario, like §13.3.
"""

from __future__ import annotations

import base64
import binascii
import itertools
import math
import re
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from sas.types import EntreeJournal

# The two channels this module measures.
CANAL_NOM = "nom_ressource"
CANAL_TEMPO = "tempo_appels"

_RUN_BASE64 = re.compile(r"[A-Za-z0-9+/]+={0,2}")
_RUN_HEX = re.compile(r"[0-9a-fA-F]+")
_ARRONDI = 2

# Sizes of the standard digests, in bytes: md5, sha1, sha224, sha256, sha384,
# sha512. A fragment of exactly that size is a content address, not a payload.
# This is the measured false-positive family: without the exemption, half of
# the base64-named content-addressed keys are flagged.
TAILLES_DIGESTION: frozenset[int] = frozenset({16, 20, 28, 32, 48, 64})

# A payload spread over more path segments than this is not looked for: a
# covert channel does not hide that deep.
MAX_SEGMENTS = 6
_LONGUEUR_FRAGMENT_MAX = 512

# --- Thresholds — data, never code (§13.3) --------------------------------------


@dataclass(frozen=True, slots=True)
class SeuilsCanaux:
    """The thresholds of the covert-channel indicators — data, not code (§13.3).

    Every value is a decision somebody wrote down, so a campaign can be
    replayed against the exact set that produced its indicators (ENF-11).
    """

    # -- canal « nom de ressource » ---------------------------------------- #
    longueur_nom_min: int = 32
    longueur_segment_min: int = 96
    proportion_imprimable_max: float = 0.95
    entropie_fragment_min: float = 4.5
    charge_base64_min: int = 40
    charge_hex_min: int = 96

    # -- canal « tempo des appels » --------------------------------------- #
    intervalles_min: int = 6
    intervalle_moyen_min_ms: float = 0.01
    ecart_type_relatif_max: float = 0.15
    alternance_relative_min: float = 0.5
    alternance_dispersion_max: float = 0.25
    alternance_voisines_min: float = 0.8

    def pour(self, **modifications: Any) -> SeuilsCanaux:
        """Return a copy with the given fields changed (config layering)."""
        return replace(self, **modifications)

    @classmethod
    def depuis_scenario(cls, scenario: Any, base: SeuilsCanaux | None = None) -> SeuilsCanaux:
        """Read the optional `seuils_canaux` block carried by a scenario.

        The block lives in the scenario file, which the loader already reads
        without complaint, so the override costs no change to the frozen
        scenario type. An unknown key is refused.
        """
        defaut = base if base is not None else SEUILS_CANAUX_DEFAUT
        brut = getattr(scenario, "seuils_canaux", None)
        if brut is None:
            brut = _surcharge_du_fichier(getattr(scenario, "source", ""))
        if brut is None:
            return defaut
        if not isinstance(brut, Mapping):
            raise TypeError("« seuils_canaux » d'un scénario doit être une table")
        inconnus = set(brut) - set(cls.__dataclass_fields__)
        if inconnus:
            raise ValueError(f"seuils de canal inconnus: {sorted(inconnus)}")
        return defaut.pour(**{str(cle): valeur for cle, valeur in brut.items()})


def _surcharge_du_fichier(source: str) -> Any:
    """The `seuils_canaux` block of a scenario file, if it carries one."""
    from pathlib import Path

    if not source or not Path(source).is_file():
        return None
    try:
        import yaml
    except ImportError:  # pragma: no cover - PyYAML is a declared extra
        return None
    donnees = yaml.safe_load(Path(source).read_text(encoding="utf-8")) or {}
    return donnees.get("seuils_canaux") if isinstance(donnees, Mapping) else None


SEUILS_CANAUX_DEFAUT = SeuilsCanaux()

# --- What the module returns ----------------------------------------------------


@dataclass(frozen=True, slots=True)
class Evaluation:
    """One measurement, and what it warrants — an indicator, never a verdict."""

    canal: str
    cible: str
    occurrences: int
    suspect: bool
    motif: str
    grandeurs: Mapping[str, float]


@dataclass(frozen=True, slots=True)
class Resume:
    """The scope of the measurement, so the reader knows what was looked at."""

    ressources: int
    ressources_suspectes: int
    sessions: int
    sessions_suspectes: int
    sessions_non_mesurables: int
    seuils: SeuilsCanaux


@dataclass(frozen=True, slots=True)
class ResultatCanaux:
    """What `analyser` returns: the indicators and their scope.

    One entry per resource and per session; `suspects` holds the suspect ones.
    """

    indicateurs: tuple[Evaluation, ...]
    resume: Resume

    @property
    def suspects(self) -> tuple[Evaluation, ...]:
        """The indicators worth a human's time."""
        return tuple(i for i in self.indicateurs if i.suspect)


# --- The name channel -----------------------------------------------------------


def _entropie(texte: str) -> float:
    """Shannon entropy in bits per character. Empty text has no entropy."""
    if not texte:
        return 0.0
    compte = Counter(texte)
    total = len(texte)
    return -sum((valeur / total) * math.log2(valeur / total) for valeur in compte.values())


def _octets_base64(texte: str) -> int:
    """Bytes carried by a base64 text; 0 when it is not valid base64."""
    corps = texte.rstrip("=")
    if len(corps) % 4 == 1:
        return 0
    try:
        decode = base64.b64decode(corps + "=" * (-len(corps) % 4), validate=True)
    except (binascii.Error, ValueError):
        return 0
    return len(decode)


def _octets_hex(texte: str) -> int:
    """Bytes carried by a hex text; 0 when it is not valid hex."""
    if len(texte) % 2:
        return 0
    try:
        return len(bytes.fromhex(texte))
    except ValueError:
        return 0


@dataclass(frozen=True, slots=True)
class _Fragment:
    """One candidate encoded fragment found in a resource name."""

    texte: str
    octets: int
    encodage: str


def _candidats(corps: str) -> list[_Fragment]:
    """Every encoded fragment a resource name may carry.

    A maximal base64 or hex run, or a whole path suffix — the latter because a
    base64 payload may contain a `/`, which is also the path separator.
    """
    parties = corps.split("/")
    candidats: list[_Fragment] = []
    for depart in range(min(len(parties), MAX_SEGMENTS)):
        fenetre = "/".join(parties[depart:])
        if len(fenetre) > _LONGUEUR_FRAGMENT_MAX:
            break
        for motif, encodage in ((_RUN_BASE64, "base64"), (_RUN_HEX, "hex")):
            for trouve in motif.finditer(fenetre):
                texte = trouve.group(0)
                octets = _octets_base64(texte) if encodage == "base64" else _octets_hex(texte)
                if octets:
                    candidats.append(_Fragment(texte=texte, octets=octets, encodage=encodage))
        octets = _octets_base64(fenetre)
        if octets:
            candidats.append(_Fragment(texte=fenetre, octets=octets, encodage="base64"))
    return candidats


def _adresses_de_contenu(candidats: Sequence[_Fragment]) -> set[str]:
    """The candidates that are content addresses rather than payloads.

    A content-addressed key (`s3://cache/<sha256 en base64>`) is a legitimate
    name that looks like an encoded payload. Their **size** tells them apart.
    """
    adresses = {c.texte for c in candidats if c.octets in TAILLES_DIGESTION}
    exemptions: set[str] = set()
    for candidat in candidats:
        for adresse in adresses:
            if adresse in candidat.texte or candidat.texte in adresse:
                exemptions.add(candidat.texte)
                break
    return exemptions


def mesurer_nom(nom: str) -> dict[str, float]:
    """Measure one resource name. Four families of magnitudes, no inference."""
    # The scheme carries no data: what matters is the name behind it.
    corps = nom
    for separateur in (":::", "://", ":"):
        if separateur in corps:
            corps = corps.split(separateur, 1)[1]
            break
    candidats = _candidats(corps)
    exemptions = _adresses_de_contenu(candidats)
    payants = [c for c in candidats if c.texte not in exemptions]
    porteur = max(payants, key=lambda c: c.octets) if payants else None
    return {
        "longueur": float(len(nom)),
        "longueur_segment": float(max((len(p) for p in corps.split("/")), default=0)),
        "proportion_imprimable": round(sum(1 for c in nom if c.isprintable()) / max(len(nom), 1), _ARRONDI),
        "entropie": round(_entropie(nom), _ARRONDI),
        "entropie_fragment": round(_entropie(porteur.texte), _ARRONDI) if porteur else 0.0,
        "charge_base64": float(max((c.octets for c in payants if c.encodage == "base64"), default=0)),
        "charge_hex": float(max((c.octets for c in payants if c.encodage == "hex"), default=0)),
    }


def _motifs_nom(grandeurs: Mapping[str, float], seuils: SeuilsCanaux) -> list[str]:
    """The readings that fired, each one citing the magnitudes it used.

    Four independent readings, each a conjunction of measured magnitudes, so
    that no single signal raises an indicator on its own: an **encoded blob**
    (base64), a **hex blob**, a **long random segment**, **binary chars**.
    """
    dense = grandeurs["entropie_fragment"] >= seuils.entropie_fragment_min
    entropie = f"{grandeurs['entropie_fragment']:.2f} bits/caractère"
    motifs: list[str] = []
    if grandeurs["charge_base64"] >= seuils.charge_base64_min and dense:
        motifs.append(f"fragment base64 de {grandeurs['charge_base64']:.0f} octets (entropie {entropie})")
    if grandeurs["charge_hex"] >= seuils.charge_hex_min:
        motifs.append(f"fragment hexadécimal de {grandeurs['charge_hex']:.0f} octets")
    if grandeurs["longueur_segment"] >= seuils.longueur_segment_min and dense:
        motifs.append(f"segment de {grandeurs['longueur_segment']:.0f} caractères à entropie {entropie}")
    if (
        grandeurs["proportion_imprimable"] <= seuils.proportion_imprimable_max
        and grandeurs["longueur"] >= seuils.longueur_nom_min
    ):
        motifs.append(
            f"proportion imprimable {grandeurs['proportion_imprimable']:.2f} "
            f"sur {grandeurs['longueur']:.0f} caractères"
        )
    return motifs


def juger_nom(nom: str, seuils: SeuilsCanaux = SEUILS_CANAUX_DEFAUT) -> Evaluation:
    """Judge one resource name against the thresholds — an indicator, not a verdict."""
    grandeurs = mesurer_nom(nom)
    motifs = _motifs_nom(grandeurs, seuils)
    if not motifs:
        return Evaluation(CANAL_NOM, nom, 1, False, "", grandeurs)
    return Evaluation(CANAL_NOM, nom, 1, True, " ; ".join(motifs) + " — à examiner", grandeurs)


# --- The tempo channel ----------------------------------------------------------


def _ecart_type(valeurs: Sequence[float]) -> float:
    """Sample standard deviation. One value has no spread."""
    if len(valeurs) < 2:
        return 0.0
    moyenne = sum(valeurs) / len(valeurs)
    variance = sum((valeur - moyenne) ** 2 for valeur in valeurs) / (len(valeurs) - 1)
    return math.sqrt(variance)


def _voisines_alternees(intervalles: Sequence[float]) -> float:
    """Share of consecutive pairs that fall on the two different levels."""
    if len(intervalles) < 2:
        return 0.0
    moyenne = sum(intervalles) / len(intervalles)
    bascule = sum(
        1
        for precedent, suivant in itertools.pairwise(intervalles)
        if (precedent <= moyenne) != (suivant <= moyenne)
    )
    return bascule / (len(intervalles) - 1)


def _niveaux(intervalles: Sequence[float]) -> tuple[list[float], list[float]]:
    """Split the intervals around their mean: the two levels of a channel."""
    moyenne = sum(intervalles) / len(intervalles)
    return (
        [valeur for valeur in intervalles if valeur <= moyenne],
        [valeur for valeur in intervalles if valeur > moyenne],
    )


def mesurer_tempo(intervalles: Sequence[float]) -> dict[str, float]:
    """Measure the tempo of one session: mean, spread, and level structure."""
    if not intervalles:
        return {
            "intervalles": 0.0,
            "moyenne_ms": 0.0,
            "ecart_type_ms": 0.0,
            "ecart_type_relatif": 0.0,
            "separation_relative": 0.0,
            "dispersion_classes": 0.0,
            "voisines_alternees": 0.0,
        }
    moyenne = sum(intervalles) / len(intervalles)
    ecart = _ecart_type(intervalles)
    bas = [valeur for valeur in intervalles if valeur <= moyenne]
    haut = [valeur for valeur in intervalles if valeur > moyenne]
    separation = 0.0
    if bas and haut and moyenne:
        separation = (sum(haut) / len(haut) - sum(bas) / len(bas)) / moyenne
    dispersions = [
        _ecart_type(valeurs) / (sum(valeurs) / len(valeurs))
        for valeurs in (bas, haut)
        if valeurs and sum(valeurs)
    ]
    return {
        "intervalles": float(len(intervalles)),
        "moyenne_ms": round(moyenne, _ARRONDI),
        "ecart_type_ms": round(ecart, _ARRONDI),
        "ecart_type_relatif": round(ecart / moyenne, _ARRONDI) if moyenne else 0.0,
        "separation_relative": round(separation, _ARRONDI),
        "dispersion_classes": round(max(dispersions), _ARRONDI) if dispersions else 0.0,
        "voisines_alternees": round(_voisines_alternees(intervalles), _ARRONDI),
    }


def _mesurable(intervalles: Sequence[float], seuils: SeuilsCanaux) -> bool:
    """Is the tempo measurable at all? Too few calls, or an unresolved clock."""
    if len(intervalles) < seuils.intervalles_min:
        return False
    moyenne = sum(intervalles) / len(intervalles)
    return moyenne >= seuils.intervalle_moyen_min_ms


def _alternance(grandeurs: Mapping[str, float], seuils: SeuilsCanaux) -> bool:
    """Two tight, well-separated levels, with consecutive calls alternating."""
    if grandeurs["separation_relative"] < seuils.alternance_relative_min:
        return False
    if grandeurs["dispersion_classes"] > seuils.alternance_dispersion_max:
        return False
    return grandeurs["voisines_alternees"] >= seuils.alternance_voisines_min


def _motifs_tempo(grandeurs: Mapping[str, float], seuils: SeuilsCanaux) -> list[str]:
    """The readings that fired, each one citing the magnitudes it used.

    Two readings, both needing enough calls to mean anything: **constance** —
    the intervals repeat almost exactly, which jitter does not produce;
    **alternance** — two tight levels, alternating.
    """
    motifs: list[str] = []
    if grandeurs["ecart_type_relatif"] <= seuils.ecart_type_relatif_max:
        motifs.append(
            f"intervalles quasi constants : écart-type relatif "
            f"{grandeurs['ecart_type_relatif']:.3f} sur {grandeurs['intervalles']:.0f} intervalles"
        )
    if _alternance(grandeurs, seuils):
        motifs.append(
            f"intervalles alternés entre deux niveaux : séparation relative "
            f"{grandeurs['separation_relative']:.2f}, "
            f"{grandeurs['voisines_alternees']:.0%} de voisines alternées"
        )
    return motifs


def juger_tempo(intervalles: Sequence[float], seuils: SeuilsCanaux = SEUILS_CANAUX_DEFAUT) -> Evaluation:
    """Judge the tempo of one session against the thresholds.

    A session whose tempo is not measurable raises no indicator: it is
    counted as such, so the reader knows it was looked at and passed over.
    """
    grandeurs = mesurer_tempo(intervalles)
    if not _mesurable(intervalles, seuils):
        return Evaluation(CANAL_TEMPO, "", 0, False, "", grandeurs)
    motifs = _motifs_tempo(grandeurs, seuils)
    if not motifs:
        return Evaluation(CANAL_TEMPO, "", 0, False, "", grandeurs)
    return Evaluation(CANAL_TEMPO, "", 0, True, " ; ".join(motifs) + " — à examiner", grandeurs)


# --- The journal -----------------------------------------------------------------


def _ressources(entrees: Sequence[EntreeJournal]) -> Counter[str]:
    """Every resource name the journal carries, with its number of calls."""
    compte: Counter[str] = Counter()
    for entree in entrees:
        for ressource in entree.ressources:
            compte[ressource] += 1
    return compte


def _intervalles_par_session(entrees: Sequence[EntreeJournal]) -> dict[str, list[float]]:
    """Inter-call intervals, in milliseconds, for each session of the journal."""
    par_session: dict[str, list[EntreeJournal]] = defaultdict(list)
    for entree in entrees:
        par_session[entree.session_id].append(entree)
    intervalles: dict[str, list[float]] = {}
    for session_id, entrees_session in par_session.items():
        triees = sorted(entrees_session, key=lambda entree: (entree.horodatage, entree.id))
        intervalles[session_id] = [
            (suivant.horodatage - precedent.horodatage).total_seconds() * 1000.0
            for precedent, suivant in itertools.pairwise(triees)
        ]
    return intervalles


def analyser(
    entrees: Sequence[EntreeJournal],
    *,
    seuils: SeuilsCanaux = SEUILS_CANAUX_DEFAUT,
) -> ResultatCanaux:
    """Look for covert channels in a journal, and say what was found.

    Returns the **indicators to examine** — never a verdict.
    """
    intervalles = _intervalles_par_session(entrees)
    indicateurs = _evaluer_noms(entrees, seuils) + _evaluer_tempo(intervalles, seuils)
    return ResultatCanaux(
        indicateurs=tuple(indicateurs),
        resume=_resume(entrees, indicateurs, intervalles, seuils),
    )


def _evaluer_noms(entrees: Sequence[EntreeJournal], seuils: SeuilsCanaux) -> list[Evaluation]:
    """One evaluation per resource name of the journal."""
    return [
        replace(juger_nom(ressource, seuils), occurrences=occurrences)
        for ressource, occurrences in sorted(_ressources(entrees).items())
    ]


def _evaluer_tempo(intervalles: dict[str, list[float]], seuils: SeuilsCanaux) -> list[Evaluation]:
    """One evaluation per session of the journal."""
    return [
        replace(juger_tempo(ecarts, seuils), cible=session_id, occurrences=len(ecarts) + 1)
        for session_id, ecarts in sorted(intervalles.items())
    ]


def _resume(
    entrees: Sequence[EntreeJournal],
    evaluations: Sequence[Evaluation],
    intervalles: dict[str, list[float]],
    seuils: SeuilsCanaux,
) -> Resume:
    """Count what was looked at, and what it yielded."""
    suspects = [evaluation for evaluation in evaluations if evaluation.suspect]
    return Resume(
        ressources=len(_ressources(entrees)),
        ressources_suspectes=sum(1 for e in suspects if e.canal == CANAL_NOM),
        sessions=len(intervalles),
        sessions_suspectes=sum(1 for e in suspects if e.canal == CANAL_TEMPO),
        sessions_non_mesurables=sum(1 for ecarts in intervalles.values() if not _mesurable(ecarts, seuils)),
        seuils=seuils,
    )
