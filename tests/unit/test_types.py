"""Lot 0 — the frozen domain types behave as the contracts promise."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

import sas.types as types
from sas.types import (
    SEVERITE,
    Budgets,
    Decision,
    EntreeJournal,
    Mode,
    Nature,
    StatutManifeste,
    Verdict,
)


def toutes_les_dataclasses() -> list[type]:
    return [
        valeur
        for nom, valeur in vars(types).items()
        if dataclasses.is_dataclass(valeur) and isinstance(valeur, type) and not nom.startswith("_")
    ]


def test_toutes_les_dataclasses_sont_gelees() -> None:
    """A measurement can never be edited after the fact (spec §22.1)."""
    non_gelees = [c.__name__ for c in toutes_les_dataclasses() if not c.__dataclass_params__.frozen]
    assert non_gelees == []


def test_au_moins_trente_entites_du_modele() -> None:
    """The data model of §22 must be fully typed before the lots start."""
    assert len(toutes_les_dataclasses()) >= 30


def test_une_dataclasse_gelee_refuse_la_mutation() -> None:
    budgets = Budgets(
        appels_par_execution=25,
        jetons_par_execution=60_000,
        duree_maximale_secondes=180,
        memoire_maximale_mio=512,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        budgets.appels_par_execution = 999  # type: ignore[misc]


def test_severite_couvre_les_cinq_natures() -> None:
    """§13.1 — every nature has a severity, including the undetermined one."""
    assert set(SEVERITE) == set(Nature)
    assert SEVERITE[Nature.HOSTILE] == "critique"
    assert SEVERITE[Nature.EXPLORATION] == "aucune"
    assert SEVERITE[Nature.INDETERMINEE] == "revue_humaine"


def test_valeurs_des_enumerations_stables() -> None:
    """Reports, API and IaC quote these strings; they are part of the contract."""
    assert [m.value for m in Mode] == ["ombre", "observe"]
    assert Decision.REFUSE.value == "refuse"
    assert StatutManifeste.VALIDE.value == "valide"
    assert {v.value for v in Verdict} == {
        "homologue",
        "homologue_sous_conditions",
        "refuse",
        "non_mesurable",
    }


def test_les_natures_sont_celles_du_chapitre_13() -> None:
    assert [n.value for n in Nature] == [
        "exploration",
        "debordement",
        "tentative",
        "hostile",
        "indeterminee",
    ]


def _entree(**modifications: object) -> EntreeJournal:
    base: dict[str, object] = {
        "id": "appel-1",
        "tenant_id": "tenant-1",
        "session_id": "sess-1",
        "campagne_id": "camp-1",
        "agent_id": "agent-1",
        "agent_version": "3.4.1",
        "scenario_id": "S1",
        "numero_rejeu": 1,
        "parent_id": None,
        "outil": "lire_ticket",
        "parametres": {},
        "decision": Decision.AUTORISE,
        "regle_appliquee": "manifeste:outils",
        "resultat": {},
        "horodatage": datetime(2026, 11, 27, 9, 12, tzinfo=UTC),
        "latence_ms": 12.0,
        "jetons": 4600,
    }
    base.update(modifications)
    return EntreeJournal(**base)  # type: ignore[arg-type]


def test_une_entree_de_journal_porte_toute_la_chaine_causale() -> None:
    """§17.1 — the fields a report needs, no more guessing later."""
    entree = _entree(parent_id="appel-0", sortie_reseau=True, destination="https://x.invalid")
    assert entree.parent_id == "appel-0"
    assert entree.sortie_reseau is True
    assert entree.destination == "https://x.invalid"
    assert entree.empreinte_prec == ""


def test_les_champs_libres_sont_immuables() -> None:
    entree = _entree(parametres={"a": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        entree.parametres = {}  # type: ignore[misc]
