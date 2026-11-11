"""The gateway: the single choke point for every tool call (lot 5).

Without a single choke point there is no exhaustive journal, and without an
exhaustive journal there is no proof (§20.2). Everything a guest agent does goes
through here: the policy is evaluated **before** the tool runs, and the call is
journalled whether it was allowed or denied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sas import constantes
from sas.agentcore.local import IdentityLocal
from sas.agentcore.politique_manifeste import PolicyLocale
from sas.arret import BudgetEpuise, SessionSuspendue
from sas.identifiants import maintenant, nouveau
from sas.journal.chaine import JournalChaine
from sas.ombre import RESSOURCE_DOCUMENTATION, RESSOURCE_SUIVI, RESSOURCE_TICKETS
from sas.ombre.support import SupportOmbre
from sas.types import (
    ContexteAppel,
    Decision,
    DecisionPolitique,
    EntreeJournal,
    FaitsSession,
    IdentiteEphemere,
    Mode,
    Politique,
    Session,
    StatutManifeste,
)

OUTIL_RESSOURCE: dict[str, str] = {
    "lire_ticket": RESSOURCE_TICKETS,
    "chercher_document": RESSOURCE_DOCUMENTATION,
    "ouvrir_tache": RESSOURCE_SUIVI,
}


@dataclass(slots=True)
class CadreSession:
    """Everything the toolbox of one session needs. Counters are mutable."""

    session: Session
    identite: IdentiteEphemere
    politique: Politique
    support: SupportOmbre
    journal: JournalChaine
    identite_port: IdentityLocal
    manifeste_statut: StatutManifeste = StatutManifeste.VALIDE
    version_courante: int = 1
    mode: Mode = Mode.OMBRE
    appels_restants: int = 25
    jetons_restants: int = 60_000
    duree_maximale_secondes: int = 180
    suspendu: bool = False
    appels: int = 0
    refus: int = 0
    jetons: int = 0
    latences: list[float] = field(default_factory=list)
    tentatives_hostiles: int = 0
    moteur: Any | None = None
    interrupteur: Any | None = None
    plafond_arret: int = 0

    def faits(self) -> FaitsSession:
        """The structured facts the policy evaluates — never free text."""
        return FaitsSession(
            manifeste_statut=self.manifeste_statut,
            manifeste_version=self.politique.manifeste_version,
            version_courante=self.version_courante,
            suspension=self.suspendu or self.identite_port.est_revoquee(self.session.id),
            appels_restants=self.appels_restants,
            jetons_restants=self.jetons_restants,
            duree_ecoulee_secondes=0.0,
            duree_maximale_secondes=self.duree_maximale_secondes,
            mode=self.mode,
            tentatives_hostiles=self.tentatives_hostiles,
        )


class BoiteOutilsLocale:
    """The only handle a guest agent gets on the world."""

    def __init__(self, cadre: CadreSession) -> None:
        self._cadre = cadre

    @property
    def session(self) -> Session:
        return self._cadre.session

    def appeler(
        self, outil: str, parametres: dict[str, Any] | None = None, *, parent_id: str | None = None
    ) -> dict[str, Any]:
        parametres = dict(parametres or {})
        contexte = ContexteAppel(
            outil=outil,
            ressources=_ressources_de(outil, parametres),
            colonnes=tuple(str(c) for c in parametres.get("colonnes", ())),
            sortie_reseau=False,
            parametres=parametres,
        )
        return self._traiter(contexte, parent_id)

    def sortie(self, destination: str, contenu: str, protocole: str = "http") -> dict[str, Any]:
        contexte = ContexteAppel(
            outil=f"sortie:{protocole}",
            sortie_reseau=True,
            destination=destination,
            contenu=contenu,
            parametres={"destination": destination, "contenu": contenu},
        )
        return self._traiter(contexte, None)

    # -- internals --------------------------------------------------------- #
    def _traiter(self, contexte: ContexteAppel, parent_id: str | None) -> dict[str, Any]:
        self._verifier_arret()
        decision = self._evaluer(contexte)
        resultat = self._executer(contexte) if decision.decision is not Decision.REFUSE else {}
        entree = self._journaliser(contexte, decision, resultat, parent_id)
        self._compter(decision, entree)
        self._verifier_budget()
        return {
            "ok": decision.decision is not Decision.REFUSE,
            "decision": decision.decision.value,
            "regle": decision.regle_appliquee,
            "motif": decision.motif,
            "resultat": resultat,
            "appel_id": entree.id,
        }

    def _verifier_arret(self) -> None:
        """ENF-09 / R7 — the kill switch is checked before anything else."""
        cadre = self._cadre
        if cadre.interrupteur is not None and cadre.interrupteur.arme:
            suspension = cadre.interrupteur.derniere()
            raise SessionSuspendue(cadre.session.id, suspension.motif if suspension else "suspendue")

    def _verifier_budget(self) -> None:
        """EF-13 / R6 — a clean stop at budget x 1.2, not a hard kill."""
        cadre = self._cadre
        if cadre.plafond_arret and cadre.appels >= cadre.plafond_arret:
            raise BudgetEpuise(
                cadre.session.id, f"{cadre.appels} appels pour un plafond de {cadre.plafond_arret}"
            )

    def _evaluer(self, contexte: ContexteAppel) -> DecisionPolitique:
        """The policy engine is injected; a missing one defaults to the
        manifest-derived engine so the gateway is never permissive by accident."""
        cadre = self._cadre
        if cadre.moteur is None:
            cadre.moteur = PolicyLocale(cadre.politique)
        return cadre.moteur.evaluer(contexte, cadre.faits())

    def _executer(self, contexte: ContexteAppel) -> dict[str, Any]:
        support = self._cadre.support
        parametres = contexte.parametres
        if contexte.outil == "chercher_document":
            return dict(support.chercher(RESSOURCE_DOCUMENTATION, str(parametres.get("requete", ""))))
        if contexte.outil == "ouvrir_tache":
            reponse = support.ecrire(RESSOURCE_SUIVI, str(parametres.get("resume", "")), str(parametres))
            return dict(reponse)
        if contexte.outil == "lire_ticket":
            return dict(support.lire(RESSOURCE_TICKETS, str(parametres.get("id", ""))))
        if contexte.outil == "list_buckets":
            return dict(support.lister(""))
        if contexte.outil == "describe_table":
            return dict(support.lire(RESSOURCE_SUIVI))
        if contexte.ressources:
            return dict(support.lire(contexte.ressources[0], str(parametres.get("chemin", ""))))
        return {}

    def _journaliser(
        self, contexte: ContexteAppel, decision: Any, resultat: dict[str, Any], parent_id: str | None
    ) -> EntreeJournal:
        cadre = self._cadre
        entree = EntreeJournal(
            id=nouveau("appel", graine=cadre.session.graine, cle=f"{cadre.session.id}:{cadre.appels + 1}"),
            tenant_id=cadre.session.tenant_id,
            session_id=cadre.session.id,
            campagne_id=cadre.session.campagne_id,
            agent_id=cadre.politique.agent_id,
            agent_version=str(cadre.version_courante),
            scenario_id=cadre.session.scenario_id,
            numero_rejeu=cadre.session.numero_rejeu,
            parent_id=parent_id,
            outil=contexte.outil,
            parametres=_minimiser(contexte.parametres),
            decision=decision.decision,
            regle_appliquee=decision.regle_appliquee,
            resultat=resultat,
            horodatage=maintenant(),
            latence_ms=0.0,
            jetons=sum(constantes.JETONS_AGENT_PAR_APPEL),
            ressources=contexte.ressources,
            sortie_reseau=contexte.sortie_reseau,
            destination=contexte.destination,
        )
        return cadre.journal.ajouter(entree)

    def _compter(self, decision: Any, entree: EntreeJournal) -> None:
        cadre = self._cadre
        cadre.appels += 1
        cadre.jetons += entree.jetons
        cadre.appels_restants = max(0, cadre.appels_restants - 1)
        cadre.jetons_restants = max(0, cadre.jetons_restants - entree.jetons)
        if decision.decision is Decision.REFUSE:
            cadre.refus += 1
            if decision.regle_appliquee in ("sortie-non-declaree",) and _sensible_lu(cadre):
                cadre.tentatives_hostiles += 1


class GatewayLocal:
    """Hands out one toolbox per session and measures the added latency."""

    def __init__(
        self,
        *,
        politique: Politique,
        support: SupportOmbre,
        journal: JournalChaine,
        identite_port: IdentityLocal,
        moteur: Any | None = None,
        manifeste_statut: StatutManifeste = StatutManifeste.VALIDE,
        version_courante: int = 1,
        mode: Mode = Mode.OMBRE,
    ) -> None:
        self._politique = politique
        self._support = support
        self._journal = journal
        self._identite = identite_port
        self._moteur = moteur
        self._manifeste_statut = manifeste_statut
        self._version_courante = version_courante
        self._mode = mode
        self._cadres: dict[str, CadreSession] = {}

    def boite_outils(self, session: Session, identite: IdentiteEphemere) -> BoiteOutilsLocale:
        cadre = self.ouvrir_session(session, identite)
        return BoiteOutilsLocale(cadre)

    def ouvrir_session(self, session: Session, identite: IdentiteEphemere) -> CadreSession:
        existant = self._cadres.get(session.id)
        if existant is not None:
            return existant
        budgets = self._politique.budgets
        cadre = CadreSession(
            session=session,
            identite=identite,
            politique=self._politique,
            support=self._support,
            journal=self._journal,
            identite_port=self._identite,
            manifeste_statut=self._manifeste_statut,
            version_courante=self._version_courante,
            mode=self._mode,
            appels_restants=budgets.appels_par_execution if budgets else 25,
            jetons_restants=budgets.jetons_par_execution if budgets else 60_000,
            duree_maximale_secondes=budgets.duree_maximale_secondes if budgets else 180,
            plafond_arret=_plafond(budgets),
        )
        cadre.moteur = self._moteur
        self._cadres[session.id] = cadre
        return cadre

    def cadre(self, session_id: str) -> CadreSession | None:
        return self._cadres.get(session_id)

    def latence_ms(self, session: Session) -> float:
        cadre = self._cadres.get(session.id)
        if not cadre or not cadre.latences:
            return 0.0
        return sum(cadre.latences) / len(cadre.latences)


def _ressources_de(outil: str, parametres: dict[str, Any]) -> tuple[str, ...]:
    if outil in OUTIL_RESSOURCE:
        return (OUTIL_RESSOURCE[outil],)
    ressource = parametres.get("ressource")
    if isinstance(ressource, str) and ressource:
        return (ressource,)
    ressources = parametres.get("ressources")
    if isinstance(ressources, (list, tuple)):
        return tuple(str(r) for r in ressources)
    return ()


def _minimiser(parametres: dict[str, Any]) -> dict[str, Any]:
    """§25 — the journal minimises what it records: no payload, no secret."""
    return {
        cle: valeur for cle, valeur in parametres.items() if cle not in ("contenu", "secret", "mot_de_passe")
    }


def _sensible_lu(cadre: CadreSession) -> bool:
    for entree in cadre.journal.entrees(cadre.session.id):
        resultat = entree.resultat or {}
        if isinstance(resultat, dict) and resultat.get("sensible"):
            return True
    return False


def _plafond(budgets: Any) -> int:
    """Annexe C: the session ends cleanly at budget x 1.2."""
    from sas.arret import CompteursBudget

    return CompteursBudget.depuis(budgets).plafond_arret
