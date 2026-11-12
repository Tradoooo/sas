"""The eight KPIs of §5.2, measured rather than targeted.

A KPI table full of targets is a marketing document. This module computes the
ones the product can actually measure, and says plainly which ones it cannot:

* KPI-1 out-of-scope denials — counted from the journal;
* KPI-2 onboarding delay — measured from the request to the attestation, in days;
* KPI-3 cost per homologation — measured from token and runtime counters, never
  estimated afterwards (ENF-10);
* KPI-4 journal coverage — a blocking requirement, 100 % or the campaign is void;
* KPI-5 declared/observed gap — counted both ways;
* KPI-6 drift detection delay — measured from the injected change to the alert;
* KPI-7 published statistical confidence — the bound itself;
* KPI-8 detected compositions — counted.

Anything not measurable here is reported as `None` with a reason, so the public
dashboard can never be mistaken for a claim.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sas import constantes
from sas.analyseur.agregation import Agregat
from sas.types import Composition, Derive, Ecart, EtatChaine


@dataclass(frozen=True, slots=True)
class Kpi:
    id: str
    nom: str
    valeur: Any
    unite: str
    cible: str
    mesure: bool
    note: str = ""


def kpi_1(agregat: Agregat) -> Kpi:
    """Out-of-scope denials, by rule — exploration included, because filtering
    happens downstream and must stay visible (§13.5)."""
    return Kpi(
        id="KPI-1",
        nom=constantes.KPI["KPI-1"],
        valeur=dict(sorted(agregat.regles.items())),
        unite="refus par règle",
        cible="mesuré sur les agents de démonstration",
        mesure=True,
        note=f"{agregat.refus} refus au total sur {agregat.appels} appels",
    )


def kpi_2(demande_le: datetime | None, attestation_le: datetime | None) -> Kpi:
    """Onboarding delay: from the request to the dated attestation."""
    if demande_le is None or attestation_le is None:
        return Kpi(
            "KPI-2",
            constantes.KPI["KPI-2"],
            None,
            "jours",
            "semaines → jours",
            False,
            "non mesuré : il faut horodater la demande du commanditaire, que le produit ne stocke pas encore",
        )
    delta = (attestation_le - demande_le).total_seconds() / 86400.0
    return Kpi(
        "KPI-2",
        constantes.KPI["KPI-2"],
        round(delta, 2),
        "jours",
        "semaines → jours",
        True,
        "de la demande à l'attestation datée",
    )


def kpi_3(cout: Decimal, n_rejeux: int) -> Kpi:
    """Measured cost per homologation, against the ≤ 1 $ mixed-mode target."""
    cible = Decimal("1.00")
    return Kpi(
        "KPI-3",
        constantes.KPI["KPI-3"],
        float(cout),
        "$",
        f"≤ {cible} $ en mode mixte",
        True,
        f"mesuré à N={n_rejeux} rejeux ; la cible de l'annexe G porte sur N=6",
    )


def kpi_4(appels_emis: int, entrees_journal: int, etat_chaine: EtatChaine) -> Kpi:
    """Journal coverage — blocking. Below 1.00 the campaign proves nothing."""
    couverture = 1.0 if appels_emis == 0 else entrees_journal / appels_emis
    return Kpi(
        "KPI-4",
        constantes.KPI["KPI-4"],
        round(couverture, 4),
        "ratio",
        "100 % — exigence bloquante",
        True,
        _note_couverture(couverture, etat_chaine),
    )


def _note_couverture(couverture: float, etat_chaine: EtatChaine) -> str:
    """Say exactly which part of the blocking requirement failed.

    A single "non compliant" note would hide the difference between a missing
    entry and a broken chain, and the two are not the same failure: one is a gap
    in the log, the other means the log can no longer be trusted at all.
    """
    if couverture < constantes.COUVERTURE_JOURNAL_CIBLE:
        return f"EXIGENCE NON TENUE : couverture {couverture:.2%}, la campagne ne prouve rien"
    if not etat_chaine.integre:
        return f"RUPTURE de chaîne à {etat_chaine.premiere_rupture} : le journal n'est plus fiable"
    return f"chaîne intègre, {etat_chaine.entrees} entrées"


def kpi_5(ecarts: Sequence[Ecart]) -> Kpi:
    """Declared vs observed, both directions."""
    debordements = sum(1 for e in ecarts if e.type.value == "debordement")
    mortes = sum(1 for e in ecarts if e.type.value == "permission_morte")
    return Kpi(
        "KPI-5",
        constantes.KPI["KPI-5"],
        {"debordements": debordements, "permissions_mortes": mortes},
        "comptes",
        "publié par agent",
        True,
    )


def kpi_6(derives: Sequence[Derive], changement_le: datetime | None = None) -> Kpi:
    """Drift detection delay: from the change to the alert.

    Measured when the caller supplies the instant of the injected change (that is
    what the R16 test does). Without it the KPI is reported unmeasured rather
    than guessed.
    """
    if changement_le is None or not derives:
        return Kpi(
            "KPI-6",
            constantes.KPI["KPI-6"],
            None,
            "heures",
            "< 1 cycle de surveillance",
            False,
            "non mesuré : il faut une dérive injectée à un instant connu",
        )
    premiere = min(d.alerte_le for d in derives)
    heures = (premiere - changement_le).total_seconds() / 3600.0
    return Kpi(
        "KPI-6",
        constantes.KPI["KPI-6"],
        round(heures, 2),
        "heures",
        "< 1 cycle de surveillance",
        True,
        "cycle de surveillance hebdomadaire par défaut (§15.4)",
    )


def kpi_7(borne_texte: str) -> Kpi:
    return Kpi(
        "KPI-7", constantes.KPI["KPI-7"], borne_texte, "texte", "affichée sur chaque attestation", True
    )


def kpi_8(compositions: Sequence[Composition]) -> Kpi:
    motifs: dict[str, int] = {}
    for composition in compositions:
        motifs[composition.motif.value] = motifs.get(composition.motif.value, 0) + 1
    return Kpi(
        "KPI-8",
        constantes.KPI["KPI-8"],
        dict(sorted(motifs.items())),
        "compositions par motif",
        "démontré sur l'agent curieux",
        True,
    )


def tableau(
    *,
    agregat: Agregat,
    appels_emis: int,
    etat_chaine: EtatChaine,
    cout: Decimal,
    n_rejeux: int,
    ecarts: Sequence[Ecart],
    compositions: Sequence[Composition],
    borne_texte: str,
    demande_le: datetime | None = None,
    attestation_le: datetime | None = None,
    changement_le: datetime | None = None,
    derives: Sequence[Derive] = (),
) -> tuple[Kpi, ...]:
    """The eight KPIs in order, measured where possible and honest where not."""
    return (
        kpi_1(agregat),
        kpi_2(demande_le, attestation_le),
        kpi_3(cout, n_rejeux),
        kpi_4(appels_emis, etat_chaine.entrees, etat_chaine),
        kpi_5(ecarts),
        kpi_6(derives, changement_le),
        kpi_7(borne_texte),
        kpi_8(compositions),
    )


def en_json(kpis: Sequence[Kpi]) -> list[dict[str, Any]]:
    """What the portal and the report quote — no object, only plain values."""
    return [
        {
            "id": k.id,
            "nom": k.nom,
            "valeur": k.valeur,
            "unite": k.unite,
            "cible": k.cible,
            "mesure": k.mesure,
            "note": k.note,
        }
        for k in kpis
    ]


def non_mesures(kpis: Sequence[Kpi]) -> tuple[str, ...]:
    return tuple(k.id for k in kpis if not k.mesure)


def cycle_surveillance(defaut_hebdomadaire: bool = True) -> timedelta:
    """§15.4 — weekly by default, and on every declared event."""
    return timedelta(days=7) if defaut_hebdomadaire else timedelta(0)
