"""Interval estimation: what an observation licenses you to say (§14, KPI-7).

The point of these tests is not that Wilson's formula is computed correctly — it
is standard — but that the product uses it in the **conservative** direction:
"nothing observed in six replays" must come out as "a behaviour occurring up to
58 % of runs cannot be excluded", never as "no problem found".
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from sas import constantes
from sas.intervalle import (
    arret_sequentiel,
    cout_pour_confiance,
    echelle_confiance,
    n_minimal,
    portee_etendue,
    wilson,
    z,
)
from sas.statistiques import probabilite_detection


def test_z_correspond_aux_quantiles_usuels() -> None:
    assert round(z(0.95), 4) == 1.9600
    assert round(z(0.99), 4) == 2.5758
    assert z(0.90) < z(0.95) < z(0.99)


def test_z_refuse_une_confiance_hors_intervalle() -> None:
    for valeur in (0.0, 1.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            z(valeur)


def test_wilson_reste_dans_l_intervalle() -> None:
    """Unlike the normal approximation, Wilson never leaves [0, 1] — including
    at k = 0 and at k = N, which are the two cases this product meets most."""
    for succes in range(0, 7):
        intervalle = wilson(succes, 6)
        assert 0.0 <= intervalle.bas <= intervalle.haut <= 1.0


def test_zero_sur_six_donne_une_borne_superieure_explicite() -> None:
    """§14.4 — six replays with nothing observed still miss a lot."""
    intervalle = wilson(0, 6)
    assert intervalle.bas == 0.0
    assert 0.5 < intervalle.haut < 0.65
    assert intervalle.ponctuelle == 0.0


def test_la_borne_se_resserre_avec_les_rejeux() -> None:
    """More replays buy a tighter statement — the whole point of §14.5."""
    bornes = [wilson(0, n).haut for n in (2, 6, 12, 29, 59)]
    assert bornes == sorted(bornes, reverse=True)
    assert bornes[-1] < 0.1


def test_comptages_incoherents_refuses() -> None:
    with pytest.raises(ValueError):
        wilson(7, 6)
    with pytest.raises(ValueError):
        wilson(-1, 6)


def test_zero_essai_n_est_pas_exploitable() -> None:
    intervalle = wilson(0, 0)
    assert intervalle.exploitable is False
    assert intervalle.haut == 1.0  # nothing observed, nothing excluded


def test_n_minimal_utilise_l_estimation_ponctuelle_par_defaut() -> None:
    """A behaviour seen 3 times in 6 replays needs N = 5 for 95 % — the same
    figure §14.3 gives for p = 0.5, which is the point estimate here."""
    assert n_minimal(wilson(3, 6)) == 5


def test_n_minimal_conservateur_repond_honnetement_quand_il_ne_peut_pas() -> None:
    """On the lower bound, a small sample promises nothing: the answer is None,
    not an optimistic number."""
    assert n_minimal(wilson(3, 6), conservateur=True) is None
    assert n_minimal(wilson(0, 6)) is None


def test_n_minimal_sur_un_echantillon_assez_grand() -> None:
    """6 replays out of 6: the conservative bound is usable and gives a number."""
    assert n_minimal(wilson(6, 6), conservateur=True) is not None


def test_arret_sequentiel_rejoint_le_chapitre_14_3() -> None:
    assert arret_sequentiel(0.50) == 5
    assert arret_sequentiel(0.25) == 11
    assert arret_sequentiel(0.10) == 29
    assert arret_sequentiel(0.05) == 59


def test_arret_sequentiel_est_borne() -> None:
    """A confidence nobody will pay for must not produce an absurd N."""
    assert arret_sequentiel(0.001, confiance=0.99, n_max=60) <= 60


def test_le_prix_de_la_confiance_est_coherent_avec_l_annexe_g() -> None:
    """Annexe G.7 quotes $4.36 for the N = 29 level; measured here, quantized."""
    detail = cout_pour_confiance(0.10)
    assert detail["n_rejeux"] == 29
    assert detail["sessions"] == 29 * len(constantes.SCENARIOS_LANCES)
    assert abs(float(detail["cout_total"]) - 4.36) < 0.05
    assert detail["confiance_atteinte"] >= constantes.CONFIANCE_CIBLE


def test_le_cout_est_lineaire_en_n_mais_pas_la_confiance() -> None:
    """§14.5 — the trade-off a customer arbitrates, stated numerically."""
    echelle = echelle_confiance()
    couts = [ligne["cout_total"] for ligne in echelle]
    confiance = [ligne["confiance_atteinte"] for ligne in echelle]
    assert couts == sorted(couts)
    assert all(isinstance(c, Decimal) for c in couts)
    # The confidence column saturates while the cost keeps climbing.
    assert confiance[-1] - confiance[0] < 0.05
    assert couts[-1] > couts[0] * 5


def test_le_cout_de_l_analyseur_seul_est_toujours_inferieur() -> None:
    """§26.3 — in production the guest's tokens are the vendor's or the client's."""
    detail = cout_pour_confiance(0.25)
    assert detail["cout_analyseur_seul"] < detail["cout_total"]


def test_portee_etendue_sur_zero_decouverte() -> None:
    """The sentence a report must print when nothing was found."""
    portee = portee_etendue(6, [False] * 6)
    assert portee.decouvertes_zero is True
    assert portee.borne_superieure_zero > 0.5
    assert "ne peut pas être exclu" in portee.phrase_zero
    assert "58" in portee.phrase_zero


def test_portee_etendue_en_anglais() -> None:
    """ENF-13 — the same statement in both languages."""
    portee = portee_etendue(6, [False] * 6, langue="en")
    assert "cannot be excluded" in portee.phrase_zero
    assert "58" in portee.phrase_zero


def test_portee_etendue_quand_une_decouverte_existe() -> None:
    portee = portee_etendue(6, [True, False, False, False, False, False])
    assert portee.decouvertes_zero is False
    assert portee.borne_superieure_zero == 0.0
    assert "1 rejeux sur 6" in portee.phrase_zero or "Observé sur 1" in portee.phrase_zero


def test_la_borne_publiee_et_l_intervalle_sont_coherents() -> None:
    """The detection bound of §14.2 and the Wilson interval answer the same
    question from two sides: if N replays detect p with confidence c, then
    observing nothing in N replays must leave p above the Wilson bound's reach."""
    n, p = 6, 0.5
    assert probabilite_detection(p, n) > 0.98
    intervalle = wilson(0, n)
    assert intervalle.haut < p + 0.15
