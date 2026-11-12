"""Lot 7 — the export format: versioned, self-describing, deterministic.

The export is what a third party receives. It must say, without any knowledge
of the Sas code, how to recompute its fingerprints and how to tell whether the
file is complete.
"""

from __future__ import annotations

import json

from sas.journal.chaine import JournalChaine
from sas.journal.export import ALGORITHME, FORMAT_VERSION, enveloppe, exporter

from .conftest import HORODATAGE, INSTANT, journal_sain, lignes_export


def test_l_export_porte_une_version_de_format() -> None:
    """A format that evolves carries its version: an old reader must be able to refuse."""
    texte = exporter(journal_sain(2), exporte_le=INSTANT)
    enveloppe_objet = json.loads(lignes_export(texte)[0])
    assert enveloppe_objet["format_version"] == FORMAT_VERSION
    assert FORMAT_VERSION == "sas-journal-export/1"


def test_l_enveloppe_decrit_l_algorithme_en_donnees() -> None:
    """The reader must not need the Sas code: the algorithm travels with the file."""
    enveloppe_objet = json.loads(lignes_export(exporter(journal_sain(1), exporte_le=INSTANT))[0])
    algorithme = enveloppe_objet["algorithme"]
    assert algorithme["empreinte"] == "sha256"
    assert algorithme["canonique"]["cles_triees"] is True
    assert algorithme["canonique"]["separateurs"] == [",", ":"]
    assert algorithme["canonique"]["ensure_ascii"] is False
    assert algorithme["projection"]["champs_exclus"] == ["empreinte", "empreinte_prec"]
    assert algorithme["liaison"]["graine"] == ""
    assert enveloppe_objet["algorithme"] == ALGORITHME


def test_l_enveloppe_declare_les_sessions_avec_leur_etat() -> None:
    """Each session declares its size, its tip and its integrity state."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    enveloppe_objet = json.loads(lignes_export(texte)[0])
    sessions = enveloppe_objet["sessions"]
    assert len(sessions) == 1
    session = sessions[0]
    assert session["session_id"] == "sess-a"
    assert session["entrees"] == 3
    assert session["integrite"] is True
    assert session["empreinte_finale"].startswith("sha256:")
    assert session["premiere_rupture"] is None


def test_les_entrees_sont_verbatim_dans_l_ordre() -> None:
    """The export carries the entries as they are, never rewritten."""
    journal = journal_sain(3)
    texte = exporter(journal, exporte_le=INSTANT)
    corps = "\n".join(lignes_export(texte)[1:])
    assert corps == journal.exporter().rstrip("\n")


def test_l_export_est_deterministe_a_horodatage_fige() -> None:
    """Two exports of the same journal give the same bytes — the file can be diffed."""
    journal = journal_sain(3)
    premier = exporter(journal, exporte_le=INSTANT)
    second = exporter(journal, exporte_le=INSTANT)
    assert premier == second
    assert premier.encode("utf-8") == second.encode("utf-8")


def test_l_horodatage_par_defaut_suit_l_horloge_figee() -> None:
    """With the clock pinned, the export date is pinned too."""
    from sas.identifiants import figer_horloge

    figer_horloge(HORODATAGE)
    try:
        texte = exporter(journal_sain(1))
    finally:
        figer_horloge(None)
    enveloppe_objet = json.loads(lignes_export(texte)[0])
    assert enveloppe_objet["exporte_le"] == HORODATAGE.isoformat()


def test_l_export_ne_depend_que_du_journal() -> None:
    """Two different journals give two different exports — the fingerprint is not a constant."""
    un = exporter(journal_sain(1), exporte_le=INSTANT)
    deux = exporter(journal_sain(2), exporte_le=INSTANT)
    assert un != deux
    assert json.loads(lignes_export(deux)[0])["entrees"] == 2


def test_l_export_dune_session_seule_ne_contient_que_cette_session() -> None:
    """A targeted export is a valid export: the envelope declares only what it carries."""
    journal = journal_sain(4, sessions=("sess-a", "sess-b"))
    texte = exporter(journal, session_id="sess-b", exporte_le=INSTANT)
    enveloppe_objet = json.loads(lignes_export(texte)[0])
    assert [s["session_id"] for s in enveloppe_objet["sessions"]] == ["sess-b"]
    assert enveloppe_objet["entrees"] == 2
    assert len(lignes_export(texte)) == 3


def test_l_enveloppe_se_lit_toute_seule() -> None:
    """The envelope is a plain JSON object: a third party parses it with the stdlib."""
    enveloppe_objet = enveloppe(journal_sain(2), exporte_le=INSTANT)
    assert isinstance(enveloppe_objet, dict)
    assert json.loads(json.dumps(enveloppe_objet)) == enveloppe_objet


def test_le_journal_reste_la_seule_source_des_empreintes() -> None:
    """The export never re-implements the chain: it reuses what the chain produced."""
    journal = journal_sain(3)
    enveloppe_objet = enveloppe(journal, exporte_le=INSTANT)
    attendu = journal.derniere_empreinte("sess-a")
    assert enveloppe_objet["sessions"][0]["empreinte_finale"] == attendu
    assert enveloppe_objet["sessions"][0]["integrite"] == journal.verifier("sess-a").integre


def test_une_enveloppe_vide_est_valide() -> None:
    """An empty journal exports an empty, still verifiable, file."""
    texte = exporter(JournalChaine(), exporte_le=INSTANT)
    enveloppe_objet = json.loads(lignes_export(texte)[0])
    assert enveloppe_objet["entrees"] == 0
    assert enveloppe_objet["sessions"] == []
    assert len(lignes_export(texte)) == 1
