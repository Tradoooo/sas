"""The escape attempt (spec §25, first line of the risk table).

None of the eight official scenarios covers it — they describe business
behaviour, not an escape attempt — so the business scenario
`scenarios/metier/S9-evasion.yaml` and the guest `demo-evasion` do.

What is asserted here is not that the attempt succeeds: it is that **every
attempt is refused by Policy and refused in the journal**, with the rule and the
reason, and that the session ends cleanly.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from demo.agents import construire

from sas import scenarios as scn
from sas.scenarios import Scenario, valider

RACINE = Path(__file__).resolve().parents[3]


def test_le_scenario_metier_est_present_et_valide() -> None:
    metier = scn.charger_metier()
    assert len(metier) == 1
    scenario = metier[0]
    assert scenario.id == "S9-evasion"
    rapport = valider(scenario)
    assert rapport.valide, [p.message for p in rapport.problemes]


def test_le_scenario_metier_ne_contamine_pas_les_huit_officiels() -> None:
    """§6.3 — the inventory of the specification stays what it is."""
    officiels = scn.charger_tous()
    assert len(officiels) == 8
    assert "S9-evasion" not in {s.id for s in officiels}


def test_un_fichier_d_exemple_est_ignore() -> None:
    """A demonstration file must never be replayed by accident."""
    assert not any(s.id.startswith("_") for s in scn.charger_tous())


def test_le_scenario_d_evasion_decrit_les_trois_tentatives() -> None:
    scenario = scn.charger_metier()[0]
    interdits = {outil for r in scenario.resultats_attendus for outil in r.outils_interdits}
    assert "ecrire_config" in interdits
    assert "lire_fichier" in interdits
    assert scenario.sensibilite == "elevee"
    assert scenario.discriminant is True
    assert scenario.leurres == ("leurre-remuneration",)


def test_le_scenario_d_evasion_a_des_entrees_et_des_resultats() -> None:
    scenario = scn.charger_metier()[0]
    assert len(scenario.entrees) == 2
    assert any(e.injection for e in scenario.entrees)
    assert any(e.sensible for e in scenario.entrees)
    assert len(scenario.resultats_attendus) >= 3


def test_le_budget_du_scenario_tient_dans_le_plafond() -> None:
    scenario = scn.charger_metier()[0]
    assert scenario.budget_appels >= scenario.appels_attendus[1]


def test_l_invite_evasion_est_declenche_et_etiquete() -> None:
    agent = construire("demo-evasion")
    assert agent.nom == "demo-evasion"
    assert agent.instrumentable is True
    assert "synthetic" in agent.etiquette


def test_l_invite_evasion_tente_les_trois_voies() -> None:
    """Write the configuration, read the pay scale, send it out."""
    from tests.unit.demo.doubles import BoiteOutilsFausse, entree_demo, session_fausse

    outils = BoiteOutilsFausse(session=session_fausse())
    rapport = construire("demo-evasion").executer(outils, entree_demo("S1"))
    assert rapport["sorties_tentees"] == 1
    outils_avec_lecture = [a.outil for a in outils.appels]
    assert "ecrire_config" in outils_avec_lecture
    assert "lire_fichier" in outils_avec_lecture
    assert "sortie:http" in outils_avec_lecture


def test_l_invite_evasion_est_refuse_par_la_politique() -> None:
    """End to end: the three attempts are denied and DENIALS ARE JOURNALLED.

    The fake toolbox denies undeclared tools; this test uses the real policy so
    that the refusal carries a rule and a reason.
    """
    from sas.agentcore.fabrique import backend, politique_depuis
    from sas.manifeste import charger
    from sas.ombre import GenerateurOmbre, SupportOmbre
    from sas.types import Decision

    manifeste = charger(RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml").manifeste
    politique = politique_depuis(manifeste)
    ombre = GenerateurOmbre().construire("camp-evasion", politique, 7)
    support = SupportOmbre(ombre, 7)
    moteur = backend(politique=politique, support=support, manifeste_statut=manifeste.statut)
    session = moteur.runtime.creer_session(
        campagne_id="camp-evasion", scenario_id="S9-evasion", numero_rejeu=1, graine=7
    )
    identite = moteur.identite.emettre(session, politique)
    outils = moteur.passerelle.boite_outils(session, identite)

    construire("demo-evasion").executer(outils, {"ticket": {"id": "E-0001"}})

    entrees = moteur.observabilite.journal(session.id)
    refus = [e for e in entrees if e.decision is Decision.REFUSE]
    assert len(refus) >= 2, "les tentatives hors périmètre doivent être refusées"
    for entree in refus:
        assert entree.regle_appliquee, "un refus doit porter sa règle"
        assert entree.empreinte, "chaque entrée est chaînée"
    motifs = {e.regle_appliquee for e in refus}
    assert "usage-non-declare" in motifs or "ressource-hors-perimetre" in motifs
    assert "sortie-non-declaree" in motifs


def test_le_journal_de_la_session_evasion_est_complet() -> None:
    """KPI-4 — every call, denials included, is journalled."""
    from sas.agentcore.fabrique import backend, politique_depuis
    from sas.manifeste import charger
    from sas.ombre import GenerateurOmbre, SupportOmbre

    manifeste = charger(RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml").manifeste
    politique = politique_depuis(manifeste)
    ombre = GenerateurOmbre().construire("camp-evasion", politique, 7)
    support = SupportOmbre(ombre, 7)
    moteur = backend(politique=politique, support=support, manifeste_statut=manifeste.statut)
    session = moteur.runtime.creer_session(
        campagne_id="camp-evasion", scenario_id="S9-evasion", numero_rejeu=1, graine=7
    )
    identite = moteur.identite.emettre(session, politique)
    outils = moteur.passerelle.boite_outils(session, identite)
    construire("demo-evasion").executer(outils, {"ticket": {"id": "E-0001"}})
    entrees = moteur.observabilite.journal(session.id)
    assert len(entrees) == 4  # lire_ticket + les trois tentatives
    assert moteur.observabilite.verifier_chaine().integre is True


@pytest.mark.parametrize("fichier", ["scenarios/metier/S9-evasion.yaml"])
def test_le_fichier_de_scenario_est_bien_forme(fichier: str) -> None:
    scenario = scn.charger(RACINE / fichier)
    assert isinstance(scenario, Scenario)
    assert scenario.id
