"""Lot 0 — deterministic randomness and fingerprints (contract B, D, E)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from sas import aleatoire, identifiants


def test_meme_graine_memes_tirages() -> None:
    a = [aleatoire.entier(7, "ombre", 0, 10**6) for _ in range(5)]
    b = [aleatoire.entier(7, "ombre", 0, 10**6) for _ in range(5)]
    assert a == b


def test_flux_differents_independants() -> None:
    """The shadow generator and a guest agent must never draw from the same
    sequence, or a replay would be correlated with the environment."""
    ombre = aleatoire.probabilite(7, "ombre")
    invite = aleatoire.probabilite(7, "invite")
    assert ombre != invite


def test_melange_reproductible() -> None:
    elements = list(range(20))
    assert aleatoire.melange(3, "x", elements) == aleatoire.melange(3, "x", elements)
    assert sorted(aleatoire.melange(3, "x", elements)) == elements


def test_graine_derivee_stable_et_distincte() -> None:
    assert aleatoire.graine_derivee(11, "S4", 2) == aleatoire.graine_derivee(11, "S4", 2)
    assert aleatoire.graine_derivee(11, "S4", 2) != aleatoire.graine_derivee(11, "S4", 3)


def test_choix_refuse_le_vide() -> None:
    with pytest.raises(ValueError):
        aleatoire.choix(1, "x", [])


def test_echantillon_ne_deborde_pas() -> None:
    assert aleatoire.echantillon(5, "x", [1, 2, 3], 10) == [1, 2, 3]
    assert len(aleatoire.echantillon(5, "x", list(range(50)), 7)) == 7


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #


def test_identifiant_deterministe_avec_graine() -> None:
    assert identifiants.nouveau("sess", graine=9, cle="S1:3") == identifiants.nouveau(
        "sess", graine=9, cle="S1:3"
    )
    assert identifiants.nouveau("sess", graine=9, cle="S1:3") != identifiants.nouveau(
        "sess", graine=9, cle="S1:4"
    )


def test_identifiant_unique_sans_graine() -> None:
    tirage = {identifiants.nouveau("camp") for _ in range(200)}
    assert len(tirage) == 200


def test_prefixe_inconnu_refuse() -> None:
    with pytest.raises(ValueError):
        identifiants.nouveau("nimporte")


def test_empreinte_canonique_insensible_a_l_ordre() -> None:
    assert identifiants.empreinte({"b": 2, "a": 1}) == identifiants.empreinte({"a": 1, "b": 2})
    assert identifiants.empreinte({"a": 1}).startswith("sha256:")


def test_empreinte_canonique_decimal_et_horodatage() -> None:
    """Decimal('0.10') and Decimal('0.1') are different prices, not different
    spellings of the same price."""
    assert identifiants.empreinte(Decimal("0.10")) != identifiants.empreinte(Decimal("0.1"))
    date = datetime(2026, 11, 27, 9, 12, tzinfo=UTC)
    assert identifiants.empreinte(date) == identifiants.empreinte(date.isoformat())


def test_tronquer_pour_les_rapports() -> None:
    court = identifiants.tronquer("sha256:c4d9e1f2a3b4c5d6")
    assert court == "sha256:c4d9e1f2a3b4…"


def test_chaine_de_journal_detecte_une_modification() -> None:
    """§17.1 — a deletion or an edit in the journal is detected on reading."""
    premiere = identifiants.chainer("", {"outil": "lire_ticket", "decision": "autorise"})
    seconde = identifiants.chainer(premiere, {"outil": "ouvrir_tache", "decision": "autorise"})
    assert seconde != premiere
    falsifiee = identifiants.chainer(premiere, {"outil": "ouvrir_tache", "decision": "refuse"})
    assert falsifiee != seconde


def test_numero_attestation() -> None:
    date = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)
    assert identifiants.numero_attestation(date, 312) == "SAS-ATT-2026-0312"


def test_maintenant_est_utc() -> None:
    assert identifiants.maintenant().tzinfo is not None
