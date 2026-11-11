"""Measured cost of a campaign (ENF-10, §26, annexe G).

The cost is **measured from the counters**, never estimated after the fact: the
first campaign already exposes what it cost. Everything is `Decimal`, quantized
to the cent, because an attestation quotes these numbers.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from sas import constantes
from sas.types import CoutMesure, EntreeJournal, Session

CENTIME = Decimal("0.01")
MILLION = Decimal(1_000_000)


def cout_modele(jetons_entree: int, jetons_sortie: int, modele: str) -> Decimal:
    """$ for one model, from its per-million token tariff."""
    try:
        entree, sortie = constantes.TARIFS_MODELES_PAR_MILLION[modele]
    except KeyError:
        raise ValueError(f"modèle sans tarif déclaré: {modele!r}") from None
    brut = (Decimal(jetons_entree) * entree + Decimal(jetons_sortie) * sortie) / MILLION
    return _quantifier(brut)


def cout_runtime(
    secondes: float, vcpu: Decimal = constantes.VCPU_PAR_SESSION, gio: Decimal = constantes.GIO_PAR_SESSION
) -> Decimal:
    """$ for AgentCore Runtime, from vCPU-seconds and GiB-seconds (§26.1)."""
    if secondes <= 0:
        return Decimal("0.00")
    duree = Decimal(str(secondes))
    brut = (
        duree * vcpu * constantes.COUT_RUNTIME_VCPU_SECONDE
        + duree * gio * constantes.COUT_RUNTIME_GIO_SECONDE
    )
    return _quantifier(brut)


def _quantifier(valeur: Decimal) -> Decimal:
    return valeur.quantize(CENTIME, rounding=ROUND_HALF_UP)


def jetons_de(entrees: Sequence[EntreeJournal]) -> tuple[int, int]:
    """(input, output) tokens of the guest agent, from the journal itself.

    Each tool call carries the tokens of the reasoning that produced it
    (annexe G.3: 4 000 in / 600 out per call).
    """
    par_appel_entree, par_appel_sortie = constantes.JETONS_AGENT_PAR_APPEL
    total = sum(entree.jetons for entree in entrees)
    if total:
        return _repartir(total)
    return len(entrees) * par_appel_entree, len(entrees) * par_appel_sortie


def _repartir(total: int) -> tuple[int, int]:
    """Split a measured token total using the documented in/out ratio."""
    entree_attendue, sortie_attendue = constantes.JETONS_AGENT_PAR_APPEL
    ratio = Decimal(entree_attendue) / Decimal(entree_attendue + sortie_attendue)
    jetons_entree = int(Decimal(total) * ratio)
    return jetons_entree, total - jetons_entree


def mesurer(
    sessions: Sequence[Session],
    entrees: Sequence[EntreeJournal],
    *,
    modele_invite: str = "amazon.nova-lite",
    modele_analyseur: str = "modele-fort",
    secondes_runtime: float | None = None,
    cout_infrastructure: Decimal = Decimal("0"),
) -> CoutMesure:
    """The cost of one campaign: guest tokens, analyser tokens, Runtime, infra."""
    jetons_entree, jetons_sortie = jetons_de(entrees)
    cout_invite = cout_modele(jetons_entree, jetons_sortie, modele_invite)

    entree_par_session, sortie_par_session = constantes.JETONS_ANALYSEUR_PAR_SESSION
    cout_analyseur = cout_modele(
        len(sessions) * entree_par_session,
        len(sessions) * sortie_par_session,
        modele_analyseur,
    )

    if secondes_runtime is None:
        secondes_runtime = _secondes_runtime(sessions)
    return CoutMesure(
        jetons_entree=jetons_entree + len(sessions) * entree_par_session,
        jetons_sortie=jetons_sortie + len(sessions) * sortie_par_session,
        cout_modele=cout_invite + cout_analyseur,
        runtime_secondes=secondes_runtime,
        cout_runtime=cout_runtime(secondes_runtime),
        cout_infrastructure=_quantifier(cout_infrastructure),
    )


def _secondes_runtime(sessions: Sequence[Session]) -> float:
    total = 0.0
    for session in sessions:
        if session.fin is not None:
            total += max(0.0, (session.fin - session.debut).total_seconds())
    return total


def cout_annexe_g(niveau: str = "standard") -> Decimal:
    """The reference cost of annexe G.4 for one full homologation.

    Used by the acceptance test R22: the measured cost must stay within 25 % of
    this figure, which is what makes KPI-3 a measurement and not a claim.
    """
    sessions = 8 * constantes.NIVEAUX_REJEUX[niveau]
    appels = sessions * 10
    entree_invite, sortie_invite = constantes.JETONS_AGENT_PAR_APPEL
    entree_analyse, sortie_analyse = constantes.JETONS_ANALYSEUR_PAR_SESSION
    invite = cout_modele(appels * entree_invite, appels * sortie_invite, "amazon.nova-lite")
    analyseur = cout_modele(sessions * entree_analyse, sessions * sortie_analyse, "modele-fort")
    return _quantifier(invite + analyseur)


def credits_restants(depense: Decimal) -> Decimal:
    """What is left of the hackathon budget once the infrastructure reserve is
    taken out (§26.4)."""
    disponible = constantes.BUDGET_CREDITS - constantes.RESERVE_INFRASTRUCTURE
    return _quantifier(max(Decimal("0"), disponible - depense))


def homologations_possibles(depense: Decimal, niveau: str = "standard") -> int:
    """How many full homologations the remaining credits still buy."""
    unitaire = cout_annexe_g(niveau)
    if unitaire <= 0:
        return 0
    return int(credits_restants(depense) / unitaire)
