"""Lot 7 — the audit a third party runs, on the text it received.

The audit is the point of the lot: it must find a break, name the entry and
the index, and refuse a format it does not know — with the standard library
only, without executing Sas.
"""

from __future__ import annotations

import json

from sas.journal.audit import auditer
from sas.journal.export import exporter

from .conftest import INSTANT, journal_sain, modifier_entree, supprimer_entree


def test_un_journal_sain_est_audite_comme_integre() -> None:
    """R9 — the round trip: export then audit gives « intact »."""
    rapport = auditer(exporter(journal_sain(3), exporte_le=INSTANT))
    assert rapport.integre is True
    assert rapport.entrees == 3
    assert rapport.sessions == 1
    assert rapport.premiere_rupture is None
    assert rapport.motif == ""


def test_une_entree_modifiee_est_detectee_avec_son_identifiant_et_son_index() -> None:
    """R9 — a decision rewritten after the fact breaks the chain at that entry."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    altere = modifier_entree(texte, 1, decision="refuse")
    rapport = auditer(altere)
    assert rapport.integre is False
    assert rapport.premiere_rupture == "appel-1"
    assert rapport.index_rupture == 1
    assert rapport.session_rupture == "sess-a"
    assert rapport.motif == "empreinte-incoherente"


def test_une_entree_supprimee_est_detectee() -> None:
    """R9 — a missing entry breaks the link of the one that follows."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    tronque = supprimer_entree(texte, 1)
    rapport = auditer(tronque)
    assert rapport.integre is False
    assert rapport.motif == "liaison-rompue"
    assert rapport.premiere_rupture == "appel-2"
    assert rapport.index_rupture == 1


def test_une_derniere_entree_supprimee_est_refusee_comme_export_incomplet() -> None:
    """A tail cut leaves a valid chain but an incomplete file: it is still refused."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    rapport = auditer(supprimer_entree(texte, 2))
    assert rapport.integre is False
    assert rapport.motif == "export-incomplet"
    assert "tronqué" in rapport.message


def test_une_version_de_format_inconnue_est_refusee() -> None:
    """An unknown version is refused, not guessed."""
    texte = exporter(journal_sain(2), exporte_le=INSTANT)
    lignes = texte.splitlines()
    enveloppe_objet = json.loads(lignes[0])
    enveloppe_objet["format_version"] = "sas-journal-export/99"
    lignes[0] = json.dumps(enveloppe_objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    rapport = auditer("\n".join(lignes) + "\n")
    assert rapport.integre is False
    assert rapport.motif == "format-inconnu"
    assert "sas-journal-export/99" in rapport.message


def test_une_absence_d_enveloppe_est_refusee() -> None:
    """A raw JSONL without an envelope is not an export: it is refused."""
    rapport = auditer('{"id":"x"}\n')
    assert rapport.integre is False
    assert rapport.motif == "format-inconnu"


def test_un_algorithme_inconnu_est_refuse() -> None:
    """The format is self-describing: an algorithm we cannot check is a refusal."""
    texte = exporter(journal_sain(2), exporte_le=INSTANT)
    lignes = texte.splitlines()
    enveloppe_objet = json.loads(lignes[0])
    enveloppe_objet["algorithme"]["empreinte"] = "md5"
    lignes[0] = json.dumps(enveloppe_objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    rapport = auditer("\n".join(lignes) + "\n")
    assert rapport.integre is False
    assert rapport.motif == "algorithme-inconnu"


def test_une_empreinte_export_falsifiee_est_detectee() -> None:
    """The fingerprint of the whole file binds the entries: touching one is visible."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    lignes = texte.splitlines()
    enveloppe_objet = json.loads(lignes[0])
    enveloppe_objet["empreinte_export"] = "sha256:" + "0" * 64
    lignes[0] = json.dumps(enveloppe_objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    rapport = auditer("\n".join(lignes) + "\n")
    assert rapport.integre is False
    assert rapport.motif == "empreinte-export-incoherente"


def test_un_export_tronque_est_refuse() -> None:
    """An export cut short is not a complete export."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    rapport = auditer("\n".join(texte.splitlines()[:2]) + "\n")
    assert rapport.integre is False
    assert rapport.motif == "export-incomplet"


def test_une_entree_illisible_est_refusee() -> None:
    """A line that is not a JSON object is not an entry."""
    texte = exporter(journal_sain(2), exporte_le=INSTANT)
    lignes = texte.splitlines()
    lignes[1] = "{pas du json"
    rapport = auditer("\n".join(lignes) + "\n")
    assert rapport.integre is False
    assert rapport.motif == "entree-invalide"


def test_un_export_vide_est_refuse() -> None:
    """An empty file is not an export."""
    rapport = auditer("")
    assert rapport.integre is False
    assert rapport.motif == "export-vide"


def test_les_sessions_multiples_sont_verifiees_separament() -> None:
    """Each session has its own chain: a break in one does not hide the other."""
    texte = exporter(journal_sain(4, sessions=("sess-a", "sess-b")), exporte_le=INSTANT)
    rapport = auditer(texte)
    assert rapport.integre is True
    assert rapport.sessions == 2
    assert rapport.entrees == 4


def test_une_session_ajoutee_est_refusee() -> None:
    """An entry of an undeclared session is a forged file."""
    texte = exporter(journal_sain(2), exporte_le=INSTANT)
    lignes = texte.splitlines()
    entree_objet = json.loads(lignes[1])
    entree_objet["session_id"] = "sess-z"
    lignes[1] = json.dumps(entree_objet, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    rapport = auditer("\n".join(lignes) + "\n")
    assert rapport.integre is False
    assert rapport.motif in {"export-incomplet", "empreinte-incoherente", "liaison-rompue"}
