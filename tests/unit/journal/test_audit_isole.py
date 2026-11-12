"""Lot 7 — the audit must be able to run without Sas.

This is the difference between an audit and a tautology. If the auditor
reused `sas.identifiants.canonique`, it would only prove that Sas agrees with
itself; it would not prove anything to a third party. The auditor implements
the **published** format instead, and this module proves it.

Two independent proofs:

* the auditor's module imports nothing from Sas at all — it is checked by
  running it in a fresh interpreter and reading `sys.modules`;
* the fingerprints are recomputed here, with the standard library only, and
  compared with the ones the export carries.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from sas.journal.export import exporter

from .conftest import INSTANT, journal_sain, modifier_entree

RACINE = Path(__file__).resolve().parents[3]
SOURCE_AUDIT = RACINE / "src" / "sas" / "journal" / "audit.py"


def canonique(valeur: object) -> str:
    """The canonical form of the published format, re-implemented here."""
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def empreinte_attendue(prec: str, entree: dict[str, object]) -> str:
    """The fingerprint of one entry, computed from the published rules only."""
    projection = canonique(
        {cle: v for cle, v in entree.items() if cle not in ("empreinte", "empreinte_prec")}
    )
    corps = canonique({"prec": prec, "entree": projection})
    return "sha256:" + hashlib.sha256(corps.encode("utf-8")).hexdigest()


def test_le_module_audit_ne_charge_aucun_module_sas() -> None:
    """In a fresh interpreter, importing the auditor loads no Sas module at all."""
    script = (
        "import sys, importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('audit_iso', {str(SOURCE_AUDIT)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['audit_iso'] = module\n"
        "spec.loader.exec_module(module)\n"
        "print(any(m == 'sas' or m.startswith('sas.') for m in sys.modules))\n"
    )
    resultat = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(RACINE),
    )
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert resultat.stdout.strip() == "False", (
        "l'auditeur ne doit charger aucun module Sas : il implémente le format publié"
    )


def test_les_empreintes_se_recalculent_avec_la_stdlib_seule() -> None:
    """Recomputed here with the stdlib only, the fingerprints match the export."""
    texte = exporter(journal_sain(3), exporte_le=INSTANT)
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    entrees = [json.loads(ligne) for ligne in lignes[1:]]
    prec = ""
    for entree in entrees:
        assert empreinte_attendue(prec, entree) == entree["empreinte"]
        assert entree["empreinte_prec"] == prec
        prec = entree["empreinte"]


def test_le_code_du_verificateur_publie_est_copiable_tel_quel() -> None:
    """The published verifier runs on the export and reaches the same verdict."""
    for langue in ("en", "fr"):
        document = (RACINE / "docs" / f"FORMAT-JOURNAL.{langue}.md").read_text(encoding="utf-8")
        blocs = [bloc.split("```")[0] for bloc in document.split("```python")[1:]]
        codes = [bloc for bloc in blocs if "sys.stdin" in bloc]
        assert codes, f"le document publié ({langue}) doit contenir le vérificateur complet"
        resultat = subprocess.run(
            [sys.executable, "-c", codes[0]],
            input=exporter(journal_sain(3), exporte_le=INSTANT),
            capture_output=True,
            text=True,
            check=False,
            cwd=str(RACINE),
        )
        assert resultat.returncode == 0, resultat.stdout + resultat.stderr
        assert "INTÈGRE" in resultat.stdout or "INTEGRE" in resultat.stdout
        # A broken export must be refused by the published code, not only by the module.
        resultat = subprocess.run(
            [sys.executable, "-c", codes[0]],
            input=modifier_entree(exporter(journal_sain(3), exporte_le=INSTANT), 1, decision="refuse"),
            capture_output=True,
            text=True,
            check=False,
            cwd=str(RACINE),
        )
        assert resultat.returncode != 0, "le vérificateur publié doit refuser un export rompu"
        assert "RUPTURE" in resultat.stdout or "RUPTURE" in resultat.stderr
