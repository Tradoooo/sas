"""Semantic validation of a manifest (spec §21.1, §9.3, EF-01…EF-05).

Every refusal carries an **actionable** message: the architect must know what
to change, not only that something is wrong. The structural check lives in
`sas.manifeste.schema`; this module checks meaning.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from sas import constantes
from sas.manifeste.schema import probleme
from sas.types import (
    DonneeDemandee,
    Manifeste,
    ProblemeValidation,
    RapportValidation,
    StatutManifeste,
)

EMPREINTE_VALIDE = re.compile(r"^sha256:[0-9a-f]{64}$")
VAGUES = ("accès", "acces", "toutes", "tous les", "données", "donnees")
PREFIXE_S3 = re.compile(r"^(?:arn:aws:s3:::)?([^/]+)(?:/(.*))?$")
MOTS_INTERDICTION_SORTIE = ("requête réseau sortante", "requete reseau sortante", "sortie", "sortant")


def valider(manifeste: Manifeste, *, cles_absentes: Sequence[str] = ()) -> RapportValidation:
    """Full semantic validation. `cles_absentes` comes from the loader."""
    problemes: list[ProblemeValidation] = []
    problemes += _verifier_grain(manifeste.donnees_demandees)
    problemes += _verifier_justifications(manifeste)
    problemes += _verifier_sorties(manifeste, cles_absentes)
    problemes += _verifier_budgets(manifeste)
    problemes += _verifier_scenarios(manifeste)
    problemes += _verifier_interdictions(manifeste)
    problemes += _verifier_identite(manifeste)
    problemes += _verifier_engagements(manifeste)
    problemes += _verifier_signatures(manifeste)
    return RapportValidation(not problemes, tuple(problemes))


def est_executable(manifeste: Manifeste, version_courante: str) -> tuple[bool, str]:
    """EF-04 / ENF-01 — no run without a signed, validated, current manifest."""
    if manifeste.statut is not StatutManifeste.VALIDE:
        return (
            False,
            f"manifeste au statut « {manifeste.statut.value} » : "
            "signature éditeur et validation commanditaire exigées",
        )
    if manifeste.signature is None or manifeste.validation_client is None:
        return False, "manifeste non signé ou non validé"
    if manifeste.identite.version_agent != version_courante:
        return False, (
            f"le manifeste vise la version {manifeste.identite.version_agent} "
            f"de l'agent, la version courante est {version_courante}"
        )
    if (
        manifeste.empreinte
        and manifeste.signature.empreinte_document
        and (manifeste.empreinte != manifeste.signature.empreinte_document)
    ):
        return False, "l'empreinte du document signé ne correspond plus au manifeste"
    return True, ""


# --------------------------------------------------------------------------- #
# Individual checks — one function per family, each returning actionable items
# --------------------------------------------------------------------------- #


def _verifier_grain(donnees: Iterable[DonneeDemandee]) -> list[ProblemeValidation]:
    """EF-02 — « accès S3 » is refused; the prefix is required."""
    trouves: list[ProblemeValidation] = []
    for donnee in donnees:
        if _vague(donnee.ressource):
            trouves.append(
                probleme(
                    f"donnees_demandees[{donnee.ressource}]",
                    "grain-trop-large",
                    f"la ressource « {donnee.ressource} » n'est pas au grain fin",
                    "Déclarer la ressource précise : bucket ET préfixe, table ET colonnes, index nommé.",
                )
            )
            continue
        if donnee.type == "s3" and not _prefixe_s3(donnee.ressource):
            trouves.append(
                probleme(
                    f"donnees_demandees[{donnee.ressource}]",
                    "prefixe-absent",
                    f"la ressource S3 « {donnee.ressource} » n'a pas de préfixe",
                    "Ajouter un préfixe, par exemple arn:aws:s3:::client-tickets/entree/*.",
                )
            )
        if donnee.type == "table" and not donnee.colonnes:
            trouves.append(
                probleme(
                    f"donnees_demandees[{donnee.ressource}]",
                    "colonnes-absentes",
                    f"la table « {donnee.ressource} » est déclarée sans colonnes",
                    "Lister les colonnes réellement utilisées.",
                )
            )
    return trouves


def _vague(ressource: str) -> bool:
    texte = ressource.strip().lower()
    if not texte:
        return True
    if any(mot in texte for mot in VAGUES):
        return True
    return texte in ("*", "s3", "table", "index", "bucket")


def _prefixe_s3(ressource: str) -> bool:
    """True when the ARN carries at least one path segment after the bucket."""
    match = PREFIXE_S3.match(ressource.strip())
    if not match:
        return False
    apres = (match.group(2) or "").strip("/")
    return bool(apres) and apres != "*"


def _verifier_justifications(manifeste: Manifeste) -> list[ProblemeValidation]:
    trouves: list[ProblemeValidation] = []
    for outil in manifeste.outils_demandes:
        if not outil.justification.strip():
            trouves.append(
                probleme(
                    f"outils_demandes[{outil.nom}]",
                    "justification-absente",
                    f"l'outil « {outil.nom} » n'est pas justifié",
                    "Expliquer en une phrase pourquoi l'agent en a besoin.",
                )
            )
        if outil.operation not in ("lecture", "ecriture", "execution"):
            trouves.append(
                probleme(
                    f"outils_demandes[{outil.nom}]",
                    "operation-inconnue",
                    f"opération « {outil.operation} » inconnue",
                    "Utiliser lecture, ecriture ou execution.",
                )
            )
    for donnee in manifeste.donnees_demandees:
        if not donnee.justification.strip():
            trouves.append(
                probleme(
                    f"donnees_demandees[{donnee.ressource}]",
                    "justification-absente",
                    f"la donnée « {donnee.ressource} » n'est pas justifiée",
                    "Expliquer pourquoi cette ressource est nécessaire.",
                )
            )
    for sortie in manifeste.sorties_autorisees:
        if not sortie.justification.strip():
            trouves.append(
                probleme(
                    f"sorties_autorisees[{sortie.destination}]",
                    "justification-absente",
                    f"la sortie « {sortie.destination} » n'est pas justifiée",
                    "Expliquer pourquoi cette sortie est nécessaire.",
                )
            )
    return trouves


def _verifier_sorties(manifeste: Manifeste, cles_absentes: Sequence[str]) -> list[ProblemeValidation]:
    """§9.3 — outbound is forbidden by default and declared one by one."""
    if "sorties_autorisees" in cles_absentes:
        return [
            probleme(
                "sorties_autorisees",
                "cle-absente",
                "la clé « sorties_autorisees » est absente du manifeste",
                "Écrire explicitement `sorties_autorisees: []` pour déclarer "
                "qu'aucune sortie n'est demandée.",
            )
        ]
    trouves: list[ProblemeValidation] = []
    for sortie in manifeste.sorties_autorisees:
        if "*" in sortie.destination or not sortie.destination.strip():
            trouves.append(
                probleme(
                    f"sorties_autorisees[{sortie.destination}]",
                    "sortie-joker",
                    "une sortie ne peut pas être déclarée avec un joker",
                    "Déclarer chaque destination nominativement.",
                )
            )
        if sortie.protocole not in ("http", "courriel", "dns", "webhook"):
            trouves.append(
                probleme(
                    f"sorties_autorisees[{sortie.destination}]",
                    "protocole-inconnu",
                    f"protocole « {sortie.protocole} » inconnu",
                    "Utiliser http, courriel, dns ou webhook.",
                )
            )
    return trouves


def _verifier_budgets(manifeste: Manifeste) -> list[ProblemeValidation]:
    budgets = manifeste.budgets
    trouves: list[ProblemeValidation] = []
    for nom, valeur in (
        ("appels_par_execution", budgets.appels_par_execution),
        ("jetons_par_execution", budgets.jetons_par_execution),
        ("duree_maximale_secondes", budgets.duree_maximale_secondes),
        ("memoire_maximale_mio", budgets.memoire_maximale_mio),
    ):
        if valeur <= 0:
            trouves.append(
                probleme(
                    f"budgets.{nom}",
                    "budget-absent",
                    f"le budget « {nom} » est absent ou nul",
                    f"Renseigner « {nom} » avec une valeur strictement positive.",
                )
            )
    requis = _appels_requis(manifeste)
    if requis and budgets.appels_par_execution < requis:
        trouves.append(
            probleme(
                "budgets.appels_par_execution",
                "budget-incoherent",
                f"le budget d'appels ({budgets.appels_par_execution}) est inférieur "
                f"au minimum requis par les scénarios déclarés ({requis})",
                f"Porter « appels_par_execution » à {requis} au moins, ou retirer un scénario.",
            )
        )
    if budgets.duree_maximale_secondes < budgets.appels_par_execution:
        trouves.append(
            probleme(
                "budgets.duree_maximale_secondes",
                "budget-incoherent",
                "la durée maximale laisse moins d'une seconde par appel déclaré",
                "Augmenter « duree_maximale_secondes » ou réduire « appels_par_execution ».",
            )
        )
    return trouves


def _appels_requis(manifeste: Manifeste) -> int:
    """Highest call count expected by the declared official scenarios."""
    requis = 0
    for scenario in manifeste.scenarios:
        attendus = constantes.APPELS_ATTENDUS.get(scenario.id)
        if attendus:
            requis = max(requis, attendus[1])
    return requis


def _verifier_scenarios(manifeste: Manifeste) -> list[ProblemeValidation]:
    if not manifeste.scenarios:
        return [
            probleme(
                "scenarios",
                "scenarios-absents",
                "aucun scénario déclaré",
                "Déclarer au moins un cas d'usage nominal à rejouer.",
            )
        ]
    trouves: list[ProblemeValidation] = []
    vus: set[str] = set()
    for scenario in manifeste.scenarios:
        if not scenario.id.strip() or not scenario.nom.strip():
            trouves.append(
                probleme(
                    "scenarios",
                    "scenario-incomplet",
                    "un scénario sans identifiant ou sans nom",
                    "Renseigner l'identifiant et le nom de chaque scénario.",
                )
            )
        if scenario.id in vus:
            trouves.append(
                probleme(
                    f"scenarios[{scenario.id}]",
                    "scenario-en-double",
                    f"le scénario « {scenario.id} » est déclaré deux fois",
                    "Ne déclarer chaque scénario qu'une fois.",
                )
            )
        vus.add(scenario.id)
    return trouves


def _verifier_interdictions(manifeste: Manifeste) -> list[ProblemeValidation]:
    """§21.1 — an explicit prohibition contradicting a request is refused."""
    trouves: list[ProblemeValidation] = []
    texte = " | ".join(manifeste.interdictions_explicites).lower()
    interdit_sortie = any(mot in texte for mot in MOTS_INTERDICTION_SORTIE)
    if interdit_sortie and manifeste.sorties_autorisees:
        trouves.append(
            probleme(
                "interdictions_explicites",
                "interdiction-contradictoire",
                "une interdiction exclut toute requête sortante alors que des sorties sont autorisées",
                "Retirer l'interdiction ou retirer les sorties autorisées.",
            )
        )
    outils = {outil.nom.lower() for outil in manifeste.outils_demandes}
    for interdiction in manifeste.interdictions_explicites:
        for outil in outils:
            if outil and outil in interdiction.lower():
                trouves.append(
                    probleme(
                        "interdictions_explicites",
                        "interdiction-contradictoire",
                        f"l'interdiction « {interdiction} » vise l'outil demandé « {outil} »",
                        "Retirer l'outil demandé ou reformuler l'interdiction.",
                    )
                )
    return trouves


def _verifier_identite(manifeste: Manifeste) -> list[ProblemeValidation]:
    identite = manifeste.identite
    trouves: list[ProblemeValidation] = []
    if not EMPREINTE_VALIDE.match(identite.empreinte_paquet.strip()):
        trouves.append(
            probleme(
                "identite.empreinte_paquet",
                "empreinte-invalide",
                f"l'empreinte « {identite.empreinte_paquet[:24]}… » n'est pas au format sha256:<64 hex>",
                "Fournir l'empreinte complète du paquet ou de l'image.",
            )
        )
    for champ, valeur in (
        ("modele", identite.modele),
        ("version_modele", identite.version_modele),
        ("version_agent", identite.version_agent),
        ("editeur", identite.editeur),
    ):
        if not valeur.strip():
            trouves.append(
                probleme(
                    f"identite.{champ}",
                    "champ-vide",
                    f"« {champ} » est vide",
                    f"Renseigner « {champ} » : c'est ce qui permet de détecter une dérive non déclarée.",
                )
            )
    return trouves


def _verifier_engagements(manifeste: Manifeste) -> list[ProblemeValidation]:
    engagements = manifeste.engagements
    trouves: list[ProblemeValidation] = []
    for champ, valeur in (
        ("notification_changement_modele", engagements.notification_changement_modele),
        ("notification_changement_invite", engagements.notification_changement_invite),
        ("delai_correction_critique", engagements.delai_correction_critique),
        ("contact", engagements.contact),
    ):
        if not valeur.strip():
            trouves.append(
                probleme(
                    f"engagements.{champ}",
                    "engagement-absent",
                    f"l'engagement « {champ} » est absent",
                    f"Renseigner « {champ} » : sans lui, une dérive non déclarée n'engage personne.",
                )
            )
    return trouves


def _verifier_signatures(manifeste: Manifeste) -> list[ProblemeValidation]:
    """EF-03 — editor signature and sponsor validation are both required."""
    trouves: list[ProblemeValidation] = []
    if manifeste.signature is None:
        trouves.append(
            probleme(
                "signature",
                "signature-absente",
                "la signature de l'éditeur est absente",
                "Faire signer le manifeste par une personne habilitée à engager l'éditeur.",
            )
        )
    else:
        for champ, valeur in (
            ("signataire", manifeste.signature.signataire),
            ("qualite", manifeste.signature.qualite),
        ):
            if not valeur.strip():
                trouves.append(
                    probleme(
                        f"signature.{champ}",
                        "champ-vide",
                        f"« {champ} » est vide",
                        f"Renseigner « {champ} ».",
                    )
                )
    if manifeste.validation_client is None:
        trouves.append(
            probleme(
                "validation_client",
                "validation-absente",
                "la validation du commanditaire est absente",
                "Faire valider le périmètre par le commanditaire (RSSI ou DPO).",
            )
        )
    elif not manifeste.validation_client.perimetre_approuve.strip():
        trouves.append(
            probleme(
                "validation_client.perimetre_approuve",
                "champ-vide",
                "le périmètre approuvé n'est pas précisé",
                "Préciser ce que le commanditaire approuve.",
            )
        )
    return trouves
