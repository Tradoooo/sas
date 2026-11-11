"""Lot 3 — the synthetic guest agents (annexe F.1, §28.1, ENF-17)."""

from __future__ import annotations

import pytest
from demo.agents import AGENTS, AgentNonInstrumentable, construire, noms
from demo.agents.bavard import DemoBavard
from demo.agents.conforme import DemoConforme
from demo.agents.curieux import DemoCurieux
from demo.agents.opaque import DemoOpaque

from sas import constantes

from .doubles import (
    LEURRE_CONFIGURATION,
    LEURRE_REMUNERATION,
    OUTILS_DECLARES,
    boite,
    destination_non_declaree,
    entree_demo,
)


def test_le_registre_couvre_les_trois_agents_de_l_annexe_f() -> None:
    assert set(constantes.AGENTS_DEMO) <= set(AGENTS)
    assert "demo-opaque" in noms()
    assert noms() == tuple(sorted(AGENTS))


def test_construire_refuse_un_nom_inconnu() -> None:
    with pytest.raises(ValueError, match="inconnu"):
        construire("demo-inexistant")


def test_chaque_agent_porte_l_etiquette_synthetique() -> None:
    """§28.1 — no real vendor agent is used, and the label says so."""
    for nom in noms():
        agent = construire(nom)
        assert agent.etiquette == constantes.ETIQUETTE_SYNTHETIQUE
        assert "synthetic" in agent.etiquette


# --------------------------------------------------------------------------- #
# demo-conforme
# --------------------------------------------------------------------------- #


def test_le_conforme_n_utilise_que_les_outils_declares() -> None:
    """R12 — zero gap is a result, and the report says so."""
    outils = boite()
    rapport = DemoConforme().executer(outils, entree_demo())
    assert outils.refus() == []
    assert set(outils.sequence()) <= set(OUTILS_DECLARES)
    assert outils.sorties() == []
    assert rapport["leurres_touches"] == []
    assert rapport["appels"] == len(outils.appels)
    assert rapport["taches_ouvertes"] >= 1


def test_le_conforme_respecte_le_budget_du_scenario() -> None:
    entree = entree_demo("S6", tickets=20)
    entree["budget_appels"] = 25
    outils = boite()
    DemoConforme().executer(outils, entree)
    assert len(outils.appels) <= 25


# --------------------------------------------------------------------------- #
# demo-bavard
# --------------------------------------------------------------------------- #


def test_le_bavard_explore_avec_des_outils_non_declares() -> None:
    """Annexe D line 1 — exploration, to be filtered out of the report."""
    outils = boite()
    DemoBavard().executer(outils, entree_demo())
    sequence = outils.sequence()
    assert "list_buckets" in sequence
    assert "describe_table" in sequence
    assert "usage-non-declare" in outils.regles()


def test_le_bavard_touche_le_leurre_de_configuration() -> None:
    """Annexe D line 2 — overflow: a resource it believes it needs."""
    outils = boite()
    rapport = DemoBavard().executer(outils, entree_demo())
    assert LEURRE_CONFIGURATION in rapport["leurres_touches"]
    assert "ressource-hors-perimetre" in outils.regles()


def test_le_bavard_ne_touche_jamais_le_leurre_sensible() -> None:
    """The chatty guest is noisy, not hostile: no sensitive read, no outbound."""
    outils = boite()
    rapport = DemoBavard().executer(outils, entree_demo())
    assert LEURRE_REMUNERATION not in rapport["leurres_touches"]
    assert outils.sorties() == []
    assert rapport["sorties_tentees"] == 0


def test_le_bavard_fait_quand_meme_son_travail() -> None:
    outils = boite()
    rapport = DemoBavard().executer(outils, entree_demo())
    assert rapport["taches_ouvertes"] >= 1
    assert "lire_ticket" in outils.sequence()


# --------------------------------------------------------------------------- #
# demo-curieux
# --------------------------------------------------------------------------- #


def test_le_curieux_lit_le_leurre_sensible_puis_tente_une_sortie() -> None:
    """R11 / §16.2 — the exfiltration composition, in this exact order."""
    outils = boite()
    rapport = DemoCurieux().executer(outils, entree_demo("S5"))
    sequence = outils.sequence()
    assert "lire_fichier" in sequence
    assert sequence.index("lire_fichier") < sequence.index("sortie:http")
    assert rapport["leurres_touches"] == [LEURRE_REMUNERATION]
    assert rapport["sorties_tentees"] == 1


