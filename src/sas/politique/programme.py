"""The configurable policy engine (lot 6): the rules are data, not code.

`PolicyLocale` (lot 5) evaluates annexe C in the order the specification writes
it, with the refusal names the analyser classifies. This module does **not**
replace that order: the perimeter of the manifest is frozen in the derivation
(EF-05) and `PolicyLocale` is its reference evaluation. What this module adds is
the part annexe C does not reach — the *client's* policy — in the same form the
composition rules of §16.2 already use: **data** (`regles/politique.yaml`), not
code.

So the engine composes, and only in one direction:

1. `PolicyLocale` evaluates the manifest perimeter first. A refusal there wins,
   with its own rule name and family — the classification of §13 is untouched.
2. On an *allowed* call, the additive rules run, in order. A rule can only
   **refuse** (narrow the perimeter, never widen it) or **authorize under a
   condition** (`Decision.AUTORISE_SOUS_CONDITION`), which says *why* the call
   is allowed and records that condition in the journal.

A rule is scoped to a scenario through a condition on the fact `scenario`, so
the same program can treat S5 (sensitive data) differently from S8 (outbound)
without a code change. The facts are a small closed vocabulary over
`ContexteAppel` and `FaitsSession` — never free text — and a fact that is not in
the vocabulary is refused at load time, not ignored: a rule nobody can evaluate
is a rule nobody can trust.

Finally, the family of a refusal is what the analyser uses to decide whether
it is a finding. The base families keep living in `politique_manifeste.py`; a
refusal rule added here must name a **known** `regle` of the right family, and
the loader refuses the file otherwise. A data-defined refusal the analyser
cannot classify would be a silent hole.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sas.agentcore.politique_manifeste import REGLES_BORNAGE, REGLES_PERIMETRE
from sas.types import ContexteAppel, FaitsSession

RACINE = Path(__file__).resolve().parents[3]
FICHIER_DEFAUT = RACINE / "regles" / "politique.yaml"

#: The closed vocabulary of facts a condition may compare. A fact is a name
#: with a typed value, never a sentence to interpret. It deliberately carries
#: nothing the base perimeter already decides — the base refuses a
#: non-declared tool or resource before these rules run, so a fact that could
#: never be true here would be a rule nobody can evaluate.
PREDICATS: frozenset[str] = frozenset(
    {
        "scenario",
        "mode",
        "sortie_reseau",
        "outil",
        "destination",
        "appels_restants",
        "jetons_restants",
        "tentatives_hostiles",
        "duree_ecoulee",
    }
)

#: How a fact may be compared. `vrai`/`faux` need no value; `egal`/`different`
#: compare equality; `contient` checks a substring; `au_moins`/`au_plus` are
#: numeric thresholds.
COMPARAISONS: frozenset[str] = frozenset(
    {"vrai", "faux", "egal", "different", "contient", "au_moins", "au_plus"}
)

#: What a rule does when its conditions hold.
EFFETS: frozenset[str] = frozenset({"refuser", "autoriser_sous_condition"})


class ErreurPolitique(ValueError):
    """A rule file that cannot be applied is refused, never repaired."""


@dataclass(frozen=True, slots=True)
class Condition:
    """One structured fact and how it is compared."""

    fait: str
    comparaison: str
    valeur: Any = None

    def verifie(self, etat: dict[str, Any]) -> bool:
        observe = etat.get(self.fait)
        if self.comparaison == "vrai":
            return bool(observe)
        if self.comparaison == "faux":
            return not observe
        if self.comparaison == "egal":
            return observe == self.valeur
        if self.comparaison == "different":
            return observe != self.valeur
        if self.comparaison == "contient":
            return isinstance(observe, str) and str(self.valeur) in observe
        if self.comparaison == "au_moins":
            return _numerique(observe) is not None and _numerique(observe) >= _valeur_numerique(self.valeur)
        if self.comparaison == "au_plus":
            return _numerique(observe) is not None and _numerique(observe) <= _valeur_numerique(self.valeur)
        raise ErreurPolitique(f"comparaison inconnue : {self.comparaison!r}")


def _numerique(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _valeur_numerique(valeur: Any) -> float | None:
    nombre = _numerique(valeur)
    if nombre is None:
        raise ErreurPolitique(f"valeur numérique attendue, reçu {valeur!r}")
    return nombre


@dataclass(frozen=True, slots=True)
class Regle:
    """One rule: when it fires, what it decides, and how it says so."""

    id: str
    effet: str
    conditions: tuple[Condition, ...]
    regle_appliquee: str
    motif: str

    def declenche(self, etat: dict[str, Any]) -> bool:
        return all(condition.verifie(etat) for condition in self.conditions)


@dataclass(frozen=True, slots=True)
class Programme:
    """The additive program: the rules, in the order they are evaluated."""

    regles: tuple[Regle, ...] = ()


def charger_programme(chemin: str | Path | None = None) -> Programme:
    """Read the rule program. An unknown key is refused, never ignored.

    The scenario loader learned this the hard way: a YAML key that the code
    does not read is a promise nobody keeps — it fails silently, the rule is
    simply not applied, and the report says nothing about it.
    """
    import yaml

    source = Path(chemin) if chemin is not None else FICHIER_DEFAUT
    donnees = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    inconnues = set(donnees) - {"regles_politique"}
    if inconnues:
        raise ErreurPolitique(
            f"clés inconnues dans {source.name} : {', '.join(sorted(inconnues))}. "
            "Une clé que le moteur ne lit pas est une règle qui ne s'applique pas."
        )
    regles = tuple(_regle(d, index) for index, d in enumerate(donnees.get("regles_politique", ())))
    ids = [r.id for r in regles]
    doublons = {i for i in ids if ids.count(i) > 1}
    if doublons:
        raise ErreurPolitique(f"identifiants de règles en double : {', '.join(sorted(doublons))}")
    return Programme(regles=regles)


def _regle(donnees: dict[str, Any], index: int) -> Regle:
    """One rule of the file, checked field by field."""
    connues = {"id", "effet", "quand", "regle", "motif"}
    inconnues = set(donnees) - connues
    if inconnues:
        raise ErreurPolitique(f"règle #{index} : clés inconnues {', '.join(sorted(inconnues))}.")
    identifiant = str(donnees.get("id", "")).strip()
    if not identifiant:
        raise ErreurPolitique(f"règle #{index} : identifiant manquant")
    effet = str(donnees.get("effet", "refuser"))
    if effet not in EFFETS:
        raise ErreurPolitique(
            f"règle « {identifiant} » : effet {effet!r} inconnu (attendu : {', '.join(sorted(EFFETS))})."
        )
    regle_appliquee = str(donnees.get("regle", "")).strip()
    if not regle_appliquee:
        raise ErreurPolitique(f"règle « {identifiant} » : nom de règle manquante")
    # A refusal must be classable. `autoriser_sous_condition` gates nothing, so
    # it carries a condition label, not a refusal name.
    if effet == "refuser" and regle_appliquee not in REGLES_PERIMETRE | REGLES_BORNAGE:
        raise ErreurPolitique(
            f"règle « {identifiant} » : « {regle_appliquee} » n'est une règle connue ni de périmètre "
            "ni de bornage — un refus doit être classable (EF-22)."
        )
    conditions = tuple(_condition(c, identifiant) for c in donnees.get("quand", ()))
    if not conditions:
        raise ErreurPolitique(f"règle « {identifiant} » : aucune condition — elle ne déclencherait jamais")
    return Regle(
        id=identifiant,
        effet=effet,
        conditions=conditions,
        regle_appliquee=regle_appliquee,
        motif=str(donnees.get("motif", "")),
    )


def _condition(donnees: dict[str, Any], identifiant: str) -> Condition:
    connues = {"fait", "comparaison", "valeur"}
    inconnues = set(donnees) - connues
    if inconnues:
        raise ErreurPolitique(
            f"règle « {identifiant} » : clés de condition inconnues {', '.join(sorted(inconnues))}."
        )
    fait = str(donnees.get("fait", ""))
    if fait not in PREDICATS:
        raise ErreurPolitique(
            f"règle « {identifiant} » : fait {fait!r} inconnu — "
            f"le vocabulaire fermé est : {', '.join(sorted(PREDICATS))}."
        )
    comparaison = str(donnees.get("comparaison", "vrai"))
    if comparaison not in COMPARAISONS:
        raise ErreurPolitique(
            f"règle « {identifiant} » : comparaison {comparaison!r} inconnue "
            f"(attendu : {', '.join(sorted(COMPARAISONS))})."
        )
    valeur = donnees.get("valeur")
    if comparaison in ("au_moins", "au_plus") and _numerique(valeur) is None:
        raise ErreurPolitique(
            f"règle « {identifiant} » : la comparaison {comparaison!r} exige une valeur numérique, "
            f"reçu {valeur!r}."
        )
    return Condition(fait=fait, comparaison=comparaison, valeur=valeur)


def etat(
    contexte: ContexteAppel,
    faits_session: FaitsSession,
    *,
    scenario_id: str | None = None,
) -> dict[str, Any]:
    """The structured facts an additive rule is evaluated against.

    These are exactly the facts the base perimeter does **not** already decide:
    the identity of the call, the counters of the session, and the scenario.
    """
    return {
        "scenario": scenario_id or "",
        "mode": faits_session.mode.value if hasattr(faits_session.mode, "value") else str(faits_session.mode),
        "sortie_reseau": bool(contexte.sortie_reseau),
        "outil": contexte.outil,
        "destination": contexte.destination,
        "appels_restants": int(faits_session.appels_restants),
        "jetons_restants": int(faits_session.jetons_restants),
        "tentatives_hostiles": int(faits_session.tentatives_hostiles),
        "duree_ecoulee": float(faits_session.duree_ecoulee_secondes),
    }
