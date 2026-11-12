"""Generate `docs/RECETTE.md` from the test corpus — so it cannot lie.

The acceptance matrix is a submission deliverable (spec §29). Its first version
was written by hand while only seven lots existed and drifted behind the code:
rows said "not covered yet" for requirements that later gained a named test.
A matrix that under-reports is as misleading as one that over-reports.

This script applies the exact same rule as `scripts/check_contest.py`: an
identifier (`EF-xx`, `ENF-xx`, `R<n>`) is *covered* when it appears in at least
one Python file under `tests/` or `eval/`. It emits `docs/RECETTE.md` with, for
each covered identifier, the real file (and the test function, when one of its
docstring or body mentions it). `--verifier` exits non-zero when the committed
file has drifted, so the CI fails on a stale matrix instead of shipping one.

Stdlib only. The requirement texts below are the short forms of spec §12, §19
and §33.2, kept here as the single source so the prose and the scan stay in one
place.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CIBLE = RACINE / "docs" / "RECETTE.md"

EXIGENCES_FONCTIONNELLES: dict[str, str] = {
    "EF-01": "Enter, validate and version an agent manifest",
    "EF-02": "Refuse a manifest whose permissions are not fine-grained",
    "EF-03": "Require the editor's signature and the sponsor's validation",
    "EF-04": "Refuse any execution without a signed, validated, current manifest",
    "EF-05": "Derive the perimeter policy from the manifest, never hand-written",
    "EF-10": "Build a shadow environment from the manifest declaration",
    "EF-11": "Run the guest in an isolated session with an ephemeral identity",
    "EF-12": "Run N replays per scenario with controlled seed and dispersion",
    "EF-13": "Bound every execution (calls, tokens, duration, memory); clean stop",
    "EF-14": "Journal 100 % of tool calls with their causal chain",
    "EF-15": "Immediate suspension, in shadow as well as observed mode",
    "EF-16": "Isolate sessions; no state leak except explicitly declared memory",
    "EF-17": "Destroy the shadow environment at campaign end, with proof",
    "EF-20": "Compute the behaviour envelope across N replays",
    "EF-21": "Declared/observed gap both ways; cross-reference IAM Access Analyzer",
    "EF-22": "Classify each out-of-scope attempt (grid of §13)",
    "EF-23": "Detect forbidden compositions on chains of two and three calls",
    "EF-24": "Publish the statistical confidence bound for N replays",
    "EF-25": "A model never fixes a final severity or classification; code decides",
    "EF-30": "Keep a reference envelope per homologated version",
    "EF-31": "Replay scenarios periodically and compare to the reference",
    "EF-32": "Alert on new attempts, vanished behaviour, budget overshoot",
    "EF-33": "Detect an undeclared version or model change",
    "EF-34": "Auto-suspend an agent whose drift exceeds the configured threshold",
    "EF-40": "Produce a complete homologation report, in French and English",
    "EF-41": "Produce a dated, chained, exportable, deliberately-poor attestation",
    "EF-42": "Produce a gap report for the editor, without client data",
    "EF-43": "Keep a registry of every third-party agent of a client",
    "EF-44": "Replay a specific scenario from a finding",
    "EF-50": "Strictly isolate tenants: no session, journal or report crosses",
    "EF-51": "Derive tenant identity from the token, never from free text",
    "EF-52": "Bound and expose the cost per tenant",
    "EF-53": "Let an editor see only the gap report that concerns it",
}

EXIGENCES_NON_FONCTIONNELLES: dict[str, str] = {
    "ENF-01": "No execution without a signed, validated, current manifest",
    "ENF-02": "Ephemeral identity per session, never a long-lived guest credential",
    "ENF-03": "Call/token/duration/memory budgets enforced by Policy, clean stop",
    "ENF-04": "100 % journalling, denials included, chained and immutable",
    "ENF-05": "Strict isolation between sessions and between tenants",
    "ENF-06": "Shadow environment destroyed at campaign end, with proof",
    "ENF-07": "No real personal data in the demonstration set",
    "ENF-08": "Added latency < 100 ms per tool call in observed mode (to confirm)",
    "ENF-09": "Kill switch effective in under 5 seconds, shadow and observed",
    "ENF-10": "Cost per homologation measured and exposed, never estimated afterwards",
    "ENF-11": "Reproducibility: same scenarios, same seed, same conclusions",
    "ENF-12": "Configurable journal retention, effective and provable purge",
    "ENF-13": "French and English interface and reports; English submission deliverables",
    "ENF-14": "Files < 500 lines, functions < 50 lines, CI ≤ 5 min",
    "ENF-15": "Reproducible IaC deployment, no undocumented manual step",
    "ENF-16": "The solution stays online free until 2027-01-22",
    "ENF-17": "A non-instrumentable agent is declared not measurable, never compliant",
}

RECETTE: dict[str, str] = {
    "R1": "Launch a campaign without a signed manifest → explicit refusal, no session",
    "R2": 'Submit a manifest with a coarse "S3 access" → refused, actionable reason',
    "R3": "Modify the manifest after signature → new version, attestation invalidated",
    "R4": "The generated policy matches the manifest; no hand-written rule",
    "R5": "Run 8 scenarios x 6 replays -> 48 isolated sessions, no state leak",
    "R6": "Exceed the call budget → clean stop, session marked, campaign continues",
    "R7": "Suspend during a session → stop, credentials revoked, no later call",
    "R8": "Count emitted vs journalled calls → 100 %, denials included",
    "R9": "Break the journal fingerprint chain → break detected on read",
    "R10": "Chatty agent touching a decoy → gap published, exploration filtered",
    "R11": "Curious agent: sensitive read then outbound → hostile, refused",
    "R12": "Conforming agent → zero gap, homologated, and the report says so",
    "R13": "Exploration filtering → exploration calls do not appear as findings",
    "R14": "Declared permissions never used → published as dead permissions",
    "R15": "Two campaigns with the same seed → same conclusions",
    "R16": "Change the model without the version → drift detected next cycle",
    "R17": "Verify the published bound → a p-known behaviour detected as expected",
    "R18": "Client A tries to read B's journal → refused and journaled",
    "R19": "Attestation → poor in detail, no client data, statistical scope present",
    "R20": "Editor report → no client content",
    "R21": "Destroy the shadow environment → proof, no residual resource",
    "R22": "Measured cost → deviation < 25 % vs annexe G",
    "R23": "Add a scenario in data → executable without a code change",
    "R24": "Non-instrumentable agent → declared not measurable, no attestation",
}


def _scan_corpus() -> tuple[dict[str, list[str]], frozenset[str]]:
    """For each identifier, the `file::test` spots that mention it — and the
    set of every test function name in the tree (so a file name is not mistaken
    for a test name)."""
    citations: dict[str, list[str]] = {}
    noms_tests: set[str] = set()
    for fichier in sorted((RACINE / "tests").rglob("*.py")) + sorted((RACINE / "eval").rglob("*.py")):
        source = fichier.read_text(encoding="utf-8")
        relatif = fichier.relative_to(RACINE).as_posix()
        try:
            arbre = ast.parse(source)
        except SyntaxError:
            continue
        for noeud in ast.walk(arbre):
            if isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)) and noeud.name.startswith("test_"):
                noms_tests.add(noeud.name)
        for identifiant in _identifiants():
            if re.search(rf"\b{identifiant}\b", source):
                spots = _spots(arbre, source, identifiant)
                if spots:
                    citations.setdefault(identifiant, []).extend(f"{relatif}::{s}" for s in spots)
                else:
                    citations.setdefault(identifiant, []).append(relatif)
    for identifiant in citations:
        # stable, de-duplicated, readable
        uniques: list[str] = []
        for c in citations[identifiant]:
            if c not in uniques:
                uniques.append(c)
        citations[identifiant] = uniques
    return citations, frozenset(noms_tests)


def _identifiants() -> list[str]:
    """The frozen identifier table (`sas.constantes`), not a hand-made range.

    `scripts/check_contest.py` reads the same table, so the matrix and the
    conformity guard count exactly the same requirements.
    """
    sys.path.insert(0, str(RACINE / "src"))
    from sas import constantes

    return list(constantes.EF) + list(constantes.ENF) + list(constantes.RECETTE)


def _spots(arbre: ast.AST, source: str, identifiant: str) -> list[str]:
    """Test functions whose docstring or body mentions the identifier."""
    trouve: list[str] = []
    for noeud in ast.walk(arbre):
        if not isinstance(noeud, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not noeud.name.startswith("test_"):
            continue
        fragments = [ast.get_docstring(noeud) or ""]
        fragments += [ast.get_source_segment(source, s) or "" for s in noeud.body]
        if any(re.search(rf"\b{identifiant}\b", f) for f in fragments):
            trouve.append(noeud.name)
    return sorted(trouve)


def _statut(citations: dict[str, list[str]], identifiant: str) -> str:
    spots = citations.get(identifiant, [])
    if not spots:
        return "**not covered yet** — no test quotes this identifier"
    premiers = spots[:3]
    liste = "`, `".join(premiers)
    reste = f" (+{len(spots) - 3})" if len(spots) > 3 else ""
    return f"**covered** — `{liste}`{reste}"


def _table(lignes: list[tuple[str, str, str]]) -> str:
    corps = "\n".join(f"| {identifiant} | {libelle} | {statut} |" for identifiant, libelle, statut in lignes)
    return "| ID | Requirement (short) | Status |\n|---|---|---|\n" + corps + "\n"


def _resume(citations: dict[str, list[str]], famille: str, identifiants: list[str]) -> str:
    couverts = sum(1 for i in identifiants if citations.get(i))
    return f"**{couverts} / {len(identifiants)} {famille}** covered by the test corpus."


def generer() -> str:
    citations, _ = _scan_corpus()
    lignes_r = [(i, RECETTE[i], _statut(citations, i)) for i in sorted(RECETTE, key=_cle)]
    lignes_ef = [
        (i, EXIGENCES_FONCTIONNELLES[i], _statut(citations, i)) for i in sorted(EXIGENCES_FONCTIONNELLES)
    ]
    lignes_enf = [
        (i, EXIGENCES_NON_FONCTIONNELLES[i], _statut(citations, i))
        for i in sorted(EXIGENCES_NON_FONCTIONNELLES)
    ]

    r_identifiants = sorted(RECETTE, key=_cle)
    ef_identifiants = sorted(EXIGENCES_FONCTIONNELLES)
    enf_identifiants = sorted(EXIGENCES_NON_FONCTIONNELLES)

    resumes = " ".join(
        (
            _resume(citations, "R", r_identifiants),
            _resume(citations, "EF", ef_identifiants),
            _resume(citations, "ENF", enf_identifiants),
        )
    )
    return f"""# Sas — Acceptance matrix (R1-R24, EF-01...EF-53, ENF-01...ENF-17)

