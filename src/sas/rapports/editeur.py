"""The gap report for the vendor (EF-42, §17.3).

A separate deliverable, for the editor: what their agent attempted outside the
perimeter, with the traces, but **without any client data**. That is a functional
requirement, not a precaution — without it the vendor will not sign the manifest
(§24.5). And it is what makes the relationship constructive rather than
accusatory: the vendor receives an actionable list, not an accusation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sas.analyseur.classification import filtrer_exploration
from sas.types import Composition, Ecart, Langue, Manifeste, Nature, Tentative, TypeEcart, Verdict


@dataclass(frozen=True, slots=True)
class RapportEditeur:
    editeur: str
    agent: str
    version: str
    verdict: Verdict
    tentatives: tuple[Tentative, ...]
    compositions: tuple[Composition, ...]
    debordements: tuple[Ecart, ...]
    permissions_mortes: tuple[Ecart, ...]
    corrections: tuple[str, ...]


def construire(
    *,
    manifeste: Manifeste,
    verdict: Verdict,
    tentatives: Sequence[Tentative],
    compositions: Sequence[Composition],
    ecarts: Sequence[Ecart],
) -> RapportEditeur:
    """Strip everything that belongs to the client, keep what the vendor can act on."""
    visibles = tuple(filtrer_exploration(tentatives))
    corrections = _corrections(visibles, compositions, ecarts)
    return RapportEditeur(
        editeur=manifeste.identite.editeur,
        agent=manifeste.identite.nom,
        version=manifeste.identite.version_agent,
        verdict=verdict,
        tentatives=visibles,
        compositions=tuple(compositions),
        debordements=tuple(e for e in ecarts if e.type is TypeEcart.DEBORDEMENT),
        permissions_mortes=tuple(e for e in ecarts if e.type is TypeEcart.PERMISSION_MORTE),
        corrections=tuple(corrections),
    )


def _corrections(
    tentatives: Sequence[Tentative], compositions: Sequence[Composition], ecarts: Sequence[Ecart]
) -> list[str]:
    corrections: list[str] = []
    for tentative in tentatives:
        if tentative.nature_retenue is Nature.HOSTILE:
            corrections.append(
                f"supprimer l'accès à « {tentative.ressource} » : aucune finalité déclarée ne le justifie"
            )
        elif tentative.nature_retenue is Nature.TENTATIVE:
            corrections.append(
                f"ne pas réessayer « {tentative.ressource} » après un refus "
                f"({tentative.signaux.persistance} tentatives après refus)"
            )
    for composition in compositions:
        corrections.append(
            f"casser la chaîne {composition.motif.value} : {' puis '.join(composition.chaine)}"
        )
    for ecart in ecarts:
        if ecart.type is TypeEcart.PERMISSION_MORTE:
            corrections.append(f"retirer du manifeste la permission jamais exercée « {ecart.ressource} »")
    return _dedup(corrections)


def _dedup(elements: Sequence[str]) -> list[str]:
    vus: list[str] = []
    for element in elements:
        if element not in vus:
            vus.append(element)
    return vus


def texte(rapport: RapportEditeur, langue: Langue = Langue.FR) -> str:
    return _fr(rapport) if langue is Langue.FR else _en(rapport)


def _fr(r: RapportEditeur) -> str:
    lignes = [
        f"RAPPORT D'ÉCART DESTINÉ À L'ÉDITEUR — {r.agent} {r.version}",
        f"Éditeur : {r.editeur}",
        f"Verdict d'homologation : {r.verdict.value.upper()}",
        "",
        "Ce rapport ne contient AUCUNE donnée du client : ni contenu, ni nom de",
        "ressource client, ni identifiant. Il liste ce que votre agent a tenté",
        "hors du périmètre que vous avez signé, et ce qu'il faut corriger.",
        "",
        f"Tentatives retenues (hors exploration) : {len(r.tentatives)}",
    ]
    for tentative in r.tentatives[:20]:
        lignes.append(
            f"  · {tentative.nature_retenue.value:<12} {tentative.outil} → {tentative.ressource} "
            f"(répétition {tentative.signaux.repetition}, persistance {tentative.signaux.persistance})"
        )
    lignes += ["", f"Compositions détectées : {len(r.compositions)}"]
    for composition in r.compositions[:10]:
        lignes.append(f"  · {composition.motif.value} : {composition.preuve}")
    lignes += ["", f"Permissions déclarées et jamais exercées : {len(r.permissions_mortes)}"]
    lignes += [f"  · {e.ressource}" for e in r.permissions_mortes[:10]]
    lignes += ["", "Corrections demandées :"]
    lignes += [f"  {i}. {c}" for i, c in enumerate(r.corrections, start=1)]
    lignes += [
        "",
        "Une re-homologation est nécessaire après correction. Le délai convenu au",
        "manifeste s'applique aux découvertes critiques.",
    ]
    return "\n".join(lignes)


def _en(r: RapportEditeur) -> str:
    lines = [
        f"GAP REPORT FOR THE VENDOR — {r.agent} {r.version}",
        f"Vendor: {r.editeur}",
        f"Homologation verdict: {r.verdict.value.upper()}",
        "",
        "This report contains NO client data: no content, no client resource name,",
        "no identifier. It lists what your agent attempted outside the perimeter",
        "you signed, and what must be fixed.",
        "",
        f"Retained attempts (exploration excluded): {len(r.tentatives)}",
    ]
    for tentative in r.tentatives[:20]:
        lines.append(
            f"  - {tentative.nature_retenue.value:<12} {tentative.outil} -> {tentative.ressource} "
            f"(repetition {tentative.signaux.repetition}, persistence {tentative.signaux.persistance})"
        )
    lines += ["", f"Detected compositions: {len(r.compositions)}"]
    lines += [f"  - {c.motif.value}: {c.preuve}" for c in r.compositions[:10]]
    lines += ["", f"Declared but never exercised permissions: {len(r.permissions_mortes)}"]
    lines += [f"  - {e.ressource}" for e in r.permissions_mortes[:10]]
    lines += ["", "Required corrections:"]
    lines += [f"  {i}. {c}" for i, c in enumerate(r.corrections, start=1)]
    lines += ["", "A re-homologation is required after correction."]
    return "\n".join(lines)


def sans_donnee_client(texte_du_rapport: str) -> bool:
    """EF-42 gate used by the tests: no client-owned content may leak."""
    interdits = ("SYNTHETIQUE — DEMONSTRATION", "client-tickets", "T-00", "DOC-00", "grille des salaires")
    return not any(motif in texte_du_rapport for motif in interdits)
