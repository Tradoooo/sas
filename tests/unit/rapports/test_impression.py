"""The attestation as a printable artefact (EF-41, §17.2)."""

from __future__ import annotations

from sas.cli_partage import charger_contexte, invite, lancer
from sas.rapports import impression
from sas.types import Langue


def dossier(agent: str = "demo-conforme", scenarios=("S1", "S4")):
    contexte = charger_contexte(scenarios)
    return lancer(agent=invite(agent), contexte=contexte, rejeux=2, graine=7)


def test_le_pdf_est_un_vrai_pdf_d_une_page() -> None:
    document = impression.pdf(dossier().attestation)
    assert document.format == "pdf"
    assert document.pages == 1
    assert document.contenu.startswith(b"%PDF-1.4")
    assert document.contenu.rstrip().endswith(b"%%EOF")
    ok, motif = impression.verifiable(document.contenu)
    assert ok, motif


def test_le_pdf_contient_le_numero_d_attestation() -> None:
    attestation = dossier().attestation
    document = impression.pdf(attestation)
    assert document.nom == f"{attestation.numero}.pdf"
    assert attestation.numero in document.texte


def test_le_pdf_existe_dans_les_deux_langues() -> None:
    """ENF-13 — the deliverable a vendor or an insurer receives."""
    attestation = dossier().attestation
    francais = impression.pdf(attestation, Langue.FR)
    anglais = impression.pdf(attestation, Langue.EN)
    assert "ATTESTATION D'HOMOLOGATION" in francais.texte
    assert "HOMOLOGATION ATTESTATION" in anglais.texte
    assert francais.contenu != anglais.contenu


def test_le_pdf_porte_la_portee_statistique() -> None:
    """KPI-7 — the one thing that makes the document signable."""
    document = impression.pdf(dossier().attestation)
    assert "PORTÉE STATISTIQUE" in document.texte
    assert "rare" in document.texte.lower()


def test_le_pdf_ne_contient_aucune_donnee_client() -> None:
    """§17.2 — deliberately poor in details."""
    document = impression.pdf(dossier("demo-bavard", ("S1", "S4", "S5")).attestation)
    for interdit in ("T-0001", "SYNTHETIQUE", "grille des salaires", "coef "):
        assert interdit not in document.texte, interdit


def test_le_pdf_tient_sur_une_page() -> None:
    """§17.2 — one page. Anything past the fold is dropped, not spilled."""
    attestation = dossier().attestation
    document = impression.pdf(attestation)
    assert document.pages == 1
    # The content stream is deflate-compressed, so the line count is carried by
    # the Document rather than counted in the bytes.
    assert 0 < document.lignes_rendues <= 60
    assert b"/Count 1" in document.contenu


def test_la_vue_d_impression_est_autonome() -> None:
    """No script, no external resource: the print view must work offline."""
    html = impression.html_impression(dossier().attestation, Langue.FR)
    assert "<script" not in html
    assert "http://" not in html and "https://" not in html
    assert "@page" in html
    assert "ATTESTATION D'HOMOLOGATION" in html


def test_la_vue_d_impression_echappe_le_html() -> None:
    """A vendor name is untrusted input rendered into a page."""
    from dataclasses import replace

    attestation = dossier().attestation
    piegee = replace(attestation, editeur='<img src=x onerror="alert(1)">')
    html = impression.html_impression(piegee)
    assert "<img" not in html
    assert "&lt;img" in html


def test_la_vue_d_impression_dit_ce_qu_est_le_scellement() -> None:
    """Honesty: an HMAC seal is not an eIDAS electronic signature."""
    html = impression.html_impression(dossier().attestation)
    assert "HMAC" in html
    assert "eIDAS" in html


def test_un_agent_non_mesurable_n_a_rien_a_imprimer() -> None:
    """ENF-17 — no attestation, therefore no printable artefact."""
    assert dossier("demo-opaque").attestation is None


def test_verifiable_rejette_ce_qui_n_est_pas_un_pdf() -> None:
    ok, motif = impression.verifiable(b"ceci n'est pas un pdf")
    assert ok is False
    assert motif
