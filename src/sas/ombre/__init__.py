"""Lot 2 — the shadow environment: replica, marked decoys, destruction proof.

Public surface. Other lots import `sas.ombre`, never a sub-module.
"""

from __future__ import annotations

from sas.ombre import donnees, leurres
from sas.ombre.destruction import detruire, inventaire_avant, preuve, ressource_detruite, verifier_destruction
from sas.ombre.generateur import (
    RESSOURCE_DOCUMENTATION,
    RESSOURCE_SUIVI,
    RESSOURCE_TICKETS,
    GenerateurOmbre,
)
from sas.ombre.leurres import est_leurre, leurres_par_defaut, sensibles
from sas.ombre.support import SupportOmbre, empreinte_inventaire, normaliser

__all__ = [
    "RESSOURCE_DOCUMENTATION",
    "RESSOURCE_SUIVI",
    "RESSOURCE_TICKETS",
    "GenerateurOmbre",
    "SupportOmbre",
    "detruire",
    "donnees",
    "empreinte_inventaire",
    "est_leurre",
    "inventaire_avant",
    "leurres",
    "leurres_par_defaut",
    "normaliser",
    "preuve",
    "ressource_detruite",
    "sensibles",
    "verifier_destruction",
]
