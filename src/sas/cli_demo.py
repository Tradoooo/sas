"""`sas demo` — the three synthetic guests, three different verdicts (§28).

Runs offline, on synthetic data, and prints what the 3-minute video shows:

* 0:55  the chatty guest exploring with undeclared tools and touching the
        configuration decoy;
* 1:10  the exploration filtering — thousands of denials, a handful of findings;
* 1:40  the curious guest reading the sensitive decoy then attempting an
        outbound call, denied;
* 1:55  the exfiltration composition, identified by code from the signals;
* 2:10  three verdicts: approved with conditions, refused, approved;
* 2:25  the attestation with its statistical scope.
"""

from __future__ import annotations

import sys
from collections.abc import Sequence

from sas import constantes
from sas.cli_partage import charger_contexte, etiquette_synthese, lancer
from sas.homologation import Dossier, resume
from sas.statistiques import phrase_portee
from sas.store.base import Depot


def executer_demo(
    *,
    rejeux: int = 2,
    graine: int = 11,
    agent: str = "",
    scenarios: Sequence[str] = (),
    depot: Depot | None = None,
    tenant_id: str = "tenant-demo",
) -> int:
    invites = (agent,) if agent else constantes.AGENTS_DEMO
    contexte = charger_contexte(scenarios)
    if not contexte.scenarios:
        print("ERREUR: aucun scénario sélectionné", file=sys.stderr)
        return 1

    _entete(contexte, rejeux, graine)
    dossiers: list[tuple[str, Dossier]] = []
    for rang, nom in enumerate(invites, start=_rang_du_jour(depot) + 1):
        dossier = _un_agent(nom, contexte, rejeux, graine, depot, tenant_id, rang)
        dossiers.append((nom, dossier))

    print("\n" + "=" * 78)
    print("2:10  VERDICTS")
    print("=" * 78)
    for nom, dossier in dossiers:
        synthese = resume(dossier)
        print(f"  {nom:<15} {synthese['verdict'].upper()}")
        if dossier.decision.conditions:
            for condition in dossier.decision.conditions:
                print(f"      · {condition}")
        for motif in dossier.decision.motifs:
            print(f"      - {motif}")

    _borne(dossiers)
    return 0


def _entete(contexte: object, rejeux: int, graine: int) -> None:
    manifeste = contexte.manifeste
    scenarios = contexte.scenarios
    print("Sas — démonstration : trois agents invités synthétiques, trois verdicts")
    print(f"  {etiquette_synthese()}")
    print(f"  agent de référence   {manifeste.identite.nom} {manifeste.identite.version_agent}")
    print(f"  éditeur              {manifeste.identite.editeur}")
    print(f"  modèle déclaré       {manifeste.identite.modele} ({manifeste.identite.version_modele})")
    liste = ", ".join(scenario.id for scenario in scenarios)
    print(f"  scénarios            {liste} x {rejeux} rejeux · graine {graine}")
    print(f"  sorties autorisées   {len(manifeste.sorties_autorisees)} (aucune par défaut)")


def _rang_du_jour(depot: Depot | None) -> int:
    """The next attestation number of the day.

    The numero is a daily sequence: when the demo writes to a real store, it
    continues the numbering the store already holds instead of restarting at 1
    and issuing a second attestation under a number taken yesterday's.
    """
    if depot is None:
        return 0
    from sas.identifiants import maintenant

    aujourdhui = maintenant().date()
    return sum(1 for attestation in depot.attestations() if attestation.date.date() == aujourdhui)


def _un_agent(
    nom: str,
    contexte: object,
    rejeux: int,
    graine: int,
    depot: Depot | None = None,
    tenant_id: str = "tenant-demo",
    rang_du_jour: int = 1,
) -> Dossier:
    from sas.cli_partage import invite

    print("\n" + "=" * 78)
    print(f"{nom}")
    print("=" * 78)
    try:
        agent = invite(nom)
    except ValueError as exc:
        print(f"  agent inconnu: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    dossier = lancer(
        agent=agent,
        contexte=contexte,
        rejeux=rejeux,
        graine=graine,
        depot=depot,
        tenant_id=tenant_id,
        rang_du_jour=rang_du_jour,
    )
    if depot is not None:
        _persister(depot, dossier)
    _afficher(nom, dossier)
    return dossier


def _persister(depot: Depot, dossier: Dossier) -> dict[str, int]:
    """Write what the campaign produced into the store.

    The campaign and its sessions were written by the orchestrator; the journal,
    the findings and the attestation are written here, so the store holds the
    same evidence the report quotes — not a summary of it.
    """
    from sas.store.persistance import persister

    return persister(depot, dossier)


def _afficher(nom: str, dossier: Dossier) -> None:
    synthese = resume(dossier)
    if synthese["verdict"] == "non_mesurable":
        print("  cet agent ne passe pas par la passerelle : déclaré NON MESURABLE,")
        print("  jamais « conforme ». Aucune attestation n'est produite (ENF-17).")
        return
    print(f"  sessions {synthese['sessions']} · appels {synthese['appels']} · refus {synthese['refus']}")
    print(
        f"  couverture du journal {synthese['couverture']:.2f} · chaîne "
        f"{'intègre' if synthese['chaine_integre'] else 'ROMPUE'}"
    )
    print(f"  découvertes : {synthese['decouvertes']}")
    print(
        f"  écarts {synthese['ecarts']} · compositions {synthese['compositions']} · "
        f"coût {synthese['cout']:.2f} $"
    )
    for composition in dossier.compositions[:3]:
        print(f"    ! {composition.motif.value} ({composition.nature.value}) : {composition.preuve}")
    if nom == "demo-bavard":
        print(
            f"  {synthese['decouvertes'].get('exploration', 0)} appel(s) d'exploration FILTRÉ(S) : "
            "du bruit de raisonnement, pas une découverte (§13.5)"
        )
    if dossier.attestation is not None:
        print(f"  attestation {dossier.attestation.numero} — {dossier.attestation.resultat.value}")


def _borne(dossiers: Sequence[tuple[str, Dossier]]) -> None:
    print("\n" + "=" * 78)
    print("2:25  PORTÉE STATISTIQUE — ce que ces rejeux prouvent, et ce qu'ils ne prouvent pas")
    print("=" * 78)
    for nom, dossier in dossiers:
        if dossier.attestation is None:
            continue
        print(f"  {nom}")
        print(f"    {phrase_portee(dossier.borne, 'fr')}")
