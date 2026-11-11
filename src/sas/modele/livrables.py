"""Sas — registre, tenants, éditeurs et agents (lot 0, gelé).

Défini dans `docs/CONTRACTS.md` : aucune modification hors changement de
contrat. Le chemin d'import public reste `sas.types`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal

from sas.modele.base import StatutAgent, Verdict


@dataclass(frozen=True, slots=True)
class Tenant:
    id: str
    nom_client: str
    contact_commanditaire: str
    retention_jours: int = 90


@dataclass(frozen=True, slots=True)
class Editeur:
    id: str
    nom: str
    contact: str
    signature_publique: str = ""


@dataclass(frozen=True, slots=True)
class Agent:
    id: str
    tenant_id: str
    editeur_id: str
    nom: str
    version_courante: str
    empreinte: str
    statut: StatutAgent = StatutAgent.EN_ATTENTE
    instrumentable: bool = True
    modele_declare: str = ""


@dataclass(frozen=True, slots=True)
class LigneRegistre:
    agent: Agent
    editeur: Editeur
    derniere_homologation: datetime | None
    valide_jusquau: datetime | None
    resultat: Verdict | None
    campagnes: int
    cout_cumule: Decimal


@dataclass(frozen=True, slots=True)
class ContexteTenant:
    """Derived from the token, never from free text (EF-51)."""

    tenant_id: str
    role: Literal[
        "commanditaire",
        "architecte",
        "juridique",
        "analyste_msp",
        "responsable_compte",
        "editeur",
    ]
    acteur: str
    editeur_id: str | None = None
    jeton: str = ""
