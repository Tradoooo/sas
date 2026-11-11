"""Declarative schema of the agent manifest (spec §9.2, annexe A).

The manifest is a *format*, not an interview (§3.4): the blocks and fields are
declared here as data, the structural validator reads them, and
`schemas/manifeste.schema.json` is generated from the same table so a third
party can read the format without reading the code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sas.types import ProblemeValidation, RapportValidation

TYPES_PRIMITIFS: tuple[str, ...] = ("str", "int", "bool", "date", "empreinte", "liste", "objet")


@dataclass(frozen=True, slots=True)
class Champ:
    nom: str
    type: str
    obligatoire: bool = True
    elements: str = ""  # block name, for a list of objects
    commentaire: str = ""


@dataclass(frozen=True, slots=True)
class Bloc:
    nom: str
    champs: tuple[Champ, ...]
    commentaire: str = ""


# --------------------------------------------------------------------------- #
# The table itself — annexe A, block by block
# --------------------------------------------------------------------------- #

BLOCS: Mapping[str, Bloc] = MappingProxyType(
    {
        b.nom: b
        for b in (
            Bloc(
                "manifeste",
                (
                    Champ("version", "int", commentaire="manifest version, incremented on any change"),
                    Champ("date", "date"),
                ),
                "header",
            ),
            Bloc(
                "identite",
                (
                    Champ("nom", "str"),
                    Champ("editeur", "str"),
                    Champ("version_agent", "str"),
                    Champ("empreinte_paquet", "empreinte"),
                    Champ("modele", "str"),
                    Champ("version_modele", "str"),
                    Champ("engagement_notification_modele", "bool"),
                ),
                "who and what exactly is running",
            ),
            Bloc(
                "finalite",
                (
                    Champ("fait", "str"),
                    Champ("ne_fait_pas", "liste"),
                ),
                "what the agent does, and what it does not do",
            ),
            Bloc(
                "outils_demandes",
                (
                    Champ("nom", "str"),
                    Champ("operation", "str", commentaire="lecture | ecriture | execution"),
                    Champ("justification", "str"),
                ),
                "one entry per requested tool",
            ),
            Bloc(
                "donnees_demandees",
                (
                    Champ("type", "str", commentaire="s3 | table | index | http"),
                    Champ("ressource", "str"),
                    Champ("justification", "str"),
                    Champ("colonnes", "liste", obligatoire=False),
                    Champ("prefixes", "liste", obligatoire=False),
                    Champ("sensible", "bool", obligatoire=False),
                ),
                "fine-grained resources: never 'access to the data'",
            ),
            Bloc(
                "sorties_autorisees",
                (
                    Champ("destination", "str"),
                    Champ("protocole", "str", commentaire="http | courriel | dns | webhook"),
                    Champ("justification", "str"),
                ),
                "empty by default; the key must be present",
            ),
            Bloc(
                "budgets",
                (
                    Champ("appels_par_execution", "int"),
                    Champ("jetons_par_execution", "int"),
                    Champ("duree_maximale_secondes", "int"),
                    Champ("memoire_maximale_mio", "int"),
                ),
                "hard bounds, enforced by Policy",
            ),
            Bloc(
                "memoire",
                (Champ("persistante", "bool"),),
                "if true, replays are no longer independent (§14.6)",
            ),
            Bloc(
                "scenarios",
                (
                    Champ("id", "str"),
                    Champ("nom", "str"),
                    Champ("sensibilite", "str", obligatoire=False),
                ),
                "nominal use cases the agent must handle",
            ),
            Bloc(
                "interdictions_explicites",
                (Champ("texte", "str"),),
                "what the agent must never do, even if technically able",
            ),
            Bloc(
                "engagements",
                (
                    Champ("notification_changement_modele", "str"),
                    Champ("notification_changement_invite", "str"),
                    Champ("delai_correction_critique", "str"),
                    Champ("contact", "str"),
                ),
                "vendor commitments",
            ),
            Bloc(
                "signature",
                (
                    Champ("signataire", "str"),
                    Champ("qualite", "str"),
                    Champ("date", "date"),
                    Champ("empreinte_document", "empreinte", obligatoire=False),
                ),
                "editor signature",
            ),
            Bloc(
                "validation_client",
                (
                    Champ("commanditaire", "str"),
                    Champ("date", "date"),
                    Champ("perimetre_approuve", "str"),
                    Champ("mode_autorise", "str"),
                ),
                "sponsor validation",
            ),
        )
    }
)

# Blocks that hold a list of objects rather than a single mapping.
BLOCS_LISTES: tuple[str, ...] = (
    "outils_demandes",
    "donnees_demandees",
    "sorties_autorisees",
    "scenarios",
    "interdictions_explicites",
)

BLOCS_OBLIGATOIRES: tuple[str, ...] = (
    "manifeste",
    "identite",
    "finalite",
    "outils_demandes",
    "donnees_demandees",
    "sorties_autorisees",
    "budgets",
    "scenarios",
    "interdictions_explicites",
    "engagements",
)

# A block listed here is required by the published schema, but its *absence* is
# reported by the semantic validator rather than by the structural one: annexe A
# refuses an absent `sorties_autorisees` key while accepting an empty list, and
# only the semantic layer can tell the two apart (and say what to write).
BLOCS_ABSENCE_SEMANTIQUE: tuple[str, ...] = ("sorties_autorisees",)


def probleme(champ: str, code: str, message: str, action: str) -> ProblemeValidation:
    return ProblemeValidation(champ=champ, code=code, message=message, action=action)


def _verifier_objet(chemin: str, bloc: Bloc, donnees: Any) -> list[ProblemeValidation]:
    if not isinstance(donnees, Mapping):
        return [
            probleme(
                chemin, "type-inattendu", f"« {chemin} » doit être un objet", f"Reprendre le bloc {bloc.nom}."
            )
        ]
    trouves: list[ProblemeValidation] = []
    connus = {c.nom for c in bloc.champs}
    for cle in donnees:
        if cle not in connus:
            trouves.append(
                probleme(
                    f"{chemin}.{cle}",
                    "cle-inconnue",
                    f"clé « {cle} » absente du format",
                    f"Retirer « {cle} » ou demander un changement de contrat.",
                )
            )
    for champ in bloc.champs:
        if champ.obligatoire and champ.nom not in donnees:
            trouves.append(
                probleme(
                    f"{chemin}.{champ.nom}",
                    "champ-absent",
                    f"le champ « {champ.nom} » est obligatoire",
                    f"Renseigner « {champ.nom} » dans le bloc {bloc.nom}.",
                )
            )
    return trouves


def valider_structure(donnees: Mapping[str, Any]) -> RapportValidation:
    """Structural validation only: blocks, required fields, unknown keys.

    Semantics (grain of a permission, coherence of a budget) is the job of
    `sas.manifeste.validation`.
    """
    if not isinstance(donnees, Mapping):
        return RapportValidation(
            False,
            (probleme("", "document-invalide", "document illisible", "Fournir un objet YAML ou JSON."),),
        )
    problemes = _blocs_absents(donnees) + _blocs_inconnus(donnees)
    for nom, valeur in donnees.items():
        if nom in BLOCS:
            problemes += _verifier_valeur(nom, valeur)
    return RapportValidation(not problemes, tuple(problemes))


def _blocs_absents(donnees: Mapping[str, Any]) -> list[ProblemeValidation]:
    return [
        probleme(
            bloc,
            "bloc-absent",
            f"le bloc « {bloc} » est absent",
            f"Ajouter le bloc « {bloc} » (annexe A).",
        )
        for bloc in BLOCS_OBLIGATOIRES
        if bloc not in donnees and bloc not in BLOCS_ABSENCE_SEMANTIQUE
    ]


def _blocs_inconnus(donnees: Mapping[str, Any]) -> list[ProblemeValidation]:
    return [
        probleme(
            nom,
            "bloc-inconnu",
            f"bloc « {nom} » inconnu",
            "Retirer ce bloc ou demander un changement de contrat.",
        )
        for nom in donnees
        if nom not in BLOCS
    ]


def _verifier_valeur(nom: str, valeur: Any) -> list[ProblemeValidation]:
    bloc = BLOCS[nom]
    if nom not in BLOCS_LISTES:
        return _verifier_objet(nom, bloc, valeur)
    if not isinstance(valeur, (list, tuple)):
        return [
            probleme(
                nom,
                "type-inattendu",
                f"« {nom} » doit être une liste",
                f"Fournir une liste d'objets {nom}.",
            )
        ]
    problemes: list[ProblemeValidation] = []
    for index, element in enumerate(valeur):
        if isinstance(element, Mapping):
            problemes += _verifier_objet(f"{nom}[{index}]", bloc, element)
        elif nom != "interdictions_explicites":
            problemes.append(
                probleme(
                    f"{nom}[{index}]",
                    "type-inattendu",
                    "entrée non objet",
                    "Chaque entrée doit être un objet.",
                )
            )
    return problemes


def schema_json() -> dict[str, Any]:
    """JSON Schema (draft 2020-12) generated from the table above."""
    proprietes: dict[str, Any] = {}
    for nom, bloc in BLOCS.items():
        proprietes[nom] = _schema_bloc(bloc, liste=nom in BLOCS_LISTES)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/BaptisteFaisy/sas/schemas/manifeste.schema.json",
        "title": "Sas agent manifest",
        "description": "Signed declaration of what a third-party agent asks for and commits to (spec §9).",
        "type": "object",
        "additionalProperties": False,
        "required": list(BLOCS_OBLIGATOIRES),
        "properties": proprietes,
    }


def _schema_champ(champ: Champ) -> dict[str, Any]:
    correspondance = {
        "str": {"type": "string", "minLength": 1},
        "int": {"type": "integer", "exclusiveMinimum": 0},
        "bool": {"type": "boolean"},
        "date": {"type": "string", "format": "date"},
        "empreinte": {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"},
    }
    schema = dict(correspondance.get(champ.type, {"type": "string"}))
    if champ.type == "liste":
        schema = {"type": "array", "items": {"type": "string"}}
    if champ.commentaire:
        schema["description"] = champ.commentaire
    return schema


def _schema_bloc(bloc: Bloc, *, liste: bool) -> dict[str, Any]:
    objet = {
        "type": "object",
        "additionalProperties": False,
        "required": [c.nom for c in bloc.champs if c.obligatoire],
        "properties": {c.nom: _schema_champ(c) for c in bloc.champs},
    }
    if not liste:
        objet["description"] = bloc.commentaire
        return objet
    return {"type": "array", "description": bloc.commentaire, "items": objet}
