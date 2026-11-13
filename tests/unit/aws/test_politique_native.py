"""La syntaxe native de la policy AgentCore : grammaire et concordance.

Deux choses sont prouvées ici, et rien de plus :

* **la grammaire** — un document JSON se lit, se valide, et un document mal
  écrit est refusé au lieu d'être réinventé ;
* **la concordance** — le moteur natif (`sas.agentcore.politique_native`) rend
  la **même décision** que le moteur local (`PolicyLocale`) pour les mêmes
  faits, sur les scénarios du dépôt. C'est la preuve que la grammaire sait
  porter le périmètre.

Ce que ces tests ne prouvent **pas** : que cette syntaxe est celle d'AgentCore
Policy. Ça demande un test exécuté contre la vraie API AWS — le point 2 du
§34, qui reste ouvert, et que `docs/ECHECS.md` dit tel quel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from sas.agentcore import ports
from sas.agentcore.politique_manifeste import PolicyLocale, deriver
from sas.agentcore.politique_native import (
    ErreurSyntaxeNative,
    PolicyNative,
    document_natif,
    document_natif_depuis_manifeste,
    vers_json,
)
from sas.scenarios import Scenario, charger_metier, charger_tous
from sas.types import (
    ContexteAppel,
    Decision,
    DecisionPolitique,
    FaitsSession,
    Manifeste,
    Mode,
    Politique,
    StatutManifeste,
)

RACINE = Path(__file__).resolve().parents[3]
FIXTURE = RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml"

#: La sortie que le scénario S8 essaie de faire : elle n'est pas déclarée.
DESTINATION_NON_DECLAREE = "https://paie.exemple.invalid"


# --------------------------------------------------------------------------- #
# Les parties du test
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def manifeste() -> Manifeste:
    from sas.manifeste import charger

    return charger(FIXTURE).manifeste


@pytest.fixture(scope="module")
def politique(manifeste: Manifeste) -> Politique:
    return deriver(manifeste, Mode.OMBRE)


@pytest.fixture(scope="module")
def moteur_local(politique: Politique) -> PolicyLocale:
    return PolicyLocale(politique)


@pytest.fixture(scope="module")
def moteur_natif(politique: Politique) -> PolicyNative:
    return PolicyNative(document_natif(politique))


# --------------------------------------------------------------------------- #
# La grammaire : ce qui se lit, et ce qui est refusé
# --------------------------------------------------------------------------- #


def test_un_document_avec_une_cle_inconnue_est_refuse() -> None:
    document = document_natif_depuis_manifeste(_manifeste())
    document["effet_special"] = "allow"
    with pytest.raises(ErreurSyntaxeNative, match="clés inconnues"):
        PolicyNative(document)


def test_un_format_inconnu_est_refuse() -> None:
    document = document_natif_depuis_manifeste(_manifeste())
    document["version"] = "1999"
    with pytest.raises(ErreurSyntaxeNative, match="format de policy natif inconnu"):
        PolicyNative(document)


def test_un_json_illisible_est_refuse() -> None:
    with pytest.raises(ErreurSyntaxeNative, match="illisible"):
        PolicyNative.depuis_json("{ceci n'est pas du json")


def test_un_outil_en_double_est_refuse() -> None:
    document = document_natif_depuis_manifeste(_manifeste())
    document["tools"].append(dict(document["tools"][0]))
    with pytest.raises(ErreurSyntaxeNative, match="en double"):
        PolicyNative(document)


def test_un_budget_negatif_est_refuse() -> None:
    document = document_natif_depuis_manifeste(_manifeste())
    document["budgets"]["appels"] = -1
    with pytest.raises(ErreurSyntaxeNative, match=r"budgets\.appels"):
        PolicyNative(document)


def test_un_effet_par_defaut_qui_autorise_est_refuse() -> None:
    document = document_natif_depuis_manifeste(_manifeste())
    document["default"] = "allow"
    with pytest.raises(ErreurSyntaxeNative, match="refuse par défaut"):
        PolicyNative(document)


def test_le_document_derive_du_manifeste_porte_le_perimetre(politique: Politique) -> None:
    """EF-05 : le document natif et la politique locale portent le même périmètre."""
    document = document_natif(politique)
    assert document["agent"] == politique.agent_id
    assert document["manifest"]["version"] == politique.manifeste_version
    assert [outil["id"] for outil in document["tools"]] == [regle.outil for regle in politique.regles]
    assert document["tools"][0]["resources"] == list(politique.regles[0].ressources)
    assert document["outputs"] == list(politique.sorties_autorisees)
    assert document["budgets"]["appels"] == (
        politique.budgets.appels_par_execution if politique.budgets else 0
    )


def test_le_document_tient_en_json_et_se_relit(moteur_natif: PolicyNative, politique: Politique) -> None:
    """Le document natif circule en JSON : il se sérialise et se relit."""
    texte = vers_json(moteur_natif.document())
    relu = PolicyNative.depuis_json(texte)
    assert relu.document() == moteur_natif.document()
    assert relu.outils() == moteur_natif.outils()
    assert relu.version_manifeste() == politique.manifeste_version


def test_le_moteur_natif_satisfait_le_port(moteur_natif: PolicyNative) -> None:
    assert isinstance(moteur_natif, ports.Policy)


def test_le_coupe_circuit_du_moteur_natif_refuse_la_suivant(politique: Politique) -> None:
    """Un moteur neuf : le coupe-circuit ne doit pas fuir d'un test à l'autre."""
    moteur = PolicyNative(document_natif(politique))
    moteur.suspendre(politique.agent_id, "test")
    assert moteur.suspendu(politique.agent_id) is True
    decision = moteur.evaluer(_contexte("lire_ticket"), _faits(politique))
    assert decision.regle_appliquee == "suspension"
    moteur.reprendre(politique.agent_id)
    assert moteur.evaluer(_contexte("lire_ticket"), _faits(politique)).decision is Decision.AUTORISE


def test_policy_aws_evaluer_agentcore_natif_rend_encore_none() -> None:
    """§34 point 2 reste ouvert : tant qu'AWS n'a pas confirmé, rien n'est branché."""
    from sas.agentcore import aws

    assert aws.PolicyAWS().evaluer_agentcore_natif(_contexte("lire_ticket"), _faits(None)) is None


