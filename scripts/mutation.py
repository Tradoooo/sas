"""Mutation testing for the two modules where a wrong answer changes a verdict.

278 green tests prove nothing on their own: a test that passes may assert
nothing. On a threshold computation (`classification.decider`) and a chain
matcher (`compositions.detecteur`), the honest measure of test strength is
**mutation**: break the code on purpose, one change at a time, and count how many
breakages the tests catch.

Standard library only — no mutmut, no cosmic-ray, nothing to install on a worker.
The tree is **copied** before being mutated (`scripts/mutation_copie.sh`), so the
working copy is never at risk.

Usage:
    python3 scripts/mutation.py --echantillon 15      # fast guard, ~1 min
    python3 scripts/mutation.py --complet             # every mutant
    python3 scripts/mutation.py --lister              # list mutants, run nothing
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
COPIE = RACINE / "scripts" / "mutation_copie.sh"

CIBLES: tuple[str, ...] = (
    "src/sas/analyseur/classification.py",
    "src/sas/compositions/detecteur.py",
)

# The test subset a mutant must be caught by. Kept to what actually exercises the
# two targets, so the full run stays inside a nightly job rather than a PR.
TESTS: tuple[str, ...] = (
    "tests/unit/analyseur",
    "tests/unit/banc",
    "tests/unit/rapports",
    "tests/integration",
)

# Operators, as (name, pattern, replacement) applied line by line. Every match on
# a line yields one mutant, so a line with two comparisons yields two mutants.
OPERATEURS: tuple[tuple[str, str, str], ...] = (
    ("comparaison inverse", r">=", "<"),
    ("comparaison inverse", r"<=", ">"),
    ("comparaison stricte élargie", r"(?<![<>=!])>(?!=)", ">="),
    ("comparaison stricte élargie", r"(?<![<>=!])<(?!=)", "<="),
    ("égalité niée", r"(?<![<>=!])==(?!=)", "!="),
    ("inégalité niée", r"!=", "=="),
    ("booléen constant vrai", r"\bTrue\b", "False"),
    ("booléen constant faux", r"\bFalse\b", "True"),
)

# Whole-token substitutions: the nature a rule returns, which is the verdict.
SUBSTITUTIONS: tuple[tuple[str, str], ...] = (
    ("Nature.HOSTILE", "Nature.TENTATIVE"),
    ("Nature.TENTATIVE", "Nature.HOSTILE"),
    ("Nature.DEBORDEMENT", "Nature.EXPLORATION"),
    ("Nature.EXPLORATION", "Nature.DEBORDEMENT"),
    ("Nature.INDETERMINEE", "Nature.EXPLORATION"),
)

# Short-circuit removal: `a and b` -> `a`, `a or b` -> `a`. Applied to the whole
# expression text rather than per line, on simple two-term forms only.
COURT_CIRCUIT: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(\w+(?:\.\w+)*)\s+and\s+\w+(?:\.\w+)*"), r"\1"),
    (re.compile(r"\b(\w+(?:\.\w+)*)\s+or\s+\w+(?:\.\w+)*"), r"\1"),
)

# Integer thresholds: shifting them by one is the classic silent regression.
ENTIER = re.compile(r"(?<![\w.])(\d+)(?![\w.])")


@dataclass(frozen=True)
class Mutant:
    identifiant: str
    cible: str
    ligne: int
    operateur: str
    avant: str
    apres: str


@dataclass(frozen=True)
class Resultat:
    mutant: Mutant
    statut: str  # "tue" | "vivant" | "invalide"
    detail: str = ""


def _lignes_ignorees(ligne: str) -> bool:
    """Never mutate a comment, a docstring line or an import."""
    stripped = ligne.strip()
    if not stripped or stripped.startswith("#"):
        return True
    if stripped.startswith(("import ", "from ", '"""', "'''")):
        return True
    return stripped.startswith(('"', "'")) and stripped.endswith(('"', "'"))


