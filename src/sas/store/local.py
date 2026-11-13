"""The in-memory store: the `Depot` port, tenant-scoped (lot 5).

One instance is bound to **one** tenant, and no method takes a tenant as a
parameter: isolation is structural rather than a filter somebody might forget
(EF-50, EF-51). The integrity rules of §22.1 are enforced here, on write.

The journal chain is delegated to `sas.journal.chaine` — one implementation, not
two.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import datetime, timedelta

from sas.identifiants import maintenant
from sas.journal.chaine import JournalChaine
from sas.store.integrite import AccesInterdit, IntegriteRefusee
from sas.types import (
    Acces,
    Agent,
    Attestation,
    Campagne,
    Composition,
    ContexteTenant,
    Derive,
    Ecart,
    Editeur,
    EntreeJournal,
    Enveloppe,
    Manifeste,
    Nature,
    Session,
    StatutAgent,
    StatutManifeste,
    Tenant,
    Tentative,
)

Decideur = Callable[[Tentative], Nature]


class DepotLocal:
    """Everything the product persists, in memory, for one tenant."""

    def __init__(self, tenant: Tenant) -> None:
        self._tenant = tenant
        self._editeurs: dict[str, Editeur] = {}
        self._agents: dict[str, Agent] = {}
        self._manifestes: dict[str, dict[int, Manifeste]] = {}
        self._campagnes: dict[str, Campagne] = {}
        self._sessions: dict[str, Session] = {}
        self._journal = JournalChaine()
        self._tentatives: dict[str, Tentative] = {}
        self._compositions: dict[str, Composition] = {}
        self._ecarts: dict[str, Ecart] = {}
        self._enveloppes: dict[str, Enveloppe] = {}
        self._derives: dict[str, Derive] = {}
        self._attestations: dict[str, Attestation] = {}
        self._acces: list[Acces] = []

    @property
    def tenant_id(self) -> str:
        return self._tenant.id

    # -- registry ---------------------------------------------------------- #
    def enregistrer_tenant(self, tenant: Tenant) -> None:
        if tenant.id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, tenant.id)
        self._tenant = tenant

    def enregistrer_editeur(self, editeur: Editeur) -> None:
        self._editeurs[editeur.id] = editeur

    def enregistrer_agent(self, agent: Agent) -> None:
        if agent.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, agent.tenant_id)
        self._agents[agent.id] = agent

    def agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def agents(self) -> Sequence[Agent]:
        return tuple(self._agents.values())

    def editeur(self, editeur_id: str) -> Editeur | None:
        return self._editeurs.get(editeur_id)

    def editeurs(self) -> Sequence[Editeur]:
        return tuple(self._editeurs.values())

    def tenant(self, tenant_id: str) -> Tenant | None:
        return self._tenant if tenant_id == self._tenant.id else None

    # -- manifests --------------------------------------------------------- #
    def enregistrer_manifeste(self, manifeste: Manifeste) -> None:
        versions = self._manifestes.setdefault(manifeste.agent_id, {})
        if manifeste.version in versions and versions[manifeste.version].statut is StatutManifeste.REMPLACE:
            raise IntegriteRefusee("une version remplacée ne se réécrit pas")
        versions[manifeste.version] = manifeste

    def manifeste(self, manifeste_id: str, version: int | None = None) -> Manifeste | None:
        versions = self._manifestes.get(manifeste_id, {})
        if version is None:
            return self.manifeste_courant(manifeste_id)
        return versions.get(version)

    def manifeste_courant(self, agent_id: str) -> Manifeste | None:
        versions = self._manifestes.get(agent_id, {})
        actifs = [v for v, m in versions.items() if m.statut is not StatutManifeste.REMPLACE]
        return versions[max(actifs)] if actifs else (versions[max(versions)] if versions else None)

    def versions_manifeste(self, agent_id: str) -> Sequence[int]:
        return tuple(sorted(self._manifestes.get(agent_id, {})))

    def remplacer_manifeste(self, agent_id: str) -> None:
        """R3 — the previous versions stop being in force, which invalidates the
        attestation that rested on them."""
        versions = self._manifestes.get(agent_id, {})
        if not versions:
            return
        derniere = max(versions)
        for numero, manifeste in versions.items():
            if numero < derniere:
                versions[numero] = replace(manifeste, statut=StatutManifeste.REMPLACE)

    # -- campaigns and sessions -------------------------------------------- #
    def enregistrer_campagne(self, campagne: Campagne) -> None:
        if campagne.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, campagne.tenant_id)
        self._campagnes[campagne.id] = campagne

    def campagne(self, campagne_id: str) -> Campagne | None:
        return self._campagnes.get(campagne_id)

    def campagnes(self, agent_id: str | None = None) -> Sequence[Campagne]:
        toutes = tuple(self._campagnes.values())
        if agent_id is None:
            return toutes
        return tuple(c for c in toutes if c.agent_id == agent_id)

    def enregistrer_session(self, session: Session) -> None:
        """§22.1 rule 1 — no session without a valid manifest at the right version."""
        if session.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, session.tenant_id)
        campagne = self._campagnes.get(session.campagne_id)
        if campagne is None:
            raise IntegriteRefusee(f"session orpheline : campagne {session.campagne_id} inconnue")
        manifeste = self._manifestes.get(campagne.agent_id, {}).get(campagne.manifeste_version)
        if manifeste is None or manifeste.statut is not StatutManifeste.VALIDE:
            raise IntegriteRefusee("aucune session sans manifeste signé et validé pour la version courante")
        self._sessions[session.id] = session

    def session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def sessions(self, campagne_id: str) -> Sequence[Session]:
        return tuple(
            sorted(
                (s for s in self._sessions.values() if s.campagne_id == campagne_id),
                key=lambda s: (s.scenario_id, s.numero_rejeu, s.id),
            )
        )

    # -- journal ----------------------------------------------------------- #
    def ajouter_entree(self, entree: EntreeJournal) -> EntreeJournal:
        if entree.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, entree.tenant_id)
        return self._journal.ajouter(entree)

    def entrees(self, campagne_id: str) -> Sequence[EntreeJournal]:
        return tuple(e for e in self._journal.entrees() if e.campagne_id == campagne_id)

    def entrees_session(self, session_id: str) -> Sequence[EntreeJournal]:
        return self._journal.entrees(session_id)

    @property
    def journal(self) -> JournalChaine:
        return self._journal

    # -- access log (§7) --------------------------------------------------- #
    def enregistrer_acces(self, acces: Acces) -> None:
        """Append one access record. Append-only: nothing removes a row here,
        only the retention purge does (ENF-12)."""
        if acces.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, acces.tenant_id)
        self._acces.append(acces)

    def acces(self) -> Sequence[Acces]:
        return tuple(self._acces)

    # -- measurements ------------------------------------------------------ #
    def enregistrer_tentative(self, tentative: Tentative) -> None:
        if tentative.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, tentative.tenant_id)
        if not isinstance(tentative.nature_retenue, Nature):
            raise IntegriteRefusee("la nature retenue doit être calculée, pas recopiée")
        self._tentatives[tentative.id] = tentative

    def recalculer_nature(self, tentative: Tentative, decideur: Decideur) -> Tentative:
        """§22.1 rule 3 — the retained nature is always recomputed by code."""
        return replace(tentative, nature_retenue=decideur(tentative))

    def tentatives(self, campagne_id: str) -> Sequence[Tentative]:
        return tuple(t for t in self._tentatives.values() if t.campagne_id == campagne_id)

    def tentative(self, tentative_id: str) -> Tentative | None:
        return self._tentatives.get(tentative_id)

    def enregistrer_composition(self, composition: Composition) -> None:
        self._compositions[composition.id] = composition

    def compositions(self, campagne_id: str) -> Sequence[Composition]:
        return tuple(c for c in self._compositions.values() if c.campagne_id == campagne_id)

    def enregistrer_ecart(self, ecart: Ecart) -> None:
        self._ecarts[ecart.id] = ecart

    def ecarts(self, campagne_id: str) -> Sequence[Ecart]:
        return tuple(e for e in self._ecarts.values() if e.campagne_id == campagne_id)

    def enregistrer_enveloppe(self, enveloppe: Enveloppe) -> None:
        if enveloppe.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, enveloppe.tenant_id)
        self._enveloppes[enveloppe.id] = enveloppe

    def enveloppes(self, agent_id: str) -> Sequence[Enveloppe]:
        return tuple(
            sorted((e for e in self._enveloppes.values() if e.agent_id == agent_id), key=lambda e: e.date)
        )

    def enveloppe_reference(self, agent_id: str) -> Enveloppe | None:
        references = [e for e in self.enveloppes(agent_id) if e.reference]
        return references[-1] if references else None

    def enregistrer_derive(self, derive: Derive) -> None:
        if derive.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, derive.tenant_id)
        self._derives[derive.id] = derive

    def derives(self, agent_id: str | None = None) -> Sequence[Derive]:
        tous = tuple(self._derives.values())
        return tous if agent_id is None else tuple(d for d in tous if d.agent_id == agent_id)

    # -- deliverables ------------------------------------------------------ #
    def enregistrer_attestation(self, attestation: Attestation) -> None:
        """§22.1 rule 4 — immutable; a correction is a new dated attestation."""
        if attestation.tenant_id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, attestation.tenant_id)
        existante = self._attestations.get(attestation.id)
        if existante is not None and existante != attestation:
            raise IntegriteRefusee(f"l'attestation {attestation.numero} existe déjà : elle ne se corrige pas")
        agent = self._agent_de_la_campagne(attestation.campagne_id)
        if agent is not None and agent.statut is StatutAgent.NON_MESURABLE:
            raise IntegriteRefusee("un agent non mesurable ne reçoit aucune attestation (ENF-17)")
        self._attestations[attestation.id] = attestation

    def attestation(self, attestation_id: str) -> Attestation | None:
        return self._attestations.get(attestation_id)

    def attestations(self, campagne_id: str | None = None) -> Sequence[Attestation]:
        toutes = tuple(sorted(self._attestations.values(), key=lambda a: a.date))
        return toutes if campagne_id is None else tuple(a for a in toutes if a.campagne_id == campagne_id)

    def _agent_de_la_campagne(self, campagne_id: str) -> Agent | None:
        campagne = self._campagnes.get(campagne_id)
        return self._agents.get(campagne.agent_id) if campagne else None

    # -- housekeeping ------------------------------------------------------ #
    def purger(self, jours: int) -> int:
        """ENF-12 — the retention purge is effective and provable.

        `purge.purger_attestee()` wraps this call and produces the signed proof:
        what was removed, when, by whom, and the chain root before and after.
        """
        limite_effective = min(jours, self._tenant.retention_jours)
        seuil = maintenant() - timedelta(days=limite_effective)
        avant = len(self._journal)
        self._journal.purger_avant(seuil)
        self._sessions = {k: v for k, v in self._sessions.items() if v.debut >= seuil}
        self._acces = [a for a in self._acces if a.horodatage >= seuil]
        return avant - len(self._journal)

    def entrees_expirees(self, seuil: datetime) -> tuple[EntreeJournal, ...]:
        """The entries a purge at `seuil` would remove.

        Used by the purge attestation to name what it removed — identifiers and
        fingerprints, never the content.
        """
        return tuple(e for e in self._journal.entrees() if e.horodatage < seuil)

    def acces_expires(self, seuil: datetime) -> tuple[Acces, ...]:
        """The access records a purge at `seuil` would remove — named by the
        purge attestation by identifier and fingerprint, never by content."""
        return tuple(a for a in self._acces if a.horodatage < seuil)

    def cout_cumule(self) -> dict[str, float]:
        """EF-52 — measured cost per campaign, plus the total."""
        par_campagne = {c.id: float(c.cout_mesure.total) for c in self._campagnes.values()}
        return {**par_campagne, "total": round(sum(par_campagne.values()), 2)}

    def compter(self) -> dict[str, int]:
        """A debug/registry helper: how much this tenant holds."""
        return {
            "agents": len(self._agents),
            "manifestes": sum(len(v) for v in self._manifestes.values()),
            "campagnes": len(self._campagnes),
            "sessions": len(self._sessions),
            "journal": len(self._journal),
            "tentatives": len(self._tentatives),
            "attestations": len(self._attestations),
            "acces": len(self._acces),
        }


def verifier_acces(depot: DepotLocal, contexte: ContexteTenant) -> None:
    """EF-51 — the tenant comes from the token, never from a parameter."""
    if contexte.tenant_id != depot.tenant_id:
        raise AccesInterdit(depot.tenant_id, contexte.tenant_id)
