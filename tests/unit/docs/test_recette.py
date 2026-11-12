"""The acceptance matrix must not drift behind the code.

`docs/RECETTE.md` is a submission deliverable (spec §29). Its first version was
written by hand when only seven lots existed and it under-reported the
coverage for the rest of the project: rows said "not covered yet" for
requirements that later gained a named test. A matrix that under-reports is as
misleading as one that over-reports — a judge reads it as a list of what the
project does not do.

These tests make the matrix **generated** and prove two things:

* the committed file is exactly what the generator produces (no hand edit
  survives);
* the generator's rule is the same one `scripts/check_contest.py` applies — an
  identifier is covered when a test file quotes it — so the two never disagree
  about what is covered.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
GENERATEUR = RACINE / "scripts" / "genere_recette.py"
MATRICE = RACINE / "docs" / "RECETTE.md"


def _charger_generateur():
    specification = importlib.util.spec_from_file_location("sas_genere_recette", GENERATEUR)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_la_matrice_commitee_est_bien_celle_du_generateur() -> None:
    """No hand edit of the matrix survives: it is regenerated."""
    module = _charger_generateur()
    assert MATRICE.read_text(encoding="utf-8") == module.generer(), (
        "docs/RECETTE.md diffère du générateur : relancer scripts/genere_recette.py"
    )


def test_le_verificateur_du_generateur_passe() -> None:
    """The generator's own `--verifier` mode is what CI calls; it must pass."""
    resultat = subprocess.run(
        [sys.executable, str(GENERATEUR), "--verifier"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert resultat.returncode == 0, resultat.stderr


def test_la_matrice_cite_un_test_reel_pour_chaque_exigence_couverte() -> None:
    """Every `file::test` the matrix cites exists — a name that does not exist
    is the same lie as a row that says "not covered yet"."""
    import re

    module = _charger_generateur()
    citations, noms_tests = module._scan_corpus()
    assert noms_tests, "aucun test trouvé dans le dépôt"

    corps = MATRICE.read_text(encoding="utf-8")
    for chemin, nom in re.findall(r"`([A-Za-z0-9_/.\-]+\.py)::(test_[A-Za-z0-9_]+)`", corps):
        assert (RACINE / chemin).is_file(), f"fichier cité mais absent : {chemin}"
        assert nom in noms_tests, f"test cité mais inexistant : {chemin}::{nom}"

    # And the coverage the matrix claims is the coverage the corpus has.
    for identifiant, spots in citations.items():
        if not spots:
            continue
        assert f"| {identifiant} |" in corps, f"{identifiant} couvert mais absent de la matrice"
