"""Interval estimation and what a finding actually proves (spec §14, KPI-7).

`statistiques.py` answers "would N replays have detected a behaviour of
probability p?". That is the **detection** bound, and it is necessary but not
sufficient: once a behaviour *has* been observed, the reader wants to know how
frequent it really is, and how many replays it would take to say so.

Three additions, all stdlib:

* a **Wilson score interval** on the observed frequency — the honest range for
  "seen k times in N replays", which for small N is much wider than the raw
  frequency suggests, and says so;
* the **minimum N** needed to bound an observed behaviour at a given confidence;
* the **price of confidence**: how many replays, therefore how many dollars, a
  given confidence costs (§14.5, §26.2).

Why Wilson rather than the normal approximation: at N = 6 and k = 0 the normal
interval is meaningless (it goes negative) while Wilson stays inside [0, 1] and
keeps a usable upper bound — which is exactly the case that matters here, because
"zero findings in six replays" is the most common and the most over-read result.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import NormalDist

from sas import constantes
from sas.statistiques import probabilite_detection, rejeux_necessaires

ARRONDI = 4
_NORMALE = NormalDist()


def z(confiance: float = 0.95) -> float:
    """Two-sided normal quantile. Stdlib, no approximation table to maintain."""
    if not 0.0 < confiance < 1.0:
        raise ValueError("la confiance doit être dans ]0, 1[")
    return _NORMALE.inv_cdf(0.5 + confiance / 2.0)


@dataclass(frozen=True, slots=True)
class Intervalle:
    """A Wilson score interval on an observed frequency."""

    succes: int
    essais: int
    confiance: float
    bas: float
    haut: float
    ponctuelle: float

    @property
    def largeur(self) -> float:
        return round(self.haut - self.bas, ARRONDI)

    @property
    def exploitable(self) -> bool:
        """False when the sample says nothing: no replay, no interval."""
        return self.essais > 0


def wilson(succes: int, essais: int, confiance: float = 0.95) -> Intervalle:
    """Wilson score interval for `succes` observed in `essais` replays."""
    if essais < 0 or succes < 0 or succes > essais:
        raise ValueError("comptages incohérents : il faut 0 <= succes <= essais")
    if essais == 0:
        return Intervalle(0, 0, confiance, 0.0, 1.0, 0.0)
    zz = z(confiance) ** 2
    p = succes / essais
    denominateur = 1.0 + zz / essais
    centre = p + zz / (2 * essais)
    marge = zz * math.sqrt(p * (1 - p) / essais + zz / (4 * essais**2))
    return Intervalle(
        succes=succes,
        essais=essais,
        confiance=confiance,
        bas=round(max(0.0, (centre - marge) / denominateur), ARRONDI),
        haut=round(min(1.0, (centre + marge) / denominateur), ARRONDI),
        ponctuelle=round(p, ARRONDI),
    )


def n_minimal(
    intervalle: Intervalle, confiance: float = constantes.CONFIANCE_CIBLE, *, conservateur: bool = False
) -> int | None:
    """How many replays it would take to detect this behaviour at `confiance`.

    By default the **point estimate** k/N is used, because that is the frequency
    actually observed. With `conservateur=True` the lower bound of the interval is
    used instead, which is the least favourable plausible frequency — and at the
    small N a first homologation runs at, that bound is usually 0, so the honest
    answer is `None`: the sample is too small to promise anything (§14.4).
    """
    if not intervalle.exploitable:
        return None
    cible = intervalle.bas if conservateur else intervalle.ponctuelle
    if cible <= 0.0:
        return None
    return rejeux_necessaires(min(cible, 0.999999), confiance)


def arret_sequentiel(
    p_cible: float,
    confiance: float = constantes.CONFIANCE_CIBLE,
    n_max: int = 60,
) -> int:
    """Replays needed to reach `confiance` on a behaviour of probability p_cible.

    This is what makes §14.5 an arbitration rather than a default: the caller
    asks for a confidence and gets a number of replays, which §26.2 turns into a
    price. Bounded by `n_max` because past that the cost is no longer an
    arbitration a customer will make.
    """
    return min(n_max, rejeux_necessaires(p_cible, confiance))


def cout_pour_confiance(
    p_cible: float,
    *,
    confiance: float = constantes.CONFIANCE_CIBLE,
    scenarios: int = len(constantes.SCENARIOS_LANCES),
    modele_invite: str = "amazon.nova-lite",
    modele_analyseur: str = "modele-fort",
    appels_par_session: int = 10,
) -> dict[str, object]:
    """The price of a confidence level (§14.5 + annexe G). One computation, quoted."""
    from sas import couts

    n = arret_sequentiel(p_cible, confiance)
    sessions = n * scenarios
    appels = sessions * appels_par_session
    entree_invite, sortie_invite = constantes.JETONS_AGENT_PAR_APPEL
    entree_analyse, sortie_analyse = constantes.JETONS_ANALYSEUR_PAR_SESSION
    invite = couts.cout_modele(appels * entree_invite, appels * sortie_invite, modele_invite)
    analyseur = couts.cout_modele(sessions * entree_analyse, sessions * sortie_analyse, modele_analyseur)
    total = (invite + analyseur).quantize(Decimal("0.01"))
    return {
        "probabilite_cible": p_cible,
        "confiance": confiance,
        "n_rejeux": n,
        "sessions": sessions,
        "cout_total": total,
        "cout_analyseur_seul": couts.cout_modele(
            sessions * entree_analyse, sessions * sortie_analyse, modele_analyseur
        ),
        "confiance_atteinte": probabilite_detection(p_cible, n),
    }


def echelle_confiance(p_cibles: Sequence[float] = (0.5, 0.25, 0.1, 0.05)) -> tuple[dict[str, object], ...]:
    """The table a sales conversation needs: confidence wanted -> price."""
    return tuple(cout_pour_confiance(p) for p in p_cibles)


@dataclass(frozen=True, slots=True)
class PorteeEtendue:
    """What one campaign's observations really license you to say."""

    n_rejeux: int
    intervalles: tuple[Intervalle, ...]
    decouvertes_zero: bool
    borne_superieure_zero: float
    phrase_zero: str


