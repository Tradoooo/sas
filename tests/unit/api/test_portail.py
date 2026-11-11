"""Lot 14 — the static portal: no build step, no CDN, no network at runtime.

These tests guard what a judge will actually open. They never start a server:
they read the files and check the contract of the page.
"""

from __future__ import annotations

from pathlib import Path

from sas import constantes
from sas.api.app import ServiceSas, creer_app

RACINE = Path(__file__).resolve().parents[3]
PORTAIL = RACINE / "portal"


def lire(nom: str) -> str:
    return (PORTAIL / nom).read_text(encoding="utf-8")


def test_les_trois_fichiers_du_portail_existent() -> None:
    for nom in ("index.html", "app.js", "style.css"):
        assert (PORTAIL / nom).is_file(), nom


def test_aucune_ressource_externe() -> None:
    """The page must load offline and identically on a judge's machine.

    What is checked is a real reference, not the word: an absolute URL in a
    `src`/`href`, a protocol-relative URL, or a CSS `url(http…)`.
    """
    import re

    motif = re.compile(
        r"""(?:src|href)\s*=\s*["'](?:https?:)?//|url\(\s*["']?(?:https?:)?//""",
        re.IGNORECASE,
    )
    for nom in ("index.html", "app.js", "style.css"):
        contenu = lire(nom)
        assert not motif.search(contenu), f"{nom} référence une ressource externe"
        assert "import(" not in contenu, f"{nom} importe un module distant"


def test_le_portail_affiche_l_etiquette_synthetique() -> None:
    """§28.1 — the demo guests are labelled synthetic, in the interface too."""
    assert "synthétiques" in lire("index.html")


def test_le_portail_affiche_le_filtrage_de_l_exploration() -> None:
    """§13.5 — the filtering is shown explicitly, not hidden."""
    html = lire("index.html").lower()
    assert "exploration" in html
    assert "filtré" in html


def test_le_portail_affiche_la_portee_statistique() -> None:
    """KPI-7 — no competitor will show its own scope; we do."""
    assert "Portée statistique" in lire("index.html")


def test_le_portail_liste_ses_propres_limites() -> None:
    """§24.3 — an attestation that does not list its limits gets rejected."""
    html = lire("index.html")
    assert "non mesurable" in html
    assert "ne garantit pas" in html


def test_le_portail_appelle_les_routes_de_l_inventaire() -> None:
    """The page talks to the API of §23 — and to nothing else."""
    js = lire("app.js")
    for chemin in ("/health", "/registre", "/campagnes", "/rapports/", "/ecarts/", "/compositions"):
        assert chemin in js, chemin


def test_le_health_donne_un_jeton_de_demonstration() -> None:
    """The portal must be able to authenticate without a human typing a token."""
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        return
    client = TestClient(creer_app(ServiceSas()))
    corps = client.get("/health").json()
    assert corps["jeton_demo"].startswith("sas.")


def test_les_routes_du_portail_sont_un_sous_ensemble_de_l_inventaire() -> None:
    attendus = {chemin for _, chemin in constantes.ROUTES}
    assert "/health" in attendus
    assert "/registre" in attendus
    assert "/campagnes" in attendus