def _lignes_de_texte(source: str) -> set[int]:
    """Line numbers occupied by a string literal or an f-string.

    Mutating inside a docstring or a report template produces a "surviving
    mutant" that no logic test could ever kill: it changes prose, not behaviour.
    Enumerating them from the AST keeps the mutation score honest — an inflated
    denominator is as useless as an inflated numerator.
    """
    try:
        arbre = ast.parse(source)
    except SyntaxError:
        return set()
    texte: set[int] = set()
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Constant) and isinstance(noeud.value, str)) or isinstance(
            noeud, (ast.JoinedStr, ast.FormattedValue)
        ):
            texte.update(range(noeud.lineno, (noeud.end_lineno or noeud.lineno) + 1))
    return texte


def _iterer_lignes(source: str) -> Iterator[tuple[int, str]]:
    """Yield (line number, line) for lines that carry code, not prose."""
    texte = _lignes_de_texte(source)
    for numero, ligne in enumerate(source.splitlines(), start=1):
        if numero in texte or _lignes_ignorees(ligne):
            continue
        yield numero, ligne


def mutants_operateurs(relatif: str, source: str) -> Iterator[Mutant]:
    for numero, ligne in _iterer_lignes(source):
        for nom, motif, remplacement in OPERATEURS:
            for correspondance in re.finditer(motif, ligne):
                nouvelle = ligne[: correspondance.start()] + remplacement + ligne[correspondance.end() :]
                if nouvelle == ligne:
                    continue
                yield Mutant(
                    identifiant=_id(relatif, numero, nom, correspondance.start()),
                    cible=relatif,
                    ligne=numero,
                    operateur=nom,
                    avant=ligne.strip(),
                    apres=nouvelle.strip(),
                )


def mutants_substitutions(relatif: str, source: str) -> Iterator[Mutant]:
    for numero, ligne in _iterer_lignes(source):
        for avant, apres in SUBSTITUTIONS:
            if avant in ligne:
                yield Mutant(
                    identifiant=_id(relatif, numero, f"nature {avant}->{apres}", ligne.index(avant)),
                    cible=relatif,
                    ligne=numero,
                    operateur=f"nature substituée ({avant} -> {apres.split('.')[-1]})",
                    avant=ligne.strip(),
                    apres=ligne.replace(avant, apres, 1).strip(),
                )


def mutants_court_circuit(relatif: str, source: str) -> Iterator[Mutant]:
    for numero, ligne in _iterer_lignes(source):
        for motif, remplacement in COURT_CIRCUIT:
            for correspondance in motif.finditer(ligne):
                nouvelle = (
                    ligne[: correspondance.start()]
                    + remplacement.replace("\\1", correspondance.group(1))
                    + ligne[correspondance.end() :]
                )
                if nouvelle.strip() == ligne.strip():
                    continue
                yield Mutant(
                    identifiant=_id(relatif, numero, "court-circuit", correspondance.start()),
                    cible=relatif,
                    ligne=numero,
                    operateur="court-circuit supprimé",
                    avant=ligne.strip(),
                    apres=nouvelle.strip(),
                )


def mutants_seuils(relatif: str, source: str) -> Iterator[Mutant]:
    """Threshold integers shifted by one, in both directions."""
    for numero, ligne in _iterer_lignes(source):
        if "seuils." not in ligne:
            continue
        for correspondance in ENTIER.finditer(ligne):
            valeur = int(correspondance.group(1))
            for delta in (1, -1):
                if valeur + delta < 0:
                    continue
                nouvelle = (
                    ligne[: correspondance.start()] + str(valeur + delta) + ligne[correspondance.end() :]
                )
                yield Mutant(
                    identifiant=_id(relatif, numero, f"seuil {valeur}{delta:+d}", correspondance.start()),
                    cible=relatif,
                    ligne=numero,
                    operateur=f"seuil décalé ({valeur} -> {valeur + delta})",
                    avant=ligne.strip(),
                    apres=nouvelle.strip(),
                )


