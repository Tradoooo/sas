"""From a campaign result to the full dossier (spec §11.1 steps 7-10).

One entry point, so the CLI, the API and the tests all read the same numbers:

    journal -> aggregation (code) -> compositions (data rules)
            -> classification (code decides, model proposes)
            -> declared/observed gaps -> verdict -> attestation + reports

No step here asks a model for a decision (EF-25).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sas import ecarts as module_ecarts
from sas import statistiques
from sas.analyseur.agregation import Agregat, agreger
from sas.analyseur.classification import classer, compter_par_nature
from sas.compositions import detecter as detecter_compositions
from sas.compositions import ressources_dans_composition
from sas.constantes import SEUILS_DEFAUT, Seuils
from sas.identifiants import maintenant, nouveau
from sas.orchestrateur.campagne import ResultatCampagne
from sas.rapports import attestation as module_attestation
from sas.rapports import editeur as module_editeur
from sas.rapports import rapport as module_rapport
from sas.rapports.verdict import Decision, trancher
from sas.signature import calculer as calculer_signature
from sas.signature import sceller as sceller_signature
from sas.types import (
    Attestation,
    BorneStatistique,
    Composition,
    Ecart,
    Enveloppe,
    Langue,
    Manifeste,
    PropositionModele,
    SignatureComportementale,
    Tentative,
)


@dataclass(frozen=True, slots=True)
class Mesures:
    """The output of passes 1 to 3, before any document is written."""

    agregat: Agregat
    tentatives: tuple[Tentative, ...]
    compositions: tuple[Composition, ...]
    ecarts: tuple[Ecart, ...]
    decision: Decision
    borne: BorneStatistique
    signature: SignatureComportementale


@dataclass(frozen=True, slots=True)
class Dossier:
    """Everything one homologation produced. The portal reads this."""

    campagne: ResultatCampagne
    agregat: Agregat
    tentatives: tuple[Tentative, ...]
    compositions: tuple[Composition, ...]
    ecarts: tuple[Ecart, ...]
    decision: Decision
    borne: BorneStatistique
    signature: SignatureComportementale
    attestation: Attestation | None
    rapport_fr: str
    rapport_en: str
    rapport_editeur: str
    kpi: dict[str, Any]


def mesurer(
    resultat: ResultatCampagne,
    *,
    manifeste: Manifeste,
    tenant_id: str,
    propositions: dict[str, PropositionModele] | None = None,
    seuils: Seuils = SEUILS_DEFAUT,
    ressources_sensibles: Sequence[str] = (),
    leurres: Sequence[str] = (),
    acces_inutilises: Sequence[Any] = (),
    source_native_disponible: bool = False,
    graine: int = 0,
) -> Mesures:
    """Passes 1 to 3 of §21.4: aggregate, detect compositions, classify, gap."""
    agregat = agreger(resultat.entrees)
    compositions = detecter_compositions(
        resultat.campagne.id,
        resultat.entrees,
        destinations_declarees=[s.destination for s in manifeste.sorties_autorisees],
        graine=graine,
    )
    composees = ressources_dans_composition(compositions, resultat.entrees)
    tentatives = classer(
        resultat.campagne.id,
        tenant_id,
        agregat,
        ressources_sensibles=ressources_sensibles or _sensibles(manifeste, leurres),
        ressources_scenarios=_ressources_des_scenarios(manifeste),
        compositions=composees,
        propositions=propositions or {},
        leurres=leurres,
        seuils=seuils,
        graine=graine,
    )
    ecarts = _ecarts(resultat, manifeste, agregat, acces_inutilises, source_native_disponible, graine)
    return Mesures(
        agregat=agregat,
        tentatives=tentatives,
        compositions=compositions,
        ecarts=ecarts,
        decision=trancher(tentatives, compositions, ecarts, non_mesurable=resultat.non_mesurable),
        borne=statistiques.borne(
            resultat.campagne.n_rejeux, memoire_persistante=manifeste.memoire_persistante
        ),
        signature=sceller_signature(calculer_signature(agregat)),
    )


def analyser(
    resultat: ResultatCampagne,
    *,
    manifeste: Manifeste,
    tenant_id: str,
    propositions: dict[str, PropositionModele] | None = None,
    seuils: Seuils = SEUILS_DEFAUT,
    ressources_sensibles: Sequence[str] = (),
    leurres: Sequence[str] = (),
    acces_inutilises: Sequence[Any] = (),
    source_native_disponible: bool = False,
    signataire: str = "Analyste MSP",
    date: datetime | None = None,
    rang_du_jour: int = 1,
    graine: int = 0,
) -> Dossier:
    """Run passes 1 to 3 and produce every deliverable."""
    mesure = mesurer(
        resultat,
        manifeste=manifeste,
        tenant_id=tenant_id,
        propositions=propositions,
        seuils=seuils,
        ressources_sensibles=ressources_sensibles,
        leurres=leurres,
        acces_inutilises=acces_inutilises,
        source_native_disponible=source_native_disponible,
        graine=graine,
    )
    attestation_objet = _attestation(
        resultat, manifeste, mesure.decision, mesure.borne, signataire, date or maintenant(), rang_du_jour
    )
    entrees_rapport = _entrees_rapport(resultat, manifeste, mesure, attestation_objet)
    rapport_editeur = module_editeur.construire(
        manifeste=manifeste,
        verdict=mesure.decision.verdict,
        tentatives=mesure.tentatives,
        compositions=mesure.compositions,
        ecarts=mesure.ecarts,
    )
    return _dossier(resultat, mesure, attestation_objet, entrees_rapport, rapport_editeur)


def _dossier(
    resultat: ResultatCampagne,
    mesure: Mesures,
    attestation_objet: Attestation | None,
    entrees_rapport: module_rapport.EntreesRapport,
    rapport_editeur: module_editeur.RapportEditeur,
) -> Dossier:
    """Assemble the deliverables from the measurements. No computation here."""
    return Dossier(
        campagne=resultat,
        agregat=mesure.agregat,
        tentatives=mesure.tentatives,
        compositions=mesure.compositions,
        ecarts=mesure.ecarts,
        decision=mesure.decision,
        borne=mesure.borne,
        signature=mesure.signature,
        attestation=attestation_objet,
        rapport_fr=module_rapport.generer(entrees_rapport, Langue.FR),
        rapport_en=module_rapport.generer(entrees_rapport, Langue.EN),
        rapport_editeur=module_editeur.texte(rapport_editeur, Langue.FR),
        kpi=module_rapport.kpi(entrees_rapport),
    )


def enveloppe(
    dossier: Dossier,
    *,
    agent_id: str,
    tenant_id: str,
    version: str,
    reference: bool = False,
    date: datetime | None = None,
) -> Enveloppe:
    """EF-30 — keep one envelope per homologated version, as the reference."""
    return Enveloppe(
        id=nouveau("env", cle=f"{agent_id}:{version}:{dossier.campagne.campagne.id}"),
        agent_id=agent_id,
        tenant_id=tenant_id,
        version=version,
        n_rejeux=dossier.campagne.campagne.n_rejeux,
        date=date or maintenant(),
        signature=dossier.signature,
        borne=dossier.borne,
        reference=reference,
    )


def resume(dossier: Dossier) -> dict[str, Any]:
    """A small JSON-able summary: what the portal and the CLI print."""
    return {
        "verdict": dossier.decision.verdict.value,
        "sessions": len(dossier.campagne.sessions),
        "appels": dossier.campagne.appels_emis,
        "refus": dossier.agregat.refus,
        "couverture": dossier.campagne.couverture_journal,
        "decouvertes": {n.value: c for n, c in compter_par_nature(dossier.tentatives).items()},
        "compositions": len(dossier.compositions),
        "ecarts": len(dossier.ecarts),
        "cout": float(dossier.campagne.cout_mesure.total),
        "chaine_integre": dossier.campagne.etat_chaine.integre,
        "attestation": dossier.attestation.numero if dossier.attestation else None,
    }


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _ecarts(
    resultat: ResultatCampagne,
    manifeste: Manifeste,
    agregat: Agregat,
    acces_inutilises: Sequence[Any],
    source_native_disponible: bool,
    graine: int,
) -> tuple[Ecart, ...]:
    """EF-21 — dead permissions are cross-referenced with the native source."""
    calcules = module_ecarts.calculer(
        resultat.campagne.id,
        agregat,
        declarees=module_ecarts.ressources_declarees_depuis(manifeste, resultat.campagne.mode),
        graine=graine,
    )
    return module_ecarts.croiser_acces_inutilises(
        resultat.campagne.id, calcules, acces_inutilises, disponible=source_native_disponible
    )


def _entrees_rapport(
    resultat: ResultatCampagne,
    manifeste: Manifeste,
    mesure: Mesures,
    attestation_objet: Attestation | None,
) -> module_rapport.EntreesRapport:
    return module_rapport.EntreesRapport(
        manifeste=manifeste,
        decision=mesure.decision,
        tentatives=mesure.tentatives,
        compositions=mesure.compositions,
        ecarts=mesure.ecarts,
        cout=resultat.cout_mesure,
        etat_chaine=resultat.etat_chaine,
        sessions=len(resultat.sessions),
        appels=resultat.appels_emis,
        refus=mesure.agregat.refus,
        borne_texte=statistiques.phrase_portee(mesure.borne, "fr"),
        attestation=attestation_objet,
        limites_ombre=_limites_ombre(manifeste, mesure.agregat),
        source_permissions_mortes=_source(mesure.ecarts),
    )


def _attestation(
    resultat: ResultatCampagne,
    manifeste: Manifeste,
    decision: Decision,
    borne: BorneStatistique,
    signataire: str,
    date: datetime,
    rang: int,
) -> Attestation | None:
    """ENF-17 — an unmeasurable agent receives no attestation at all."""
    if decision.verdict.value == "non_mesurable":
        return None
    return module_attestation.construire(
        campagne=resultat.campagne,
        manifeste=manifeste,
        decision=decision,
        borne=borne,
        etat_chaine=resultat.etat_chaine,
        compositions=(),
        rang_du_jour=rang,
        signataire=signataire,
        date=date,
        ombre_detruite_le=resultat.ombre_detruite_le,
    )


def _ressources_des_scenarios(manifeste: Manifeste) -> tuple[str, ...]:
    """A resource that serves a declared scenario has a link to the purpose."""
    from sas.ombre.replication import table_repliquees
    from sas.ombre.support import normaliser

    declarees = tuple({normaliser(d.ressource) for d in manifeste.donnees_demandees})
    return tuple(table_repliquees(declarees))


def _sensibles(manifeste: Manifeste, leurres: Sequence[str]) -> tuple[str, ...]:
    sensibles = tuple(d.ressource for d in manifeste.donnees_demandees if d.sensible)
    return sensibles + tuple(leurres)


def _limites_ombre(manifeste: Manifeste, agregat: Agregat) -> tuple[str, ...]:
    """§10.4 — honesty requirement: name what shadow mode cannot reveal."""
    limites = [
        "Les scénarios dont l'issue dépend du contenu réel d'un ticket ne sont "
        "pas entièrement révélés en mode Ombre."
    ]
    if manifeste.memoire_persistante:
        limites.append(
            "L'agent déclare une mémoire persistante : les rejeux ne sont plus "
            "indépendants et la borne statistique ne s'applique pas (§14.6)."
        )
    if agregat.appels == 0:
        limites.append("Aucun appel n'a été observé : ce rapport ne prouve rien.")
    return tuple(limites)


def _source(ecarts: Sequence[Ecart]) -> str:
    for ecart in ecarts:
        if ecart.source == "iam-access-analyzer":
            return "iam-access-analyzer"
    return "journal"
