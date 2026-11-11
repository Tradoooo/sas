"""Sas — énumérations et natures du domaine (lot 0, gelé).

Défini dans `docs/CONTRACTS.md` : aucune modification hors changement de
contrat. Le chemin d'import public reste `sas.types`.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from types import MappingProxyType


class Mode(str, Enum):
    """The two operating modes of the airlock (spec §10)."""

    OMBRE = "ombre"
    OBSERVE = "observe"


class Nature(str, Enum):
    """The four natures of an out-of-scope attempt (spec §13.1)."""

    EXPLORATION = "exploration"
    DEBORDEMENT = "debordement"
    TENTATIVE = "tentative"
    HOSTILE = "hostile"
    INDETERMINEE = "indeterminee"


SEVERITE: Mapping[Nature, str] = MappingProxyType(
    {
        Nature.EXPLORATION: "aucune",
        Nature.DEBORDEMENT: "faible",
        Nature.TENTATIVE: "elevee",
        Nature.HOSTILE: "critique",
        Nature.INDETERMINEE: "revue_humaine",
    }
)


class Verdict(str, Enum):
    HOMOLOGUE = "homologue"
    SOUS_CONDITIONS = "homologue_sous_conditions"
    REFUSE = "refuse"
    NON_MESURABLE = "non_mesurable"


class StatutManifeste(str, Enum):
    BROUILLON = "brouillon"
    INVALIDE = "invalide"
    SIGNE_EDITEUR = "signe_editeur"
    VALIDE = "valide"
    REMPLACE = "remplace"


class StatutAgent(str, Enum):
    EN_ATTENTE = "en_attente"
    HOMOLOGUE = "homologue"
    SOUS_CONDITIONS = "sous_conditions"
    REFUSE = "refuse"
    SUSPENDU = "suspendu"
    NON_MESURABLE = "non_mesurable"


class Decision(str, Enum):
    """What Policy decided about one tool call (spec annexe C)."""

    AUTORISE = "autorise"
    AUTORISE_SOUS_CONDITION = "autorise_sous_condition"
    REFUSE = "refuse"


class StatutCampagne(str, Enum):
    PLANIFIEE = "planifiee"
    EN_COURS = "en_cours"
    SUSPENDUE = "suspendue"
    TERMINEE = "terminee"
    ECHOUEE = "echouee"


class StatutSession(str, Enum):
    EN_COURS = "en_cours"
    TERMINEE = "terminee"
    BUDGET_DEPASSE = "budget_depasse"
    SUSPENDUE = "suspendue"
    ERREUR = "erreur"


class TypeEcart(str, Enum):
    DEBORDEMENT = "debordement"
    PERMISSION_MORTE = "permission_morte"


class MotifComposition(str, Enum):
    EXFILTRATION = "exfiltration"
    ELEVATION = "elevation"
    PERSISTENCE = "persistence"


class Langue(str, Enum):
    FR = "fr"
    EN = "en"


class ActionDerive(str, Enum):
    JOURNALISEE = "journalisee"
    ALERTE = "alerte"
    ALERTE_IMMEDIATE = "alerte_immediate"
    SUSPENSION = "suspension"
    REHOMOLOGATION = "rehomologation"
