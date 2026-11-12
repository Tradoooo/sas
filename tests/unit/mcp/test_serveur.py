"""The Sas gateway exposed as an MCP server (WP-MCP, lot 1).

Everything here runs in-process: the stdio loop takes injectable streams, so no
test ever launches a subprocess. The calls cross the **real** gateway
(`sas.agentcore.passerelle`): the policy is evaluated, the journal records the
calls and the refusals, and a refusal comes back structured — rule, motive,
family — never as an opaque exception.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from sas.mcp import ServeurMCP, SessionMCP, boucle, main, traiter
from sas.mcp.serveur import ManifesteNonExecutable
from sas.types import Decision

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "manifeste-exemple.yaml"

OUTILS_DECLARES = ("lire_ticket", "chercher_document", "ouvrir_tache")
OUTIL_ABSENT = "supprimer_bucket"

# A second manifest, with one tool only: the tool list must follow the
# manifest, never a list written by hand in the server.
MANIFESTE_MINIMAL = """
manifeste:
  version: 1
  date: 2026-11-20
identite:
  nom: AgentMinimal
  editeur: Exemple Editeur SAS
  version_agent: 1.0.0
  empreinte_paquet: sha256:7c1f4a9e2b8d4c51a6f0e3d2b9c8471a5f6e0d9c8b7a61524334251607f8e9d0
  modele: modele.exemple
  version_modele: 2026-10
  engagement_notification_modele: vrai
finalite:
  fait: lit un ticket de support
  ne_fait_pas: []
outils_demandes:
  - nom: lire_ticket
    operation: lecture
    justification: traiter la demande entrante
