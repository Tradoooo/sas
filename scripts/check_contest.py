"""Hackathon submission conformity check (lot 0, frozen).

`make contest` — prints a report and exits non-zero when a **blocking** item
is missing. Warnings never fail the build: they list what is still in flight
while the lots land one by one.

Checks, all offline and stdlib-only:

* deliverables present and in English (spec §29);
* the six AgentCore components each do real work in the code (§20.2);
* every functional / non-functional requirement and every acceptance test of
  §33.2 is covered by at least one test (traceability matrix);
* eight scenarios and three demo guests exist (§6.3, annexe F);
* evaluation bench sized as specified (annexe F.3);
* CI budget respected (≤ 5 min per job, user rule 2026-10-24);
* no secret-looking material anywhere in the tracked tree;
* size limits (< 500 lines / < 50 per function).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

LIVRABLES: tuple[tuple[str, bool], ...] = (
    ("README.md", True),
    ("LICENSE", True),
    ("docs/ARCHITECTURE.md", True),
    ("docs/HLD.md", True),
    ("docs/SUBMISSION.md", True),
    ("docs/TEST-INSTRUCTIONS.md", True),
    ("docs/VIDEO.md", True),
    ("docs/CONTRACTS.md", True),
    ("docs/RUNBOOK.md", False),
    ("docs/RECETTE.md", False),
    ("docs/fr/CAHIER-DES-CHARGES.md", True),
)

AGENTCORE: tuple[str, ...] = (
    "Runtime",
    "Gateway",
    "Identity",
    "Policy",
    "Memory",
    "Observability",
)

SECRETS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bASIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-airo-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
)

IGNORES: tuple[str, ...] = (".git", "__pycache__", "node_modules", ".venv", "cdk.out", ".build")


def fichiers(suffixes: tuple[str, ...]) -> list[Path]:
    trouves: list[Path] = []
    for chemin in sorted(RACINE.rglob("*")):
        if not chemin.is_file() or chemin.suffix not in suffixes:
            continue
        if any(partie in IGNORES for partie in chemin.parts):
            continue
        trouves.append(chemin)
    return trouves


def relatif(chemin: Path) -> str:
    return str(chemin.relative_to(RACINE))


def texte(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8", errors="replace")


class Rapport:
    def __init__(self) -> None:
        self.bloquants: list[str] = []
        self.avertissements: list[str] = []
        self.ok: list[str] = []

    def exiger(self, condition: bool, message: str) -> bool:
        (self.ok if condition else self.bloquants).append(message)
        return condition

    def preferer(self, condition: bool, message: str) -> bool:
        (self.ok if condition else self.avertissements).append(message)
        return condition


def verifier_livrables(rapport: Rapport) -> None:
    for chemin, bloquant in LIVRABLES:
        existe = (RACINE / chemin).is_file()
        if existe:
            rapport.ok.append(f"livrable {chemin}")
        elif bloquant:
            rapport.bloquants.append(f"livrable manquant: {chemin}")
        else:
            rapport.avertissements.append(f"livrable manquant (non bloquant): {chemin}")


def verifier_anglais(rapport: Rapport) -> None:
    """Submission deliverables must be English (spec preamble)."""
    for chemin in ("README.md", "docs/HLD.md", "docs/ARCHITECTURE.md", "docs/SUBMISSION.md"):
        cible = RACINE / chemin
        if not cible.is_file():
            continue
        corps = texte(cible)
        accentues = len(re.findall(r"[àâäéèêëîïôöùûüçœÀÂÄÉÈÊËÎÏÔÖÙÛÜŒ]", corps))
        rapport.preferer(accentues <= 3, f"{chemin} en anglais ({accentues} caractère(s) accentué(s))")


def verifier_agentcore(rapport: Rapport) -> None:
    """Each of the six components must appear in the AWS backend, not only in
    the prose: that is what makes them essential rather than decorative."""
    aws = RACINE / "src/sas/agentcore/aws.py"
    if not aws.is_file():
        rapport.avertissements.append("backend AWS absent (lot 17 en cours)")
        return
    corps = texte(aws)
    for composant in AGENTCORE:
        rapport.exiger(composant in corps, f"AgentCore {composant} utilisé dans le backend AWS")
    ports = RACINE / "src/sas/agentcore/ports.py"
    if ports.is_file():
        for composant in AGENTCORE:
            rapport.exiger(
                f"class {composant}(Protocol)" in texte(ports),
                f"AgentCore {composant} défini comme port",
            )


def verifier_tracabilite(rapport: Rapport) -> None:
    """Every EF-xx, ENF-xx and R1..R24 must be quoted by at least one test.

    The identifier lists come from `sas.constantes`, so the matrix follows the
    specification instead of a hand-made range.
    """
    sys.path.insert(0, str(RACINE / "src"))
    from sas import constantes

    corpus = "\n".join(texte(c) for c in fichiers((".py",)) if "tests" in c.parts or "eval" in c.parts)
    if not corpus:
        rapport.avertissements.append("aucun test trouvé (lots en cours)")
        return
    for famille, identifiants in (
        ("EF", constantes.EF),
        ("ENF", constantes.ENF),
        ("R", constantes.RECETTE),
    ):
        absents = [i for i in identifiants if i not in corpus]
        rapport.preferer(
            not absents,
            f"traçabilité {famille}: {len(identifiants) - len(absents)}/{len(identifiants)}"
            + (f" — manquent {', '.join(absents[:12])}" if absents else ""),
        )


def verifier_donnees(rapport: Rapport) -> None:
    scenarios = sorted((RACINE / "scenarios").glob("*.yaml")) if (RACINE / "scenarios").is_dir() else []
    rapport.exiger(len(scenarios) >= 8, f"8 scénarios en données ({len(scenarios)} trouvé(s))")
    rapport.exiger(
        _nombre_regles_composition() >= 3,
        f"3 règles de composition en données ({_nombre_regles_composition()} trouvée(s))",
    )
    agents = sorted((RACINE / "demo/agents").glob("*.py")) if (RACINE / "demo/agents").is_dir() else []
    rapport.exiger(len(agents) >= 4, f"3 agents invités de démonstration ({len(agents)} fichier(s))")
    gen = RACINE / "eval/genere-agents.mjs"
    rapport.preferer(gen.is_file(), "banc d'évaluation généré par script (eval/genere-agents.mjs)")


def _nombre_regles_composition() -> int:
    """Count the composition rules inside the data files, not the files.

    Three motives live in one file (spec §16.2); counting files would report a
    single rule and fail a correct repository.
    """
    dossier = RACINE / "regles"
    if not dossier.is_dir():
        return 0
    total = 0
    for fichier in sorted(dossier.glob("*.yaml")):
        try:
            import yaml

            donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        total += len(donnees.get("regles", ()))
    return total


def verifier_ci(rapport: Rapport) -> None:
    for wf in sorted((RACINE / ".github/workflows").glob("*.yml")):
        corps = texte(wf)
        jobs = len(re.findall(r"^ {2}\w[\w-]*:\n(?:.*\n)*?(?=^ {2}\w|\Z)", corps, re.M))
        delais = [int(m) for m in re.findall(r"timeout-minutes:\s*(\d+)", corps)]
        rapport.exiger(all(d <= 5 for d in delais), f"{relatif(wf)}: budget ≤ 5 min ({delais})")
        rapport.preferer(
            "fetch-depth: 1" in corps or "checkout" not in corps,
            f"{relatif(wf)}: checkout superficiel ({jobs} job(s))",
        )


def verifier_secrets(rapport: Rapport) -> None:
    """Only reports a violation: a green line per file would bury the report."""
    violes: list[str] = []
    for chemin in fichiers((".py", ".md", ".yml", ".yaml", ".json", ".ts", ".mjs", ".sh", ".txt", ".toml")):
        corps = texte(chemin)
        violes += [f"{relatif(chemin)}: {motif.pattern}" for motif in SECRETS if motif.search(corps)]
    rapport.exiger(not violes, "aucun secret dans l'arbre suivi")
    rapport.bloquants.extend(violes[:20])


def verifier_limites(rapport: Rapport) -> None:
    resultat = subprocess.run(
        [sys.executable, str(RACINE / "scripts/check_limits.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    rapport.exiger(resultat.returncode == 0, "gardes de taille (< 500 / < 50)")
    if resultat.returncode != 0:
        rapport.bloquants.append(resultat.stdout.strip()[:600])


# The needle is assembled at runtime so that this very file cannot match
# itself (it did, once).
AIGUILLE_ALEATOIRE = "import " + "random"
AIGUILLE_MESSAGE = f"{AIGUILLE_ALEATOIRE} direct"


def verifier_depots_interdits(rapport: Rapport) -> None:
    """Direct use of the stdlib PRNG breaks reproducibility (contract B)."""
    violes = [
        relatif(c)
        for c in fichiers((".py",))
        if c.name != "aleatoire.py"
        and "tests" not in c.parts
        and ".github" not in c.parts
        and AIGUILLE_ALEATOIRE in texte(c)
    ]
    rapport.exiger(not violes, "aléatoire uniquement via sas.aleatoire")
    rapport.bloquants.extend(f"{v}: {AIGUILLE_MESSAGE}" for v in violes)


def main() -> int:
    rapport = Rapport()
    verifier_livrables(rapport)
    verifier_anglais(rapport)
    verifier_agentcore(rapport)
    verifier_tracabilite(rapport)
    verifier_donnees(rapport)
    verifier_ci(rapport)
    verifier_secrets(rapport)
    verifier_limites(rapport)
    verifier_depots_interdits(rapport)

    print(f"CONFORMITÉ SOUMISSION — {len(rapport.ok)} contrôle(s) vert(s)")
    for message in rapport.avertissements:
        print(f"  ~ {message}")
    for message in rapport.bloquants:
        print(f"  ✗ {message}")
    if rapport.bloquants:
        print(f"CONFORMITÉ: {len(rapport.bloquants)} point(s) bloquant(s)")
        return 1
    print("CONFORMITÉ: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