# --------------------------------------------------------------------------- #
# La concordance : les deux moteurs, les mêmes faits, la même décision
# --------------------------------------------------------------------------- #


#: Tous les scénarios du dépôt : les huit de l'annexe B et le scénario métier.
SCENARIOS = charger_tous() + charger_metier()


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_les_deux_moteurs_concordent_sur_les_scenarios(
    scenario: Scenario,
    politique: Politique,
    moteur_local: PolicyLocale,
    moteur_natif: PolicyNative,
) -> None:
    cas = _cas(scenario, politique)
    for nom, contexte, faits in cas:
        local = moteur_local.evaluer(contexte, faits)
        natif = moteur_natif.evaluer(contexte, faits)
        assert _cle(local) == _cle(natif), f"{scenario.id} / {nom} : les deux moteurs divergent"


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda scenario: scenario.id)
def test_les_cas_du_scenario_ne_sont_pas_vides(
    scenario: Scenario,
    politique: Politique,
    moteur_local: PolicyLocale,
) -> None:
    """Une concordance qui refuserait tout ne prouverait rien."""
    cas = _cas(scenario, politique)
    regles = {moteur_local.evaluer(contexte, faits).regle_appliquee for _, contexte, faits in cas}
    assert "manifeste:autorise" in regles
    assert len(regles - {"manifeste:autorise"}) >= 4


# --------------------------------------------------------------------------- #
# Les cas : un par scénario, tirés de ses propres données
# --------------------------------------------------------------------------- #


