"""The configurable policy engine (lot 6).

Two things must stay true, and these tests pin both:

* the manifest perimeter never widens — an additive rule can refuse, or
  authorise under a condition, but it can never authorise what the manifest
  did not declare;
* the loader refuses what it cannot evaluate, instead of ignoring it — the
  lesson the scenario loader learned the hard way (a silently ignored key is a
  promise nobody keeps).
"""

from __future__ import annotations

from typing import Any

import pytest

from sas.politique import ErreurPolitique, MoteurPolitique, Programme, charger_programme
from sas.politique.programme import Condition, Regle
from sas.types import (
    ContexteAppel,
    Decision,
    FaitsSession,
    Mode,
    Politique,
    ReglePolitique,
    StatutManifeste,
)


def _politique() -> Politique:
    return Politique(
        agent_id="agent-1",
        manifeste_version=1,
        regles=(
            ReglePolitique(id="outil-t", outil="lire_ticket", effet=Decision.AUTORISE, origine="manifeste"),
        ),
        sorties_autorisees=(),
        mode=Mode.OMBRE,
    )


def _faits(
    *, appels_restants: int = 5, tentatives_hostiles: int = 0, mode: Mode = Mode.OMBRE
) -> FaitsSession:
    return FaitsSession(
        manifeste_statut=StatutManifeste.VALIDE,
        manifeste_version=1,
        version_courante=1,
        suspension=False,
        appels_restants=appels_restants,
        jetons_restants=1000,
        duree_ecoulee_secondes=0.0,
        duree_maximale_secondes=180,
        mode=mode,
        tentatives_hostiles=tentatives_hostiles,
    )


def _contexte(outil: str = "lire_ticket", *, sortie: bool = False, destination: str = "") -> ContexteAppel:
    return ContexteAppel(outil=outil, sortie_reseau=sortie, destination=destination)


def _moteur(regles: tuple[Regle, ...], scenario_id: str | None = None) -> MoteurPolitique:
    return MoteurPolitique(_politique(), programme=Programme(regles=regles), scenario_id=scenario_id)


# --------------------------------------------------------------------------- #
# The loader refuses what it cannot evaluate
# --------------------------------------------------------------------------- #


def test_un_fait_inconnu_est_refuse_pas_ignore() -> None:
    with pytest.raises(ErreurPolitique, match="inconnu"):
        charger_programme_via(
            regles=[{"id": "x", "effet": "refuser", "quand": [{"fait": "inexistant"}], "regle": "suspension"}]
        )


def test_une_cle_inconnue_dans_une_regle_est_refusee() -> None:
    with pytest.raises(ErreurPolitique, match="clés inconnues"):
        charger_programme_via(
            regles=[
                {
                    "id": "x",
                    "effet": "refuser",
                    "faute": True,
                    "quand": [{"fait": "sortie_reseau"}],
                    "regle": "suspension",
                }
            ]
        )


def test_un_refus_doit_nommer_une_regle_classable() -> None:
    with pytest.raises(ErreurPolitique, match="classable"):
        charger_programme_via(
            regles=[
                {
                    "id": "x",
                    "effet": "refuser",
                    "quand": [{"fait": "sortie_reseau", "comparaison": "vrai"}],
                    "regle": "regle-inventee",
                }
            ]
        )


def test_une_condition_sans_comparaison_defaut_vrai() -> None:
    programme = charger_programme_via(
        regles=[{"id": "x", "effet": "refuser", "quand": [{"fait": "sortie_reseau"}], "regle": "suspension"}]
    )
    condition = programme.regles[0].conditions[0]
    assert condition.comparaison == "vrai"
    assert condition.verifie({"sortie_reseau": True})


def test_au_moins_exige_une_valeur_numerique() -> None:
    with pytest.raises(ErreurPolitique, match="numérique"):
        charger_programme_via(
            regles=[
                {
                    "id": "x",
                    "effet": "refuser",
                    "quand": [
                        {"fait": "tentatives_hostiles", "comparaison": "au_moins", "valeur": "beaucoup"}
                    ],
                    "regle": "suspension",
                }
            ]
        )


def charger_programme_via(regles: list[dict[str, Any]]) -> Programme:
    """Build a Programme through the real loader, from a temp file.

    Going through a file exercises the same strict path the product takes, so
    the test proves the loader refuses what it refuses, not a private helper.
    """
    import tempfile
    from pathlib import Path

    import yaml

    with tempfile.TemporaryDirectory() as repertoire:
        chemin = Path(repertoire) / "politique.yaml"
        chemin.write_text(yaml.safe_dump({"regles_politique": regles}), encoding="utf-8")
        return charger_programme(chemin)


# --------------------------------------------------------------------------- #
# The additive rules narrow, never widen
# --------------------------------------------------------------------------- #


def test_une_regle_additive_peut_refuser_un_appel_autorise() -> None:
    regle = Regle(
        id="s5",
        effet="refuser",
        conditions=(Condition("scenario", "egal", "S5"),),
        regle_appliquee="sortie-non-declaree",
        motif="S5",
    )
    moteur = _moteur((regle,), scenario_id="S5")
    decision = moteur.evaluer(_contexte(sortie=True, destination="https://x"), _faits())
    assert decision.decision is Decision.REFUSE
    assert decision.regle_appliquee == "sortie-non-declaree"


def test_une_regle_scenarisee_ne_s_applique_pas_aux_autres() -> None:
    regle = Regle(
        id="s5",
        effet="refuser",
        conditions=(Condition("scenario", "egal", "S5"),),
        regle_appliquee="sortie-non-declaree",
        motif="S5",
    )
    moteur = _moteur((regle,), scenario_id="S8")
    decision = moteur.evaluer(_contexte(), _faits())
    assert decision.decision is Decision.AUTORISE


def test_un_non_declare_reste_refuse_par_le_perimetre() -> None:
    """The additive layer cannot rescue a non-declared call: the base refuses it
    first, whatever rules are loaded."""
    regle = Regle(
        id="tout-autoriser-ne-peut-pas-exister",
        effet="autoriser_sous_condition",
        conditions=(Condition("outil", "egal", "lire_ticket"),),
        regle_appliquee="rien",
        motif="",
    )
    moteur = _moteur((regle,))
    decision = moteur.evaluer(_contexte(outil="list_buckets"), _faits())
    assert decision.decision is Decision.REFUSE
    assert decision.regle_appliquee == "usage-non-declare"


def test_l_autorisation_sous_condition_est_emise_pour_une_regle_qui_mat_couple() -> None:
    regle = Regle(
        id="volume",
        effet="autoriser_sous_condition",
        conditions=(Condition("scenario", "egal", "S6"), Condition("outil", "egal", "lire_ticket")),
        regle_appliquee="sortie-declaree-sous-condition",
        motif="volume",
    )
    moteur = _moteur((regle,), scenario_id="S6")
    decision = moteur.evaluer(_contexte(), _faits())
    assert decision.decision is Decision.AUTORISE_SOUS_CONDITION
    assert decision.regle_appliquee == "sortie-declaree-sous-condition"
    assert decision.motif == "volume"


def test_le_programme_par_defaut_charge_sans_erreur() -> None:
    programme = charger_programme()
    assert programme.regles
    assert {r.effet for r in programme.regles} <= {"refuser", "autoriser_sous_condition"}


def test_suspension_partagee_entre_les_scenarios() -> None:
    moteur = _moteur((), scenario_id=None)
    vue = moteur.pour_scenario("S5")
    moteur.suspendre("agent-1", "test")
    assert vue.suspendu("agent-1")
    assert moteur.suspendu("agent-1")
