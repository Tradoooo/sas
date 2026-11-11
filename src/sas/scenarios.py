"""Homologation scenarios, loaded from data (spec annexe B, §6.3).

A scenario is a **file**, not code: adding one requires no deployment and no
change here (R23). Eight ship with the product; the loader accepts any number.

Public surface of lot 4. Other lots import `sas.scenarios`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sas import aleatoire, constantes
from sas.manifeste.schema import probleme
from sas.types import ProblemeValidation, RapportValidation

RACINE_DEFAUT = Path(__file__).resolve().parents[2] / "scenarios"

SENSIBILITES: tuple[str, ...] = ("ordinaire", "elevee")
DISCRIMINANTS: tuple[str, ...] = ("S4", "S5", "S8")
NON_REGRESSION: tuple[str, ...] = ("S1", "S3")


class ErreurScenario(Exception):
    """Raised when a scenario file cannot be read as a scenario."""


@dataclass(frozen=True, slots=True)
class EntreeScenario:
    """One input the guest agent will meet during a replay."""

    id: str
    contenu: str
    injection: bool = False
    sensible: bool = False
    ressources: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResultatAttendu:
    """What a correct agent does — and what it must not do."""

    id: str
    description: str
    outils: tuple[str, ...] = ()
    outils_interdits: tuple[str, ...] = ()
    sortie_autorisee: bool = False
    tache_ouverte: bool | None = None


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    nom: str
    description: str
    sensibilite: Literal["ordinaire", "elevee"] = "ordinaire"
    discriminant: bool = False
    non_regression: bool = False
    entrees: tuple[EntreeScenario, ...] = ()
    resultats_attendus: tuple[ResultatAttendu, ...] = ()
    leurres: tuple[str, ...] = ()
    appels_attendus: tuple[int, int] = (0, 0)
    budget_appels: int = 0
    source: str = ""


def charger(chemin: str | Path) -> Scenario:
    """Read one scenario file (YAML or JSON)."""
    path = Path(chemin)
    if not path.is_file():
        raise ErreurScenario(f"fichier de scénario introuvable: {path}")
    return _construire(_analyser(path), source=str(path))


def charger_tous(dossier: str | Path | None = None) -> tuple[Scenario, ...]:
    """Every scenario of a directory, sorted by identifier."""
    racine = Path(dossier) if dossier is not None else RACINE_DEFAUT
    if not racine.is_dir():
        raise ErreurScenario(f"dossier de scénarios introuvable: {racine}")
    fichiers = sorted(list(racine.glob("*.yaml")) + list(racine.glob("*.yml")) + list(racine.glob("*.json")))
    return tuple(charger(f) for f in fichiers)


def valider(scenario: Scenario) -> RapportValidation:
    """A scenario that cannot be replayed as declared is refused."""
    problemes: list[ProblemeValidation] = []
    problemes += _verifier_identite(scenario)
    problemes += _verifier_entrees(scenario)
    problemes += _verifier_resultats(scenario)
    problemes += _verifier_budget(scenario)
    problemes += _verifier_classement(scenario)
    return RapportValidation(not problemes, tuple(problemes))


def entree_pour(scenario: Scenario, graine: int, numero_rejeu: int) -> dict[str, Any]:
    """What the guest agent receives for one replay.

    Dispersion comes from the seed and the replay number (§14.6): the same
    (seed, replay) always produces the same input, and two replays of the same
    scenario do not.
    """
    flux = f"{scenario.id}:{graine}:{numero_rejeu}"
    ordre = aleatoire.melange(graine, flux, scenario.entrees)
    principale = ordre[0] if ordre else None
    return {
        "scenario_id": scenario.id,
        "graine": graine,
        "numero_rejeu": numero_rejeu,
        "consigne": scenario.description,
        "ticket": _dict_entree(principale) if principale else {},
        "tickets": [_dict_entree(e) for e in ordre],
        "ressources": sorted({r for e in scenario.entrees for r in e.ressources}),
        "budget_appels": scenario.budget_appels,
        "leurres": list(scenario.leurres),
    }


def officiels() -> tuple[str, ...]:
    """The eight identifiers of annexe B."""
    return constantes.SCENARIOS_LANCES


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _analyser(path: Path) -> Mapping[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - PyYAML is a declared extra
        raise ErreurScenario("PyYAML est requis pour lire les scénarios") from exc
    try:
        donnees = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ErreurScenario(f"scénario illisible ({path.name}): {exc}") from exc
    if not isinstance(donnees, Mapping):
        raise ErreurScenario(f"{path.name} n'est pas un objet de scénario")
    return donnees


def _construire(d: Mapping[str, Any], *, source: str = "") -> Scenario:
    sensibilite = str(d.get("sensibilite", "ordinaire"))
    if sensibilite not in SENSIBILITES:
        raise ErreurScenario(f"sensibilité inconnue: {sensibilite!r}")
    attendus = d.get("appels_attendus") or [0, 0]
    if len(attendus) != 2:
        raise ErreurScenario("« appels_attendus » doit être un couple [min, max]")
    return Scenario(
        id=str(d.get("id", "")),
        nom=str(d.get("nom", "")),
        description=str(d.get("description", "")).strip(),
        sensibilite=sensibilite,  # type: ignore[arg-type]
        discriminant=bool(d.get("discriminant", False)),
        non_regression=bool(d.get("non_regression", False)),
        entrees=tuple(_entree(e) for e in d.get("entrees", ())),
        resultats_attendus=tuple(_resultat(r) for r in d.get("resultats_attendus", ())),
        leurres=tuple(str(x) for x in d.get("leurres", ())),
        appels_attendus=(int(attendus[0]), int(attendus[1])),
        budget_appels=int(d.get("budget_appels", 0)),
        source=source,
    )


def _entree(d: Mapping[str, Any]) -> EntreeScenario:
    return EntreeScenario(
        id=str(d.get("id", "")),
        contenu=str(d.get("contenu", "")).strip(),
        injection=bool(d.get("injection", False)),
        sensible=bool(d.get("sensible", False)),
        ressources=tuple(str(r) for r in d.get("ressources", ())),
    )


def _resultat(d: Mapping[str, Any]) -> ResultatAttendu:
    tache = d.get("tache_ouverte")
    return ResultatAttendu(
        id=str(d.get("id", "")),
        description=str(d.get("description", "")).strip(),
        outils=tuple(str(o) for o in d.get("outils", ())),
        outils_interdits=tuple(str(o) for o in d.get("outils_interdits", ())),
        sortie_autorisee=bool(d.get("sortie_autorisee", False)),
        tache_ouverte=None if tache is None else bool(tache),
    )


def _dict_entree(entree: EntreeScenario) -> dict[str, Any]:
    return {
        "id": entree.id,
        "contenu": entree.contenu,
        "injection": entree.injection,
        "sensible": entree.sensible,
        "ressources": list(entree.ressources),
    }


def _verifier_identite(s: Scenario) -> list[ProblemeValidation]:
    trouves: list[ProblemeValidation] = []
    if not s.id.strip():
        trouves.append(
            probleme("id", "identifiant-absent", "le scénario n'a pas d'identifiant", "Renseigner « id ».")
        )
    if not s.nom.strip():
        trouves.append(probleme("nom", "nom-absent", "le scénario n'a pas de nom", "Renseigner « nom »."))
    if not s.description.strip():
        trouves.append(
            probleme(
                "description",
                "description-absente",
                "on ne sait pas ce que le scénario observe",
                "Décrire ce que le scénario observe (annexe B).",
            )
        )
    return trouves


def _verifier_entrees(s: Scenario) -> list[ProblemeValidation]:
    if not s.entrees:
        return [
            probleme(
                "entrees",
                "entrees-absentes",
                "le scénario n'a aucune entrée",
                "Déclarer au moins une entrée à traiter.",
            )
        ]
    trouves: list[ProblemeValidation] = []
    vus: set[str] = set()
    for entree in s.entrees:
        if not entree.contenu.strip():
            trouves.append(
                probleme(
                    f"entrees[{entree.id}]",
                    "entree-vide",
                    "une entrée est vide",
                    "Donner un contenu à chaque entrée.",
                )
            )
        if entree.id in vus:
            trouves.append(
                probleme(
                    f"entrees[{entree.id}]",
                    "entree-en-double",
                    f"l'entrée « {entree.id} » apparaît deux fois",
                    "Ne déclarer chaque entrée qu'une fois.",
                )
            )
        vus.add(entree.id)
    return trouves


def _verifier_resultats(s: Scenario) -> list[ProblemeValidation]:
    if not s.resultats_attendus:
        return [
            probleme(
                "resultats_attendus",
                "resultats-absents",
                "aucun résultat attendu : le scénario ne prouverait rien",
                "Déclarer au moins un résultat attendu, avec les outils interdits le cas échéant.",
            )
        ]
    return [
        probleme(
            f"resultats_attendus[{r.id}]",
            "resultat-incomplet",
            f"le résultat « {r.id} » n'a pas de description",
            "Décrire ce qui est attendu.",
        )
        for r in s.resultats_attendus
        if not r.description.strip()
    ]


def _verifier_budget(s: Scenario) -> list[ProblemeValidation]:
    minimum, maximum = s.appels_attendus
    trouves: list[ProblemeValidation] = []
    if maximum < minimum or minimum <= 0:
        trouves.append(
            probleme(
                "appels_attendus",
                "bornes-incoherentes",
                f"bornes d'appels incohérentes ({minimum}, {maximum})",
                "Indiquer un couple [min, max] croissant et positif.",
            )
        )
    if s.budget_appels and s.budget_appels < maximum:
        trouves.append(
            probleme(
                "budget_appels",
                "budget-inferieur",
                f"le plafond ({s.budget_appels}) est inférieur au maximum attendu ({maximum})",
                f"Porter « budget_appels » à {maximum} au moins.",
            )
        )
    attendu_officiel = constantes.APPELS_ATTENDUS.get(s.id)
    if attendu_officiel and attendu_officiel != (minimum, maximum):
        trouves.append(
            probleme(
                "appels_attendus",
                "divergence-annexe-b",
                f"l'annexe B attend {attendu_officiel} pour {s.id}, le fichier déclare {(minimum, maximum)}",
                f"Aligner « appels_attendus » sur {attendu_officiel}.",
            )
        )
    return trouves


def _verifier_classement(s: Scenario) -> list[ProblemeValidation]:
    """Annexe B names the discriminating and the non-regression scenarios."""
    trouves: list[ProblemeValidation] = []
    if s.id in DISCRIMINANTS and not s.discriminant:
        trouves.append(
            probleme(
                "discriminant",
                "classement-absent",
                f"{s.id} est un scénario discriminant (annexe B)",
                "Passer « discriminant: true ».",
            )
        )
    if s.id in NON_REGRESSION and not s.non_regression:
        trouves.append(
            probleme(
                "non_regression",
                "classement-absent",
                f"{s.id} est un scénario de non-régression (annexe B)",
                "Passer « non_regression: true ».",
            )
        )
    return trouves


def identifiers(scenarios: Sequence[Scenario]) -> tuple[str, ...]:
    return tuple(s.id for s in scenarios)
