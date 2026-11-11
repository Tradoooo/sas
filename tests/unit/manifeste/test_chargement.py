"""Lot 1 — loading the manifest: annexe A must load as-is (EF-01)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sas.manifeste import (
    BLOCS_OBLIGATOIRES,
    ErreurManifeste,
    charger,
    charger_depuis_texte,
    charger_manifeste,
    schema_json,
    valider_structure,
)
from sas.types import Mode, StatutManifeste

from .conftest import FIXTURE, donnees_base, texte_base, variante


def test_annexe_a_se_charge_telle_quelle() -> None:
    """EF-01 — the reference manifest of annexe A loads into the frozen types."""
    manifeste = charger_manifeste(FIXTURE)
    assert manifeste.identite.nom == "AgentTicket"
    assert manifeste.identite.version_agent == "3.4.1"
    assert manifeste.version == 1
    assert len(manifeste.outils_demandes) == 3
    assert len(manifeste.donnees_demandees) == 3
    assert manifeste.budgets.appels_par_execution == 25
    assert len(manifeste.scenarios) == 8


def test_les_booleens_francais_sont_lus() -> None:
    """The specification is written in French: `vrai` and `faux` must load."""
    manifeste = charger_manifeste(FIXTURE)
    assert manifeste.identite.engagement_notification_modele is True
    assert manifeste.memoire_persistante is False


def test_une_liste_vide_n_est_pas_une_cle_absente() -> None:
    """Annexe A: an absent `sorties_autorisees` is refused, an empty one is not."""
    charge = charger(FIXTURE)
    assert charge.manifeste.sorties_autorisees == ()
    assert "sorties_autorisees" not in charge.cles_absentes

    sans_cle = variante(("sorties_autorisees", None))
    assert "sorties_autorisees:" not in sans_cle
    charge_sans_cle = charger_depuis_texte(sans_cle)
    assert "sorties_autorisees" in charge_sans_cle.cles_absentes


def test_le_statut_decoule_des_signatures() -> None:
    assert charger_manifeste(FIXTURE).statut is StatutManifeste.VALIDE
    brouillon = variante(("signature", None), ("validation_client", None))
    assert charger_depuis_texte(brouillon).manifeste.statut is StatutManifeste.BROUILLON
    signe = variante(("validation_client", None))
    assert charger_depuis_texte(signe).manifeste.statut is StatutManifeste.SIGNE_EDITEUR


def test_le_mode_autorise_est_ombre_par_defaut() -> None:
    assert charger_manifeste(FIXTURE).validation_client is not None
    assert charger_manifeste(FIXTURE).validation_client.mode_autorise is Mode.OMBRE


def test_les_dates_sont_utc_conscientes() -> None:
    manifeste = charger_manifeste(FIXTURE)
    assert manifeste.date.tzinfo is not None
    assert manifeste.date.year == 2026


def test_le_json_est_accepte_aussi() -> None:
    import json

    texte = json.dumps(donnees_base(), default=str, ensure_ascii=False)
    manifeste = charger_depuis_texte(texte).manifeste
    assert manifeste.identite.nom == "AgentTicket"


def test_un_document_ilisible_leve_une_erreur_explicite() -> None:
    with pytest.raises(ErreurManifeste):
        charger_depuis_texte("::: pas du yaml ::: [")
    with pytest.raises(ErreurManifeste):
        charger_depuis_texte("- une\n- liste\n")


def test_un_bloc_inconnu_est_refuse_a_la_structure() -> None:
    with pytest.raises(ErreurManifeste) as excinfo:
        charger_depuis_texte(variante(("bloc_mystere", {"x": 1})))
    assert any(p.code == "bloc-inconnu" for p in excinfo.value.problemes)


def test_un_bloc_obligatoire_manquant_est_refuse() -> None:
    with pytest.raises(ErreurManifeste) as excinfo:
        charger_depuis_texte(variante(("engagements", None)))
    codes = {p.code for p in excinfo.value.problemes}
    assert "bloc-absent" in codes


def test_une_cle_inconnue_dans_un_bloc_est_refusee() -> None:
    with pytest.raises(ErreurManifeste) as excinfo:
        charger_depuis_texte(variante(("identite.champ_surprise", "x")))
    assert any(p.code == "cle-inconnue" for p in excinfo.value.problemes)


def test_le_schema_public_couvre_tous_les_blocs() -> None:
    """The manifest is a format a third party can read without reading code."""
    schema = schema_json()
    assert schema["$schema"].endswith("2020-12/schema")
    assert set(schema["properties"]) == set(donnees_base())
    assert set(schema["required"]) == set(BLOCS_OBLIGATOIRES)
    assert schema["additionalProperties"] is False


def test_le_schema_publie_est_a_jour() -> None:
    import json

    publie = Path(__file__).resolve().parents[3] / "schemas" / "manifeste.schema.json"
    assert publie.is_file(), "schemas/manifeste.schema.json doit être publié"
    assert json.loads(publie.read_text(encoding="utf-8")) == schema_json()


def test_valider_structure_sur_un_document_sain() -> None:
    assert valider_structure(donnees_base()).valide


def test_texte_base_non_vide() -> None:
    assert len(texte_base()) > 1000