def _manifeste() -> Manifeste:
    from sas.manifeste import charger

    return charger(FIXTURE).manifeste


def _cle(decision: DecisionPolitique) -> tuple[Any, ...]:
    """Ce sur quoi les deux moteurs doivent s'accorder : verdict, règle, marqueur."""
    return (decision.decision, decision.regle_appliquee, decision.usage_non_declare)


def _contexte(outil: str, **champs: Any) -> ContexteAppel:
    return ContexteAppel(outil=outil, **champs)


def _faits(politique: Politique | None, **surcharges: Any) -> FaitsSession:
    budgets = politique.budgets if politique is not None else None
    base: dict[str, Any] = {
        "manifeste_statut": StatutManifeste.VALIDE,
        "manifeste_version": politique.manifeste_version if politique else 1,
        "version_courante": politique.manifeste_version if politique else 1,
        "suspension": False,
        "appels_restants": budgets.appels_par_execution if budgets else 25,
        "jetons_restants": budgets.jetons_par_execution if budgets else 60_000,
        "duree_ecoulee_secondes": 0.0,
        "duree_maximale_secondes": budgets.duree_maximale_secondes if budgets else 180,
        "mode": Mode.OMBRE,
    }
    base.update(surcharges)
    return FaitsSession(**base)


def _declares(politique: Politique) -> set[str]:
    return {regle.outil for regle in politique.regles}


def _outil_nominal(scenario: Scenario, politique: Politique) -> str:
    """L'outil que le scénario attend, quand le manifeste le déclare."""
    declares = _declares(politique)
    for resultat in scenario.resultats_attendus:
        for outil in resultat.outils:
            if outil in declares:
                return outil
    return sorted(declares)[0]


def _outil_interdit(scenario: Scenario, politique: Politique) -> str | None:
    """L'outil que le scénario interdit, et que le manifeste ne déclare pas."""
    declares = _declares(politique)
    for resultat in scenario.resultats_attendus:
        for outil in resultat.outils_interdits:
            if outil not in declares:
                return outil
    return None


def _ressource_nominale(politique: Politique, outil: str) -> str:
    for regle in politique.regles:
        if regle.outil == outil and regle.ressources:
            return regle.ressources[0]
    return ""


def _cas(scenario: Scenario, politique: Politique) -> list[tuple[str, ContexteAppel, FaitsSession]]:
    """Les cas d'un scénario : le nominal, les refus, et les faits bornés."""
    outil = _outil_nominal(scenario, politique)
    ressource = _ressource_nominale(politique, outil)
    nominal = _contexte(outil, ressources=(ressource,)) if ressource else _contexte(outil)
    cas: list[tuple[str, ContexteAppel, FaitsSession]] = [
        ("nominal", nominal, _faits(politique)),
        (
            "ressource hors périmètre",
            _contexte(outil, ressources=("arn:aws:s3:::autre-client/secret/*",)),
            _faits(politique),
        ),
        ("colonne non déclarée", _contexte(outil, colonnes=("salaire_net",)), _faits(politique)),
        (
            "sortie non déclarée",
            _contexte("sortie:https", sortie_reseau=True, destination=DESTINATION_NON_DECLAREE),
            _faits(politique),
        ),
        ("suspension", nominal, _faits(politique, suspension=True)),
        ("budget d'appels épuisé", nominal, _faits(politique, appels_restants=0)),
        ("budget de jetons épuisé", nominal, _faits(politique, jetons_restants=0)),
        ("durée dépassée", nominal, _faits(politique, duree_ecoulee_secondes=180.0)),
        ("manifeste non valide", nominal, _faits(politique, manifeste_statut=StatutManifeste.BROUILLON)),
        ("manifeste périmé", nominal, _faits(politique, version_courante=2)),
    ]
    interdit = _outil_interdit(scenario, politique)
    if interdit is not None:
        cas.insert(1, ("outil non déclaré", _contexte(interdit), _faits(politique)))
    return cas
