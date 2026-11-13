"""The campaign: N replays x scenarios, isolated sessions, measured cost.

Follows §11.1 step by step. What it never does automatically (§18): grant an
undeclared permission, put an un-homologated agent in production, or ignore a
critical finding.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from sas import aleatoire
from sas.agentcore.fabrique import Backend, politique_depuis
from sas.agentcore.fabrique import backend as construire_backend
from sas.agentcore.local import AgentNonInstrumentable
from sas.agentcore.ports import AgentInvite
from sas.arret import Interrupteur, Suspension
from sas.identifiants import maintenant, nouveau
from sas.manifeste.validation import est_executable
from sas.ombre import GenerateurOmbre, SupportOmbre
from sas.orchestrateur.sessions import executer_rejeu
from sas.scenarios import Scenario, entree_pour
from sas.store.base import Depot
from sas.types import Campagne as CampagneType
from sas.types import (
    CoutMesure,
    EntreeJournal,
    EtatChaine,
    Manifeste,
    Mode,
    Session,
    StatutCampagne,
    StatutSession,
)


@dataclass(frozen=True, slots=True)
class ResultatCampagne:
    campagne: CampagneType
    sessions: tuple[Session, ...] = ()
    entrees: tuple[EntreeJournal, ...] = ()
    appels_emis: int = 0
    couverture_journal: float = 0.0
    cout_mesure: CoutMesure = field(default_factory=CoutMesure)
    etat_chaine: EtatChaine = field(default_factory=lambda: EtatChaine(True, 0))
    suspensions: tuple[Suspension, ...] = ()
    non_mesurable: bool = False
    motif_refus: str = ""
    erreurs: tuple[str, ...] = ()
    ombre_detruite_le: datetime | None = None
    preuve_destruction: str = ""


class Campagne:
    """One homologation campaign in one mode."""

    def __init__(
        self,
        *,
        campagne: CampagneType,
        manifeste: Manifeste,
        agent: AgentInvite,
        scenarios: Sequence[Scenario],
        version_courante: str | None = None,
        support: SupportOmbre | None = None,
        generateur: GenerateurOmbre | None = None,
        depot: Depot | None = None,
        backend: Backend | None = None,
        interrupteur: Interrupteur | None = None,
        memoire_persistante: bool | None = None,
    ) -> None:
        self.campagne = campagne
        self.manifeste = manifeste
        self.agent = agent
        self.scenarios = tuple(scenarios)
        self.version_courante = version_courante or manifeste.identite.version_agent
        self.depot = depot
        self.interrupteur = interrupteur or Interrupteur()
        self._generateur = generateur or GenerateurOmbre()
        self._support = support
        self._backend = backend
        self.erreurs: list[str] = []
        self._memoire_persistante = (
            manifeste.memoire_persistante if memoire_persistante is None else memoire_persistante
        )

    # -- public ------------------------------------------------------------ #
    def executer(self) -> ResultatCampagne:
        """ENF-01 — nothing runs without a signed, validated, current manifest."""
        executable, motif = est_executable(self.manifeste, self.version_courante)
        if not executable:
            return self._refuser(motif)
        if not self.agent.instrumentable:
            return self._non_mesurable()

        politique = politique_depuis(self.manifeste, self.campagne.mode)
        ombre = self._generateur.construire(self.campagne.id, politique, self.campagne.graine)
        if self._support is None:
            self._support = SupportOmbre(ombre, self.campagne.graine)
        moteur = self._assembler(politique)

        sessions = self._rejouer(moteur)
        return self._conclure(ombre, sessions)

    def suspendre(self, motif: str, par: str = "analyste") -> Suspension:
        """EF-15 — immediate suspension, in shadow as well as observed mode."""
        return self.interrupteur.armer(motif, par=par)

    # -- internals --------------------------------------------------------- #
    def _assembler(self, politique: Any) -> Backend:
        if self._backend is not None:
            return self._backend
        assert self._support is not None
        self._backend = construire_backend(
            politique=politique,
            support=self._support,
            mode=self.campagne.mode,
            tenant_id=self.campagne.tenant_id,
            memoires_persistantes={self.agent.nom: self._memoire_persistante},
            manifeste_statut=self.manifeste.statut,
            version_courante=self.manifeste.version,
        )
        return self._backend

    def _rejouer(self, moteur: Backend) -> list[Session]:
        sessions: list[Session] = []
        for scenario in self.scenarios:
            for rejeu in range(1, self.campagne.n_rejeux + 1):
                if self.interrupteur.arme:
                    return sessions
                sessions.append(self._un_rejeu(moteur, scenario, rejeu))
                if not self._memoire_persistante:
                    moteur.memoire.reinitialiser(self.campagne.id)
        return sessions

    def _un_rejeu(self, moteur: Backend, scenario: Scenario, rejeu: int) -> Session:
        graine = aleatoire.graine_derivee(self.campagne.graine, scenario.id, rejeu)
        entree = entree_pour(scenario, graine, rejeu)
        session = executer_rejeu(
            backend=moteur,
            agent=self.agent,
            scenario_id=scenario.id,
            numero_rejeu=rejeu,
            graine=graine,
            campagne_id=self.campagne.id,
            entree=entree,
            interrupteur=self.interrupteur,
            erreurs=self.erreurs,
        )
        if self.depot is not None:
            self.depot.enregistrer_session(session)
        return session

    def _conclure(self, ombre: Any, sessions: Sequence[Session]) -> ResultatCampagne:
        assert self._support is not None
        detruit_le, preuve = self._generateur.detruire(ombre)
        self._support.detruire()
        entrees = tuple(self._observabilite().entrees(self.campagne.id))
        emis = sum(s.appels for s in sessions)
        termine = maintenant()
        mesure = self._observabilite().cout(self.campagne.id)
        self.campagne = _maj_campagne(self.campagne, sessions, mesure, termine)
        if self.depot is not None:
            self.depot.enregistrer_campagne(self.campagne)
        return ResultatCampagne(
            campagne=self.campagne,
            sessions=tuple(sessions),
            entrees=entrees,
            appels_emis=emis,
            couverture_journal=_couverture(emis, entrees),
            cout_mesure=mesure,
            etat_chaine=self._observabilite().verifier_chaine(self.campagne.id),
            suspensions=tuple(self.interrupteur.suspensions),
            ombre_detruite_le=detruit_le,
            preuve_destruction=preuve,
            erreurs=tuple(self.erreurs),
        )

    def _observabilite(self) -> Any:
        assert self._backend is not None
        return self._backend.observabilite

    def _refuser(self, motif: str) -> ResultatCampagne:
        return ResultatCampagne(campagne=self.campagne, motif_refus=motif)

    def _non_mesurable(self) -> ResultatCampagne:
        """ENF-17 — declared unmeasurable, never compliant, no attestation."""
        return ResultatCampagne(
            campagne=self.campagne,
            non_mesurable=True,
            motif_refus=f"agent « {self.agent.nom} » non instrumentable : aucune mesure possible",
        )


def _couverture(emis: int, entrees: Sequence[EntreeJournal]) -> float:
    """KPI-4 — 100 % of the calls journalled, denials included."""
    if emis == 0:
        return 1.0
    return len(entrees) / emis


def _maj_campagne(
    campagne: CampagneType, sessions: Sequence[Session], mesure: CoutMesure, termine: datetime
) -> CampagneType:
    from dataclasses import replace

    suspendue = any(s.statut is StatutSession.SUSPENDUE for s in sessions)
    statut = StatutCampagne.SUSPENDUE if suspendue else StatutCampagne.TERMINEE
    return replace(campagne, statut=statut, terminee_le=termine, cout_mesure=mesure)


def _cle_campagne(agent_id: str, manifeste: Manifeste, n_rejeux: int, variante: str) -> str:
    """What makes a campaign unique — and reproducible.

    The identifier is derived from the campaign's own inputs, so the same
    inputs give the same identifier and the same fingerprints (ENF-11). The
    `variante` is the guest actually measured: the three demonstration guests
    share one reference manifest, and without it they would share one campaign
    — three runs, one row.
    """
    return f"{agent_id}:{manifeste.version}:{n_rejeux}:{variante}"


def nouvelle_campagne(
    *,
    tenant_id: str,
    agent_id: str,
    manifeste: Manifeste,
    mode: Mode = Mode.OMBRE,
    n_rejeux: int = 2,
    graine: int = 0,
    scenarios: Sequence[str] = (),
    variante: str = "",
) -> CampagneType:
    """Build the campaign record. `n_rejeux` defaults to the development level
    (§26.4 rule 2): the full N = 6 is reserved for demonstration campaigns."""
    return CampagneType(
        id=nouveau("camp", graine=graine, cle=_cle_campagne(agent_id, manifeste, n_rejeux, variante)),
        tenant_id=tenant_id,
        agent_id=agent_id,
        manifeste_id=manifeste.agent_id,
        manifeste_version=manifeste.version,
        mode=mode,
        n_rejeux=n_rejeux,
        graine=graine,
        statut=StatutCampagne.PLANIFIEE,
        debutee_le=maintenant(),
        cout_mesure=CoutMesure(cout_modele=Decimal("0")),
        scenarios=tuple(scenarios),
    )


def agent_non_instrumentable(exc: AgentNonInstrumentable) -> str:
    return exc.detail or str(exc)
