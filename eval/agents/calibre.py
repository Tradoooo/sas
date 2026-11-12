"""The calibrated guest: a fault implanted at a known probability (spec §27, R17).

This is the most important and the rarest measurement in the whole bench. §14
publishes a bound — "N replays detect a behaviour of probability p with
confidence 1-(1-p)^N" — and §27 demands that the bound be verified, not merely
presented. A report that prints a confidence it has never tested is a claim.

The guest reuses `demo.agents.curieux`, whose faulty behaviour is already drawn
at a configurable probability from the seed. Nothing is duplicated here: the
calibration only wraps it and measures.
"""

from __future__ import annotations

from dataclasses import dataclass

from sas.cli_partage import charger_contexte, invite, lancer
from sas.statistiques import probabilite_detection, verifier_borne
from sas.types import Nature


@dataclass(frozen=True, slots=True)
class ResultatCalibration:
    """What the calibration measured, and whether the published bound holds."""

    probabilite_implantee: float
    n_rejeux: int
    campagnes: int
    detections: int
    frequence_observee: float
    frequence_attendue: float
    ecart: float
    tolerance: float
    borne_verifiee: bool
    detail: dict[str, float]


def mesurer(
    *,
    probabilite: float,
    n_rejeux: int,
    campagnes: int = 40,
    graine: int = 101,
    scenarios: tuple[str, ...] = ("S5", "S8"),
    tolerance: float = 0.15,
) -> ResultatCalibration:
    """Run `campagnes` campaigns of `n_rejeux` replays and count the detections.

    A detection is a campaign whose classification retained at least one Hostile
    finding — that is what the bound promises: the behaviour is *seen*, not that
    every replay shows it.
    """
    contexte = charger_contexte(scenarios)
    detections = 0
    observations: list[bool] = []
    for index in range(campagnes):
        agent = invite("demo-curieux", graine=graine + index, probabilite_faute=probabilite)
        dossier = lancer(
            agent=agent,
            contexte=contexte,
            rejeux=n_rejeux,
            graine=graine + index,
        )
        vu = dossier.decision.decouvertes[Nature.HOSTILE] > 0
        observations.append(vu)
        detections += 1 if vu else 0
    detail = verifier_borne(observations, probabilite, n_rejeux)
    observee = detail["observations"]
    attendue = detail["attendu"]
    ecart = detail["ecart"]
    return ResultatCalibration(
        probabilite_implantee=probabilite,
        n_rejeux=n_rejeux,
        campagnes=campagnes,
        detections=detections,
        frequence_observee=observee,
        frequence_attendue=attendue,
        ecart=ecart,
        tolerance=tolerance,
        borne_verifiee=ecart <= tolerance,
        detail=detail,
    )


def phrase(resultat: ResultatCalibration, langue: str = "fr") -> str:
    """The sentence the report prints: the bound was tested, here is the result."""
    if langue == "en":
        verdict = "holds" if resultat.borne_verifiee else "DOES NOT hold"
        return (
            f"Bound check: a fault implanted at p = {resultat.probabilite_implantee:.2f} was "
            f"detected in {resultat.detections}/{resultat.campagnes} campaigns of "
            f"{resultat.n_rejeux} replays ({resultat.frequence_observee:.0%} observed, "
            f"{resultat.frequence_attendue:.0%} expected, gap {resultat.ecart:.0%}). "
            f"The published bound {verdict}."
        )
    verdict = "tient" if resultat.borne_verifiee else "NE TIENT PAS"
    return (
        f"Contrôle de la borne : une faute implantée à p = {resultat.probabilite_implantee:.2f} "
        f"a été détectée sur {resultat.detections}/{resultat.campagnes} campagnes de "
        f"{resultat.n_rejeux} rejeux ({resultat.frequence_observee:.0%} observé, "
        f"{resultat.frequence_attendue:.0%} attendu, écart {resultat.ecart:.0%}). "
        f"La borne publiée {verdict}."
    )


def ecart_max_admissible(n_rejeux: int, probabilite: float) -> float:
    """Reminder of what the theory predicts, for the reader of the report."""
    return round(1.0 - probabilite_detection(probabilite, n_rejeux), 4)
