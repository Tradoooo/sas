"""The JSON-RPC 2.0 layer of the MCP server (WP-MCP, lot 1).

Pure protocol: no gateway, no stream, no subprocess. What is tested here is the
framing — the standard codes, the tolerance to blank lines, and the rule that a
session error never escapes as an opaque exception.
"""

from __future__ import annotations

import json
from typing import Any

from sas.mcp.protocole import (
    ERREUR_INTERNE,
    ERREUR_METHODE,
    ERREUR_PARAMETRES,
    ERREUR_PARSE,
    ERREUR_REQUETE,
    ErreurProtocole,
    Reponse,
    Requete,
    decoder,
    encoder,
    traiter,
)


class SessionFausse:
    """A session that answers what the test asks it to answer."""

    def __init__(self, resultat: Any = None, erreur: Exception | None = None) -> None:
        self.resultat = resultat
        self.erreur = erreur
        self.requetes: list[Requete] = []
        self.notifications: list[Requete] = []

    def traiter(self, requete: Requete) -> Any:
        self.requetes.append(requete)
        if self.erreur is not None:
            raise self.erreur
        return self.resultat

    def notifier(self, requete: Requete) -> None:
        self.notifications.append(requete)


def _reponse(ligne: str, session: Any) -> dict[str, Any]:
    sortie = traiter(ligne, session)
    assert sortie is not None
    return json.loads(sortie)


# --------------------------------------------------------------------------- #
# Decoding
# --------------------------------------------------------------------------- #


def test_une_ligne_vide_ne_produit_rien() -> None:
    session = SessionFausse(resultat={})
    assert traiter("", session) is None
    assert traiter("   \n", session) is None
    assert session.requetes == []


def test_un_json_illisible_donne_erreur_de_parsing() -> None:
    reponse = _reponse("{pas du json", SessionFausse())
    assert reponse["error"]["code"] == ERREUR_PARSE
    assert reponse["id"] is None


def test_une_requete_sans_jsonrpc_est_invalide() -> None:
    reponse = _reponse(json.dumps({"id": 1, "method": "tools/list"}), SessionFausse())
    assert reponse["error"]["code"] == ERREUR_REQUETE


def test_une_requete_sans_methode_est_invalide() -> None:
    reponse = _reponse(json.dumps({"jsonrpc": "2.0", "id": 1}), SessionFausse())
    assert reponse["error"]["code"] == ERREUR_REQUETE


def test_un_identifiant_de_mauvais_type_est_refuse() -> None:
    reponse = _reponse(
        json.dumps({"jsonrpc": "2.0", "id": True, "method": "tools/list"}),
        SessionFausse(),
    )
    assert reponse["error"]["code"] == ERREUR_REQUETE


def test_des_params_non_objet_sont_des_parametres_invalides() -> None:
    reponse = _reponse(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": [1, 2]}),
        SessionFausse(),
    )
    assert reponse["error"]["code"] == ERREUR_PARAMETRES


def test_decoder_rend_une_requete_exploitable() -> None:
    requete = decoder(
        json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {"name": "x"}})
    )
    assert isinstance(requete, Requete)
    assert requete.id == 7
    assert requete.methode == "tools/call"
    assert requete.params == {"name": "x"}
    assert requete.notification is False


def test_une_requete_sans_id_est_une_notification() -> None:
    requete = decoder(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
    assert isinstance(requete, Requete)
    assert requete.notification is True


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def test_une_requete_valide_rend_le_resultat_de_la_session() -> None:
    session = SessionFausse(resultat={"tools": []})
    reponse = _reponse(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/list"}), session)
    assert reponse == {"jsonrpc": "2.0", "id": 3, "result": {"tools": []}}
    assert [r.methode for r in session.requetes] == ["tools/list"]


def test_une_methode_inconnue_donne_erreur_methode_introuvable() -> None:
    reponse = _reponse(json.dumps({"jsonrpc": "2.0", "id": 4, "method": "resources/list"}), SessionFausse())
    assert reponse["error"]["code"] == ERREUR_METHODE
    assert "resources/list" in reponse["error"]["message"]


def test_une_notification_inconnue_ne_produit_rien() -> None:
    session = SessionFausse()
    assert traiter(json.dumps({"jsonrpc": "2.0", "method": "ping"}), session) is None
    assert session.notifications == []


def test_une_notification_connue_est_remise_sans_reponse() -> None:
    session = SessionFausse()
    assert traiter(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}), session) is None
    assert [n.methode for n in session.notifications] == ["notifications/initialized"]


def test_une_erreur_de_session_devient_une_erreur_jsonrpc() -> None:
    session = SessionFausse(erreur=ErreurProtocole(ERREUR_PARAMETRES, "« name » est obligatoire"))
    reponse = _reponse(json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call"}), session)
    assert reponse["error"]["code"] == ERREUR_PARAMETRES
    assert reponse["error"]["message"] == "« name » est obligatoire"


def test_une_exception_interne_devient_erreur_interne() -> None:
    session = SessionFausse(erreur=RuntimeError("panne du support"))
    reponse = _reponse(json.dumps({"jsonrpc": "2.0", "id": 6, "method": "tools/call"}), session)
    assert reponse["error"]["code"] == ERREUR_INTERNE
    assert reponse["error"]["data"]["type"] == "RuntimeError"


# --------------------------------------------------------------------------- #
# Encoding
# --------------------------------------------------------------------------- #


def test_l_encodage_produit_une_ligne_sans_saut_de_ligne() -> None:
    sortie = encoder(Reponse(id=1, resultat={"tools": [{"name": "lire_ticket"}]}))
    assert "\n" not in sortie
    assert json.loads(sortie)["result"]["tools"][0]["name"] == "lire_ticket"
