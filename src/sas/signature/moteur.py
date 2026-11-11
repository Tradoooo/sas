"""Behavioural signature and drift detection (spec §15, EF-30…EF-34).

Sas does not compare code, it compares a **signature**: the weighted set of
tools called, resources touched, call sequences and budgets consumed, over the
reference scenarios (§15.2). That is what catches the case nobody else catches —
the vendor changed the model or the prompt **without changing the version**
(§15.1, R16).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from sas.analyseur.agregation import Agregat
from sas.constantes import SEUILS_DEFAUT, Seuils
from sas.identifiants import empreinte, nouveau
from sas.types import ActionDerive, Derive, EcartSignature, Enveloppe, SignatureComportementale


def calculer(agregat: Agregat) -> SignatureComportementale:
    """Normalise the counters into frequencies, so two campaigns of different
    sizes can be compared."""
    total_appels = max(1, agregat.appels)
    total_sequences = max(1, sum(agregat.sequences.values()))
    return SignatureComportementale(
        outils=_frequences(agregat.outils, total_appels),
        ressources=_frequences(agregat.ressources, total_appels),
        sequences=_frequences(agregat.sequences, total_sequences),
        budgets={
            "appels": float(agregat.appels),
            "refus": float(agregat.refus),
            "jetons": float(agregat.jetons),
        },
        empreinte="",
    )


def sceller(signature: SignatureComportementale) -> SignatureComportementale:
    from dataclasses import replace

    return replace(
        signature,
        empreinte=empreinte(
            {
                "outils": dict(sorted(signature.outils.items())),
                "ressources": dict(sorted(signature.ressources.items())),
                "sequences": dict(sorted(signature.sequences.items())),
                "budgets": dict(sorted(signature.budgets.items())),
            }
        ),
    )


def _frequences(compteurs: Counter[str], total: int) -> dict[str, float]:
    return {cle: round(valeur / total, 6) for cle, valeur in sorted(compteurs.items())}


def distance(
    reference: SignatureComportementale, courante: SignatureComportementale, seuils: Seuils = SEUILS_DEFAUT
) -> float:
    """Weighted distance between two signatures (§15.2). Bounded in [0, 1]."""
    contributions = (
        (reference.outils, courante.outils, seuils.poids_signature_outils),
        (reference.ressources, courante.ressources, seuils.poids_signature_ressources),
        (reference.sequences, courante.sequences, seuils.poids_signature_sequences),
    )
    total = 0.0
    for avant, apres, poids in contributions:
        total += poids * _distance_frequences(avant, apres)
    total += seuils.poids_signature_budgets * _distance_budgets(reference.budgets, courante.budgets)
    return round(min(1.0, total), 6)


def _distance_frequences(avant: dict[str, float], apres: dict[str, float]) -> float:
    """Total variation distance: 0 when identical, 1 when fully disjoint."""
    cles = set(avant) | set(apres)
    if not cles:
        return 0.0
    ecart = sum(abs(avant.get(cle, 0.0) - apres.get(cle, 0.0)) for cle in cles)
    return min(1.0, ecart / 2.0)


def _distance_budgets(avant: dict[str, float], apres: dict[str, float]) -> float:
    if not avant:
        return 0.0
    ecarts = []
    for cle, valeur in avant.items():
        nouvelle = apres.get(cle, 0.0)
        if valeur <= 0:
            continue
        ecarts.append(min(1.0, abs(nouvelle - valeur) / valeur))
    return sum(ecarts) / len(ecarts) if ecarts else 0.0


def detail(
    reference: SignatureComportementale, courante: SignatureComportementale
) -> tuple[EcartSignature, ...]:
    """What changed, key by key — the alert quotes it (§15.3)."""
    ecarts: list[EcartSignature] = []
    for famille, avant, apres in (
        ("outil", reference.outils, courante.outils),
        ("ressource", reference.ressources, courante.ressources),
        ("sequence", reference.sequences, courante.sequences),
    ):
        for cle in sorted(set(avant) | set(apres)):
            avant_valeur = avant.get(cle, 0.0)
            apres_valeur = apres.get(cle, 0.0)
            if abs(avant_valeur - apres_valeur) < 1e-6:
                continue
            ecarts.append(
                EcartSignature(
                    cle=cle,
                    famille=famille,
                    reference=avant_valeur,
                    courante=apres_valeur,
                    contribution=round(abs(avant_valeur - apres_valeur), 6),
                )
            )
    for cle in sorted(set(reference.budgets) | set(courante.budgets)):
        avant_valeur = reference.budgets.get(cle, 0.0)
        apres_valeur = courante.budgets.get(cle, 0.0)
        if avant_valeur == apres_valeur:
            continue
        base = avant_valeur or 1.0
        ecarts.append(
            EcartSignature(
                cle=cle,
                famille="budget",
                reference=avant_valeur,
                courante=apres_valeur,
                contribution=round(min(1.0, abs(apres_valeur - avant_valeur) / base), 6),
            )
        )
    return tuple(sorted(ecarts, key=lambda e: -e.contribution))


@dataclass(frozen=True, slots=True)
class Alerte:
    evenement: str
    action: ActionDerive
    message: str


def action_pour(
    distance_mesuree: float,
    *,
    changement_non_declare: bool = False,
    seuils: Seuils = SEUILS_DEFAUT,
) -> ActionDerive:
    """The thresholds of §15.3, as code."""
    if changement_non_declare and distance_mesuree >= seuils.distance_derive_alerte:
        return ActionDerive.REHOMOLOGATION
    if distance_mesuree >= seuils.distance_derive_suspension:
        return ActionDerive.SUSPENSION
    if distance_mesuree >= seuils.distance_derive_alerte:
        return ActionDerive.ALERTE
    return ActionDerive.JOURNALISEE


def comparer(
    *,
    agent_id: str,
    tenant_id: str,
    reference: Enveloppe,
    courante: Enveloppe,
    changement_non_declare: bool = False,
    seuils: Seuils = SEUILS_DEFAUT,
    alerte_le: object | None = None,
    graine: int = 0,
) -> Derive:
    """Compare two envelopes and decide the action. EF-31, EF-32, EF-34."""
    from sas.identifiants import maintenant

    mesure = distance(reference.signature, courante.signature, seuils)
    action = action_pour(mesure, changement_non_declare=changement_non_declare, seuils=seuils)
    return Derive(
        id=nouveau("drv", graine=graine, cle=f"{agent_id}:{reference.id}:{courante.id}"),
        agent_id=agent_id,
        tenant_id=tenant_id,
        enveloppe_ref=reference.id,
        enveloppe_courante=courante.id,
        distance=mesure,
        detail=detail(reference.signature, courante.signature),
        alerte_le=alerte_le or maintenant(),
        action=action,
        changement_non_declare=changement_non_declare,
    )


def alertes_supplementaires(
    *,
    nouvelles_tentatives: Sequence[str],
    comportements_disparus: Sequence[str],
    budget_depasse_pct: float,
) -> tuple[Alerte, ...]:
    """§15.3 — the three other triggers, independent of the distance."""
    alertes: list[Alerte] = []
    for tentative in nouvelles_tentatives:
        alertes.append(
            Alerte(
                "tentative_nouvelle", ActionDerive.ALERTE, f"nouvelle tentative hors périmètre : {tentative}"
            )
        )
    for comportement in comportements_disparus:
        alertes.append(
            Alerte(
                "comportement_disparu",
                ActionDerive.ALERTE,
                f"l'agent ne fait plus ce pour quoi il a été homologué : {comportement}",
            )
        )
    if budget_depasse_pct > 20.0:
        alertes.append(
            Alerte("budget_depasse", ActionDerive.ALERTE, f"budget dépassé de {budget_depasse_pct:.0f} %")
        )
    return tuple(alertes)


def empreintes_proches(a: str, b: str) -> bool:
    """Helper for tests: two signatures that differ only by rounding."""
    return math.isclose(len(a), len(b)) and a[:16] == b[:16]
