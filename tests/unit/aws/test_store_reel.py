"""The DynamoDB backend, tested against the **real** deployed stack.

These tests are marked `aws`: they never run on a pull request, they need the
account and the `donnees` stack. That is deliberate — spec §34 point 1 to 4 are
"test it, not read it", and until now the whole repository could say "the
backend exists, it has never been executed" (`docs/ECHECS.md` §3).

What they prove, against real tables:

* the stack is deployed, and its outputs name the tables the adapter uses;
* a write is readable, and the tenant scoping is structural, not a filter;
* the journal's chain survives the round trip to DynamoDB and back;
* the retention purge is effective on the real rows;
* an attestation cannot be corrected in place;
* the access log lands in its own real table;
* one real campaign, run through the real engine, lands in the real tables with
  its journal, its findings and its attestation.

They **skip** when the stack or the credentials are absent: a missing account
is not a green test, and it is not a red one either — it is "not run here".
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from sas.modele.base import Decision, Mode, Verdict
from sas.types import (
    Acces,
    Agent,
    Attestation,
    BorneStatistique,
    ContexteTenant,
    EntreeJournal,
    LigneBorne,
)

pytestmark = pytest.mark.aws

TENANT = "tenant-test-" + uuid.uuid4().hex[:8]
CLE = "cle-de-test-jamais-en-production"


def _depot_reel() -> Any:
    """Open the deployed store, or skip with the reason."""
    from sas.store.dynamodb import ErreurStoreAbsent, ouvrir

    try:
        return ouvrir(TENANT)
    except ErreurStoreAbsent as exc:
        pytest.skip(str(exc))


@pytest.fixture(scope="module")
def depot() -> Iterator[Any]:
    store = _depot_reel()
    yield store
    store.nettoyer()


def _agent(nom: str = "AgentTest", tenant_id: str = TENANT) -> Agent:
    return Agent(
        id=f"agent-{uuid.uuid4().hex[:8]}",
        tenant_id=tenant_id,
        editeur_id="ed-test",
        nom=nom,
        version_courante="1.0.0",
        empreinte="sha256:" + "0" * 64,
    )


def _entree(session_id: str, rang: int, horodatage: datetime | None = None) -> EntreeJournal:
    return EntreeJournal(
        id=f"appel-{session_id}-{rang}",
        tenant_id=TENANT,
        session_id=session_id,
        campagne_id="camp-test",
        agent_id="agent-test",
        agent_version="1.0.0",
        scenario_id="S1",
        numero_rejeu=rang,
        parent_id=None,
        outil="lire_ticket",
        parametres={"ticket": f"T-{rang:04d}"},
        decision=Decision.AUTORISE,
        regle_appliquee="perimetre.manifeste",
        resultat={"ok": True},
        horodatage=horodatage or datetime.now(UTC) + timedelta(seconds=rang),
        latence_ms=12.5,
        jetons=40,
    )


def _attestation() -> Attestation:
    instant = datetime.now(UTC)
    return Attestation(
        id=f"att-test-{uuid.uuid4().hex[:8]}",
        numero="SAS-ATT-TEST-0001",
        campagne_id="camp-test",
        tenant_id=TENANT,
        agent_nom="AgentTest",
        agent_version="1.0.0",
        editeur="Editeur Test",
        empreinte_paquet="sha256:c4d9",
        modele_declare="modele-test",
        mode=Mode.OMBRE,
        manifeste_version=1,
        scenarios=2,
        n_rejeux=2,
        sessions=4,
        periode_debut=instant,
        periode_fin=instant,
        resultat=Verdict.HOMOLOGUE,
        decouvertes={},
        permissions_mortes=0,
        compositions=0,
        conditions=(),
        borne=BorneStatistique(
            n_rejeux=2,
            lignes=(LigneBorne(probabilite=0.5, confiance=0.75),),
            rejeux_independants=True,
        ),
        empreinte_journal="sha256:aaaa",
        entrees_journal=10,
        ombre_detruite_le=instant,
        valide_jusquau=instant + timedelta(days=90),
        signataire="DPO",
        date=instant,
    )


# --------------------------------------------------------------------------- #
# The stack itself
# --------------------------------------------------------------------------- #


def test_les_tables_deployees_sont_celles_du_ddl(depot: Any) -> None:
    """ENF-15 — the infrastructure and the code cannot drift: the adapter is
    built from the stack's own outputs, and those are the DDL's tables."""
    from sas.store import ddl

    assert set(depot.tables) == set(ddl.TABLES)


def test_le_bucket_de_preuves_existe_pour_de_vrai(depot: Any) -> None:
    """The evidence bucket is not a name in a template: it answers."""
    import boto3
    import botocore.exceptions

    nom = depot.seau_preuves
    assert nom
    try:
        boto3.client("s3", region_name="eu-west-3").head_bucket(Bucket=nom)
    except botocore.exceptions.ClientError as exc:
        pytest.fail(f"le seau de preuves répond {exc.response['Error']['Code']} : {nom}")


# --------------------------------------------------------------------------- #
# Writes, reads, isolation
# --------------------------------------------------------------------------- #


def test_un_agent_ecrit_se_lit_depuis_dynamodb(depot: Any) -> None:
    agent = _agent()
    depot.enregistrer_agent(agent)
    relu = depot.agent(agent.id)
    assert relu is not None
    assert relu.nom == agent.nom
    assert relu.empreinte == agent.empreinte
    assert agent in depot.agents()


def test_le_depot_refuse_un_agent_d_un_autre_tenant(depot: Any) -> None:
    """EF-51 — isolation is structural on the real store, not a filter."""
    from sas.store.integrite import AccesInterdit

    with pytest.raises(AccesInterdit):
        depot.enregistrer_agent(_agent("Intrus", tenant_id="tenant-autre"))


def test_une_attestation_ne_se_corrige_pas_en_place(depot: Any) -> None:
    """§22.1 rule 4 — immutability, on the real table.

    Immutability is about the **content**: re-writing the same attestation is
    idempotent (a replayed campaign must not crash on its own evidence), while
    writing a different one under the same identifier is refused.
    """
    from dataclasses import replace

    from sas.store.integrite import IntegriteRefusee

    attestation = _attestation()
    depot.enregistrer_attestation(attestation)
    depot.enregistrer_attestation(attestation)  # same content: accepted
    with pytest.raises(IntegriteRefusee):
        depot.enregistrer_attestation(replace(attestation, resultat=Verdict.REFUSE))
    relu = depot.attestation(attestation.id)
    assert relu is not None
    assert relu.resultat is attestation.resultat
    assert relu.numero == attestation.numero


# --------------------------------------------------------------------------- #
# The journal: the evidence itself
# --------------------------------------------------------------------------- #


def test_la_chaine_du_journal_tient_le_aller_retour(depot: Any) -> None:
    """R9 — the chain is what the evidence rests on: it must survive DynamoDB.

    The entries are written one by one, read back from the table, and the chain
    is walked again. A broken chain here would mean the store cannot be trusted
    as evidence, whatever the reports say.
    """
    session = f"sess-{uuid.uuid4().hex[:8]}"
    ecrites = [depot.ajouter_entree(_entree(session, rang)) for rang in range(3)]
    lues = list(depot.entrees_session(session))
    assert len(lues) == 3
    assert [e.id for e in lues] == [e.id for e in ecrites]
    assert lues[0].empreinte_prec == ""
    assert lues[1].empreinte_prec == lues[0].empreinte
    assert lues[2].empreinte_prec == lues[1].empreinte
    for entree in lues:
        assert entree.empreinte.startswith("sha256:")


def test_le_ttl_porte_la_retention_de_chaque_entree(depot: Any) -> None:
    """ENF-12 — the row carries its own expiry, so DynamoDB can delete it."""
    session = f"sess-{uuid.uuid4().hex[:8]}"
    entree = depot.ajouter_entree(_entree(session, 0))
    items = [item for item in depot._items("journal") if item["id"].endswith(entree.id)]
    assert items
    attendu = int(entree.horodatage.timestamp()) + depot.retention_jours * 86400
    assert items[0]["expire_le"] == attendu


def test_la_purge_de_retention_emporte_les_vraies_lignes(depot: Any) -> None:
    """The purge is effective on real rows, not only in the in-memory mirror."""
    from dataclasses import replace

    from sas.store.purge import purger_attestee

    vieille = f"sess-{uuid.uuid4().hex[:8]}"
    recente = f"sess-{uuid.uuid4().hex[:8]}"
    depot.ajouter_entree(replace(_entree(vieille, 0), horodatage=datetime.now(UTC) - timedelta(days=400)))
    depot.ajouter_entree(_entree(recente, 0))
    avant = len(depot._scan("journal"))
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert attestation.nombre_purge >= 1
    assert len(depot._scan("journal")) < avant
    assert depot.entrees_session(vieille) == ()
    assert len(depot.entrees_session(recente)) == 1


# --------------------------------------------------------------------------- #
# The access log, in the real table
# --------------------------------------------------------------------------- #


def test_le_depot_dynamodb_satisfait_le_port_gele(depot: Any) -> None:
    """The port of lot 0 is the contract: the real backend must satisfy it,
    method for method — otherwise the two stores are not interchangeable."""
    from sas.store.base import Depot

    assert isinstance(depot, Depot)


def test_le_journal_des_acces_est_ecrit_dans_la_vraie_table(depot: Any) -> None:
    contexte = ContexteTenant(tenant_id=TENANT, role="analyste_msp", acteur="Analyste")
    depot.enregistrer_acces(
        Acces(
            horodatage=datetime.now(UTC),
            acteur=contexte.acteur,
            role=contexte.role,
            tenant_id=contexte.tenant_id,
            ressource="/attestations/att-1",
            action="lire",
        )
    )
    acces = list(depot.acces())
    assert acces
    assert acces[-1].ressource == "/attestations/att-1"
    assert acces[-1].id.startswith("acces-")


# --------------------------------------------------------------------------- #
# One real campaign, end to end
# --------------------------------------------------------------------------- #


def test_une_campagne_reelle_ecrit_dans_les_vraies_tables(depot: Any) -> None:
    """The demo, against DynamoDB: the engine runs, the store holds the evidence.

    This is the test that answers `docs/ECHECS.md` §3 — « nothing runs on AWS ».
    One guest, two replays, two scenarios: the campaign, its sessions, its
    journal and its attestation are written to the real tables and read back.
    """
    from sas.cli_partage import charger_contexte, invite, lancer
    from sas.store.persistance import persister

    contexte = charger_contexte(("S1", "S4"))
    dossier = lancer(
        agent=invite("demo-conforme"),
        contexte=contexte,
        rejeux=2,
        graine=7,
        tenant_id=TENANT,
        depot=depot,
    )
    ecrits = persister(depot, dossier)
    campagne = dossier.campagne.campagne
    assert depot.campagne(campagne.id) is not None
    assert len(depot.sessions(campagne.id)) == len(dossier.campagne.sessions)
    assert ecrits["journal"] >= 1
    assert ecrits["attestations"] == 1
    assert len(depot._scan("journal")) >= 1
    etat = depot.journal.verifier()
    assert etat.integre, f"chaîne rompue à {etat.premiere_rupture}"
    assert dossier.attestation is not None
    relu = depot.attestation(dossier.attestation.id)
    assert relu is not None
    assert relu.numero == dossier.attestation.numero
    assert relu.empreinte_journal == dossier.attestation.empreinte_journal
