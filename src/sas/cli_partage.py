"""Shared plumbing for the CLI commands: load the demo context, run a campaign,
analyse it. One implementation, used by `sas smoke`, `sas demo` and the tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sas import constantes
from sas.agentcore.ports import AgentInvite
from sas.homologation import Dossier, analyser
from sas.manifeste import charger
from sas.orchestrateur import Campagne, nouvelle_campagne
from sas.scenarios import Scenario, charger_tous
from sas.store.base import Depot
from sas.types import Manifeste

RACINE = Path(__file__).resolve().parents[2]
FIXTURE_MANIFESTE = RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml"
LEURRES_SENSIBLES: tuple[str, ...] = ("rh-ombre", "remuneration", "salaire")
LEURRES_MARQUES: tuple[str, ...] = ("config-ombre/app.conf", "rh-ombre/grille-2026.csv")


@dataclass(frozen=True, slots=True)
class Contexte:
    manifeste: Manifeste
    scenarios: tuple[Scenario, ...]


def charger_contexte(scenarios: Sequence[str] = ()) -> Contexte:
    """The reference manifest (annexe A) and the scenarios of annexe B."""
    manifeste = charger(FIXTURE_MANIFESTE).manifeste
    tous = charger_tous()
    if scenarios:
        tous = tuple(s for s in tous if s.id in set(scenarios))
    return Contexte(manifeste=manifeste, scenarios=tous)


def lancer(
    *,
    agent: AgentInvite,
    contexte: Contexte,
    rejeux: int = constantes.N_DEVELOPPEMENT,
    graine: int = 7,
    tenant_id: str = "tenant-demo",
    depot: Depot | None = None,
    rang_du_jour: int = 1,
) -> Dossier:
    """Run one shadow campaign and analyse it end to end."""
    campagne = nouvelle_campagne(
        tenant_id=tenant_id,
        agent_id=contexte.manifeste.agent_id,
        manifeste=contexte.manifeste,
        n_rejeux=rejeux,
        graine=graine,
        scenarios=[s.id for s in contexte.scenarios],
        variante=agent.nom,
    )
    resultat = Campagne(
        campagne=campagne,
        manifeste=contexte.manifeste,
        agent=agent,
        scenarios=contexte.scenarios,
        depot=depot,
    ).executer()
    return analyser(
        resultat,
        manifeste=contexte.manifeste,
        tenant_id=tenant_id,
        ressources_sensibles=LEURRES_SENSIBLES,
        leurres=LEURRES_MARQUES,
        graine=graine,
        rang_du_jour=rang_du_jour,
    )


def invite(nom: str, **parametres: object) -> AgentInvite:
    """Build a demo guest. Kept here so the CLI never imports `demo` twice.

    `demo/` lives at the repository root, not inside `src/`: the root is added
    to the import path here, once, rather than in every caller.
    """
    import sys

    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    from demo.agents import construire

    return construire(nom, **parametres)


def etiquette_synthese() -> str:
    return constantes.ETIQUETTE_SYNTHETIQUE
