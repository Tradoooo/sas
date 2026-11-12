"""Lot 7 — the published format and the code must not drift apart.

A published format that no longer matches the code is worse than no format:
a third party would compute the wrong thing and trust the result. These tests
bind the two together — the documentation says what the auditor implements, and
the auditor implements what the documentation says.

They import the constants straight from the code (`sas.journal.export.ALGORITHME`,
`sas.journal.audit.CANONIQUE`) and check that the document quotes the same
values. The constants are the single source of truth; the markdown is prose
about them, never a second truth.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from sas.journal.audit import CANONIQUE, CHAMPS_CHAINE, FORMATS_SUPPORTEES
from sas.journal.chaine import JournalChaine
from sas.journal.export import ALGORITHME, FORMAT_VERSION, enveloppe
from sas.types import Decision, EntreeJournal

RACINE = Path(__file__).resolve().parents[3]
DOCS = {
    "en": RACINE / "docs" / "FORMAT-JOURNAL.en.md",
    "fr": RACINE / "docs" / "FORMAT-JOURNAL.fr.md",
}


def texte(langue: str) -> str:
    return DOCS[langue].read_text(encoding="utf-8")


def test_les_deux_versions_existent_et_sont_non_vides() -> None:
    """A format published in one language only excludes half the auditors."""
    for langue, chemin in DOCS.items():
        assert chemin.is_file(), f"document absent : {chemin}"
        assert texte(langue).strip(), f"document vide : {chemin}"


def test_les_deux_documents_publient_le_meme_format() -> None:
    """The two versions describe the same format, not two formats."""
    for langue in DOCS:
        corps = texte(langue)
        assert FORMAT_VERSION in corps, f"{langue} : la version du format doit être citée"
        assert "sha256" in corps
        for champ in CHAMPS_CHAINE:
            assert champ in corps, f"{langue} : le champ {champ!r} doit être documenté"
        for version in FORMATS_SUPPORTEES:
            assert version in corps, f"{langue} : la version {version!r} doit être citée"


def test_la_regle_de_projection_est_expliquee_mot_pour_mot() -> None:
    """The projection rule is the heart of the format: it must be written out."""
    for langue in DOCS:
        corps = texte(langue).lower()
        assert "projection" in corps
        assert "ensure_ascii" in corps
        assert "cles_triees" in corps or "triées" in corps or "sorted" in corps


def test_les_constantes_du_code_sont_citees_dans_le_document() -> None:
    """The algorithm the code implements must be the one the document describes."""
    for langue in DOCS:
        corps = texte(langue)
        assert ALGORITHME["empreinte"] in corps
        assert ALGORITHME["prefixe"] in corps
        for cle, valeur in CANONIQUE.items():
            # The document writes the values as JSON, the code holds them as Python.
            attendu = json.dumps(valeur) if not isinstance(valeur, bool) else str(valeur).lower()
            assert attendu in corps.lower(), f"{langue} : {cle}={valeur!r} absent"


def test_le_verificateur_publie_est_identique_en_fr_et_en() -> None:
    """One verifier, two languages: the code block is identical, only the prose differs."""
    codes = {}
    for langue in DOCS:
        blocs = [bloc.split("```")[0] for bloc in texte(langue).split("```python")[1:]]
        retenus = [bloc for bloc in blocs if "sys.stdin" in bloc]
        assert len(retenus) == 1, f"{langue} : un seul vérificateur publié attendu"
        codes[langue] = retenus[0]
    assert codes["en"] == codes["fr"], "le code du vérificateur doit être identique dans les deux versions"


def test_les_motifs_de_refus_du_code_sont_documentes() -> None:
    """A refusal nobody can recognise is a refusal nobody can act on."""
    motifs = (
        "format-inconnu",
        "algorithme-inconnu",
        "entree-invalide",
        "export-incomplet",
        "empreinte-export-incoherente",
    )
    for motif in motifs:
        assert motif in texte("fr"), f"le motif {motif!r} doit être documenté"


def test_le_document_nomme_les_champs_de_l_enveloppe() -> None:
    """Every field of the envelope is documented as a backticked symbol."""
    entree = EntreeJournal(
        id="appel-0",
        tenant_id="tenant-a",
        session_id="sess-a",
        campagne_id="camp-1",
        agent_id="agent-1",
        agent_version="3.4.1",
        scenario_id="S1",
        numero_rejeu=1,
        parent_id=None,
        outil="lire_ticket",
        parametres={},
        decision=Decision.AUTORISE,
        regle_appliquee="manifeste:autorise",
        resultat={},
        horodatage=datetime(2026, 11, 20, 9, 30, tzinfo=UTC),
        latence_ms=1.0,
        jetons=10,
        ressources=(),
    )
    journal = JournalChaine()
    journal.ajouter(entree)
    objet = enveloppe(journal, exporte_le=datetime(2026, 11, 20, 10, 0, tzinfo=UTC))
    corps = texte("en")
    for champ in objet:
        assert re.search(rf"`{re.escape(champ)}`", corps), f"le champ {champ!r} doit être documenté"
    assert json.loads(json.dumps(objet)) == objet  # the envelope is plain JSON
