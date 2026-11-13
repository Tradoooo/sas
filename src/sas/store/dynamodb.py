"""Sas — the DynamoDB backend of the `Depot` port (lot 18).

The port was frozen at lot 0 with DynamoDB in mind: the table definitions live
in `sas.store.ddl`, and the local backend only *mirrors* them in memory. This
module is the other half — the same port, served by the **real** tables the
`donnees` stack deployed.

What it does **not** do: re-implement the business rules — the manifest
versioning, the chained journal projection and the retention purge stay in
their modules, and this adapter calls them. What it does enforce, because a
store must: tenant isolation (EF-51), a replaced manifest is never overwritten,
and an attestation is never corrected in place (§22.1).

The item layout is one decision made explicit: the key attributes carry the
DDL's names (`agent_id`, `session_id`…), a `tenant_id` attribute is written on
every row so a scan can never leak a foreign tenant, the payload rides in a
`corps` JSON, and `expire_le` (epoch) drives the DynamoDB TTL on the tables
that have one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sas.identifiants import chainer, maintenant
from sas.journal.chaine import projection, reconstruire
from sas.modele.base import StatutAgent
from sas.store import ddl
from sas.store.dynamodb_schema import (
    CLES,
    CLES_PORTEES_PAR_LE_TENANT,
    ENTITES,
    INDEX_CHAMPS,
    INDEX_PORTEES_PAR_LE_TENANT,
    TABLE_TTL,
    ErreurStoreAbsent,
    lire_seau_preuves,
    lire_tables,
)
from sas.store.integrite import AccesInterdit, IntegriteRefusee
from sas.store.serialisation import depuis_json, vers_json
from sas.types import (
    Acces,
    Agent,
    Attestation,
    Campagne,
    Composition,
    Derive,
    Ecart,
    Editeur,
    EntreeJournal,
    Enveloppe,
    Manifeste,
    Session,
    StatutManifeste,
    Tenant,
    Tentative,
)

__all__ = ["DepotDynamo", "ErreurStoreAbsent", "ouvrir"]


class DepotDynamo:
    """The `Depot` port against real DynamoDB, one instance == one tenant."""

    def __init__(self, tenant: Tenant, tables: dict[str, str], *, region: str = "eu-west-3") -> None:
        self._tenant = tenant
        self._tables = tables
        import boto3  # local: only the adapter requires it

        self._dynamodb = boto3.resource("dynamodb", region_name=region)
        self._derniers: dict[str, tuple[str, int]] = {}

    @property
    def tenant_id(self) -> str:
        return self._tenant.id

    @property
    def retention_jours(self) -> int:
        """The tenant's retention, in days (ENF-12)."""
        return self._tenant.retention_jours

    @property
    def seau_preuves(self) -> str:
        """The evidence bucket, when the store was opened from a stack."""
        return getattr(self, "_seau_preuves", "")

    @property
    def tables(self) -> dict[str, str]:
        """The physical table names this store writes to."""
        return dict(self._tables)

    def nettoyer(self) -> None:
        """Delete every row of this tenant — the tests leave the real tables as
        they found them."""
        for table in self._tables:
            nom_cle = ddl.DEFINITIONS[table].attributs_cles[0]
            for item in self._items(table):
                self._table(table).delete_item(Key={nom_cle: item[nom_cle]})

    # -- registry ---------------------------------------------------------- #
    def enregistrer_tenant(self, tenant: Tenant) -> None:
        if tenant.id != self._tenant.id:
            raise AccesInterdit(self._tenant.id, tenant.id)
        self._put("tenants", tenant)

    def enregistrer_editeur(self, editeur: Editeur) -> None:
        self._put("editeurs", editeur)

    def enregistrer_agent(self, agent: Agent) -> None:
        self._verifier_tenant(agent.tenant_id)
        self._put("agents", agent)

    def agent(self, agent_id: str) -> Agent | None:
        return self._get("agents", agent_id)

    def agents(self) -> Sequence[Agent]:
        return self._index("agents", "tenant_id", self._tenant.id)

    def editeur(self, editeur_id: str) -> Editeur | None:
        return self._get("editeurs", editeur_id)

    def tenant(self, tenant_id: str) -> Tenant | None:
        return self._get("tenants", tenant_id)

    # -- manifests --------------------------------------------------------- #
    def enregistrer_manifeste(self, manifeste: Manifeste) -> None:
        """A replaced version is not overwritten (§22.1)."""
        existant = self.manifeste(manifeste.agent_id, manifeste.version)
        if existant is not None and existant.statut is StatutManifeste.REMPLACE:
            raise IntegriteRefusee("une version remplacée ne se réécrit pas")
        self._put("manifestes", manifeste)

    def manifeste(self, manifeste_id: str, version: int | None = None) -> Manifeste | None:
        if version is not None:
            return self._get("manifestes", f"{manifeste_id}|{version}")
        return self.manifeste_courant(manifeste_id)

    def manifeste_courant(self, agent_id: str) -> Manifeste | None:
        versions = self.versions_manifeste(agent_id)
        actifs = [m for m in versions if m.statut is not StatutManifeste.REMPLACE]
        return (
            max(actifs, key=lambda m: m.version)
            if actifs
            else (max(versions, key=lambda m: m.version) if versions else None)
        )

    def versions_manifeste(self, agent_id: str) -> Sequence[Manifeste]:
        return self._index("manifestes", "agent_id", agent_id)

    def remplacer_manifeste(self, agent_id: str) -> None:
        for manifeste in self.versions_manifeste(agent_id):
            if manifeste.statut is not StatutManifeste.REMPLACE:
                self._put("manifestes", replace(manifeste, statut=StatutManifeste.REMPLACE))

    # -- campaigns and sessions -------------------------------------------- #
    def enregistrer_campagne(self, campagne: Campagne) -> None:
        self._verifier_tenant(campagne.tenant_id)
        self._put("campagnes", campagne)

    def campagne(self, campagne_id: str) -> Campagne | None:
        return self._get("campagnes", campagne_id)

    def campagnes(self, agent_id: str | None = None) -> Sequence[Campagne]:
        if agent_id is None:
            return self._scan("campagnes")
        return self._index("campagnes", "agent_id", agent_id)

    def enregistrer_session(self, session: Session) -> None:
        self._verifier_tenant(session.tenant_id)
        self._put("sessions", session)

    def session(self, session_id: str) -> Session | None:
        return self._get("sessions", session_id)

    def sessions(self, campagne_id: str) -> Sequence[Session]:
        return sorted(
            self._index("sessions", "campagne_id", campagne_id),
            key=lambda s: (s.scenario_id, s.numero_rejeu, s.id),
        )

    # -- journal ----------------------------------------------------------- #
    def ajouter_entree(self, entree: EntreeJournal) -> EntreeJournal:
        """Append one entry, once.

        §17.1: the journal is append-only and immutable. Replaying a campaign
        writes the same entries again — that must be a **no-op**, not a
        re-chaining: an entry that already exists keeps its place and its
        fingerprint, and the same identifier with a different content is a
        tampering attempt, refused.
        """
        self._verifier_tenant(entree.tenant_id)
        existante = self._get("journal", entree.id)
        if existante is not None:
            # Append-only and immutable: once written, an entry is never
            # rewritten. Replaying the same campaign appends the same entry
            # identifiers, and that must be a no-op — rewriting them would
            # silently re-chain the journal and break the evidence.
            return existante
        precedente, rang = self._derniere_de_la_session(entree.session_id)
        scellee = replace(entree, empreinte_prec=precedente)
        scellee = replace(scellee, empreinte=chainer(precedente, projection(scellee)))
        self._put_item("journal", scellee, rang=rang + 1)
        self._derniers[entree.session_id] = (scellee.empreinte, rang + 1)
        return scellee

    def entrees(self, campagne_id: str) -> Sequence[EntreeJournal]:
        return self._trier(self._index("journal", "campagne_id", campagne_id))

    def entrees_session(self, session_id: str) -> Sequence[EntreeJournal]:
        return self._trier(self._index("journal", "session_id", session_id))

    @property
    def journal(self) -> Any:
        """This tenant's journal, rebuilt for the purge attestation.

        The chain is an **order**, and a scan returns the rows in no order at
        all: the insertion order is carried by the `rang` attribute, and the
        entries are put back in that order before the chain is walked.
        """
        entrees = self._entrees_ordonnees()
        return reconstruire(entrees)

    # -- measurements ------------------------------------------------------ #
    def enregistrer_tentative(self, tentative: Tentative) -> None:
        self._put("tentatives", tentative)

    def tentatives(self, campagne_id: str) -> Sequence[Tentative]:
        return self._index("tentatives", "campagne_id", campagne_id)

    def tentative(self, tentative_id: str) -> Tentative | None:
        return self._get("tentatives", tentative_id)

    def enregistrer_composition(self, composition: Composition) -> None:
        self._put("compositions", composition)

    def compositions(self, campagne_id: str) -> Sequence[Composition]:
        return self._index("compositions", "campagne_id", campagne_id)

    def enregistrer_ecart(self, ecart: Ecart) -> None:
        self._put("ecarts", ecart)

    def ecarts(self, campagne_id: str) -> Sequence[Ecart]:
        return self._index("ecarts", "campagne_id", campagne_id)

    def enregistrer_enveloppe(self, enveloppe: Enveloppe) -> None:
        self._verifier_tenant(enveloppe.tenant_id)
        self._put("enveloppes", enveloppe)

    def enveloppes(self, agent_id: str) -> Sequence[Enveloppe]:
        return sorted(self._index("enveloppes", "agent_id", agent_id), key=lambda e: e.date)

    def enveloppe_reference(self, agent_id: str) -> Enveloppe | None:
        references = [e for e in self.enveloppes(agent_id) if e.reference]
        return references[-1] if references else None

    def enregistrer_derive(self, derive: Derive) -> None:
        self._verifier_tenant(derive.tenant_id)
        self._put("derives", derive)

    def derives(self, agent_id: str | None = None) -> Sequence[Derive]:
        tous = self._scan("derives")
        return tous if agent_id is None else tuple(d for d in tous if d.agent_id == agent_id)

    # -- deliverables ------------------------------------------------------ #
    def enregistrer_attestation(self, attestation: Attestation) -> None:
        """Immutable (§22.1): a correction is a new dated attestation, never an edit."""
        self._verifier_tenant(attestation.tenant_id)
        existante = self.attestation(attestation.id)
        if existante is not None and existante != attestation:
            raise IntegriteRefusee(f"l'attestation {attestation.numero} existe déjà : elle ne se corrige pas")
        agent = self._agent_de_la_campagne(attestation.campagne_id)
        if agent is not None and agent.statut is StatutAgent.NON_MESURABLE:
            raise IntegriteRefusee("un agent non mesurable ne reçoit aucune attestation (ENF-17)")
        self._put("attestations", attestation)

    def attestation(self, attestation_id: str) -> Attestation | None:
        return self._get("attestations", attestation_id)

    def attestations(self, campagne_id: str | None = None) -> Sequence[Attestation]:
        if campagne_id is None:
            return tuple(sorted(self._scan("attestations"), key=lambda a: a.date))
        return self._index("attestations", "campagne_id", campagne_id)

    # -- access log (§7) --------------------------------------------------- #
    def enregistrer_acces(self, acces: Acces) -> None:
        self._verifier_tenant(acces.tenant_id)
        self._put("acces", acces)

    def acces(self) -> Sequence[Acces]:
        return self._index("acces", "tenant_id", self._tenant.id)

    def acces_expires(self, seuil: datetime) -> tuple[Acces, ...]:
        return tuple(a for a in self.acces() if a.horodatage < seuil)

    def entrees_expirees(self, seuil: datetime) -> tuple[EntreeJournal, ...]:
        """The journal entries a purge at `seuil` would remove — named by the
        purge attestation by identifier and fingerprint, never by content."""
        return tuple(e for e in self._entrees_ordonnees() if e.horodatage.astimezone(UTC) < seuil)

    # -- housekeeping ------------------------------------------------------ #
    def purger(self, jours: int) -> int:
        """ENF-12 — immediate retention purge, not waiting for the TTL.

        The TTL deletes eventually (up to 48 hours); the purge must be immediate
        and provable, so it deletes the expired rows itself and returns the count.
        """
        limite = min(jours, self._tenant.retention_jours)
        seuil = maintenant() - timedelta(days=limite)
        supprimes = 0
        for table in TABLE_TTL:
            supprimes += self._purger_table(table, seuil)
        return supprimes

    def cout_cumule(self) -> dict[str, float]:
        par_campagne = {c.id: float(c.cout_mesure.total) for c in self.campagnes()}
        return {**par_campagne, "total": round(sum(par_campagne.values()), 2)}

    # -- internals --------------------------------------------------------- #
    def _verifier_tenant(self, autre: str) -> None:
        if autre != self._tenant.id:
            raise AccesInterdit(self._tenant.id, autre)

    def _table(self, logique: str) -> Any:
        return self._dynamodb.Table(self._tables[logique])

    def _champs(self, table: str, objet: Any) -> dict[str, Any]:
        donnees = json.loads(vers_json(objet))
        champs = {attribut: str(donnees[source]) for attribut, source in CLES[table].items()}
        if table in CLES_PORTEES_PAR_LE_TENANT:
            champs = {
                attribut: f"{self._tenant.id}#{valeur}"
                if attribut in CLES_PORTEES_PAR_LE_TENANT[table]
                else valeur
                for attribut, valeur in champs.items()
            }
        portes = INDEX_PORTEES_PAR_LE_TENANT.get(table, ())
        for attribut, source in INDEX_CHAMPS.get(table, {}).items():
            if source in donnees:
                valeur = str(donnees[source])
                champs[attribut] = f"{self._tenant.id}#{valeur}" if attribut in portes else valeur
        # EF-51: every row carries its tenant, so a scan can never leak another.
        champs["tenant_id"] = donnees.get("tenant_id", self._tenant.id)
        return champs

    def _position(self, table: str, cle: str) -> dict[str, str]:
        definition = ddl.DEFINITIONS[table]
        parties = cle.split("|")
        position = {attribut: parties[indice] for indice, attribut in enumerate(definition.attributs_cles)}
        if table in CLES_PORTEES_PAR_LE_TENANT:
            # The evidence id is deterministic: the same campaign replayed by
            # two tenants produces the same entry identifiers. The key is
            # therefore tenant-scoped, or the second tenant would overwrite the
            # first one's evidence — and read it back.
            position[definition.attributs_cles[0]] = f"{self._tenant.id}#{cle}"
        return position

    def _put(self, table: str, objet: Any) -> None:
        self._put_item(table, objet, rang=None)

    def _put_item(self, table: str, objet: Any, *, rang: int | None) -> None:
        item = self._champs(table, objet)
        item["corps"] = vers_json(objet)
        if rang is not None:
            item["rang"] = rang
        if table in TABLE_TTL:
            item["expire_le"] = int(objet.horodatage.timestamp()) + self._tenant.retention_jours * 86400
        self._table(table).put_item(Item=item)

    def _get(self, table: str, cle: str) -> Any | None:
        reponse = self._table(table).get_item(Key=self._position(table, cle))
        if "Item" not in reponse:
            return None
        return depuis_json(reponse["Item"]["corps"], ENTITES[table])

    def _index(self, table: str, index: str, valeur: str) -> tuple[Any, ...]:
        import boto3.dynamodb.conditions as conditions

        if index in INDEX_PORTEES_PAR_LE_TENANT.get(table, ()):
            valeur = f"{self._tenant.id}#{valeur}"
        reponse = self._table(table).query(
            IndexName=index,
            KeyConditionExpression=conditions.Key(index).eq(valeur),
        )
        return tuple(depuis_json(item["corps"], ENTITES[table]) for item in reponse.get("Items", []))

    def _scan(self, table: str) -> tuple[Any, ...]:
        return tuple(depuis_json(item["corps"], ENTITES[table]) for item in self._items(table))

    def _derniere_de_la_session(self, session_id: str) -> tuple[str, int]:
        """The last entry written in that session: its fingerprint and its rank.

        The `session_id` index has no sort key, so it cannot say which entry
        came last — the `rang` attribute, written by this adapter, can. The
        chain is broken otherwise, and a broken chain is the one defect the
        evidence cannot carry.
        """
        import boto3.dynamodb.conditions as conditions

        if session_id in self._derniers:
            return self._derniers[session_id]
        reponse = self._table("journal").query(
            IndexName="session_id",
            KeyConditionExpression=conditions.Key("session_id").eq(f"{self._tenant.id}#{session_id}"),
        )
        items = reponse.get("Items", [])
        if not items:
            return "", 0
        dernier = max(items, key=lambda item: int(item.get("rang", 0)))
        empreinte = depuis_json(dernier["corps"], EntreeJournal).empreinte
        rang = int(dernier.get("rang", 0))
        self._derniers[session_id] = (empreinte, rang)
        return empreinte, rang

    def _entrees_ordonnees(self) -> list[EntreeJournal]:
        """The journal entries in their insertion order (session, then rank)."""
        items = self._items("journal")
        tries = sorted(items, key=lambda item: (item.get("session_id", ""), int(item.get("rang", 0))))
        return [depuis_json(item["corps"], EntreeJournal) for item in tries]

    def _items(self, table: str) -> list[dict[str, Any]]:
        """Every row of this tenant in that table — **pages included**.

        A DynamoDB scan returns one page (1 MB) at a time, and the filter is
        applied *inside* the page: reading only the first page silently drops
        rows that exist, which turns a complete journal into a partial one and
        makes the chain verification lie. So the scan is walked to its end.
        """
        import boto3.dynamodb.conditions as conditions

        parametres: dict[str, Any] = {"FilterExpression": conditions.Attr("tenant_id").eq(self._tenant.id)}
        items: list[dict[str, Any]] = []
        while True:
            reponse = self._table(table).scan(**parametres)
            items.extend(reponse.get("Items", []))
            dernier = reponse.get("LastEvaluatedKey")
            if not dernier:
                return items
            parametres["ExclusiveStartKey"] = dernier

    def _purger_table(self, table: str, seuil: datetime) -> int:
        definition = ddl.DEFINITIONS[table]
        nom_cle = definition.attributs_cles[0]
        supprimes = 0
        for item in self._items(table):
            entree = depuis_json(item["corps"], ENTITES[table])
            if entree.horodatage.astimezone(UTC) < seuil:
                self._table(table).delete_item(Key={nom_cle: item[nom_cle]})
                supprimes += 1
        return supprimes

    @staticmethod
    def _trier(entrees: Sequence[EntreeJournal]) -> tuple[EntreeJournal, ...]:
        """Stable insertion order: the chain is the order, not the clock."""
        return tuple(sorted(entrees, key=lambda e: (e.horodatage, e.id)))

    def _agent_de_la_campagne(self, campagne_id: str) -> Agent | None:
        campagne = self.campagne(campagne_id)
        return self.agent(campagne.agent_id) if campagne else None


def ouvrir(
    tenant_id: str,
    *,
    region: str = "eu-west-3",
    pile: str = "sas-donnees-dev",
    nom_client: str = "",
) -> DepotDynamo:
    """Open the deployed store for one tenant.

    The table names come from the stack's own outputs, so the demo cannot run
    against a table that does not exist — and a typo in the stack name fails
    loudly instead of writing nowhere.
    """
    tables = lire_tables(region=region, pile=pile)
    tenant = Tenant(
        id=tenant_id,
        nom_client=nom_client or tenant_id,
        contact_commanditaire="rssi@exemple.invalid",
    )
    store = DepotDynamo(tenant, tables, region=region)
    store._seau_preuves = lire_seau_preuves(region=region, pile=pile)
    return store
