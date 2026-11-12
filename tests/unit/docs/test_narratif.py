"""The guard on the narrative package: every claim must be checkable.

The narrative (the use case, the before/after, the two infographics) is the
part of the submission a judge reads in ten minutes. It is also the part where
a lie is cheapest to write — a plausible percentage, a plausible customer
story, a plausible diagram. This module makes three of those impossible,
offline and with the standard library only:

* the **use case stays fictional** — the mention "composite scenario" (or
  "fictif") must open the document, so a composite can never drift into a
  customer story by omission;
* every **file path** quoted in the two documents resolves to a real file, so
  no reader is sent to a file that does not exist;
* every **figure** quoted in the two documents is retrievable in the
  repository — in `portal/data/demo.json`, in `eval/` or in `docs/` — so a
  number nobody measured cannot reach the submission.

The two SVGs are checked as XML: parsable, with a `viewBox`, with readable
text, and with no script, no `@import` and no remote resource.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]

CAS_D_USAGE = RACINE / "docs" / "narratif" / "CAS-D-USAGE.md"
AVANT_APRES = RACINE / "docs" / "narratif" / "AVANT-APRES.md"
INFOGRAPHIE_APPROCHES = RACINE / "docs" / "narratif" / "infographie-approches.svg"
INFOGRAPHIE_CANAL = RACINE / "docs" / "narratif" / "infographie-canal.svg"

SVG = (INFOGRAPHIE_APPROCHES, INFOGRAPHIE_CANAL)
NARRATIFS = (CAS_D_USAGE, AVANT_APRES)

# The mention that keeps the use case fictional, and where it must appear.
MENTIONS_FICTION = ("composite scenario", "fictif")
FICTION_EN_TETE_DE_LIGNE = 400

# A path quoted in backticks, rooted in a directory of the repository.
RACINES = r"src|tests|eval|docs|scripts|schemas|regles|portal|infra|demo|scenarios|media"
CHEMIN = re.compile(r"`((?:" + RACINES + r")/[A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`")

# Code spans and fenced blocks carry paths, commands and identifiers — the
# digits inside them are not figures.
CODE = re.compile(r"```.*?```|`[^`]*`", re.S)
# A number, with its decimal separator, as it may be written in prose.
NOMBRE = re.compile(r"(?<![\w.])(\d+(?:[.,]\d+)*)(?![\w])")
# An ISO date, kept whole: its parts are not figures.
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# A section reference (`§16.4`) points at the specification, it is not a figure.
SECTION = re.compile(r"§\s*\d+(?:[.,]\d+)*")
# The numbering of a Markdown heading (`## 2.1 ...`) is a structure, not a figure.
TITRE = re.compile(r"(?m)^(#{1,6}\s+)\d+(?:[.,]\d+)*[.)]?\s+")
# The name of a standard is a name, not a figure.
STANDARD = re.compile(r"ISO(?:/IEC)?\s*27001", re.I)


def _tokens_bruts(texte: str) -> set[str]:
    """Every numeric token of a raw text: standalone numbers and whole dates."""
    jetons = {m.group(1).replace(",", ".") for m in NOMBRE.finditer(texte)}
    jetons |= {m.group(0) for m in DATE.finditer(texte)}
    return jetons


def _corpus() -> frozenset[str]:
    """Every figure the repository legitimately contains.

    The corpus is the published dataset, the evaluation bench and the
    documentation — the three places a number may legitimately come from. The
    narrative itself is excluded: a document never vouches for its own figures.
    The corpus is read raw: what the repository contains is what it contains.
    """
    morceaux: list[str] = []
    fichiers: list[Path] = [RACINE / "portal" / "data" / "demo.json"]
    for dossier in ("eval", "docs"):
        fichiers += sorted(p for p in (RACINE / dossier).rglob("*") if p.is_file())
    for chemin in fichiers:
        if (RACINE / "docs" / "narratif") in chemin.parents:
            continue  # the narrative itself never vouches for its own figures
        if "__pycache__" in chemin.parts:
            continue  # a bytecode cache is not a source of figures
        morceaux.append(chemin.read_text(encoding="utf-8", errors="replace"))
    return frozenset(_tokens_bruts("\n".join(morceaux)))


def _nombres(texte: str) -> list[str]:
    """The figures a text quotes, normalised (comma or dot as decimal separator).

    The same extraction is applied to the corpus and to the documents, so the
    comparison is like for like. What is *not* a figure is removed first:
    code spans and fenced blocks (paths, commands, identifiers), section
    references (`§16.4`), the numbering of Markdown headings, ISO dates, and
    the name of a standard (`ISO 27001`).
    """
    brut = CODE.sub(" ", texte)
    brut = SECTION.sub(" ", brut)
    brut = TITRE.sub(r"\1", brut)
    brut = STANDARD.sub(" ", brut)
    trouves: list[str] = []
    for correspondance in DATE.finditer(brut):
        trouves.append(correspondance.group(0))
    sans_dates = DATE.sub(" ", brut)
    for correspondance in NOMBRE.finditer(sans_dates):
        trouves.append(correspondance.group(1).replace(",", "."))
    return trouves


def _texte_svg(chemin: Path) -> str:
    """The readable content of an SVG: every text node, joined."""
    racine = ET.parse(chemin).getroot()
    morceaux = [noeud.text.strip() for noeud in racine.iter() if noeud.text and noeud.text.strip()]
    morceaux += [
        valeur.strip()
        for noeud in racine.iter()
        for cle, valeur in noeud.attrib.items()
        if cle.endswith("title") or cle.endswith("label") or cle.endswith("desc")
    ]
    return " ".join(morceaux)


def _nom_local(balise: str) -> str:
    """A tag name without its namespace."""
    return balise.rsplit("}", 1)[-1]


def _noms_locaux(racine: ET.Element) -> list[str]:
    """Tag names without their namespace."""
    return [_nom_local(balise.tag) for balise in racine.iter()]


def _sans_nom_espace_noms(source: str) -> str:
    """The source without the namespace declarations — what may not contain a URL."""
    return re.sub(r"xmlns(:[A-Za-z0-9_-]+)?\s*=\s*\"[^\"]*\"", " ", source)


# --------------------------------------------------------------------------
# the fiction guard
# --------------------------------------------------------------------------


def test_le_cas_d_usage_est_une_fiction_composite_et_le_dit_en_tete() -> None:
    """The scenario must announce itself as a composite in its first lines."""
    assert CAS_D_USAGE.is_file(), "docs/narratif/CAS-D-USAGE.md est absent"
    texte = CAS_D_USAGE.read_text(encoding="utf-8")
    debut = texte[:FICTION_EN_TETE_DE_LIGNE].lower()
    assert any(mention in debut for mention in MENTIONS_FICTION), (
        "le cas d'usage doit annoncer 'composite scenario' (ou 'fictif') dans ses "
        f"premières lignes — début lu : {debut[:160]!r}"
    )


def test_le_cas_d_usage_ne_pretend_jamais_venir_d_un_client_reel() -> None:
    """The phrases that would turn a composite into a customer story are refused."""
    interdit = (
        "a customer told us",
        "our customer said",
        "a customer told",
        "our customers report",
        "the customer told us",
    )
    texte = CAS_D_USAGE.read_text(encoding="utf-8").lower()
    trouves = [phrase for phrase in interdit if phrase in texte]
    assert not trouves, f"le cas d'usage se présente comme un témoignage client : {trouves}"


# --------------------------------------------------------------------------
# the paths guard
# --------------------------------------------------------------------------


def test_chaque_chemin_cite_existe_dans_le_depot() -> None:
    """Every backticked path of the two documents resolves to a real file."""
    manquants: list[str] = []
    for document in NARRATIFS:
        texte = document.read_text(encoding="utf-8")
        for cite in CHEMIN.findall(texte):
            if not (RACINE / cite).is_file():
                manquants.append(f"{document.name} → {cite}")
    assert not manquants, "chemins cités mais absents :\n" + "\n".join(manquants)


def test_chaque_document_cite_au_moins_une_source() -> None:
    """A narrative without a single source is exactly what this package forbids."""
    for document in NARRATIFS:
        cites = CHEMIN.findall(document.read_text(encoding="utf-8"))
        assert cites, f"{document.name} ne cite aucun fichier du dépôt"


# --------------------------------------------------------------------------
# the figures guard
# --------------------------------------------------------------------------


def test_chaque_chiffre_cite_est_retrouvable_dans_le_depot() -> None:
    """A figure nobody measured must not reach the submission."""
    corpus = _corpus()
    assert corpus, "corpus de référence vide"
    introuvables: list[str] = []
    for document in NARRATIFS:
        for figure in _nombres(document.read_text(encoding="utf-8")):
            if figure in corpus:
                continue
            introuvables.append(f"{document.name} → {figure}")
    assert not introuvables, "chiffres cités sans source dans le dépôt :\n" + "\n".join(
        sorted(set(introuvables))
    )


def test_les_chiffres_cles_du_recit_sont_bien_presents() -> None:
    """Spot-check the figures the dossier relies on, so the generic check cannot pass by luck."""
    attendu = {
        CAS_D_USAGE: ("0.82", "8.9", "0.667", "100", "98", "82", "9", "160", "2027-02-10"),
        AVANT_APRES: ("0.82", "8.9", "100", "9", "90", "0"),
    }
    for document, figures in attendu.items():
        texte = document.read_text(encoding="utf-8")
        for figure in figures:
            assert figure in texte, f"{document.name} ne cite plus le chiffre {figure}"


def test_le_repertoire_media_rappelle_que_le_cas_d_usage_est_fictif() -> None:
    """The media index must declare the use case fictional too — it points at it."""
    texte = (RACINE / "media" / "README.md").read_text(encoding="utf-8").lower()
    assert any(mention.lower() in texte for mention in MENTIONS_FICTION), (
        "media/README.md doit rappeler que le cas d'usage est une fiction"
    )
    assert "cas d'usage" in texte or "use case" in texte, "media/README.md doit désigner le cas d'usage"


# --------------------------------------------------------------------------
# the infographics guard
# --------------------------------------------------------------------------


def test_les_deux_svg_existent_et_sont_du_xml_parsable() -> None:
    """Both infographics must parse as XML — a broken image is a broken argument."""
    for chemin in SVG:
        assert chemin.is_file(), f"infographie absente : {chemin.relative_to(RACINE)}"
        try:
            ET.parse(chemin)
        except ET.ParseError as erreur:
            raise AssertionError(f"{chemin.name} n'est pas du XML valide : {erreur}") from erreur


def test_chaque_svg_a_un_viewbox_et_du_texte() -> None:
    """An explicit `viewBox` (so it scales) and at least one `<text>` (so it carries meaning)."""
    for chemin in SVG:
        racine = ET.parse(chemin).getroot()
        assert racine.get("viewBox"), f"{chemin.name} n'a pas de viewBox explicite"
        assert "text" in _noms_locaux(racine), f"{chemin.name} ne contient aucun <text>"


def test_chaque_svg_est_lisible_sans_ressource_externe() -> None:
    """No script, no `@import`, no remote URL outside the namespace declaration."""
    for chemin in SVG:
        source = chemin.read_text(encoding="utf-8")
        assert "<script" not in source.lower(), f"{chemin.name} contient un <script>"
        assert "@import" not in source, f"{chemin.name} contient un @import"
        restant = _sans_nom_espace_noms(source)
        assert "http" not in restant, f"{chemin.name} référence une ressource distante"
        assert "url(" not in restant.replace("url(#fleche)", ""), (
            f"{chemin.name} référence une ressource externe par url()"
        )


def test_le_texte_des_svg_est_lisible_au_dessus_de_11_px() -> None:
    """Every text element must declare a font size of at least 11 px."""
    for chemin in SVG:
        racine = ET.parse(chemin).getroot()
        tailles: list[float] = []
        for noeud in racine.iter():
            if _nom_local(noeud.tag) != "text":
                continue
            valeur = noeud.get("font-size")
            assert valeur, f"{chemin.name} : un <text> n'a pas de font-size"
            tailles.append(float(str(valeur).replace("px", "")))
        assert tailles, f"{chemin.name} : aucun <text> à mesurer"
        assert min(tailles) >= 11, f"{chemin.name} : texte trop petit ({min(tailles)} px)"


def test_les_svg_emploient_seulement_une_police_generique() -> None:
    """No remote font: only generic families."""
    generiques = ("Arial", "Helvetica", "sans-serif", "serif", "monospace", "Verdana", "Tahoma")
    for chemin in SVG:
        racine = ET.parse(chemin).getroot()
        familles = [
            valeur for noeud in racine.iter() for cle, valeur in noeud.attrib.items() if cle == "font-family"
        ]
        for famille in familles:
            assert any(generique in famille for generique in generiques), (
                f"{chemin.name} utilise une police non générique : {famille}"
            )


def test_les_svg_annoncent_leur_sens_par_le_texte() -> None:
    """The meaning must be carried by words, not by colour alone."""
    attendus = {
        INFOGRAPHIE_APPROCHES: ("rempart", "piege", "Sas", "IAM Access Analyzer", "CloudTrail"),
        INFOGRAPHIE_CANAL: ("Policy", "journal", "attestation", "sponsor", "gateway"),
    }
    for chemin, mots in attendus.items():
        texte = _texte_svg(chemin)
        for mot in mots:
            assert mot.lower() in texte.lower(), f"{chemin.name} ne dit pas {mot!r} en toutes lettres"


def test_les_svg_donnent_leur_pleine_largeur_pour_etre_lus() -> None:
    """Both images are meant to be read at 1200 px wide."""
    for chemin in SVG:
        racine = ET.parse(chemin).getroot()
        largeur = racine.get("width")
        assert largeur and largeur.rstrip("px").strip() == "1200", (
            f"{chemin.name} n'est pas dimensionné pour 1200 px de large (width={largeur})"
        )
