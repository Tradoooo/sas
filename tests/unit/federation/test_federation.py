"""Envelope federation and version diff — including the privacy gate."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sas import federation
from sas.cli_partage import charger_contexte, invite, lancer
from sas.homologation import enveloppe
from sas.types import Verdict

DATE = datetime(2026, 11, 28, 10, 0, tzinfo=UTC)
SEL = "sel-de-federation-de-test"


def _dossier(agent: str, scenarios=("S1", "S4")):
    contexte = charger_contexte(scenarios)
    return lancer(agent=invite(agent), contexte=contexte, rejeux=2, graine=7)


def _partagee(agent: str, version: str = "3.4.1", scenarios=("S1", "S4")):
    dossier = _dossier(agent, scenarios)
    enveloppe_objet = enveloppe(
        dossier, agent_id="agentticket", tenant_id="tenant-demo", version=version, date=DATE
    )
    return federation.anonymiser(
        enveloppe_objet,
        agent_id="agentticket",
        editeur="Exemple Editeur SAS",
        verdict=dossier.decision.verdict,
        sel=SEL,
        refus=float(dossier.agregat.refus),
    )


# --------------------------------------------------------------------------- #
# Categories and pseudonyms
# --------------------------------------------------------------------------- #


def test_les_categories_sont_grossieres_et_stables() -> None:
    assert federation.categorie("s3://rh-ombre/grille-2026.csv") == "s3:lecture"
    assert federation.categorie("client-tickets-ombre/entree") == "s3:lecture"
    assert federation.categorie("kb-documentation-ombre") == "index:recherche"
    assert federation.categorie("dynamodb:suivi-ombre") == "dynamodb:ecriture"
    assert federation.categorie("https://collecte.exemple.invalid/ingest") == "http:sortie"
    assert federation.categorie("inconnu") == federation.CATEGORIE_DEFAUT


def test_le_pseudonyme_est_stable_et_depend_du_sel() -> None:
    premier = federation.pseudonymiser("agent-1", "Editeur", SEL)
    assert premier == federation.pseudonymiser("agent-1", "Editeur", SEL)
    assert premier != federation.pseudonymiser("agent-1", "Editeur", "autre-sel")
    assert premier != federation.pseudonymiser("agent-2", "Editeur", SEL)
    assert premier.startswith("fed-")


# --------------------------------------------------------------------------- #
# The privacy gate — the whole point of the module
# --------------------------------------------------------------------------- #


def test_aucun_nom_de_client_ne_sort_d_une_enveloppe_partagee() -> None:
    """§24.5 as an executable property, not a promise."""
    partagee = _partagee("demo-bavard")
    sensibles = [
        "client-tickets",
        "rh-ombre",
        "grille-2026",
        "kb-documentation-ombre",
        "dynamodb:suivi-ombre",
        "tenant-demo",
        "Exemple Editeur",
    ]
    assert federation.aucun_nom_client_ne_sort(partagee, sensibles)


def test_les_categories_remplacent_les_noms() -> None:
    partagee = _partagee("demo-curieux", scenarios=("S5", "S8"))
    assert partagee.categories, "il faut au moins une catégorie"
    for cle in partagee.categories:
        assert cle in {c for _, c in federation.CATEGORIES} | {federation.CATEGORIE_DEFAUT}


def test_l_empreinte_de_l_enveloppe_partagee_est_stable() -> None:
    assert _partagee("demo-conforme").empreinte == _partagee("demo-conforme").empreinte


def test_le_verdict_est_partage_mais_pas_les_decouvertes() -> None:
    partagee = _partagee("demo-curieux", scenarios=("S5", "S8"))
    assert partagee.verdict == Verdict.REFUSE.value
    assert not hasattr(partagee, "tentatives")
    assert not hasattr(partagee, "compositions")


# --------------------------------------------------------------------------- #
# The federated profile
# --------------------------------------------------------------------------- #


def test_profil_vide() -> None:
    profil = federation.profiler([])
    assert profil.participants == 0
    assert profil.frequence_outils == {}


def test_profil_sur_plusieurs_participants() -> None:
    enveloppes = [
        _partagee("demo-conforme"),
        _partagee("demo-bavard"),
        _partagee("demo-curieux", scenarios=("S5", "S8")),
    ]
    profil = federation.profiler(enveloppes)
    assert profil.participants == 3
    assert profil.rejeux_median == 2
    # `lire_ticket` is used by all three; `list_buckets` only by the chatty one.
    assert profil.frequence_outils["lire_ticket"] == 1.0
    assert profil.frequence_outils["list_buckets"] < 1.0


def test_rien_n_est_signale_en_dessous_de_trois_participants() -> None:
    """With two participants, "unusual" means nothing. Saying so is the point."""
    profil = federation.profiler([_partagee("demo-conforme"), _partagee("demo-bavard")])
    assert federation.atypiques(_partagee("demo-bavard"), profil) == ()


def test_un_comportement_rare_est_signale_comme_indicateur() -> None:
    # Douze conformes et un bavard : l'outil d'exploration tombe sous le seuil
    # de 10 % de la fédération, donc il est signalé comme indicateur.
    enveloppes = [_partagee("demo-conforme") for _ in range(12)] + [_partagee("demo-bavard")]
    profil = federation.profiler(enveloppes)
    bavard = enveloppes[-1]
    suspects = federation.atypiques(bavard, profil)
    assert any("list_buckets" in s for s in suspects)
    # An indicator, never a verdict: the wording says what was seen, not a nature.
    assert all("fédération" in s for s in suspects)


def test_un_comportement_partage_n_est_pas_signale() -> None:
    enveloppes = [_partagee("demo-conforme") for _ in range(4)]
    profil = federation.profiler(enveloppes)
    assert federation.atypiques(enveloppes[0], profil) == ()


# --------------------------------------------------------------------------- #
# Version diff (§15.1)
# --------------------------------------------------------------------------- #


def test_diff_entre_deux_versions_du_meme_agent() -> None:
    avant = _dossier("demo-conforme")
    apres = _dossier("demo-bavard")
    diff = federation.diff_versions(
        agent_id="agentticket",
        avant=enveloppe(avant, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE),
        apres=enveloppe(
            apres, agent_id="agentticket", tenant_id="t", version="3.5.0", date=DATE + timedelta(days=30)
        ),
    )
    assert diff.distance > 0
    assert diff.apparitions, "le bavard explore : quelque chose doit apparaître"
    assert diff.version_avant == "3.4.1"
    assert diff.version_apres == "3.5.0"
    assert diff.changement_non_declare is False


def test_un_changement_non_declare_est_marque() -> None:
    """§15.1 — the case no paper guarantee catches."""
    avant = _dossier("demo-conforme")
    apres = _dossier("demo-bavard")
    diff = federation.diff_versions(
        agent_id="agentticket",
        avant=enveloppe(avant, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE),
        apres=enveloppe(
            apres, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE + timedelta(days=7)
        ),
        declare=False,
    )
    assert diff.changement_non_declare is True
    assert "non déclaré" in federation.resume_diff(diff)


def test_deux_versions_identiques_ne_bougent_pas() -> None:
    premier = _dossier("demo-conforme")
    second = _dossier("demo-conforme")
    diff = federation.diff_versions(
        agent_id="agentticket",
        avant=enveloppe(premier, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE),
        apres=enveloppe(second, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE),
    )
    assert diff.distance == 0.0
    assert diff.apparitions == ()
    assert diff.disparitions == ()


def test_le_resume_existe_dans_les_deux_langues() -> None:
    avant = _dossier("demo-conforme")
    apres = _dossier("demo-bavard")
    diff = federation.diff_versions(
        agent_id="agentticket",
        avant=enveloppe(avant, agent_id="agentticket", tenant_id="t", version="3.4.1", date=DATE),
        apres=enveloppe(apres, agent_id="agentticket", tenant_id="t", version="3.5.0", date=DATE),
    )
    francais = federation.resume_diff(diff, "fr")
    anglais = federation.resume_diff(diff, "en")
    assert "distance comportementale" in francais
    assert "behavioural distance" in anglais