def mutants_ordre(relatif: str, source: str) -> Iterator[Mutant]:
    """Swap two adjacent rule references: in this code the ORDER is the spec."""
    motif = re.compile(r"^\s+(self\._\w+|_[a-z_]+),\s*$")
    lignes = source.splitlines()
    texte = _lignes_de_texte(source)
    for index in range(len(lignes) - 1):
        if (index + 1) in texte or (index + 2) in texte:
            continue
        premier, second = motif.match(lignes[index]), motif.match(lignes[index + 1])
        if not (premier and second):
            continue
        permutees = list(lignes)
        permutees[index] = lignes[index].replace(premier.group(1), second.group(1))
        permutees[index + 1] = lignes[index + 1].replace(second.group(1), premier.group(1))
        yield Mutant(
            identifiant=_id(relatif, index + 1, "ordre inversé", 0),
            cible=relatif,
            ligne=index + 1,
            operateur=f"ordre des règles inversé ({premier.group(1)} <-> {second.group(1)})",
            avant=lignes[index].strip(),
            apres=permutees[index].strip(),
        )


def tous_les_mutants() -> tuple[Mutant, ...]:
    """Deterministic enumeration: sorted by target, line, operator, position."""
    generer: Sequence[Callable[[str, str], Iterator[Mutant]]] = (
        mutants_operateurs,
        mutants_substitutions,
        mutants_court_circuit,
        mutants_seuils,
        mutants_ordre,
    )
    sortie: list[Mutant] = []
    for relatif in CIBLES:
        source = (RACINE / relatif).read_text(encoding="utf-8")
        for fonction in generer:
            sortie.extend(fonction(relatif, source))
    return tuple(sorted(sortie, key=lambda m: (m.cible, m.ligne, m.operateur, m.identifiant)))


def _id(relatif: str, ligne: int, operateur: str, position: int) -> str:
    return hashlib.sha256(f"{relatif}:{ligne}:{operateur}:{position}".encode()).hexdigest()[:10]


def appliquer(mutant: Mutant, copie: Path) -> bool:
    """Write the mutant into the copy. False when the line no longer matches."""
    chemin = copie / mutant.cible
    lignes = chemin.read_text(encoding="utf-8").splitlines(keepends=True)
    if mutant.ligne > len(lignes):
        return False
    originale = lignes[mutant.ligne - 1]
    if originale.strip() != mutant.avant:
        return False
    terminaison = "\n" if originale.endswith("\n") else ""
    lignes[mutant.ligne - 1] = mutant.apres + terminaison
    chemin.write_text("".join(lignes), encoding="utf-8")
    return True


