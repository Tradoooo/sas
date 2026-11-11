"""Lot 1 — acceptance tests R1 to R4 of the specification (§33.2).

Each test quotes the requirement identifiers it proves, so
`scripts/check_contest.py` can build the traceability matrix automatically.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from sas.manifeste import (
    ErreurManifeste,
    charger,
    charger_depuis_texte,
    empreinte_manifeste,
    est_executable,
    invalidations,
    nouvelle_version,
    projection,
    valider,
    valider_structure,
)
from sas.types import StatutManifeste

from .conftest import FIXTURE, donnees_base, variante

DATE = datetime(2026, 11, 21, tzinfo=UTC)


def test_R1_lancer_sans_manifeste_signe_est_refuse() -> None:
    """R1, EF-04, ENF-01 — no signature, no run, no session created.

    The orchestrator (lot 5) calls `est_executable` before creating any
    session; this test proves the gate itself.
    """
    charge = charger(FIXTURE)
    brouillon = replace(charge.manifeste, signature=None, statut=StatutManifeste.BROUILLON)
    executable, motif = est_executable(brouillon, "3.4.1")
    assert executable is False
    assert "brouillon" in motif

    signe_seulement = replace(charge.manifeste, validation_client=None, statut=StatutManifeste.SIGNE_EDITEUR)
    executable, motif = est_executable(signe_seulement, "3.4.1")
    assert executable is False
    assert "valide" in motif or "signature" in motif

    assert est_executable(charge.manifeste, "3.4.1") == (True, "")


def test_R2_manifeste_avec_acces_s3_sans_prefixe_refuse() -> None:
    """R2, EF-02 — a coarse permission is refused with an actionable reason."""
    for ressource in (
        "arn:aws:s3:::client-tickets",
        "arn:aws:s3:::client-tickets/*",
        "accès aux données du client",
    ):
        charge = charger_depuis_texte(variante(("donnees_demandees.0.ressource", ressource)))
        rapport = valider(charge.manifeste, cles_absentes=charge.cles_absentes)
        assert not rapport.valide, ressource
        assert all(p.action.strip() for p in rapport.problemes), ressource
        assert any(p.code in ("prefixe-absent", "grain-trop-large") for p in rapport.problemes), ressource


def test_R3_modifier_le_manifeste_apres_signature() -> None:
    """R3, §9.3 — a change creates a new version and kills the attestation."""
    charge = charger(FIXTURE)
    signe = charge.manifeste
    resserre = replace(signe, donnees_demandees=signe.donnees_demandees[:1])
    suivant = nouvelle_version(resserre, {"date": DATE})

    assert suivant.version == signe.version + 1
    assert suivant.statut is StatutManifeste.BROUILLON
    assert suivant.signature is None
    consequences = invalidations(signe, suivant)
    assert any("invalidée" in c for c in consequences)
    executable, _ = est_executable(suivant, "3.4.1")
    assert executable is False


def test_R4_la_politique_derivee_repose_sur_une_reference_unique() -> None:
    """R4, EF-05 — the manifest is the single source: the applied policy and
    the comparison baseline are the same fingerprint, so they cannot diverge.

    The generation of the policy itself is lot 6; what is proven here is that
    no hand-written rule can slip in between the signed text and the reference.
    """
    charge = charger(FIXTURE)
    manifeste = charge.manifeste

    assert manifeste.empreinte == empreinte_manifeste(manifeste)
    assert manifeste.signature is not None
    assert manifeste.signature.empreinte_document == manifeste.empreinte

    # Every field the policy is derived from is inside the fingerprint.
    engageants = projection(manifeste)
    for champ in ("outils_demandes", "donnees_demandees", "sorties_autorisees", "budgets"):
        assert champ in engageants

    # Changing one declared resource changes the fingerprint: there is no state
    # in which the signed text and the applied perimeter disagree.
    modifie = replace(manifeste, donnees_demandees=manifeste.donnees_demandees[:-1])
    assert empreinte_manifeste(modifie) != manifeste.empreinte


def test_un_document_structurellement_invalide_ne_produit_pas_de_manifeste() -> None:
    """EF-01 — an unreadable document is refused before anything else."""
    with pytest.raises(ErreurManifeste):
        charger_depuis_texte(variante(("budgets", None)))


def test_la_structure_valide_le_document_de_reference() -> None:
    assert valider_structure(donnees_base()).valide is True
