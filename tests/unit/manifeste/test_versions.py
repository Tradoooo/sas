"""Lot 1 — versioning and sealing (§9.3, EF-03, EF-05, R3, R4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from sas.manifeste import (
    avec_empreinte,
    empreinte_manifeste,
    historique,
    invalidations,
    marquer_remplace,
    nouvelle_version,
    projection,
    sceller,
    signer_editeur,
    valider_commanditaire,
    verifier,
)
from sas.types import Mode, StatutManifeste

from .conftest import FIXTURE, manifeste_valide

DATE = datetime(2026, 11, 20, tzinfo=UTC)
CLE = "cle-de-test-jamais-en-production"


def test_l_empreinte_est_stable_et_canonique() -> None:
    """R4 / EF-05 — one single reference: the manifest's own fingerprint."""
    premier = manifeste_valide()
    second = manifeste_valide()
    assert empreinte_manifeste(premier) == empreinte_manifeste(second)
    assert premier.empreinte == empreinte_manifeste(premier)


def test_l_empreinte_ne_depend_ni_du_statut_ni_des_signatures() -> None:
    manifeste = manifeste_valide()
    sans_signature = replace(manifeste, signature=None, statut=StatutManifeste.BROUILLON)
    assert empreinte_manifeste(sans_signature) == empreinte_manifeste(manifeste)


def test_un_changement_de_perimetre_change_l_empreinte() -> None:
    """EF-05 — the perimeter and the reference move together, or not at all."""
    manifeste = manifeste_valide()
    resserre = replace(manifeste, donnees_demandees=manifeste.donnees_demandees[:1])
    assert empreinte_manifeste(resserre) != empreinte_manifeste(manifeste)


def test_la_projection_ne_garde_que_les_champs_qui_engagent() -> None:
    projection_manifeste = projection(manifeste_valide())
    assert "signature" not in projection_manifeste
    assert "statut" not in projection_manifeste
    assert "donnees_demandees" in projection_manifeste


def test_R3_modifier_apres_signature_cree_une_nouvelle_version() -> None:
    """R3 / §9.3 — a change creates a new version and kills the attestation."""
    signe = manifeste_valide()
    resserre = replace(signe, donnees_demandees=signe.donnees_demandees[:1])
    suivant = nouvelle_version(resserre, {"date": DATE, "motif": "périmètre resserré"})
    assert suivant.version == signe.version + 1
    assert suivant.statut is StatutManifeste.BROUILLON
    assert suivant.signature is None
    assert suivant.validation_client is None
    consequences = invalidations(signe, suivant)
    assert any("attestation en cours est invalidée" in c for c in consequences)
    assert any("re-homologation" in c for c in consequences)
    assert any("bloc « donnees_demandees »" in c for c in consequences)


def test_la_version_precedente_est_remplacee() -> None:
    ancien = marquer_remplace(manifeste_valide())
    assert ancien.statut is StatutManifeste.REMPLACE


def test_une_modification_purement_administrative_est_dite() -> None:
    """A version bump with no perimeter change says so, rather than implying
    that something moved."""
    manifeste = manifeste_valide()
    identique = replace(manifeste, version=2)
    consequences = invalidations(manifeste, avec_empreinte(identique))
    assert any("inchangé" in c for c in consequences)


def test_historique_trie_du_plus_ancien() -> None:
    base = manifeste_valide()
    versions = {2: base, 1: base, 10: base}
    assert historique(versions) == (1, 2, 10)


def test_le_sceau_depend_de_la_cle() -> None:
    manifeste = manifeste_valide()
    assert sceller(manifeste, CLE) != sceller(manifeste, "autre-cle")
    assert sceller(manifeste, CLE).startswith("hmac-sha256:")


def test_signer_editeur_pose_le_statut_et_l_empreinte() -> None:
    """EF-03 — the editor signs first."""
    brouillon = replace(
        manifeste_valide(), signature=None, validation_client=None, statut=StatutManifeste.BROUILLON
    )
    signe = signer_editeur(
        brouillon,
        signataire="Directrice technique",
        qualite="habilitée à engager l'éditeur",
        date=DATE,
        cle=CLE,
    )
    assert signe.statut is StatutManifeste.SIGNE_EDITEUR
    assert signe.signature is not None
    assert signe.signature.empreinte_document == empreinte_manifeste(signe)


def test_valider_commanditaire_exige_la_signature() -> None:
    import pytest

    brouillon = replace(manifeste_valide(), signature=None, statut=StatutManifeste.BROUILLON)
    with pytest.raises(ValueError):
        valider_commanditaire(
            brouillon,
            commanditaire="RSSI",
            date=DATE,
            perimetre_approuve="intégralité",
            cle=CLE,
        )


def test_premiere_homologation_en_ombre_seulement() -> None:
    """§10.1 — the observed mode cannot be authorised before anything is measured."""
    import pytest

    signe = signer_editeur(
        replace(manifeste_valide(), validation_client=None, statut=StatutManifeste.BROUILLON),
        signataire="CTO",
        qualite="habilitée",
        date=DATE,
        cle=CLE,
    )
    with pytest.raises(ValueError):
        valider_commanditaire(
            signe,
            commanditaire="RSSI",
            date=DATE,
            perimetre_approuve="intégralité",
            mode=Mode.OBSERVE,
            cle=CLE,
        )
    valide = valider_commanditaire(
        signe,
        commanditaire="RSSI",
        date=DATE,
        perimetre_approuve="intégralité",
        mode=Mode.OBSERVE,
        homologation_precedente=True,
        cle=CLE,
    )
    assert valide.validation_client is not None
    assert valide.validation_client.mode_autorise is Mode.OBSERVE


def test_R3_un_manifeste_modifie_apres_signature_ne_verifie_plus() -> None:
    """R3 — the seal detects any later edit."""
    signe = signer_editeur(
        replace(manifeste_valide(), validation_client=None, statut=StatutManifeste.BROUILLON),
        signataire="CTO",
        qualite="habilitée",
        date=DATE,
        cle=CLE,
    )
    assert verifier(signe)[0] is True
    falsifie = replace(signe, budgets=replace(signe.budgets, appels_par_execution=999))
    ok, motif = verifier(falsifie)
    assert ok is False
    assert "empreinte" in motif


def test_le_sceau_est_verifie_avec_la_cle() -> None:
    signe = signer_editeur(
        replace(manifeste_valide(), validation_client=None, statut=StatutManifeste.BROUILLON),
        signataire="CTO",
        qualite="habilitée",
        date=DATE,
        cle=CLE,
    )
    sceau = sceller(signe, CLE)
    assert verifier(signe, cle=CLE, sceau=sceau)[0] is True
    assert verifier(signe, cle="mauvaise-cle", sceau=sceau)[0] is False


def test_un_manifeste_non_signe_ne_verifie_pas() -> None:
    brouillon = replace(manifeste_valide(), signature=None, statut=StatutManifeste.BROUILLON)
    ok, motif = verifier(brouillon)
    assert ok is False
    assert "non signé" in motif


def test_la_fixture_de_reference_verifie() -> None:
    from sas.manifeste import charger

    manifeste = charger(FIXTURE).manifeste
    assert verifier(manifeste) == (True, "signature vérifiée")
