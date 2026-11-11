"""Declared vs observed, in both directions (spec §2, EF-21, KPI-5).

Two kinds of gap, and both matter:

* **overflow** — the agent touched something it did not declare;
* **dead permission** — the agent declared something it never used.

Dead permissions are **cross-referenced with IAM Access Analyzer** rather than
recomputed (§20.2): what AWS has already proven is quoted, not reinvented. When
the native source is not available yet — it needs 90 days of history — the report
says so instead of silently publishing a partial figure.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sas.analyseur.agregation import Agregat
from sas.identifiants import nouveau
from sas.ombre.support import normaliser
from sas.types import Ecart, Mode, TypeEcart


def calculer(
    campagne_id: str,
    agregat: Agregat,
    *,
    declarees: Sequence[str],
    utilisees: Sequence[str] | None = None,
    graine: int = 0,
) -> tuple[Ecart, ...]:
    """Build the gap list. `utilisees` defaults to what the journal shows."""
    observees = list(utilisees) if utilisees is not None else list(agregat.ressources)
    ecarts: list[Ecart] = []
    for ressource in sorted(set(observees)):
        if not _declaree(ressource, declarees):
            ecarts.append(
                Ecart(
                    id=nouveau("ecart", graine=graine, cle=f"{campagne_id}:deb:{ressource}"),
                    campagne_id=campagne_id,
                    type=TypeEcart.DEBORDEMENT,
                    ressource=ressource,
                    declare=False,
                    observe=True,
                    frequence=int(agregat.ressources.get(ressource, 0)),
                    source="journal",
                )
            )
    for ressource in sorted(set(declarees)):
        if not _observee(ressource, observees):
            ecarts.append(
                Ecart(
                    id=nouveau("ecart", graine=graine, cle=f"{campagne_id}:morte:{ressource}"),
                    campagne_id=campagne_id,
                    type=TypeEcart.PERMISSION_MORTE,
                    ressource=ressource,
                    declare=True,
                    observe=False,
                    frequence=0,
                    source="journal",
                )
            )
    return tuple(ecarts)


def croiser_acces_inutilises(
    campagne_id: str,
    ecarts: Sequence[Ecart],
    acces_inutilises: Sequence[Any],
    *,
    disponible: bool,
) -> tuple[Ecart, ...]:
    """EF-21 — quote the native source for dead permissions.

    A finding already produced by IAM Access Analyzer is annotated with
    `source = "iam-access-analyzer"`; when the service has no history yet, the
    dead permissions found by the journal keep `source = "journal"` and the
    report states that the native cross-reference was unavailable.
    """
    if not disponible:
        return tuple(ecarts)
    natives = {normaliser(str(d.get("ressource", d.get("resource", "")))) for d in acces_inutilises}
    enrichis: list[Ecart] = []
    for ecart in ecarts:
        if ecart.type is TypeEcart.PERMISSION_MORTE and normaliser(ecart.ressource) in natives:
            enrichis.append(
                Ecart(
                    id=ecart.id,
                    campagne_id=campagne_id,
                    type=ecart.type,
                    ressource=ecart.ressource,
                    declare=ecart.declare,
                    observe=ecart.observe,
                    frequence=ecart.frequence,
                    source="iam-access-analyzer",
                )
            )
        else:
            enrichis.append(ecart)
    return tuple(enrichis)


def debordements(ecarts: Sequence[Ecart]) -> tuple[Ecart, ...]:
    return tuple(e for e in ecarts if e.type is TypeEcart.DEBORDEMENT)


def permissions_mortes(ecarts: Sequence[Ecart]) -> tuple[Ecart, ...]:
    return tuple(e for e in ecarts if e.type is TypeEcart.PERMISSION_MORTE)


def ressources_declarees_depuis(manifeste: Any, mode: Mode = Mode.OMBRE) -> tuple[str, ...]:
    """The declared resources, in the naming the journal actually records.

    In shadow mode the guest touches the **replica** (spec 10.1), so the declared
    perimeter must be mapped onto the replica before comparing: otherwise every
    legitimate call would be reported as an overflow and every declaration as a
    dead permission, which is precisely the false signal this report must not
    produce.
    """
    from sas.ombre.replication import table_repliquees

    declarees = tuple({normaliser(d.ressource) for d in manifeste.donnees_demandees})
    return table_repliquees(declarees) if mode is Mode.OMBRE else declarees


def ressources_observees(agregat: Agregat) -> tuple[str, ...]:
    return tuple(sorted(agregat.ressources))


def _declaree(ressource: str, declarees: Sequence[str]) -> bool:
    cible = normaliser(ressource)
    return any(
        cible == normaliser(d) or cible.startswith(normaliser(d).rstrip("*").rstrip("/")) for d in declarees
    )


def _observee(declaree: str, observees: Sequence[str]) -> bool:
    cible = normaliser(declaree).rstrip("*").rstrip("/")
    return any(normaliser(o).startswith(cible) for o in observees)
