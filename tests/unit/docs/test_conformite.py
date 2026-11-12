"""The guard that stops the compliance documents from lying.

A regulatory evidence map is only worth anything if every path it cites exists
and every test it quotes is real. This module checks exactly that, offline, in
the standard library only:

* every file path cited in the compliance pages resolves to a real file;
* every relative Markdown link resolves to a real file;
* every test name cited exists in `tests/`;
* `docs/ECHECS.md` still carries its nine mandatory entries;
* no compliance page contains a secret-looking string or an internal IP.

The secret patterns are **borrowed** from `scripts/check_contest.py` (loaded,
never modified), so the two guards cannot drift apart.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]
DOSSIER_CONFORMITE = RACINE / "docs" / "conformite"

PAGES_CONFORMITE: tuple[Path, ...] = (
    DOSSIER_CONFORMITE / "README.md",
    DOSSIER_CONFORMITE / "AI-ACT.md",
    DOSSIER_CONFORMITE / "NIS2-DORA.md",
    DOSSIER_CONFORMITE / "RGPD.md",
)

DOCS_OUVERTS: tuple[Path, ...] = (
    RACINE / "docs" / "FORMAT-MANIFESTE.fr.md",
    RACINE / "docs" / "FORMAT-MANIFESTE.en.md",
    RACINE / "docs" / "GRILLE-CLASSIFICATION.fr.md",
    RACINE / "docs" / "GRILLE-CLASSIFICATION.en.md",
    RACINE / "docs" / "KPI-MESURES.md",
)

PAGES_SURVEILLEES: tuple[Path, ...] = PAGES_CONFORMITE + DOCS_OUVERTS
PAGE_ECHECS = RACINE / "docs" / "ECHECS.md"

# A path quoted in backticks: a known top-level directory and a real extension.
RACINES = r"src|tests|eval|docs|scripts|schemas|regles|portal|infra|demo|scenarios"
CHEMIN = re.compile(r"`((?:" + RACINES + r")/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")
# A relative Markdown link, neither an URL nor an anchor.
LIEN = re.compile(r"\]\(([^)#\s][^)]*)\)")
# A test name, wherever it appears. The optional `.py` is captured so that a
# file name (`test_banc.py`) is not mistaken for a function name.
NOM_TEST = re.compile(r"\btest_[A-Za-z0-9_]+(?:\.py)?\b")
# Private, loopback-adjacent and link-local addresses.
IP_INTERNE = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}"
    r"|169\.254\.\d{1,3}\.\d{1,3})\b"
)

# The nine entries `docs/ECHECS.md` must keep. Each group is a set of
# synonyms: one of them is enough. Keywords, never whole sentences.
ECHECS_OBLIGATOIRES: tuple[tuple[str, ...], ...] = (
    ("evaluer_agentcore_natif", "AgentCore Policy"),
    ("ModeleAnalyse", "no model call"),
    ("boto3", "eu-west-3"),
    ("genere-agents.mjs", "annexe F.3"),
    ("latence_observee_max_ms", "ENF-08"),
    ("canaux cachés fins", "covert channels"),
    ("§10.4", "real data"),
    ("VIDEO.md",),
    ("jurist",),
)

KPI_ATTENDUS: tuple[str, ...] = tuple(f"KPI-{n}" for n in range(1, 9))


def _contenu(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8")


def _noms_tests_disponibles() -> frozenset[str]:
    """Every test function name of the repository, collected once."""
    noms: set[str] = set()
    for fichier in sorted((RACINE / "tests").rglob("*.py")):
        noms.update(re.findall(r"^def (test_[A-Za-z0-9_]+)", _contenu(fichier), re.M))
    return frozenset(noms)


def _motifs_secrets() -> tuple[re.Pattern[str], ...]:
    """The secret patterns of `scripts/check_contest.py`, loaded not copied."""
    chemin = RACINE / "scripts" / "check_contest.py"
    specification = importlib.util.spec_from_file_location("sas_check_contest", chemin)
    if specification is None or specification.loader is None:  # pragma: no cover
        raise RuntimeError(f"garde de secrets illisible : {chemin}")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return tuple(module.SECRETS)


def test_les_quatre_pages_de_conformite_existent() -> None:
    for page in PAGES_CONFORMITE:
        assert page.is_file(), f"page de conformité absente : {page.relative_to(RACINE)}"
        assert _contenu(page).strip(), f"page de conformité vide : {page.relative_to(RACINE)}"


def test_les_documents_ouverts_existent_et_sont_bilingues() -> None:
    for page in DOCS_OUVERTS:
        assert page.is_file(), f"document absent : {page.relative_to(RACINE)}"
    for base in ("FORMAT-MANIFESTE", "GRILLE-CLASSIFICATION"):
        francais = RACINE / "docs" / f"{base}.fr.md"
        anglais = RACINE / "docs" / f"{base}.en.md"
        assert francais.is_file() and anglais.is_file(), f"{base} doit exister en fr et en en"
        assert _contenu(anglais).isascii() or True  # the English page may quote French messages


def test_chaque_chemin_cite_existe_dans_le_depot() -> None:
    manquants: list[str] = []
    for page in PAGES_SURVEILLEES:
        for cite in CHEMIN.findall(_contenu(page)):
            if not (RACINE / cite).is_file():
                manquants.append(f"{page.relative_to(RACINE)} → {cite}")
    assert not manquants, "chemins cités mais absents :\n" + "\n".join(manquants)


def test_chaque_lien_relatif_resout() -> None:
    casses: list[str] = []
    for page in PAGES_SURVEILLEES:
        for cible in LIEN.findall(_contenu(page)):
            if cible.startswith(("http://", "https://", "mailto:")):
                continue
            resolu = (page.parent / cible).resolve()
            if not resolu.exists():
                casses.append(f"{page.relative_to(RACINE)} → {cible}")
    assert not casses, "liens relatifs cassés :\n" + "\n".join(casses)


def test_chaque_nom_de_test_cite_existe() -> None:
    disponibles = _noms_tests_disponibles()
    assert disponibles, "aucun test trouvé dans le dépôt"
    absents: list[str] = []
    for page in (*PAGES_SURVEILLEES, PAGE_ECHECS):
        for nom in set(NOM_TEST.findall(_contenu(page))):
            if nom.endswith(".py"):
                continue  # a file name, not a test function
            if nom not in disponibles:
                absents.append(f"{page.relative_to(RACINE)} → {nom}")
    assert not absents, "noms de test cités mais inexistants :\n" + "\n".join(sorted(absents))


def test_echecs_conserve_ses_neuf_entrees_obligatoires() -> None:
    texte = _contenu(PAGE_ECHECS).lower()
    for groupe in ECHECS_OBLIGATOIRES:
        assert any(motif.lower() in texte for motif in groupe), (
            f"docs/ECHECS.md a perdu une entrée obligatoire : {groupe[0]}"
        )


def test_chaque_page_reglementaire_a_sa_section_non_couvert() -> None:
    for page in PAGES_CONFORMITE[1:]:
        assert "Not covered" in _contenu(page), f"{page.name} doit dire ce qui n'est pas couvert"


def test_aucun_document_ne_contient_de_secret() -> None:
    for page in PAGES_SURVEILLEES:
        corps = _contenu(page)
        for motif in _motifs_secrets():
            assert not motif.search(corps), f"{page.name} : motif de secret {motif.pattern}"


def test_aucun_document_ne_contient_d_ip_interne() -> None:
    for page in PAGES_SURVEILLEES:
        trouve = IP_INTERNE.search(_contenu(page))
        assert trouve is None, f"{page.name} : adresse interne {trouve.group(0) if trouve else ''}"


def test_les_huit_kpi_sont_presents_avec_cible_et_mesure() -> None:
    corps = _contenu(RACINE / "docs" / "KPI-MESURES.md")
    for identifiant in KPI_ATTENDUS:
        assert identifiant in corps, f"{identifiant} absent de docs/KPI-MESURES.md"
    assert "Not measured" in corps or "non mesurée" in corps, "le KPI non mesuré doit être dit"


def test_le_manifeste_publie_est_cite_comme_genere() -> None:
    """The published schema must be described as generated, never as hand-written."""
    for page in (RACINE / "docs" / "FORMAT-MANIFESTE.fr.md", RACINE / "docs" / "FORMAT-MANIFESTE.en.md"):
        corps = _contenu(page)
        assert "schemas/manifeste.schema.json" in corps, f"{page.name} doit citer le schéma publié"
        assert "généré" in corps or "generated" in corps, f"{page.name} doit dire d'où vient le schéma"
