"""Lot 1 — the agent manifest: format, validation, versioning, seal.

Public surface of the lot. Other lots import `sas.manifeste`, never a
sub-module.
"""

from __future__ import annotations

from sas.manifeste.chargement import (
    Chargement,
    ErreurManifeste,
    charger,
    charger_depuis_texte,
    charger_manifeste,
)
from sas.manifeste.schema import (
    BLOCS,
    BLOCS_ABSENCE_SEMANTIQUE,
    BLOCS_LISTES,
    BLOCS_OBLIGATOIRES,
    schema_json,
    valider_structure,
)
from sas.manifeste.signature import sceller, signer_editeur, valider_commanditaire, verifier
from sas.manifeste.validation import est_executable, valider
from sas.manifeste.versions import (
    CHAMPS_ENGAGEANTS,
    avec_empreinte,
    empreinte_manifeste,
    historique,
    invalidations,
    marquer_remplace,
    nouvelle_version,
    projection,
)

__all__ = [
    "BLOCS",
    "BLOCS_ABSENCE_SEMANTIQUE",
    "BLOCS_LISTES",
    "BLOCS_OBLIGATOIRES",
    "CHAMPS_ENGAGEANTS",
    "Chargement",
    "ErreurManifeste",
    "avec_empreinte",
    "charger",
    "charger_depuis_texte",
    "charger_manifeste",
    "empreinte_manifeste",
    "est_executable",
    "historique",
    "invalidations",
    "marquer_remplace",
    "nouvelle_version",
    "projection",
    "sceller",
    "schema_json",
    "signer_editeur",
    "valider",
    "valider_commanditaire",
    "valider_structure",
    "verifier",
]
