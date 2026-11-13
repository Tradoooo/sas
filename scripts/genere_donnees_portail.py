"""Generate the portal's public dataset by running the real engine.

GitHub Pages is static: there is no Python behind `tradoooo.github.io/sas`.
Rather than hard-coding fake numbers in the page, this script **runs the airlock
for real** — three synthetic guests, the eight scenarios of annexe B, N replays —
and writes what it measured to `portal/data/demo.json`. The portal serves that
file when no API answers, and says which mode it is in.

Deterministic: same seed, same output. The deploy workflow regenerates it and
fails if the committed file is stale.

Usage:
    PYTHONPATH=src python3 scripts/genere_donnees_portail.py [--rejeux 2] [--sortie portal/data/demo.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
sys.path.insert(0, str(RACINE))

from sas import (  # noqa: E402  - sys.path is set just above
    constantes,
    libelles,
)
from sas.cli_partage import charger_contexte, invite, lancer  # noqa: E402
from sas.homologation import Dossier, resume  # noqa: E402
from sas.rapports import attestation as module_attestation  # noqa: E402
from sas.rapports import editeur as module_editeur  # noqa: E402
from sas.statistiques import phrase_portee  # noqa: E402
from sas.types import Langue, Nature  # noqa: E402

GRANGE_DEFAUT = 11
SORTIE_DEFAUT = RACINE / "portal" / "data" / "demo.json"

# The dataset is a reproducible reference run: the clock is pinned so that
# regenerating it produces identical bytes (ENF-11). The deploy workflow relies
# on this — it regenerates and diffs, and fails if the published numbers are
# stale. Pinning the clock is what makes that check meaningful rather than
# always-red on a timestamp.
INSTANT_REFERENCE = "2026-11-12T00:00:00Z"


def un_agent(nom: str, *, rejeux: int, graine: int) -> dict[str, Any]:
    """Run one guest through the airlock and serialise what it produced."""
    contexte = charger_contexte()
    agent = invite(nom)
    dossier = lancer(agent=agent, contexte=contexte, rejeux=rejeux, graine=graine)
    return {
        "nom": nom,
        "etiquette": getattr(agent, "etiquette", constantes.ETIQUETTE_SYNTHETIQUE),
        "instrumentable": bool(agent.instrumentable),
        "scenarios": [s.id for s in contexte.scenarios],
        "n_rejeux": rejeux,
        "graine": graine,
        "resume": resume(dossier),
        "conditions": list(dossier.decision.conditions),
        "motifs": list(dossier.decision.motifs),
        "compositions": _compositions(dossier),
        "ecarts": _ecarts(dossier),
        "tentatives": _tentatives(dossier),
        "portee_fr": phrase_portee(dossier.borne, "fr"),
        "portee_en": phrase_portee(dossier.borne, "en"),
        "attestation": _attestation(dossier),
        "rapport_fr": dossier.rapport_fr,
        "rapport_en": dossier.rapport_en,
        "rapport_editeur": dossier.rapport_editeur,
        "cout": _cout(dossier),
        "journal": _journal_replay(dossier),
        "filtrage": _filtrage(dossier),
    }


def _compositions(dossier: Dossier) -> list[dict[str, Any]]:
    """The forbidden chains, as the page lists them (§16.2)."""
    return [
        {"motif": c.motif.value, "nature": c.nature.value, "preuve": c.preuve, "regle": c.regle}
        for c in dossier.compositions[:8]
    ]


def _ecarts(dossier: Dossier) -> list[dict[str, Any]]:
    """Declared vs observed, both directions (EF-21, KPI-5)."""
    return [
        {"type": e.type.value, "ressource": e.ressource, "frequence": e.frequence, "source": e.source}
        for e in dossier.ecarts
    ]


def _tentatives(dossier: Dossier) -> list[dict[str, Any]]:
    """The classified attempts, with the signals that decided the nature."""
    return [
        {
            "ressource": t.ressource,
            "outil": t.outil,
            "nature": t.nature_retenue.value,
            "repetition": t.signaux.repetition,
            "persistance": t.signaux.persistance,
            "sensible": t.signaux.sensible,
            "sessions": len(t.session_ids),
        }
        for t in dossier.tentatives[:40]
    ]


def _journal_replay(dossier: Dossier, limite: int = 40) -> dict[str, Any]:
    """One session's calls, in order, for the step-through replay.

    The session chosen is the most instructive one: the session that carries a
    detected composition if there is one, else the one with the most denials,
    else the first. Bounding denials (budget, duration, suspension) are tagged
    apart from perimeter denials, because the page must not paint a session the
    airlock stopped in the same colour as an agent overreaching.
    """
    from sas.agentcore.politique_manifeste import REGLES_BORNAGE

    sessions = {s.id: s for s in dossier.campagne.sessions}
    cible = _session_instructive(dossier)
    entrees = [e for e in dossier.campagne.entrees if e.session_id == cible]
    entrees.sort(key=lambda e: (e.horodatage, e.id))
    debut = entrees[0].horodatage if entrees else None
    appels = []
    for index, entree in enumerate(entrees[:limite]):
        appels.append(
            {
                "n": index + 1,
                "outil": entree.outil,
                "ressources": list(entree.ressources),
                "decision": entree.decision.value,
                "regle": entree.regle_appliquee,
                "bornage": entree.regle_appliquee in REGLES_BORNAGE,
                "sortie": entree.sortie_reseau,
                "destination": entree.destination,
                "t_ms": round((entree.horodatage - debut).total_seconds() * 1000, 1) if debut else 0.0,
                "jetons": entree.jetons,
                "sensible": bool((entree.resultat or {}).get("sensible"))
                if isinstance(entree.resultat, dict)
                else False,
                "empreinte": entree.empreinte[:19] + "…",
            }
        )
    session = sessions.get(cible)
    return {
        "session": cible,
        "scenario": session.scenario_id if session else "",
        "rejeu": session.numero_rejeu if session else 0,
        "appels": appels,
        "tronque": len(entrees) > limite,
        "total": len(entrees),
    }


def _session_instructive(dossier: Dossier) -> str:
    """The session that best shows what happened: composition first, then denials."""
    if dossier.compositions:
        return dossier.compositions[0].session_id
    par_session: dict[str, int] = {}
    for entree in dossier.campagne.entrees:
        if entree.decision.value == "refuse":
            par_session[entree.session_id] = par_session.get(entree.session_id, 0) + 1
    if par_session:
        return max(sorted(par_session), key=lambda s: par_session[s])
    if dossier.campagne.sessions:
        return dossier.campagne.sessions[0].id
    return ""


def _filtrage(dossier: Dossier) -> dict[str, Any]:
    """§13.5 — the before/after of exploration filtering, as counted.

    This is the panel that separates a product from a raw log: the reader sees
    the volume that arrives, what is noise, and what is left for a human.
    """
    from sas.analyseur.classification import filtrer_exploration

    total = dossier.agregat.refus
    exploration = dossier.decision.decouvertes.get(Nature.EXPLORATION, 0)
    visibles = filtrer_exploration(dossier.tentatives)
    return {
        "refus_bruts": total,
        "exploration_filtree": exploration,
        "restent_a_lire": len(visibles),
        "dont_hostiles": dossier.decision.decouvertes.get(Nature.HOSTILE, 0),
        "dont_tentatives": dossier.decision.decouvertes.get(Nature.TENTATIVE, 0),
        "dont_debordements": dossier.decision.decouvertes.get(Nature.DEBORDEMENT, 0),
        "dont_revue_humaine": dossier.decision.decouvertes.get(Nature.INDETERMINEE, 0),
    }


def _cout(dossier: Dossier) -> dict[str, Any]:
    """Measured cost, never estimated afterwards (ENF-10)."""
    mesure = dossier.campagne.cout_mesure
    return {
        "modele": float(mesure.cout_modele),
        "runtime": float(mesure.cout_runtime),
        "total": float(mesure.total),
        "jetons_entree": mesure.jetons_entree,
        "jetons_sortie": mesure.jetons_sortie,
        "runtime_secondes": mesure.runtime_secondes,
    }


def _attestation(dossier: Dossier) -> dict[str, Any] | None:
    """ENF-17 — an unmeasurable guest has no attestation, and the page says so."""
    if dossier.attestation is None:
        return None
    return {
        "numero": dossier.attestation.numero,
        "verdict": dossier.attestation.resultat.value,
        "texte_fr": module_attestation.texte(dossier.attestation, "fr"),
        "texte_en": module_attestation.texte(dossier.attestation, "en"),
        "valide_jusquau": f"{dossier.attestation.valide_jusquau:%Y-%m-%d}",
        "empreinte_journal": dossier.attestation.empreinte_journal,
        "entrees_journal": dossier.attestation.entrees_journal,
    }


def registre(dossiers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The fleet registry the portal shows on the left."""
    return [
        {
            "nom": d["nom"],
            "version": "1.0.0",
            "statut": d["resume"]["verdict"],
            "attestation": (d["attestation"] or {}).get("numero"),
            "cout": d["cout"]["total"],
        }
        for d in dossiers
    ]


