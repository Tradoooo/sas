"""Lot 15 — deliverables: report FR/EN, attestation, vendor gap report.

Public surface: `EntreesRapport`, `generer`, `kpi`, `construire` (attestation),
`texte` (attestation), `RapportEditeur`, `rapport_editeur`.
"""

from __future__ import annotations

from sas.rapports import attestation, editeur, rapport
from sas.rapports.attestation import construire, texte
from sas.rapports.editeur import RapportEditeur, sans_donnee_client
from sas.rapports.rapport import EntreesRapport, generer, kpi
from sas.rapports.verdict import Decision, est_bloquant
from sas.rapports.verdict import trancher as decider_verdict

__all__ = [
    "Decision",
    "EntreesRapport",
    "RapportEditeur",
    "attestation",
    "construire",
    "decider_verdict",
    "editeur",
    "est_bloquant",
    "generer",
    "kpi",
    "rapport",
    "sans_donnee_client",
    "texte",
]
