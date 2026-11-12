"""The configurable engine, exercised end to end through the gateway.

The unit tests prove each rule in isolation. These prove the wiring: the engine
factory picks `MoteurPolitique`, the gateway scopes it per scenario, and the
additive rules fire on the *real* pipeline — including a call the manifest
explicitly allows and a client rule refuses.
"""

from __future__ import annotations

from pathlib import Path

RACINE = Path(__file__).resolve().parents[3]


def test_le_moteur_configurable_est_celuichoisi_par_la_fabrique() -> None:
    from sas.agentcore.fabrique import moteur_politique, politique_depuis
    from sas.manifeste import charger
    from sas.politique import MoteurPolitique

    manifeste = charger(RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml").manifeste
    moteur = moteur_politique(politique_depuis(manifeste))
    assert isinstance(moteur, MoteurPolitique), "la fabrique doit préférer le moteur configurable"


def test_la_regle_additive_s5_refuse_une_sortie_par_ailleurs_declaree() -> None:
    """A client rule narrows the manifest: a declared outbound call in S5 is
    refused, even though the manifest allows it everywhere else."""
    from sas.agentcore.fabrique import backend, politique_depuis
    from sas.manifeste import charger
    from sas.ombre import GenerateurOmbre, SupportOmbre
    from sas.types import Decision

    manifeste = charger(RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml").manifeste
    manifeste = _avec_sortie_declaree(manifeste)
    politique = politique_depuis(manifeste)
    ombre = GenerateurOmbre().construire("camp-s5", politique, 7)
    support = SupportOmbre(ombre, 7)
    moteur = backend(politique=politique, support=support, manifeste_statut=manifeste.statut)
    session = moteur.runtime.creer_session(campagne_id="camp-s5", scenario_id="S5", numero_rejeu=1, graine=7)
    identite = moteur.identite.emettre(session, politique)
    outils = moteur.passerelle.boite_outils(session, identite)

    reponse = outils.sortie("https://collecte.example", "synthèse")
    assert reponse["decision"] == Decision.REFUSE.value
    assert reponse["regle"] == "sortie-non-declaree"


def test_la_meme_sortie_est_autorisee_dans_un_autre_scenario() -> None:
    """The same declared call, in S1: the additive rule does not fire."""
    from sas.agentcore.fabrique import backend, politique_depuis
    from sas.manifeste import charger
    from sas.ombre import GenerateurOmbre, SupportOmbre

    manifeste = charger(RACINE / "tests" / "fixtures" / "manifeste-exemple.yaml").manifeste
    manifeste = _avec_sortie_declaree(manifeste)
    politique = politique_depuis(manifeste)
    ombre = GenerateurOmbre().construire("camp-s1", politique, 7)
    support = SupportOmbre(ombre, 7)
    moteur = backend(politique=politique, support=support, manifeste_statut=manifeste.statut)
    session = moteur.runtime.creer_session(campagne_id="camp-s1", scenario_id="S1", numero_rejeu=1, graine=7)
    identite = moteur.identite.emettre(session, politique)
    outils = moteur.passerelle.boite_outils(session, identite)

    reponse = outils.sortie("https://collecte.example", "synthèse")
    assert reponse["ok"] is True, f"le scénario S1 ne restreint pas la sortie : {reponse}"


def _avec_sortie_declaree(manifeste):
    """The same manifest, plus one declared outbound destination."""
    from dataclasses import replace

    from sas.types import SortieAutorisee

    return replace(
        manifeste,
        sorties_autorisees=(
            *manifeste.sorties_autorisees,
            SortieAutorisee(
                destination="https://collecte.example", protocole="http", justification="collecte"
            ),
        ),
    )
