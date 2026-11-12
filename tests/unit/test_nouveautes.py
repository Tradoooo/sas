"""Retention purge, audit export, manifest proposal, access log.

The four capabilities added on top of the engine: what was deleted and on whose
authority, what an auditor receives, how a manifest is drafted from an
observation, and who read what.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from sas.api.acces import ACTIONS, JournalAcces
from sas.audit import (
    MEMBRE_ATTESTATION,
    MEMBRE_JOURNAL,
    MEMBRE_RAPPORT,
    exporter,
    lire_membre,
    verifier,
)
from sas.manifeste.observation import observer, proposer, sorties_observées
from sas.store.purge import purger_attestee
from sas.store.purge import verifier as verifier_purge
from sas.types import ContexteTenant

CLE = "cle-de-test-jamais-en-production"
MAINTENANT = datetime(2026, 11, 28, 12, 0, tzinfo=UTC)


def _depot(age_jours: int = 200):
    """A store with one old entry and one recent one."""
    from sas.identifiants import maintenant
    from sas.store.local import DepotLocal
    from sas.types import Agent, EntreeJournal, Tenant

    depot = DepotLocal(Tenant(id="tenant-a", nom_client="A", contact_commanditaire="rssi-a@exemple.invalid"))
    agent = Agent(
        id="agent-1",
        tenant_id="tenant-a",
        editeur_id="ed-1",
        nom="AgentTicket",
        version_courante="3.4.1",
        empreinte="sha256:" + "0" * 64,
    )
    depot.enregistrer_agent(agent)
    for index, age in enumerate((age_jours, 1)):
        depot.ajouter_entree(
            EntreeJournal(
                id=f"appel-{index}",
                tenant_id="tenant-a",
                session_id="sess-1",
                campagne_id="camp-1",
                agent_id="agent-1",
                agent_version="3.4.1",
                scenario_id="S1",
                numero_rejeu=1,
                parent_id=None,
                outil="lire_ticket",
                parametres={"id": "T-0001"},
                decision="autorise",
                regle_appliquee="manifeste:autorise",
                resultat={"ok": True},
                horodatage=maintenant() - timedelta(days=age),
                latence_ms=3.0,
                jetons=4600,
                ressources=("client-tickets-ombre/entree",),
            )
        )
    return depot


# --------------------------------------------------------------------------- #
# Purge attestée (ENF-12)
# --------------------------------------------------------------------------- #


def test_la_purge_atteste_ce_qu_elle_a_supprime() -> None:
    """ENF-12 — rétention configurable et purge effective et prouvée.
    ENF-12 — rétention configurable et purge effective et prouvée.
    ENF-12 — rétention configurable et purge effective et prouvée.
    """
    depot = _depot(age_jours=200)
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert attestation.nombre_purge == 1
    assert len(depot.entrees("camp-1")) == 1
    assert attestation.signataire == "DPO"
    assert attestation.signature.startswith("hmac-sha256:")


def test_la_purge_atteste_ne_quote_jamais_le_contenu() -> None:
    """A purge record that quoted the data it deleted would leak the very thing
    it was supposed to remove."""
    depot = _depot(age_jours=200)
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    texte = str(attestation.resume())
    assert "T-0001" not in texte
    assert "lire_ticket" not in texte


def test_le_sceau_de_la_purge_se_verifie() -> None:
    depot = _depot(age_jours=200)
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    ok, motif = verifier_purge(attestation, CLE)
    assert ok, motif
    ko, _ = verifier_purge(attestation, "autre-cle")
    assert ko is False


def test_une_purge_sans_auteur_n_est_pas_une_purge_prouvee() -> None:
    with pytest.raises(ValueError):
        purger_attestee(_depot(), 90, signataire="  ", cle=CLE)
    with pytest.raises(ValueError):
        purger_attestee(_depot(), 90, signataire="DPO", cle="")


def test_la_racine_de_chaine_change_apres_la_purge() -> None:
    depot = _depot(age_jours=200)
    attestation = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert attestation.racine_avant != attestation.racine_apres


def test_la_purge_est_idempotente() -> None:
    depot = _depot(age_jours=200)
    purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    seconde = purger_attestee(depot, 90, signataire="DPO", cle=CLE)
    assert seconde.nombre_purge == 0


# --------------------------------------------------------------------------- #
# Export d'audit
# --------------------------------------------------------------------------- #


def test_l_archive_d_audit_contient_les_trois_documents() -> None:
    archive = exporter(
        journal='{"id":"a1"}\n{"id":"a2"}\n',
        attestation="ATTESTATION\n",
        rapport="# rapport\n",
        cle=CLE,
        horodatage=MAINTENANT,
    )
    assert lire_membre(archive, MEMBRE_JOURNAL).count("\n") == 2
    assert "ATTESTATION" in lire_membre(archive, MEMBRE_ATTESTATION)
    assert "rapport" in lire_membre(archive, MEMBRE_RAPPORT)
    assert archive.manifest["entrees_journal"] == 2


def test_l_archive_d_audit_se_verifie() -> None:
    archive = exporter(journal="{}\n", attestation="a", rapport="r", cle=CLE, horodatage=MAINTENANT)
    ok, motif = verifier(archive, CLE)
    assert ok, motif


def test_un_membre_altere_est_detecte() -> None:
    """The archive is gzip: the bytes cannot be patched in place, so the tamper
    is made where it matters — the manifest's fingerprint of a member that no
    longer matches its content."""
    from sas.audit import ArchiveAudit

    archive = exporter(journal="{}\n", attestation="a", rapport="r", cle=CLE, horodatage=MAINTENANT)
    manifeste = dict(archive.manifest)
    membres = dict(manifeste["membres"])
    membres[MEMBRE_RAPPORT] = "0" * 64
    manifeste["membres"] = membres
    modifie = ArchiveAudit(
        nom=archive.nom,
        contenu=archive.contenu,
        manifest=manifeste,
        signature=archive.signature,
        horodatage=archive.horodatage,
    )
    ok, motif = verifier(modifie, CLE)
    assert ok is False
    assert "altéré" in motif


def test_l_archive_d_audit_ne_pretend_pas_chiffrer() -> None:
    archive = exporter(journal="{}\n", attestation="a", rapport="r", cle=CLE, horodatage=MAINTENANT)
    resume = archive.resume()
    assert resume["chiffre"] is False
    assert "NON chiffrée" in archive.manifest["alerte"]


def test_une_archive_sans_cle_est_refusee() -> None:
    with pytest.raises(ValueError):
        exporter(journal="", attestation="", rapport="", cle="")


# --------------------------------------------------------------------------- #
# Manifeste proposé depuis une observation (lecture seule)
# --------------------------------------------------------------------------- #


def _journal_simple():
    """A tiny journal: two authorised calls, one refused one."""
    from sas.types import Decision, EntreeJournal

    entrees = []
    for index in range(3):
        entrees.append(
            EntreeJournal(
                id=f"appel-{index}",
                tenant_id="tenant-a",
                session_id="sess-1",
                campagne_id="camp-1",
                agent_id="agent-1",
                agent_version="3.4.1",
                scenario_id="S1",
                numero_rejeu=1,
                parent_id=None,
                outil="lire_ticket",
                parametres={},
                decision=Decision.AUTORISE if index < 2 else Decision.REFUSE,
                regle_appliquee="manifeste:autorise",
                resultat={},
                horodatage=MAINTENANT,
                latence_ms=1.0,
                jetons=100,
                ressources=("client-tickets-ombre/entree",),
            )
        )
    return entrees


def test_le_brouillon_propose_les_outils_observes() -> None:
    brouillon = proposer(observer(_journal_simple()))
    noms = {outil["nom"] for outil in brouillon["outils_demandes"]}
    assert "lire_ticket" in noms
    assert brouillon["signature"] is None
    assert brouillon["validation_client"] is None
    assert brouillon["_brouillon"]["marqueur"].startswith("BROUILLON")


def test_le_brouillon_ne_declare_aucune_sortie_non_observee() -> None:
    """A guess here would be a permission nobody granted."""
    brouillon = proposer(observer(_journal_simple()))
    assert brouillon["sorties_autorisees"] == []


def test_le_brouillon_justifie_par_un_compte_et_non_par_une_raison() -> None:
    brouillon = proposer(observer(_journal_simple()))
    justification = brouillon["outils_demandes"][0]["justification"]
    assert "observé" in justification
    assert "finalité reste à rédiger" in justification


def test_un_brouillon_est_refuse_par_le_validateur() -> None:
    """EF-03 — nothing runs without a signature, and a draft has none.

    The draft is refused even before the semantic stage: it carries the marker
    `_brouillon`, which is not part of the manifest format, so the loader
    rejects it outright. That is the strongest possible refusal.
    """
    import yaml

    from sas.manifeste.chargement import ErreurManifeste, charger_depuis_texte

    brouillon = proposer(observer(_journal_simple()))
    with pytest.raises(ErreurManifeste):
        charger_depuis_texte(yaml.safe_dump(brouillon, allow_unicode=True))


def test_les_destinations_tentees_sont_remises_a_l_editeur() -> None:
    observation = observer(_journal_simple())
    assert isinstance(sorties_observées(observation), tuple)


# --------------------------------------------------------------------------- #
# Journal des accès
# --------------------------------------------------------------------------- #


def test_le_journal_des_acces_enregistre_qui_a_lu_quoi() -> None:
    journal = JournalAcces()
    contexte = ContexteTenant(tenant_id="tenant-a", role="analyste_msp", acteur="Analyste")
    journal.enregistrer(contexte, "/attestations/att-1", "lire")
    journal.enregistrer(contexte, "/rapports/camp-1", "telecharger")
    assert len(journal) == 2
    assert journal.sur_ressource("/attestations/att-1")[0].acteur == "Analyste"
    assert journal.pour_tenant("tenant-a")[0].action == "lire"
    assert journal.pour_tenant("tenant-b") == ()


def test_le_journal_des_acces_refuse_une_action_inconnue() -> None:
    journal = JournalAcces()
    contexte = ContexteTenant(tenant_id="tenant-a", role="analyste_msp", acteur="Analyste")
    with pytest.raises(ValueError):
        journal.enregistrer(contexte, "/x", "supprimer-tout")


def test_les_actions_connues_sont_celles_du_journal() -> None:
    assert "lire" in ACTIONS
    assert "telecharger" in ACTIONS