> Submission deliverable (§29). **Generated** by `scripts/genere_recette.py` —
> run `python3 scripts/genere_recette.py --verifier` (or re-run the generator)
> after touching a test, so this matrix can never drift behind the code again.
> The rule is the same one `scripts/check_contest.py` applies: an identifier is
> *covered* when at least one Python file under `tests/` or `eval/` quotes it.
> A file name is never mistaken for a test function name.

Summary: {resumes}

## 1. Acceptance tests R1-R24 (spec §33.2)

{_table(lignes_r)}

## 2. Functional requirements EF-01...EF-53 (spec §12)

{_table(lignes_ef)}

## 3. Non-functional requirements ENF-01...ENF-17 (spec §19)

{_table(lignes_enf)}
"""


def _cle(identifiant: str) -> tuple[str, int]:
    if identifiant.startswith("R"):
        return ("R", int(identifiant[1:]))
    prefixe, nombre = identifiant.split("-")
    return (prefixe, int(nombre))


def main(argv: list[str]) -> int:
    if "--verifier" in argv:
        attendu = CIBLE.read_text(encoding="utf-8") if CIBLE.is_file() else ""
        produit = generer()
        if attendu != produit:
            print(
                "docs/RECETTE.md est périmé : relancer `python3 scripts/genere_recette.py`",
                file=sys.stderr,
            )
            return 1
        return 0
    CIBLE.write_text(generer(), encoding="utf-8")
    print(f"écrit {CIBLE.relative_to(RACINE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
