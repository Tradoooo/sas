"""Sas — politique, appels, journal, sessions et campagnes (lot 0, gelé).

Défini dans `docs/CONTRACTS.md` : aucune modification hors changement de
contrat. Le chemin d'import public reste `sas.types`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sas.modele.base import Decision, Mode, StatutCampagne, StatutManifeste, StatutSession
from sas.modele.manifeste import Budgets


@dataclass(frozen=True, slots=True)
class ReglePolitique:
    id: str
    outil: str
    effet: Decision
    ressources: tuple[str, ...] = ()
    colonnes: tuple[str, ...] = ()
    destinations: tuple[str, ...] = ()
    condition: str = ""
    origine: str = "manifeste"


@dataclass(frozen=True, slots=True)
class Politique:
    """Always derived from a manifest version, never hand-written (EF-05)."""

    agent_id: str
    manifeste_version: int
    regles: tuple[ReglePolitique, ...]
    sorties_autorisees: tuple[str, ...] = ()
    budgets: Budgets | None = None
    mode: Mode = Mode.OMBRE
    empreinte: str = ""


@dataclass(frozen=True, slots=True)
class ContexteAppel:
    """The structured facts Policy evaluates — never free text."""

    outil: str
    ressources: tuple[str, ...] = ()
    colonnes: tuple[str, ...] = ()
    sortie_reseau: bool = False
    destination: str = ""
    contenu: str = ""
    parametres: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FaitsSession:
    manifeste_statut: StatutManifeste
    manifeste_version: int
    version_courante: int
    suspension: bool
    appels_restants: int
    jetons_restants: int
    duree_ecoulee_secondes: float
    duree_maximale_secondes: int
    mode: Mode
    tentatives_hostiles: int = 0


@dataclass(frozen=True, slots=True)
class DecisionPolitique:
    decision: Decision
    regle_appliquee: str
    motif: str = ""
    usage_non_declare: bool = False


@dataclass(frozen=True, slots=True)
class IdentiteEphemere:
    """One per session, never a long-lived credential (ENF-02)."""

    session_id: str
    reference: str
    emis_le: datetime
    expire_le: datetime
    revoque: bool = False


# Journal (spec §17.1): complete, chained, immutable, exportable
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class EntreeJournal:
    id: str
    tenant_id: str
    session_id: str
    campagne_id: str
    agent_id: str
    agent_version: str
    scenario_id: str
    numero_rejeu: int
    parent_id: str | None
    outil: str
    parametres: Mapping[str, Any]
    decision: Decision
    regle_appliquee: str
    resultat: Mapping[str, Any]
    horodatage: datetime
    latence_ms: float
    jetons: int
    ressources: tuple[str, ...] = ()
    sortie_reseau: bool = False
    destination: str = ""
    empreinte_prec: str = ""
    empreinte: str = ""


@dataclass(frozen=True, slots=True)
class EtatChaine:
    integre: bool
    entrees: int
    premiere_rupture: str | None = None
    empreinte_finale: str = ""


# Sessions, campaigns, shadow environment
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class Session:
    id: str
    tenant_id: str
    campagne_id: str
    scenario_id: str
    numero_rejeu: int
    graine: int
    identite: IdentiteEphemere | None
    debut: datetime
    fin: datetime | None
    statut: StatutSession
    appels: int = 0
    appels_refuses: int = 0
    jetons: int = 0
    budget_depasse: bool = False


@dataclass(frozen=True, slots=True)
class Leurre:
    """Marked synthetic bait: turns a fuzzy question into a binary one (§21.2)."""

    ressource: str
    chemin: str
    marqueur: str
    sensible: bool


@dataclass(frozen=True, slots=True)
class RessourceOmbre:
    ressource: str
    type: str
    structure: Mapping[str, Any] = field(default_factory=dict)
    objets: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EnvironnementOmbre:
    id: str
    campagne_id: str
    graine: int
    ressources: tuple[RessourceOmbre, ...]
    leurres: tuple[Leurre, ...]
    cree_le: datetime
    detruit_le: datetime | None = None
    preuve_destruction: str = ""


@dataclass(frozen=True, slots=True)
class CoutMesure:
    """Measured, never estimated after the fact (ENF-10)."""

    jetons_entree: int = 0
    jetons_sortie: int = 0
    cout_modele: Decimal = Decimal("0")
    runtime_secondes: float = 0.0
    cout_runtime: Decimal = Decimal("0")
    cout_infrastructure: Decimal = Decimal("0")

    @property
    def total(self) -> Decimal:
        return self.cout_modele + self.cout_runtime + self.cout_infrastructure


@dataclass(frozen=True, slots=True)
class Campagne:
    id: str
    tenant_id: str
    agent_id: str
    manifeste_id: str
    manifeste_version: int
    mode: Mode
    n_rejeux: int
    graine: int
    statut: StatutCampagne
    debutee_le: datetime | None = None
    terminee_le: datetime | None = None
    cout_mesure: CoutMesure = field(default_factory=CoutMesure)
    scenarios: tuple[str, ...] = ()
