"""Proposing a manifest from what an agent actually did (read-only observation).

The chicken-and-egg of a vendor integration: the editor must declare a
perimeter, but the perimeter is only knowable by watching the agent work. This
module watches — **read-only**, on an observation journal, never by running
anything — and produces a **draft** manifest: the tools actually used, the
resources actually touched, budgets derived from what was observed.

Three things it will not do, and says so in the draft itself:

* it does not **sign**. A draft has no signature, `sas.manifeste.validation`
  refuses it, and only the editor may sign (§9.3, EF-03);
* it does not **declare** anything that was not observed. A resource never
  touched is not proposed — that would turn a permissive guess into a signed
  permission;
* it does not **guess the purpose**. The justification it writes is a count, not
  a reason: "observed 12 times over 48 replays". What the resource is *for* is
  the editor's to say.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from sas.identifiants import canonique, empreinte

FACTEUR_BUDGET = 1.2
MARQUEUR_BROUILLON = "BROUILLON — à relire, compléter et signer par l'éditeur"


@dataclass(frozen=True, slots=True)
class Observation:
    """What a read-only observation of a journal shows."""

    outils: Counter[str] = field(default_factory=Counter)
    ressources: Counter[str] = field(default_factory=Counter)
    categories: Counter[str] = field(default_factory=Counter)
    sorties: Counter[str] = field(default_factory=Counter)
    sessions: int = 0
    replays: int = 0
    scenarios: tuple[str, ...] = ()
    appels: int = 0
    refus: int = 0

    @property
    def frequence_max(self) -> int:
        return max(self.outils.values(), default=0)


def observer(entrees: Iterable[Any]) -> Observation:
    """Read a journal and count what the agent did. Nothing else."""
    outils: Counter[str] = Counter()
    ressources: Counter[str] = Counter()
    sorties: Counter[str] = Counter()
    sessions: set[str] = set()
    scenarios: set[str] = set()
    appels = 0
    refus = 0
    for entree in entrees:
        appels += 1
        sessions.add(str(getattr(entree, "session_id", "")))
        scenarios.add(str(getattr(entree, "scenario_id", "")))
        decision = getattr(getattr(entree, "decision", None), "value", "")
        if decision == "refuse":
            refus += 1
        outil = str(getattr(entree, "outil", ""))
        if decision != "refuse" and outil:
            outils[outil] += 1
        if decision == "refuse" and outil and not outil.startswith("sortie"):
            # A refused call still shows what the agent TRIED to reach: it is
            # exactly what the manifest should forbid.
            outils[outil] += 1
        for ressource in getattr(entree, "ressources", ()) or ():
            if decision != "refuse":
                ressources[ressource] += 1
        if getattr(entree, "sortie_reseau", False):
            destination = str(getattr(entree, "destination", ""))
            if destination:
                sorties[destination] += 1
    return Observation(
        outils=outils,
        ressources=ressources,
        sorties=sorties,
        sessions=len(sessions),
        replays=len(sessions),
        scenarios=tuple(sorted(scenarios)),
        appels=appels,
        refus=refus,
    )


def proposer(observation: Observation, *, editeur: str = "à compléter") -> dict[str, Any]:
    """Build the draft manifest. A dict, deliberately: a `Manifeste` would be
    signable, and this must not be."""
    return {
        "manifeste": {"version": 1, "date": None},
        "identite": _identite(editeur),
        "finalite": {"fait": "à rédiger par l'éditeur", "ne_fait_pas": []},
        "outils_demandes": _outils(observation),
        "donnees_demandees": _donnees(observation),
        # Nothing was observed leaving the account, so nothing is declared as
        # allowed to leave it. A guess here would be a permission nobody granted.
        "sorties_autorisees": [],
        "budgets": _budgets(observation),
        "memoire": {"persistante": False},
        "scenarios": [{"id": identifiant, "nom": identifiant} for identifiant in observation.scenarios],
        "interdictions_explicites": [],
        "engagements": _engagements(),
        "signature": None,
        "validation_client": None,
        "_brouillon": _brouillon(observation),
    }


def _identite(editeur: str) -> dict[str, Any]:
    return {
        "nom": "à compléter",
        "editeur": editeur,
        "version_agent": "à compléter",
        "empreinte_paquet": "à compléter",
        "modele": "à compléter",
        "version_modele": "à compléter",
        "engagement_notification_modele": True,
    }


def _outils(observation: Observation) -> list[dict[str, Any]]:
    return [
        {
            "nom": nom,
            "operation": "lecture" if nom.startswith(("lire", "chercher")) else "ecriture",
            "justification": _justification(observation.outils[nom], observation.replays),
        }
        for nom in sorted(observation.outils)
    ]


def _donnees(observation: Observation) -> list[dict[str, Any]]:
    return [
        {
            "type": _type_de(ressource),
            "ressource": ressource,
            "justification": _justification(observation.ressources[ressource], observation.replays),
        }
        for ressource in sorted(observation.ressources)
    ]


def _budgets(observation: Observation) -> dict[str, Any]:
    return {
        "appels_par_execution": max(1, int(observation.frequence_max * FACTEUR_BUDGET)),
        "jetons_par_execution": 60_000,
        "duree_maximale_secondes": 180,
        "memoire_maximale_mio": 512,
    }


def _engagements() -> dict[str, Any]:
    return {
        "notification_changement_modele": "à compléter",
        "notification_changement_invite": "à compléter",
        "delai_correction_critique": "à compléter",
        "contact": "à compléter",
    }


def _brouillon(observation: Observation) -> dict[str, Any]:
    return {
        "marqueur": MARQUEUR_BROUILLON,
        "observation": {
            "appels": observation.appels,
            "refus": observation.refus,
            "sessions": observation.sessions,
            "scenarios": list(observation.scenarios),
            "empreinte_observation": empreinte(canonique(_projetable(observation))),
        },
    }


def _justification(compte: int, replays: int) -> str:
    """A count, not a reason. The editor writes the reason."""
    if not replays:
        return f"observé {compte} fois"
    return f"observé {compte} fois sur {replays} session(s) ; la finalité reste à rédiger"


def _type_de(ressource: str) -> str:
    cible = ressource.lower()
    if cible.startswith("dynamodb:"):
        return "table"
    if cible.startswith("s3://"):
        return "s3"
    if "index" in cible or cible.startswith("kb-"):
        return "index"
    return "s3"


def _projetable(observation: Observation) -> dict[str, Any]:
    return {
        "outils": dict(sorted(observation.outils.items())),
        "ressources": dict(sorted(observation.ressources.items())),
        "sorties": dict(sorted(observation.sorties.items())),
        "sessions": observation.sessions,
        "appels": observation.appels,
        "refus": observation.refus,
    }


def sorties_observées(observation: Observation) -> tuple[str, ...]:
    """The destinations the agent TRIED to reach — for the editor to declare or
    forbid, never to be granted by default."""
    return tuple(sorted(observation.sorties))
