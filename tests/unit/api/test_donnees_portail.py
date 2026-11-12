"""The public dataset of the portal (GitHub Pages).

GitHub Pages serves static files: there is no Python behind the public URL. The
page therefore reads `portal/data/demo.json`, which was produced by **running
the real engine** on the synthetic demo data. These tests guard what a judge
will see: the file exists, it is the engine's output, it carries no client
content, and it reproduces byte for byte (ENF-11).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from sas.rapports.editeur import sans_donnee_client

RACINE = Path(__file__).resolve().parents[3]
DONNEES = RACINE / "portal" / "data" / "demo.json"
PORTAIL = RACINE / "portal"


def charge() -> dict:
    return json.loads(DONNEES.read_text(encoding="utf-8"))


def test_le_fichier_de_donnees_est_present() -> None:
    assert DONNEES.is_file(), "portal/data/demo.json doit être committé"


def test_les_quatre_invites_y_sont_avec_quatre_verdicts_distincts() -> None:
    """The demo of §28.2: conforming, chatty, curious — and the unmeasurable one."""
    donnees = charge()
    noms = [a["nom"] for a in donnees["agents"]]
    assert noms == ["demo-conforme", "demo-bavard", "demo-curieux", "demo-opaque"]
    verdicts = {a["nom"]: a["resume"]["verdict"] for a in donnees["agents"]}
    assert verdicts["demo-conforme"] == "homologue"
    assert verdicts["demo-bavard"] == "homologue_sous_conditions"
    assert verdicts["demo-curieux"] == "refuse"
    assert verdicts["demo-opaque"] == "non_mesurable"


def test_le_registre_publie_les_quatre_agents() -> None:
    donnees = charge()
    assert len(donnees["registre"]) == 4
    for ligne in donnees["registre"]:
        assert ligne["nom"] and ligne["statut"]


def test_le_curieux_publie_ses_compositions() -> None:
    donnees = charge()
    curieux = next(a for a in donnees["agents"] if a["nom"] == "demo-curieux")
    assert curieux["compositions"], "la composition d'exfiltration doit être publiée"
    assert any(c["motif"] == "exfiltration" for c in curieux["compositions"])
    assert curieux["resume"]["decouvertes"]["hostile"] > 0


def test_le_conforme_publie_zero_ecart() -> None:
    """R12 — zero gap is a result, and the page says so."""
    donnees = charge()
    conforme = next(a for a in donnees["agents"] if a["nom"] == "demo-conforme")
    assert conforme["resume"]["decouvertes"]["tentative"] == 0
    assert conforme["resume"]["decouvertes"]["hostile"] == 0
    assert conforme["conditions"] == []


def test_l_opaque_n_a_pas_d_attestation() -> None:
    """ENF-17 — an unmeasurable agent is declared, never certified."""
    donnees = charge()
    opaque = next(a for a in donnees["agents"] if a["nom"] == "demo-opaque")
    assert opaque["instrumentable"] is False
    assert opaque["attestation"] is None
    assert opaque["resume"]["verdict"] == "non_mesurable"


def test_chaque_agent_publie_sa_portee_statistique() -> None:
    """KPI-7 — the page shows the reach of the measurement."""
    donnees = charge()
    for agent in donnees["agents"]:
        assert agent["portee_fr"] and agent["portee_en"]
        assert "rare" in agent["portee_fr"].lower()
        if agent["attestation"]:
            assert "STATISTICAL SCOPE" in agent["attestation"]["texte_en"]
            assert "PORTÉE STATISTIQUE" in agent["attestation"]["texte_fr"]


def test_les_rapports_publies_ne_contiennent_rien_du_client() -> None:
    """EF-42 — the published vendor report carries no client content."""
    donnees = charge()
    for agent in donnees["agents"]:
        assert sans_donnee_client(agent["rapport_editeur"]), agent["nom"]
    assert donnees["source_donnee_client"] is True


@pytest.mark.slow
def test_le_jeu_de_donnees_est_reproductible() -> None:
    """ENF-11 — regenerating it produces the same bytes.

    The workflow `deploy.yml` relies on this: it regenerates and diffs, so a
    stale public page fails the build instead of being published. Marked slow so
    the default PR run stays inside the five-minute budget; the deploy workflow
    performs the same check on every push to main.
    """
    sortie = Path("/tmp/sas-demo-regenere.json")
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "scripts" / "genere_donnees_portail.py"), "--sortie", str(sortie)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(RACINE),
    )
    assert resultat.returncode == 0, resultat.stderr[-500:]
    assert sortie.read_text(encoding="utf-8") == DONNEES.read_text(encoding="utf-8")


def test_la_page_signale_son_mode() -> None:
    """A static page must say where its numbers come from."""
    html = (PORTAIL / "index.html").read_text(encoding="utf-8")
    assert "mode-bandeau" in html
    assert "synthétiques" in html
    js = (PORTAIL / "app.js").read_text(encoding="utf-8")
    assert "data/demo.json" in js
    assert "Mode statique" in js
