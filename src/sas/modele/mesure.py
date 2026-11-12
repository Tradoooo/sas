"""Sas — mesure : tentatives, compositions, écarts, signature, dérive (lot 0, gelé).

Défini dans `docs/CONTRACTS.md` : aucune modification hors changement de
contrat. Le chemin d'import public reste `sas.types`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from sas.modele.base import ActionDerive, Mode, MotifComposition, Nature, TypeEcart, Verdict


@dataclass(frozen=True, slots=True)
class Signaux:
    """The measurable signals classification is computed from (§13.2)."""

    repetition: int = 0
    persistance: int = 0
    dispersion: int = 0
    sensible: bool = False
    lien_finalite: bool = False
    composition: bool = False
    sortie_tentee: bool = False
    leurre_touche: bool = False
    # Which forbidden chain, when `composition` is set. Decisive: §16.2 makes
    # exfiltration and elevation Hostile but persistence only Tentative, so a
    # single boolean cannot carry the rule — and treating every composition as
    # hostile would refuse an agent the specification says to investigate.
    composition_motif: str = ""
    # Whether the attempt named a **specific** resource, as opposed to enumerating
    # the environment. This signal is not in the §13.2 table, and it was added
    # because that table cannot separate annexe D rows 1 and 2: both are a single
    # call, non-sensitive, no persistence, no composition, with a link to the
    # declared purpose — yet row 1 (`list_buckets`) is Exploration and row 2
    # (reading a named configuration bucket) is Overflow. The only measurable
    # difference between them is whether a specific resource was targeted.
    cible_precise: bool = False


@dataclass(frozen=True, slots=True)
class PropositionModele:
    """What Bedrock proposes. Never what the report states (§13.4)."""

    nature: Nature
    confiance: float
    citation: str
    entrees: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Tentative:
    id: str
    campagne_id: str
    tenant_id: str
    session_ids: tuple[str, ...]
    ressource: str
    outil: str
    nature_proposee: PropositionModele | None
    nature_retenue: Nature
    signaux: Signaux
    revue_humaine: str | None = None
    desaccord: bool = False
    entrees: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Composition:
    id: str
    campagne_id: str
    session_id: str
    motif: MotifComposition
    chaine: tuple[str, ...]
    nature: Nature
    preuve: str
    regle: str


@dataclass(frozen=True, slots=True)
class Ecart:
    id: str
    campagne_id: str
    type: TypeEcart
    ressource: str
    declare: bool
    observe: bool
    frequence: int = 0
    source: str = "sas"


@dataclass(frozen=True, slots=True)
class LigneBorne:
    probabilite: float
    confiance: float


@dataclass(frozen=True, slots=True)
class BorneStatistique:
    """What N replays prove — and what they do not (spec §14)."""

    n_rejeux: int
    lignes: tuple[LigneBorne, ...]
    rejeux_independants: bool
    memoire_persistante: bool = False


@dataclass(frozen=True, slots=True)
class SignatureComportementale:
    outils: Mapping[str, float] = field(default_factory=dict)
    ressources: Mapping[str, float] = field(default_factory=dict)
    sequences: Mapping[str, float] = field(default_factory=dict)
    budgets: Mapping[str, float] = field(default_factory=dict)
    empreinte: str = ""


@dataclass(frozen=True, slots=True)
class Enveloppe:
    id: str
    agent_id: str
    tenant_id: str
    version: str
    n_rejeux: int
    date: datetime
    signature: SignatureComportementale
    borne: BorneStatistique
    reference: bool = False


@dataclass(frozen=True, slots=True)
class EcartSignature:
    cle: str
    famille: str
    reference: float
    courante: float
    contribution: float


@dataclass(frozen=True, slots=True)
class Derive:
    id: str
    agent_id: str
    tenant_id: str
    enveloppe_ref: str
    enveloppe_courante: str
    distance: float
    detail: tuple[EcartSignature, ...]
    alerte_le: datetime
    action: ActionDerive
    changement_non_declare: bool = False


@dataclass(frozen=True, slots=True)
class Attestation:
    """Dated, chained, deliberately poor in details (spec §17.2)."""

    id: str
    numero: str
    campagne_id: str
    tenant_id: str
    agent_nom: str
    agent_version: str
    editeur: str
    empreinte_paquet: str
    modele_declare: str
    mode: Mode
    manifeste_version: int
    scenarios: int
    n_rejeux: int
    sessions: int
    periode_debut: datetime
    periode_fin: datetime
    resultat: Verdict
    decouvertes: Mapping[Nature, int]
    permissions_mortes: int
    compositions: int
    conditions: tuple[str, ...]
    borne: BorneStatistique
    empreinte_journal: str
    entrees_journal: int
    ombre_detruite_le: datetime | None
    valide_jusquau: datetime
    signataire: str
    date: datetime
    chemin_s3: str = ""
    remplace: str | None = None