def portee_etendue(
    n_rejeux: int,
    observations: Sequence[bool],
    *,
    confiance: float = constantes.CONFIANCE_CIBLE,
    langue: str = "fr",
) -> PorteeEtendue:
    """Turn a list of per-replay observations into an honest scope statement.

    The case that matters most is `decouvertes_zero`: nothing was seen, and the
    only defensible statement is an upper bound on what could have been missed.
    Wilson gives that bound; "no finding" alone does not.
    """
    succes = sum(1 for vu in observations if vu)
    intervalle = wilson(succes, n_rejeux, confiance)
    zero = succes == 0 and n_rejeux > 0
    borne = intervalle.haut if zero else 0.0
    if langue == "en":
        phrase = (
            _phrase_zero_en(n_rejeux, borne, confiance)
            if zero and borne > 0
            else (f"Observed in {succes} of {n_rejeux} replays.")
        )
    else:
        phrase = (
            _phrase_zero_fr(n_rejeux, borne, confiance)
            if zero and borne > 0
            else (f"Observé sur {succes} rejeux sur {n_rejeux}.")
        )
    return PorteeEtendue(
        n_rejeux=n_rejeux,
        intervalles=(intervalle,),
        decouvertes_zero=zero,
        borne_superieure_zero=borne,
        phrase_zero=phrase,
    )


def _seuil_lisible(borne: float) -> str:
    """A bound of 0.58 reads as "up to 58 % of runs"; 0.04 reads as "1 in 25".

    Below one occurrence in two, the ratio is the more intuitive form and it is
    the one §14.4 uses; above it, a ratio of "1 in 1.7" would be nonsense, so the
    percentage is stated instead.
    """
    if borne <= 0.5:
        return f"une fois sur {1 / borne:.0f}"
    return f"{borne:.0%} des exécutions"


def _phrase_zero_fr(n_rejeux: int, borne: float, confiance: float) -> str:
    return (
        f"Rien d'observé sur {n_rejeux} rejeux. Un comportement survenant jusqu'à "
        f"{_seuil_lisible(borne)} ne peut pas être exclu (confiance {confiance:.0%})."
    )


def _phrase_zero_en(n_rejeux: int, borne: float, confiance: float) -> str:
    seuil = f"1 time in {1 / borne:.0f}" if borne <= 0.5 else f"up to {borne:.0%} of runs"
    return (
        f"Nothing was observed in {n_rejeux} replays. A behaviour occurring {seuil} "
        f"cannot be excluded ({confiance:.0%} confidence)."
    )
