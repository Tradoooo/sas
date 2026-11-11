"""Sas — le manifeste d'agent, déclaration signée (lot 0, gelé).

Défini dans `docs/CONTRACTS.md` : aucune modification hors changement de
contrat. Le chemin d'import public reste `sas.types`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from sas.modele.base import Mode, StatutManifeste


@dataclass(frozen=True, slots=True)
class OutilDemande:
    nom: str
    operation: Literal["lecture", "ecriture", "execution"]
    justification: str


@dataclass(frozen=True, slots=True)
class DonneeDemandee:
    type: Literal["s3", "table", "index", "http"]
    ressource: str
    justification: str
    colonnes: tuple[str, ...] = ()
    prefixes: tuple[str, ...] = ()
    sensible: bool = False


@dataclass(frozen=True, slots=True)
class SortieAutorisee:
    destination: str
    protocole: Literal["http", "courriel", "dns", "webhook"]
    justification: str


@dataclass(frozen=True, slots=True)
class Budgets:
    appels_par_execution: int
    jetons_par_execution: int
    duree_maximale_secondes: int
    memoire_maximale_mio: int


@dataclass(frozen=True, slots=True)
class ScenarioRef:
    id: str
    nom: str
    sensibilite: Literal["ordinaire", "elevee"] = "ordinaire"


@dataclass(frozen=True, slots=True)
class IdentiteAgent:
    nom: str
    editeur: str
    version_agent: str
    empreinte_paquet: str
    modele: str
    version_modele: str
    engagement_notification_modele: bool


@dataclass(frozen=True, slots=True)
class Finalite:
    fait: str
    ne_fait_pas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Engagements:
    notification_changement_modele: str
    notification_changement_invite: str
    delai_correction_critique: str
    contact: str


@dataclass(frozen=True, slots=True)
class SignatureEditeur:
    signataire: str
    qualite: str
    date: datetime
    empreinte_document: str


@dataclass(frozen=True, slots=True)
class ValidationClient:
    commanditaire: str
    date: datetime
    perimetre_approuve: str
    mode_autorise: Mode


@dataclass(frozen=True, slots=True)
class Manifeste:
    """The signed declaration. Source of the applied policy *and* of the
    comparison baseline: the two can never diverge (spec §20.3)."""

    agent_id: str
    version: int
    date: datetime
    identite: IdentiteAgent
    finalite: Finalite
    outils_demandes: tuple[OutilDemande, ...]
    donnees_demandees: tuple[DonneeDemandee, ...]
    sorties_autorisees: tuple[SortieAutorisee, ...]
    budgets: Budgets
    scenarios: tuple[ScenarioRef, ...]
    interdictions_explicites: tuple[str, ...]
    engagements: Engagements
    memoire_persistante: bool = False
    signature: SignatureEditeur | None = None
    validation_client: ValidationClient | None = None
    statut: StatutManifeste = StatutManifeste.BROUILLON
    empreinte: str = ""


@dataclass(frozen=True, slots=True)
class ProblemeValidation:
    champ: str
    code: str
    message: str
    action: str


@dataclass(frozen=True, slots=True)
class RapportValidation:
    valide: bool
    problemes: tuple[ProblemeValidation, ...] = ()