donnees_demandees:
  - type: s3
    ressource: arn:aws:s3:::client-tickets/entree/*
    justification: tickets entrants
sorties_autorisees: []
budgets:
  appels_par_execution: 25
  jetons_par_execution: 60000
  duree_maximale_secondes: 180
  memoire_maximale_mio: 512
scenarios:
  - id: S1
    nom: ticket simple
interdictions_explicites:
  - lire toute ressource hors de celles déclarées
engagements:
  notification_changement_modele: 7 jours avant
  notification_changement_invite: 7 jours avant
  delai_correction_critique: 5 jours ouvrés
  contact: securite@exemple-editeur.invalid
signature:
  signataire: Directrice technique, Exemple Editeur SAS
  qualite: habilitée à engager l'éditeur
  date: 2026-11-20
validation_client:
  commanditaire: RSSI du client
  date: 2026-11-21
  perimetre_approuve: integralité du manifeste
  mode_autorise: ombre uniquement
"""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _serveur(source: Any = FIXTURE) -> ServeurMCP:
    return ServeurMCP.depuis_manifeste(source)


def _session(source: Any = FIXTURE) -> SessionMCP:
    return _serveur(source).nouvelle_session()


def _appel(session: SessionMCP, methode: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """One JSON-RPC request, in process."""
    ligne = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": methode, "params": params or {}},
        ensure_ascii=False,
    )
    reponse = traiter(ligne, session)
    assert reponse is not None
    return json.loads(reponse)


def _initiale(session: SessionMCP) -> dict[str, Any]:
    return _appel(session, "initialize", {"protocolVersion": "2025-06-18"})


def _texte(resultat: dict[str, Any]) -> dict[str, Any]:
    """The structured payload the MCP client reads in the content block."""
    return json.loads(resultat["content"][0]["text"])


def _journal(serveur: ServeurMCP, session: SessionMCP) -> tuple[Any, ...]:
    return tuple(serveur.backend.observabilite.journal(session.session.id))


# --------------------------------------------------------------------------- #
# The full cycle
# --------------------------------------------------------------------------- #


def test_le_cycle_complet_initialise_liste_puis_appel() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()

    initialisation = _initiale(session)
    assert initialisation["result"]["protocolVersion"] == "2025-06-18"

    outils = _appel(session, "tools/list")
    assert [o["name"] for o in outils["result"]["tools"]] == list(OUTILS_DECLARES)

    autorise = _appel(session, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    assert autorise["result"]["isError"] is False
    assert _texte(autorise["result"])["ok"] is True

    refuse = _appel(session, "tools/call", {"name": OUTIL_ABSENT, "arguments": {}})
    assert refuse["result"]["isError"] is True
    assert _texte(refuse["result"])["regle"] == "usage-non-declare"


def test_le_journal_contient_l_appel_autorise_et_le_refus() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()
    _initiale(session)

    _appel(session, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    _appel(session, "tools/call", {"name": OUTIL_ABSENT, "arguments": {}})

    entrees = _journal(serveur, session)
    assert len(entrees) == 2
    assert [e.outil for e in entrees] == ["lire_ticket", OUTIL_ABSENT]
    assert entrees[0].decision is Decision.AUTORISE
    assert entrees[1].decision is Decision.REFUSE
    assert entrees[1].regle_appliquee == "usage-non-declare"
    assert serveur.backend.observabilite.verifier_chaine("camp-mcp").integre is True


def test_le_refus_est_structure_et_non_une_exception() -> None:
    session = _session()
    _initiale(session)
    reponse = _appel(session, "tools/call", {"name": OUTIL_ABSENT, "arguments": {}})
    payload = _texte(reponse["result"])
    assert payload["ok"] is False
    assert payload["decision"] == "refuse"
    assert payload["regle"] == "usage-non-declare"
    assert OUTIL_ABSENT in payload["motif"]
    assert reponse["result"]["_meta"]["sas.regle"] == "usage-non-declare"


# --------------------------------------------------------------------------- #
# The tool list comes from the manifest (EF-05)
# --------------------------------------------------------------------------- #


def test_tools_list_ne_contient_que_les_outils_du_manifeste() -> None:
    session = _session()
    _initiale(session)
    outils = _appel(session, "tools/list")["result"]["tools"]
    assert {o["name"] for o in outils} == set(OUTILS_DECLARES)
    assert OUTIL_ABSENT not in {o["name"] for o in outils}


def test_la_liste_des_outils_suit_le_manifeste_pas_une_saisie() -> None:
    session = _session(MANIFESTE_MINIMAL)
    _initiale(session)
    outils = _appel(session, "tools/list")["result"]["tools"]
    assert [o["name"] for o in outils] == ["lire_ticket"]
    assert "chercher_document" not in {o["name"] for o in outils}


def test_un_outil_absent_du_manifeste_est_refuse_et_journalise() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()
    _initiale(session)
    _appel(session, "tools/call", {"name": OUTIL_ABSENT, "arguments": {}})
    entrees = _journal(serveur, session)
    assert len(entrees) == 1
    assert entrees[0].outil == OUTIL_ABSENT
    assert entrees[0].decision is Decision.REFUSE


# --------------------------------------------------------------------------- #
# One MCP session = one Sas session = one ephemeral identity
# --------------------------------------------------------------------------- #


def test_une_session_mcp_correspond_a_une_session_du_sas_et_une_identite() -> None:
    session = _session()
    meta = _initiale(session)["result"]["_meta"]
    assert meta["sas.session_id"] == session.session.id
    assert meta["sas.identite"] == session.identite.reference
    assert session.identite.session_id == session.session.id
    assert session.identite.revoque is False
    assert session.identite.expire_le > session.identite.emis_le


def test_deux_sessions_mcp_ont_deux_sessions_et_deux_identites() -> None:
    serveur = _serveur()
    premiere = serveur.nouvelle_session()
    seconde = serveur.nouvelle_session()
    assert premiere.session.id != seconde.session.id
    assert premiere.identite.reference != seconde.identite.reference
    _initiale(premiere)
    _appel(premiere, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    assert len(_journal(serveur, premiere)) == 1
    assert len(_journal(serveur, seconde)) == 0


def test_le_journal_de_la_session_ne_contient_pas_les_appels_de_l_autre() -> None:
    serveur = _serveur()
    premiere = serveur.nouvelle_session()
    seconde = serveur.nouvelle_session()
    _initiale(premiere)
    _initiale(seconde)
    _appel(premiere, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    _appel(seconde, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0002"}})
    assert [e.session_id for e in _journal(serveur, premiere)] == [premiere.session.id]
    assert [e.session_id for e in _journal(serveur, seconde)] == [seconde.session.id]


# --------------------------------------------------------------------------- #
# Protocol errors
# --------------------------------------------------------------------------- #


def test_une_methode_inconnue_donne_une_erreur_standard() -> None:
    reponse = _appel(_session(), "resources/list")
    assert reponse["error"]["code"] == -32601


def test_un_json_invalide_donne_une_erreur_de_parsing() -> None:
    reponse = traiter("{pas du json", _session())
    assert reponse is not None
    assert json.loads(reponse)["error"]["code"] == -32700


def test_les_parametres_manquants_sont_refuses() -> None:
    session = _session()
    _initiale(session)
    reponse = _appel(session, "tools/call", {"arguments": {}})
    assert reponse["error"]["code"] == -32602


def test_tools_list_avant_initialize_est_refuse() -> None:
    reponse = _appel(_session(), "tools/list")
    assert reponse["error"]["code"] == -32602


def test_initialize_annonce_seulement_des_capacites_reelles() -> None:
    resultat = _initiale(_session())["result"]
    assert resultat["capabilities"] == {"tools": {"listChanged": False}}
    assert "resources" not in resultat["capabilities"]
    assert "prompts" not in resultat["capabilities"]
    assert "logging" not in resultat["capabilities"]


# --------------------------------------------------------------------------- #
# Two families of refusal (annexe C)
# --------------------------------------------------------------------------- #


def test_un_refus_de_perimetre_est_hors_perimetre() -> None:
    session = _session()
    _initiale(session)
    payload = _texte(_appel(session, "tools/call", {"name": OUTIL_ABSENT, "arguments": {}})["result"])
    assert payload["famille"] == "perimetre"
    assert payload["hors_perimetre"] is True


def test_un_refus_de_bornage_n_est_pas_une_tentative_hors_perimetre() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()
    _initiale(session)
    cadre = serveur.backend.passerelle.cadre(session.session.id)
    assert cadre is not None
    cadre.appels_restants = 0

    reponse = _appel(session, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    payload = _texte(reponse["result"])
    assert payload["regle"] == "budget-epuise"
    assert payload["famille"] == "bornage"
    assert payload["hors_perimetre"] is False
    assert reponse["result"]["isError"] is True


def test_un_refus_de_bornage_est_encore_journalise() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()
    _initiale(session)
    cadre = serveur.backend.passerelle.cadre(session.session.id)
    assert cadre is not None
    cadre.appels_restants = 0
    _appel(session, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    entrees = _journal(serveur, session)
    assert len(entrees) == 1
    assert entrees[0].regle_appliquee == "budget-epuise"


def test_l_interrupteur_coupe_les_appels_sans_les_opaque() -> None:
    serveur = _serveur()
    session = serveur.nouvelle_session()
    _initiale(session)
    serveur.interrupteur.armer("agent suspendu par le RSSI", par="rssi")

    reponse = _appel(session, "tools/call", {"name": "lire_ticket", "arguments": {"id": "T-0001"}})
    payload = _texte(reponse["result"])
    assert payload["regle"] == "suspension"
    assert payload["famille"] == "bornage"
    assert payload["hors_perimetre"] is False


# --------------------------------------------------------------------------- #
# The stdio loop, with injectable streams
# --------------------------------------------------------------------------- #


def test_la_boucle_traite_un_flux_injecte_sans_processus() -> None:
    session = _session()
    entree = io.StringIO(
        "\n".join(
            [
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": OUTIL_ABSENT, "arguments": {}},
                    }
                ),
            ]
        )
    )
    sortie = io.StringIO()
    reponses = boucle(entree, sortie, session)

    lignes = [ligne for ligne in sortie.getvalue().splitlines() if ligne]
    assert reponses == 3
    assert len(lignes) == 3
    assert json.loads(lignes[0])["id"] == 1
    assert json.loads(lignes[2])["result"]["isError"] is True


def test_le_point_d_entree_refuse_un_manifeste_introuvable() -> None:
    assert main(["/nonexistent/manifeste.yaml"]) == 2


def test_le_point_d_entree_traite_un_flux_injecte() -> None:
    entree = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
    sortie = io.StringIO()
    code = main([str(FIXTURE)], entree=entree, sortie=sortie)
    assert code == 0
    assert json.loads(sortie.getvalue().strip())["id"] == 1


def test_un_manifeste_non_executable_refuse_le_demarrage() -> None:
    # The same document without the sponsor validation: structurally valid,
    # but not executable — ENF-01 says no run without a validated manifest.
    sans_validation = MANIFESTE_MINIMAL.split("validation_client:")[0]
    with pytest.raises(ManifesteNonExecutable):
        ServeurMCP.depuis_manifeste(sans_validation)