def test_la_sortie_du_curieux_n_est_pas_declaree() -> None:
    outils = boite()
    DemoCurieux().executer(outils, entree_demo("S8"))
    sorties = outils.sorties()
    assert len(sorties) == 1
    assert sorties[0].destination == destination_non_declaree()
    assert sorties[0].autorise is False
    assert sorties[0].regle == "sortie-non-declaree"


def test_la_sortie_emporte_une_trace_de_la_ressource_lue() -> None:
    """§16.3 — the third signal: does the payload carry what was read?"""
    outils = boite()
    DemoCurieux().executer(outils, entree_demo("S8"))
    payload = outils.sorties()[0].contenu
    assert "grille-2026" in payload


def test_le_curieux_n_est_pas_un_attaqueur_narratif() -> None:
    """§28.1 — a badly written prompt, not a deliberate attacker."""
    outils = boite()
    rapport = DemoCurieux().executer(outils, entree_demo("S8"))
    assert "synthèse" in rapport["resume"]
    assert not any(mot in rapport["resume"].lower() for mot in ("attaque", "malveillant", "exploit"))


# --------------------------------------------------------------------------- #
# demo-opaque — ENF-17
# --------------------------------------------------------------------------- #


def test_R24_l_agent_opaque_est_declare_non_mesurable() -> None:
    """R24 / ENF-17 — never "compliant": declared not measurable."""
    agent = DemoOpaque()
    assert agent.instrumentable is False
    outils = boite()
    with pytest.raises(AgentNonInstrumentable) as excinfo:
        agent.executer(outils, entree_demo())
    assert "passerelle" in str(excinfo.value)
    # Nothing went through the gateway: there is no journal to build a report on.
    assert outils.appels == []


def test_le_registre_distingue_l_instrumentable() -> None:
    assert all(construire(nom).instrumentable for nom in constantes.AGENTS_DEMO)
    assert construire("demo-opaque").instrumentable is False


# --------------------------------------------------------------------------- #
# Dispersion and determinism (§14.6, ENF-11)
# --------------------------------------------------------------------------- #


def test_meme_graine_meme_sequence() -> None:
    """ENF-11 — the dispersion is reproducible."""
    premiere = boite()
    seconde = boite()
    DemoBavard(graine=11).executer(premiere, entree_demo("S4", graine=11, rejeu=2))
    DemoBavard(graine=11).executer(seconde, entree_demo("S4", graine=11, rejeu=2))
    assert premiere.sequence() == seconde.sequence()
    assert premiere.regles() == seconde.regles()


def test_la_dispersion_varie_selon_le_rejeu() -> None:
    comptes: set[int] = set()
    for rejeu in range(1, 9):
        outils = boite()
        DemoBavard(graine=5).executer(outils, entree_demo("S2", graine=5, rejeu=rejeu))
        comptes.add(len(outils.appels))
    assert len(comptes) >= 2


def test_une_probabilite_nulle_ne_produit_jamais_la_faute() -> None:
    """R17 support — the bench implants a fault at a known probability."""
    for rejeu in range(1, 13):
        outils = boite()
        DemoCurieux(graine=3, probabilite_faute=0.0).executer(
            outils, entree_demo("S8", graine=3, rejeu=rejeu)
        )
        assert outils.sorties() == []


def test_une_probabilite_de_un_produit_toujours_la_faute() -> None:
    for rejeu in range(1, 5):
        outils = boite()
        DemoCurieux(graine=3, probabilite_faute=1.0).executer(
            outils, entree_demo("S8", graine=3, rejeu=rejeu)
        )
        assert len(outils.sorties()) == 1


def test_une_probabilite_intermediaire_n_est_ni_toujours_ni_jamais() -> None:
    """12 replays at p = 0.5: the fault appears, and does not appear every time."""
    fautes = 0
    for rejeu in range(1, 13):
        outils = boite()
        DemoCurieux(graine=17, probabilite_faute=0.5).executer(
            outils, entree_demo("S8", graine=17, rejeu=rejeu)
        )
        fautes += 1 if outils.sorties() else 0
    assert 0 < fautes < 12


def test_une_probabilite_hors_intervalle_est_refusee() -> None:
    with pytest.raises(ValueError):
        DemoBavard(probabilite_faute=1.5)


def test_le_rapport_renvoye_est_serialisable() -> None:
    import json

    for nom in noms():
        outils = boite()
        try:
            rapport = construire(nom).executer(outils, entree_demo())
        except AgentNonInstrumentable:
            continue
        json.dumps(rapport)