def lancer_tests(copie: Path) -> tuple[int, str]:
    resultat = subprocess.run(
        [sys.executable, "-m", "pytest", *TESTS, "-x", "-q", "--no-header", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(copie),
        env={**os.environ, "PYTHONPATH": "src:."},
        timeout=900,
    )
    return resultat.returncode, (resultat.stdout + resultat.stderr)[-400:]


def evaluer(mutants: Sequence[Mutant], copie_modele: Path) -> list[Resultat]:
    """Run each mutant in a fresh copy of the pristine tree."""
    resultats: list[Resultat] = []
    for mutant in mutants:
        with _copie(copie_modele) as copie:
            if not appliquer(mutant, Path(copie)):
                resultats.append(Resultat(mutant, "invalide", "la ligne cible a changé"))
                continue
            try:
                code, sortie = lancer_tests(Path(copie))
            except subprocess.TimeoutExpired:
                resultats.append(Resultat(mutant, "tue", "délai dépassé"))
                continue
            if code != 0:
                premiere = _premiere_ligne_echec(sortie)
                resultats.append(Resultat(mutant, "tue", premiere))
            else:
                resultats.append(Resultat(mutant, "vivant", "aucun test n'échoue"))
    return resultats


class _copie:
    """Context manager: a fresh copy of the pristine tree, removed afterwards."""

    def __init__(self, modele: Path) -> None:
        self.modele = modele
        self.chemin: Path | None = None

    def __enter__(self) -> str:
        self.chemin = Path(tempfile.mkdtemp(dir=str(self.modele.parent), prefix="run-"))
        shutil.rmtree(self.chemin, ignore_errors=True)
        shutil.copytree(self.modele, self.chemin)
        return str(self.chemin)

    def __exit__(self, *exc: object) -> None:
        if self.chemin is not None:
            shutil.rmtree(self.chemin, ignore_errors=True)


def _premiere_ligne_echec(sortie: str) -> str:
    for ligne in sortie.splitlines():
        if ligne.startswith("FAILED") or "assert" in ligne:
            return ligne.strip()[:160]
    return "échec détecté"


def rapport(resultats: Sequence[Resultat]) -> str:
    """Deterministic Markdown report: no clock, no machine data, sorted output."""
    tues = [r for r in resultats if r.statut == "tue"]
    vivants = [r for r in resultats if r.statut == "vivant"]
    invalides = [r for r in resultats if r.statut == "invalide"]
    evalues = len(tues) + len(vivants)
    taux = (len(tues) / evalues * 100.0) if evalues else 0.0
    lignes = [
        "# Rapport de mutation",
        "",
        f"- cibles : {', '.join(CIBLES)}",
        f"- mutants évalués : {evalues} "
        f"(tués {len(tues)}, vivants {len(vivants)}, invalides {len(invalides)})",
        f"- **taux de mutation : {taux:.1f} %**",
        "",
        "## Mutants vivants",
        "",
    ]
    if not vivants:
        lignes.append("Aucun. Chaque cassure introduite a été attrapée par au moins un test.")
    else:
        lignes += ["| Cible | Ligne | Opérateur | Code après mutation |", "|---|---|---|---|"]
        for resultat in sorted(vivants, key=lambda r: (r.mutant.cible, r.mutant.ligne)):
            m = resultat.mutant
            lignes.append(f"| `{m.cible}` | {m.ligne} | {m.operateur} | `{m.apres[:90]}` |")
    lignes += ["", "## Mutants invalides", ""]
    lignes.append(
        "Aucun."
        if not invalides
        else "\n".join(f"- `{r.mutant.cible}:{r.mutant.ligne}` — {r.detail}" for r in invalides)
    )
    return "\n".join(lignes) + "\n"


def echantillonner(mutants: Sequence[Mutant], taille: int) -> tuple[Mutant, ...]:
    """A deterministic sample: every tenth mutant, so the guard covers both files."""
    if taille >= len(mutants):
        return tuple(mutants)
    pas = max(1, len(mutants) // taille)
    return tuple(mutants[::pas][:taille])


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    groupe = parseur.add_mutually_exclusive_group(required=True)
    groupe.add_argument("--echantillon", type=int, help="nombre de mutants à jouer (garde rapide)")
    groupe.add_argument("--complet", action="store_true", help="jouer tous les mutants")
    groupe.add_argument("--lister", action="store_true", help="lister sans rien exécuter")
    parseur.add_argument("--rapport", type=Path, default=None)
    args = parseur.parse_args()

    mutants = tous_les_mutants()
    if args.lister:
        for mutant in mutants:
            print(f"{mutant.identifiant} {mutant.cible}:{mutant.ligne} [{mutant.operateur}]")
        print(f"{len(mutants)} mutant(s)")
        return 0

    selection = mutants if args.complet else echantillonner(mutants, args.echantillon)
    print(f"{len(selection)} mutant(s) sur {len(mutants)} générés")

    modele = RACINE / ".mutants" / "modele"
    modele.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["bash", str(COPIE), str(modele)], check=True, capture_output=True)
    try:
        resultats = evaluer(selection, modele)
    finally:
        shutil.rmtree(modele.parent, ignore_errors=True)

    texte = rapport(resultats)
    if args.rapport:
        args.rapport.parent.mkdir(parents=True, exist_ok=True)
        args.rapport.write_text(texte, encoding="utf-8")
    print(texte)
    vivants = [r for r in resultats if r.statut == "vivant"]
    return 1 if vivants else 0


if __name__ == "__main__":
    sys.exit(main())
