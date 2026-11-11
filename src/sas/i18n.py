"""Sas — bilingual labels (lot 0, frozen).

Interface and reports exist in French and English (ENF-13); the submission
deliverables are English. A lot adds its strings here through a contract
change, never by hard-coding a sentence in two places.
"""

from __future__ import annotations

from collections.abc import Mapping

from sas.types import Langue

# key -> (francais, english)
CLES: Mapping[str, tuple[str, str]] = {
    "produit.nom": ("Sas", "Sas"),
    "produit.soustitre": (
        "Homologation et exécution contrôlée des agents IA tiers",
        "Homologation and controlled execution of third-party AI agents",
    ),
    "verdict.homologue": ("Homologué", "Approved"),
    "verdict.homologue_sous_conditions": (
        "Homologué sous conditions",
        "Approved with conditions",
    ),
    "verdict.refuse": ("Refusé", "Refused"),
    "verdict.non_mesurable": ("Non mesurable", "Not measurable"),
    "nature.exploration": ("Exploration", "Exploration"),
    "nature.debordement": ("Débordement", "Overflow"),
    "nature.tentative": ("Tentative", "Attempt"),
    "nature.hostile": ("Hostile", "Hostile"),
    "nature.indeterminee": ("Indéterminée — revue humaine", "Undetermined — human review"),
    "mode.ombre": ("Ombre", "Shadow"),
    "mode.observe": ("Observé", "Observed"),
    "rapport.titre": ("Rapport d'homologation", "Homologation report"),
    "rapport.ecart": ("Écart déclaré / observé", "Declared vs observed gap"),
    "rapport.permissions_mortes": ("Permissions mortes", "Dead permissions"),
    "rapport.compositions": ("Compositions détectées", "Detected compositions"),
    "rapport.portee": ("Portée statistique", "Statistical scope"),
    "rapport.limites": ("Ce que ce rapport ne garantit pas", "What this report does not guarantee"),
    "attestation.titre": ("Attestation d'homologation", "Homologation attestation"),
    "attestation.decision": (
        "Décision de mise en production : ressort exclusif du commanditaire.",
        "Production go-live decision: sole responsibility of the sponsor.",
    ),
    "borne.avertissement": (
        "Un comportement rare n'est PAS exclu par cette homologation.",
        "A rare behaviour is NOT excluded by this homologation.",
    ),
    "borne.memoire": (
        "L'agent déclare une mémoire persistante : les rejeux ne sont plus "
        "indépendants et la borne statistique ne s'applique pas.",
        "The agent declares a persistent memory: replays are no longer "
        "independent and the statistical bound does not apply.",
    ),
    "ombre.limite": (
        "Le mode Ombre ne couvre pas les comportements dépendant de données réelles.",
        "Shadow mode does not cover behaviours that depend on real data.",
    ),
    "journal.integre": ("Journal chaîné, aucune rupture", "Chained journal, no break"),
    "journal.rompu": ("Rupture de chaîne détectée", "Chain break detected"),
    "cout.mesure": ("Coût mesuré", "Measured cost"),
    "registre.titre": ("Registre des agents tiers", "Third-party agent registry"),
    "derive.alerte": ("Alerte de dérive", "Drift alert"),
    "invite.synthetique": (
        "Agent synthétique de démonstration",
        "Synthetic demo agent",
    ),
    "invite.non_mesurable": (
        "Cet agent ne passe pas par la passerelle : il est déclaré non mesurable, jamais conforme.",
        "This agent does not go through the gateway: it is declared not measurable, never compliant.",
    ),
}


def traduire(cle: str, langue: Langue = Langue.FR) -> str:
    """Return the label for `cle` in `langue`. Missing key -> the key itself,
    so a report never crashes on an untranslated string."""
    paire = CLES.get(cle)
    if paire is None:
        return cle
    return paire[0] if langue is Langue.FR else paire[1]


def toutes_les_cles() -> tuple[str, ...]:
    return tuple(sorted(CLES))