def construire(*, rejeux: int, graine: int, genere_le: str = "") -> dict[str, Any]:
    from datetime import datetime

    from sas.identifiants import figer_horloge

    horodatage = genere_le or INSTANT_REFERENCE
    figer_horloge(datetime.fromisoformat(horodatage.replace("Z", "+00:00")))
    try:
        return _construire(rejeux=rejeux, graine=graine, genere_le=horodatage)
    finally:
        figer_horloge(None)


def _construire(*, rejeux: int, graine: int, genere_le: str) -> dict[str, Any]:
    noms = (*constantes.AGENTS_DEMO, "demo-opaque")
    dossiers = [un_agent(nom, rejeux=rejeux, graine=graine) for nom in noms]
    premier_atteste = next((d for d in dossiers if d["attestation"]), None)
    return {
        "genere_le": genere_le,
        "reproductible": True,
        "note_reproductibilite": (
            "Horloge figée à l'instant de référence : régénérer ce fichier produit "
            "les mêmes octets (ENF-11). La CI de déploiement le vérifie par diff."
        ),
        "moteur": "sas.agentcore.local — offline, no AWS account, no model call",
        "graine": graine,
        "rejeux_par_scenario": rejeux,
        "scenarios": list(constantes.SCENARIOS_LANCES),
        "libelles": libelles.tous(),
        "avertissement": (
            "Synthetic demonstration data. The three guest agents are built for "
            "this demo and labelled as such; no real vendor agent is used, and no "
            "real personal data appears anywhere."
        ),
        "agents": dossiers,
        "registre": registre(dossiers),
        "kpi": (premier_atteste or dossiers[0])["resume"],
        "borne": {
            "niveaux": [
                {
                    "niveau": n.niveau,
                    "n": n.n_rejeux,
                    "sessions": n.sessions,
                    "confiance_p25": n.confiance_p25,
                }
                for n in _niveaux()
            ]
        },
        "rapport_editeur_exemple": (dossiers[2] if len(dossiers) > 2 else dossiers[0])["rapport_editeur"],
        "langues": [Langue.FR.value, Langue.EN.value],
        "source_donnee_client": module_editeur.sans_donnee_client(dossiers[0]["rapport_editeur"]),
    }


def _niveaux() -> list[Any]:
    from sas.statistiques import niveaux_rejeux

    return list(niveaux_rejeux())


def ecrire(donnees: dict[str, Any], sortie: Path) -> None:
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(
        json.dumps(donnees, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def main() -> int:
    parseur = argparse.ArgumentParser(description=__doc__)
    parseur.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT)
    parseur.add_argument("--graine", type=int, default=GRANGE_DEFAUT)
    parseur.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT)
    parseur.add_argument(
        "--genere-le",
        default=INSTANT_REFERENCE,
        help="timestamp to stamp the file with (the deploy workflow reuses the "
        "committed one so the regeneration is byte-for-byte comparable)",
    )
    args = parseur.parse_args()

    donnees = construire(rejeux=args.rejeux, graine=args.graine, genere_le=args.genere_le)
    ecrire(donnees, args.sortie)
    print(f"écrit {args.sortie} ({args.sortie.stat().st_size} octets)")
    for agent in donnees["agents"]:
        print(f"  {agent['nom']:<15} {agent['resume']['verdict']:<26} appels={agent['resume']['appels']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
