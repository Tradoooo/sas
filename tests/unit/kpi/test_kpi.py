"""The eight KPIs of §5.2 — measured, and honest about what is not."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sas import kpi as module_kpi
from sas.analyseur.agregation import agreger
from sas.cli_partage import charger_contexte, invite, lancer
from sas.statistiques import phrase_portee
from sas.types import ActionDerive, Derive, EtatChaine

DATE = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)


def _dossier(agent: str = "demo-bavard", scenarios=("S1", "S4", "S5")):
    contexte = charger_contexte(scenarios)
    return lancer(agent=invite(agent), contexte=contexte, rejeux=2, graine=7)


def test_le_tableau_comporte_les_huit_kpi_dans_l_ordre() -> None:
    """§5.2 — the identifiers are frozen in `constantes.KPI`; the table follows."""
    dossier = _dossier()
    tableau = module_kpi.tableau(
        agregat=dossier.agregat,
        appels_emis=dossier.campagne.appels_emis,
        etat_chaine=dossier.campagne.etat_chaine,
        cout=dossier.campagne.cout_mesure.total,
        n_rejeux=2,
        ecarts=dossier.ecarts,
        compositions=dossier.compositions,
        borne_texte=phrase_portee(dossier.borne),
    )
    assert [k.id for k in tableau] == [f"KPI-{n}" for n in range(1, 9)]


def test_KPI1_compte_les_refus_par_regle() -> None:
    dossier = _dossier()
    mesure = module_kpi.kpi_1(dossier.agregat)
    assert mesure.mesure is True
    assert sum(mesure.valeur.values()) == dossier.agregat.refus
    assert "usage-non-declare" in mesure.valeur


def test_KPI2_est_mesure_quand_les_deux_instants_existent() -> None:
    mesure = module_kpi.kpi_2(DATE, DATE + timedelta(days=9))
    assert mesure.mesure is True
    assert mesure.valeur == 9.0
    assert mesure.unite == "jours"


def test_KPI2_refuse_d_etre_devine() -> None:
    """An unmeasured KPI is reported as such: the target is 'weeks -> days',
    and inventing a number to fill it would be exactly the paper guarantee the
    product replaces."""
    mesure = module_kpi.kpi_2(None, DATE)
    assert mesure.mesure is False
    assert mesure.valeur is None
    assert "non mesuré" in mesure.note


def test_KPI3_le_cout_est_mesure_et_pas_estime() -> None:
    """ENF-10 — the cost comes from the counters."""
    dossier = _dossier("demo-conforme")
    mesure = module_kpi.kpi_3(dossier.campagne.cout_mesure.total, 2)
    assert mesure.mesure is True
    assert mesure.valeur > 0
    assert "mesuré" in mesure.note


def test_KPI4_est_bloquant_et_le_dit_quand_il_est_tenu() -> None:
    dossier = _dossier()
    mesure = module_kpi.kpi_4(
        dossier.campagne.appels_emis, len(dossier.campagne.entrees), dossier.campagne.etat_chaine
    )
    assert mesure.valeur == 1.0
    assert "100 %" in mesure.cible
    assert "chaîne intègre" in mesure.note


def test_KPI4_signale_une_rupture_de_chaine() -> None:
    """KPI-4 is blocking: a broken chain means the campaign proves nothing."""
    rompue = EtatChaine(integre=False, entrees=10, premiere_rupture="appel-1")
    mesure = module_kpi.kpi_4(10, 10, rompue)
    assert "RUPTURE" in mesure.note


def test_KPI4_signale_une_couverture_inferieure_a_un() -> None:
    mesure = module_kpi.kpi_4(100, 97, EtatChaine(integre=True, entrees=97))
    assert mesure.valeur == 0.97
    assert "NON TENUE" in mesure.note


def test_KPI5_compte_les_deux_sens() -> None:
    dossier = _dossier("demo-curieux", ("S5", "S8"))
    mesure = module_kpi.kpi_5(dossier.ecarts)
    assert set(mesure.valeur) == {"debordements", "permissions_mortes"}
    assert mesure.valeur["debordements"] >= 1


def test_KPI6_est_mesure_sur_une_derive_injectee() -> None:
    """R16 support: the delay from the injected change to the alert."""
    derive = Derive(
        id="d1",
        agent_id="a1",
        tenant_id="t",
        enveloppe_ref="e1",
        enveloppe_courante="e2",
        distance=0.4,
        detail=(),
        alerte_le=DATE + timedelta(hours=36),
        action=ActionDerive.ALERTE,
    )
    mesure = module_kpi.kpi_6([derive], changement_le=DATE)
    assert mesure.mesure is True
    assert mesure.valeur == 36.0


def test_KPI6_refuse_d_etre_devine() -> None:
    mesure = module_kpi.kpi_6([])
    assert mesure.mesure is False
    assert "non mesuré" in mesure.note


def test_KPI7_publie_la_borne() -> None:
    """KPI-7 is the one that distinguishes the product from a tool."""
    mesure = module_kpi.kpi_7("6 rejeux indépendants par scénario…")
    assert mesure.mesure is True
    assert "rejeux" in mesure.valeur


def test_KPI8_compte_les_compositions_par_motif() -> None:
    dossier = _dossier("demo-curieux", ("S5", "S8"))
    mesure = module_kpi.kpi_8(dossier.compositions)
    assert mesure.valeur.get("exfiltration", 0) > 0


def test_en_json_ne_contient_que_des_valeurs_plates() -> None:
    """What the portal prints: no object the front end would have to know about."""
    import json

    dossier = _dossier()
    tableau = module_kpi.tableau(
        agregat=dossier.agregat,
        appels_emis=dossier.campagne.appels_emis,
        etat_chaine=dossier.campagne.etat_chaine,
        cout=dossier.campagne.cout_mesure.total,
        n_rejeux=2,
        ecarts=dossier.ecarts,
        compositions=dossier.compositions,
        borne_texte=phrase_portee(dossier.borne),
        demande_le=DATE,
        attestation_le=DATE + timedelta(days=4),
    )
    serialise = json.dumps(module_kpi.en_json(tableau), default=str)
    assert "KPI-1" in serialise
    # KPI-6 reste non mesuré ici : aucune dérive n'a été injectée dans ce test.
    assert module_kpi.non_mesures(tableau) == ("KPI-6",)


def test_les_kpi_non_mesures_sont_listes() -> None:
    """The dashboard can never be mistaken for a claim: what is not measured is
    listed as not measured."""
    dossier = _dossier()
    tableau = module_kpi.tableau(
        agregat=dossier.agregat,
        appels_emis=dossier.campagne.appels_emis,
        etat_chaine=dossier.campagne.etat_chaine,
        cout=Decimal("0.30"),
        n_rejeux=2,
        ecarts=dossier.ecarts,
        compositions=dossier.compositions,
        borne_texte="…",
    )
    assert module_kpi.non_mesures(tableau) == ("KPI-2", "KPI-6")


def test_le_cycle_de_surveillance_est_hebdomadaire() -> None:
    """§15.4 — weekly by default, and on every declared event."""
    assert module_kpi.cycle_surveillance() == timedelta(days=7)


def test_l_agregation_alimente_les_kpi_depuis_le_journal() -> None:
    """The KPIs read the journal, not a parallel counter (KPI-4 depends on it)."""
    dossier = _dossier()
    agregat = agreger(dossier.campagne.entrees)
    assert agregat.appels == dossier.campagne.appels_emis
    assert len(dossier.campagne.entrees) == agregat.appels
