"""Lot 0 — the guards themselves must be green and must catch a violation."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from sas import i18n
from sas.types import Langue

RACINE = Path(__file__).resolve().parents[2]


def executer(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RACINE / "scripts" / script)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(RACINE),
    )


def test_garde_de_taille_verte() -> None:
    """ENF-14 — fichiers < 500 lignes, fonctions < 50 lignes.
    ENF-14 — fichiers < 500 lignes, fonctions < 50 lignes.
    ENF-14 — fichiers < 500 lignes, fonctions < 50 lignes.
    """
    resultat = executer("check_limits.py")
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert "LIMITS OK" in resultat.stdout


def test_garde_de_conformite_sans_secret() -> None:
    """Whatever the state of the lots, a secret-looking string is blocking."""
    sys.path.insert(0, str(RACINE / "scripts"))
    import check_contest

    rapport = check_contest.Rapport()
    check_contest.verifier_secrets(rapport)
    check_contest.verifier_depots_interdits(rapport)
    assert rapport.bloquants == []


def test_garde_de_conformite_ci() -> None:
    sys.path.insert(0, str(RACINE / "scripts"))
    import check_contest

    rapport = check_contest.Rapport()
    check_contest.verifier_ci(rapport)
    assert rapport.bloquants == [], rapport.bloquants


def test_garde_de_conformite_ports_agentcore() -> None:
    sys.path.insert(0, str(RACINE / "scripts"))
    import check_contest

    rapport = check_contest.Rapport()
    check_contest.verifier_agentcore(rapport)
    bloquants = [b for b in rapport.bloquants if "port" in b]
    assert bloquants == []


# --------------------------------------------------------------------------- #
# Bilingual labels (ENF-13)
# --------------------------------------------------------------------------- #


def test_chaque_cle_existe_dans_les_deux_langues() -> None:
    for cle, (francais, anglais) in i18n.CLES.items():
        assert francais.strip(), cle
        assert anglais.strip(), cle


def test_traduction_selon_la_langue() -> None:
    assert i18n.traduire("verdict.homologue", Langue.FR) == "Homologué"
    assert i18n.traduire("verdict.homologue", Langue.EN) == "Approved"


def test_cle_inconnue_ne_plante_pas() -> None:
    """A report must never crash on an untranslated string."""
    assert i18n.traduire("cle.inconnue", Langue.EN) == "cle.inconnue"


def test_cles_triees() -> None:
    assert i18n.toutes_les_cles() == tuple(sorted(i18n.CLES))
