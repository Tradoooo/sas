"""Envelope federation and version diff (spec §15.2, §24.5 — extended).

Two capabilities, one discipline.

**Federation.** An MSP that homologates the same vendor agent for ten clients
learns something no single client can: what that agent usually does. Publishing
an envelope into the federation must therefore leak nothing about any client —
no resource name, no ticket, no tenant identifier. What is shared is the *shape*
of the behaviour: which tools, in which order, at which frequency, and which
coarse resource categories. Client-specific names are reduced to a category
(`s3:lecture`, `dynamodb:ecriture`, `index:recherche`, `http:sortie`) and the
agent is pseudonymised with a per-federation salt.

**Version diff.** When a vendor ships a new version, the useful question is not
"is it different" but "what did it start doing, stop doing, and how much did the
rest move". That is a comparison of two signatures, presented as additions,
disappearances and shifts — the artefact §15.3 turns into an alert.

This module is a **prototype of the mechanism**, not a multi-tenant service: it
computes what a federation would say from the envelopes it is given. Deploying it
for real raises governance questions (who runs the federation, what the client
consents to) that are listed in `docs/HLD.md`, not solved here.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sas.identifiants import empreinte
from sas.signature import detail as detail_signature
from sas.signature import distance as distance_signature
from sas.types import EcartSignature, Enveloppe, SignatureComportementale, Verdict

# Coarse categories: the only resource description that leaves a tenant.
# Order matters — the first matching pattern wins, so the specific ones come
# before the generic ones.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("http://", "http:sortie"),
    ("https://", "http:sortie"),
    ("sortie:", "http:sortie"),
    ("dynamodb:", "dynamodb:ecriture"),
    ("kb-", "index:recherche"),
    ("index", "index:recherche"),
    ("s3://", "s3:lecture"),
    ("/", "s3:lecture"),
)
CATEGORIE_DEFAUT = "autre"


def categorie(ressource: str) -> str:
    """Reduce a client-specific resource name to a shareable category."""
    cible = ressource.lower()
    for motif, categorie_nom in CATEGORIES:
        if motif in cible:
            return categorie_nom
    return CATEGORIE_DEFAUT


def pseudonymiser(agent_id: str, editeur: str, sel: str) -> str:
    """A stable pseudonym: the same agent maps to the same value inside one
    federation, and to nothing recognisable outside it."""
    return "fed-" + hashlib.sha256(f"{sel}|{editeur}|{agent_id}".encode()).hexdigest()[:16]


@dataclass(frozen=True, slots=True)
class EnveloppeFederable:
    """What one client agrees to share. No name, no content, no identifier."""

    pseudonyme_agent: str
    version: str
    verdict: str
    n_rejeux: int
    date: datetime
    outils: Mapping[str, float]
    categories: Mapping[str, float]
    sequences: Mapping[str, float]
    refus: float
    empreinte: str


def anonymiser(
    enveloppe: Enveloppe,
    *,
    agent_id: str,
    editeur: str,
    verdict: Verdict,
    sel: str,
    refus: float = 0.0,
) -> EnveloppeFederable:
    """Strip everything tenant-specific from an envelope."""
    categories_agregees: dict[str, float] = {}
    for ressource, frequence in enveloppe.signature.ressources.items():
        cle = categorie(ressource)
        categories_agregees[cle] = round(categories_agregees.get(cle, 0.0) + frequence, 6)
    partagee = EnveloppeFederable(
        pseudonyme_agent=pseudonymiser(agent_id, editeur, sel),
        version=enveloppe.version,
        verdict=verdict.value,
        n_rejeux=enveloppe.n_rejeux,
        date=enveloppe.date,
        outils=dict(enveloppe.signature.outils),
        categories=categories_agregees,
        sequences=dict(enveloppe.signature.sequences),
        refus=refus,
        empreinte="",
    )
    return _sceller(partagee)


def _sceller(partagee: EnveloppeFederable) -> EnveloppeFederable:
    from dataclasses import replace

    return replace(
        partagee,
        empreinte=empreinte(
            {
                "pseudonyme": partagee.pseudonyme_agent,
                "version": partagee.version,
                "outils": sorted(partagee.outils.items()),
                "categories": sorted(partagee.categories.items()),
                "sequences": sorted(partagee.sequences.items()),
            }
        ),
    )


def aucun_nom_client_ne_sort(partagee: EnveloppeFederable, ressources: Iterable[str]) -> bool:
    """The privacy gate, as an executable property rather than a promise."""
    serialise = repr(partagee.outils) + repr(partagee.categories) + repr(partagee.sequences)
    return not any(ressource.lower() in serialise.lower() for ressource in ressources if ressource)


@dataclass(frozen=True, slots=True)
class ProfilFedere:
    """What the federation says about a behaviour, tool by tool."""

    participants: int
    frequence_outils: Mapping[str, float]
    frequence_categories: Mapping[str, float]
    verdicts: Mapping[str, int]
    rejeux_median: float


def profiler(enveloppes: Sequence[EnveloppeFederable]) -> ProfilFedere:
    """Aggregate shared envelopes into what is usual and what is not."""
    if not enveloppes:
        return ProfilFedere(0, {}, {}, {}, 0.0)
    outils = _frequence_presence(enveloppes, lambda e: e.outils)
    categories = _frequence_presence(enveloppes, lambda e: e.categories)
    verdicts: dict[str, int] = {}
    for partagee in enveloppes:
        verdicts[partagee.verdict] = verdicts.get(partagee.verdict, 0) + 1
    rejeux = sorted(e.n_rejeux for e in enveloppes)
    mediane = (
        rejeux[len(rejeux) // 2]
        if len(rejeux) % 2
        else (rejeux[len(rejeux) // 2 - 1] + rejeux[len(rejeux) // 2]) / 2
    )
    return ProfilFedere(len(enveloppes), outils, categories, verdicts, float(mediane))


def _frequence_presence(enveloppes: Sequence[EnveloppeFederable], selecteur: Any) -> dict[str, float]:
    """Share of participants for whom the key appears at all."""
    comptes: dict[str, int] = {}
    for partagee in enveloppes:
        for cle in selecteur(partagee):
            comptes[cle] = comptes.get(cle, 0) + 1
    total = len(enveloppes)
    return {cle: round(n / total, 4) for cle, n in sorted(comptes.items(), key=lambda kv: (-kv[1], kv[0]))}


def atypiques(partagee: EnveloppeFederable, profil: ProfilFedere, *, seuil: float = 0.1) -> tuple[str, ...]:
    """What this agent does that (almost) nobody else in the federation does.

    Deliberately an *indicator*, never a verdict: an unusual tool is a question
    for the analyst, not a finding. Turning it into a finding would be exactly the
    false positive §16.3 forbids.
    """
    if profil.participants < 3:
        return ()  # too few participants to say anything about "usual"
    suspects: list[str] = []
    for cle in partagee.outils:
        if profil.frequence_outils.get(cle, 0.0) <= seuil:
            suspects.append(
                f"outil « {cle} » vu chez {profil.frequence_outils.get(cle, 0.0):.0%} de la fédération"
            )
    for cle in partagee.categories:
        part = profil.frequence_categories.get(cle, 0.0)
        if part <= seuil:
            suspects.append(f"catégorie « {cle} » vue chez {part:.0%} de la fédération")
    return tuple(suspects)


# --------------------------------------------------------------------------- #
# Version diff (§15.1, §15.3)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class DiffVersions:
    agent_id: str
    version_avant: str
    version_apres: str
    distance: float
    apparitions: tuple[EcartSignature, ...]
    disparitions: tuple[EcartSignature, ...]
    deplacements: tuple[EcartSignature, ...]
    changement_non_declare: bool


def diff_versions(
    *,
    agent_id: str,
    avant: Enveloppe,
    apres: Enveloppe,
    declare: bool = True,
) -> DiffVersions:
    """What changed between two homologated versions of the same agent."""
    ecarts = detail_signature(avant.signature, apres.signature)
    apparitions = tuple(e for e in ecarts if e.reference == 0.0 and e.courante > 0.0)
    disparitions = tuple(e for e in ecarts if e.courante == 0.0 and e.reference > 0.0)
    deplacements = tuple(e for e in ecarts if e not in apparitions and e not in disparitions)
    return DiffVersions(
        agent_id=agent_id,
        version_avant=avant.version,
        version_apres=apres.version,
        distance=distance_signature(avant.signature, apres.signature),
        apparitions=apparitions,
        disparitions=disparitions,
        deplacements=deplacements,
        changement_non_declare=not declare,
    )


def resume_diff(diff: DiffVersions, langue: str = "fr") -> str:
    """The paragraph a vendor or a CISO reads, not a table of floats."""
    if langue == "en":
        head = (
            f"{diff.agent_id}: {diff.version_avant} -> {diff.version_apres}, "
            f"behavioural distance {diff.distance:.3f}"
            + (" (undeclared change)" if diff.changement_non_declare else "")
        )
        lines = [head]
        lines += [f"  + started: {e.famille} {e.cle} ({e.courante:.3f})" for e in diff.apparitions[:8]]
        lines += [f"  - stopped: {e.famille} {e.cle} (was {e.reference:.3f})" for e in diff.disparitions[:8]]
        lines += [
            f"  ~ shifted: {e.famille} {e.cle} {e.reference:.3f} -> {e.courante:.3f}"
            for e in diff.deplacements[:8]
        ]
        return "\n".join(lines)
    entete = (
        f"{diff.agent_id} : {diff.version_avant} → {diff.version_apres}, "
        f"distance comportementale {diff.distance:.3f}"
        + (" (changement non déclaré)" if diff.changement_non_declare else "")
    )
    lignes = [entete]
    lignes += [f"  + apparaît : {e.famille} {e.cle} ({e.courante:.3f})" for e in diff.apparitions[:8]]
    lignes += [
        f"  - disparaît : {e.famille} {e.cle} (valait {e.reference:.3f})" for e in diff.disparitions[:8]
    ]
    lignes += [
        f"  ~ se déplace : {e.famille} {e.cle} {e.reference:.3f} → {e.courante:.3f}"
        for e in diff.deplacements[:8]
    ]
    return "\n".join(lignes)


def signature_depuis(agregat: Any) -> SignatureComportementale:
    """Convenience for callers that hold an aggregate rather than an envelope."""
    from sas.signature import calculer, sceller

    return sceller(calculer(agregat))
