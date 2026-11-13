"""The access log, persisted in the tenant's store (idea 85, ENF-12).

The log started as an in-memory list: readable in the demo, gone at restart, and
untouched by the retention purge. These tests pin what the store version must
prove — the record reaches the tenant's depot, another tenant's record is
refused, and the same retention rule that purges the journal purges the log and
names what it removed in the sealed attestation.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from sas.api.acces import JournalAcces
from sas.identifiants import maintenant
from sas.store.integrite import AccesInterdit
from sas.store.local import DepotLocal
from sas.store.purge import purger_attestee
from sas.store.purge import verifier as verifier_purge
from sas.types import Acces, ContexteTenant, Tenant

CLE = "cle-de-test-jamais-en-production"
CONTEXTE = ContexteTenant(tenant_id="tenant-a", role="analyste_msp", acteur="Analyste")


def _depot(tenant_id: str = "tenant-a") -> DepotLocal:
    return DepotLocal(Tenant(id=tenant_id, nom_client="A", contact_commanditaire="rssi-a@exemple.invalid"))


def test_l_acces_est_ecrit_dans_le_depot_du_tenant() -> None:
    """What the portal journals is what the store holds, not a private copy."""
    depot = _depot()
    journal = JournalAcces(depot=depot)
    journal.enregistrer(CONTEXTE, "/attestations/att-1", "lire")
    journal.enregistrer(CONTEXTE, "/rapports/camp-1", "telecharger")
    assert len(depot.acces()) == 2
    assert [a.action for a in depot.acces()] == ["lire", "telecharger"]
    assert len(journal) == 2
    assert journal.sur_ressource("/attestations/att-1")[0].acteur == "Analyste"


def test_le_depot_est_la_source_quand_il_est_lie() -> None:
    """A restarted facade reads the store, not its own empty memory."""
    depot = _depot()
    JournalAcces(depot=depot).enregistrer(CONTEXTE, "/registre", "lire")
    relu = JournalAcces(depot=depot)
    assert len(relu) == 1
    assert relu.resume("tenant-a")[0]["ressource"] == "/registre"


def test_un_acces_d_un_autre_tenant_est_refuse() -> None:
    """EF-51 — isolation is structural: the depot only accepts its own tenant."""
    depot = _depot()
    intrus = Acces(
        horodatage=maintenant(),
        acteur="Autre",
        role="editeur",
        tenant_id="tenant-b",
        ressource="/registre",
        action="lire",
    )
    with pytest.raises(AccesInterdit):
        depot.enregistrer_acces(intrus)


def test_la_purge_de_retention_emporte_les_acces_expires() -> None:
    """ENF-12 — one retention rule for the journal and the access log."""
    depot = _depot()
    vieux = maintenant() - timedelta(days=200)
    journal = JournalAcces(depot=depot)
    journal.enregistrer(CONTEXTE, "/attestations/ancienne", "lire", horodatage=vieux)
    journal.enregistrer(CONTEXTE, "/attestations/recente", "lire")
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert [a.ressource for a in depot.acces()] == ["/attestations/recente"]
    assert attestation.nombre_total == 0  # no journal entry expired
    assert "acces" in attestation.tables


def test_la_purge_des_acces_est_attestee_et_ne_quote_pas_l_acteur() -> None:
    """The seal covers the access rows; the summary names identifiers and
    fingerprints, never who read what (the record itself is the secret)."""
    depot = _depot()
    journal = JournalAcces(depot=depot)
    journal.enregistrer(
        CONTEXTE, "/attestations/ancienne", "lire", horodatage=maintenant() - timedelta(days=200)
    )
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert attestation.nombre_purge == 1
    ok, motif = verifier_purge(attestation, CLE)
    assert ok, motif
    resume = str(attestation.resume())
    assert "Analyste" not in resume
    assert "/attestations/ancienne" not in resume


def test_l_identifiant_d_un_acces_est_deterministe() -> None:
    """The same record at the same instant is one row: a retry cannot forge a
    second identity, and the id is what the purge names."""
    instant = maintenant()
    premier = Acces(
        horodatage=instant,
        acteur="Analyste",
        role="analyste_msp",
        tenant_id="tenant-a",
        ressource="/registre",
        action="lire",
    )
    second = Acces(
        horodatage=instant,
        acteur="Analyste",
        role="analyste_msp",
        tenant_id="tenant-a",
        ressource="/registre",
        action="lire",
    )
    assert premier.id == second.id
    assert premier.id.startswith("acces-")
    autre = Acces(
        horodatage=instant + timedelta(seconds=1),
        acteur="Analyste",
        role="analyste_msp",
        tenant_id="tenant-a",
        ressource="/registre",
        action="lire",
    )
    assert autre.id != premier.id


def test_une_action_inconnue_est_refusee() -> None:
    with pytest.raises(ValueError):
        Acces(
            horodatage=maintenant(),
            acteur="Analyste",
            role="analyste_msp",
            tenant_id="tenant-a",
            ressource="/x",
            action="supprimer-tout",
        )
