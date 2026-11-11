"""What N replays prove — and what they do not (spec §14, KPI-7).

This module is the reason an attestation from Sas is signable: it publishes its
own scope. A report that does not state its reach is not an engineering report
(§14.4).

    P(detection) = 1 - (1 - p)^N
    N(95%)       = ln(0.05) / ln(1 - p)
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sas import constantes
from sas.types import BorneStatistique, LigneBorne

ARRONDI = 4


def probabilite_detection(p: float, n: int) -> float:
    """Probability of observing at least once a behaviour of probability `p`."""
    if n <= 0:
        return 0.0
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    return round(1.0 - (1.0 - p) ** n, ARRONDI)


def rejeux_necessaires(p: float, confiance: float = constantes.CONFIANCE_CIBLE) -> int:
    """How many independent replays are needed for `confiance` on probability p."""
    if not 0.0 < p < 1.0:
        raise ValueError("p doit être dans ]0, 1[")
    if not 0.0 < confiance < 1.0:
        raise ValueError("la confiance doit être dans ]0, 1[")
    brut = math.log(1.0 - confiance) / math.log(1.0 - p)
    return max(1, math.ceil(brut))


def table(n: int, probabilites: Sequence[float] = constantes.PROBABILITES_PUBLIEES) -> tuple[LigneBorne, ...]:
    """The lines an attestation prints: p -> confidence at N replays."""
    return tuple(LigneBorne(probabilite=p, confiance=probabilite_detection(p, n)) for p in probabilites)


def borne(
    n_rejeux: int,
    *,
    rejeux_independants: bool = True,
    memoire_persistante: bool = False,
    probabilites: Sequence[float] = constantes.PROBABILITES_PUBLIEES,
) -> BorneStatistique:
    """The published statistical scope of one homologation.

    §14.6 — if the guest declares a persistent memory, the replays are **not**
    independent and the bound does not apply. The report says so instead of
    printing a false number.
    """
    if memoire_persistante:
        rejeux_independants = False
    return BorneStatistique(
        n_rejeux=n_rejeux,
        lignes=table(n_rejeux, probabilites) if rejeux_independants else (),
        rejeux_independants=rejeux_independants,
        memoire_persistante=memoire_persistante,
    )


@dataclass(frozen=True, slots=True)
class CoutNiveau:
    niveau: str
    n_rejeux: int
    sessions: int
    confiance_p25: float


def niveaux_rejeux() -> tuple[CoutNiveau, ...]:
    """The paid levels of §14.5, with the confidence each one buys at p = 0.25."""
    return tuple(
        CoutNiveau(
            niveau=niveau,
            n_rejeux=n,
            sessions=8 * n,
            confiance_p25=probabilite_detection(0.25, n),
        )
        for niveau, n in constantes.NIVEAUX_REJEUX.items()
    )


def verifier_borne(observations: Iterable[bool], p_attendu: float, n_rejeux: int) -> dict[str, float]:
    """R17 / §27 — is the published bound *true*?

    Lot 18 implants a behaviour at a known probability `p` and measures how often
    N replays detect it. The observed frequency must sit inside the expected
    interval; otherwise the bound printed on the attestation is a claim, not a
    measurement.
    """
    echantillon = list(observations)
    total = len(echantillon)
    if total == 0:
        return {"observations": 0.0, "attendu": probabilite_detection(p_attendu, n_rejeux), "ecart": 0.0}
    observe = sum(1 for vu in echantillon if vu) / total
    attendu = probabilite_detection(p_attendu, n_rejeux)
    return {
        "observations": round(observe, ARRONDI),
        "attendu": attendu,
        "ecart": round(abs(observe - attendu), ARRONDI),
        "campagnes": float(total),
    }


def phrase_portee(b: BorneStatistique, langue: str = "fr") -> str:
    """The sentence every attestation carries (§14.4)."""
    if not b.rejeux_independants:
        if langue == "en":
            return (
                "The agent declares a persistent memory: the replays are no longer independent "
                "and no statistical bound is published."
            )
        return (
            "L'agent déclare une mémoire persistante : les rejeux ne sont plus indépendants "
            "et aucune borne statistique n'est publiée."
        )
    if langue == "en":
        lignes = ", ".join(f"{ligne.confiance:.0%} for p = {ligne.probabilite:g}" for ligne in b.lignes)
        return f"{b.n_rejeux} independent replays per scenario detect with {lignes}. A rare behaviour is NOT excluded."
    lignes = ", ".join(f"{ligne.confiance:.0%} pour p = {ligne.probabilite:g}" for ligne in b.lignes)
    return (
        f"{b.n_rejeux} rejeux indépendants par scénario détectent avec {lignes}. "
        "Un comportement rare n'est PAS exclu."
    )
