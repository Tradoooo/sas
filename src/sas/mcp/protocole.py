"""MCP over stdio — the JSON-RPC 2.0 layer, pure and free of any I/O.

The gateway is the product; this module is only the wire format. It encodes
and decodes one JSON-RPC 2.0 message per line (NDJSON), knows the four methods
Sas exposes, and turns anything malformed into a standard error code.

Nothing here reads or writes a stream: `traiter(ligne, session)` is a pure
function of its two arguments, which is what makes the whole protocol testable
without a single subprocess.

Standard JSON-RPC 2.0 codes: -32700 parse error, -32600 invalid request,
-32601 method not found, -32602 invalid params, -32603 internal error.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

JSONRPC = "2.0"

# The MCP revisions whose `initialize` / `tools/list` / `tools/call` shapes are
# implemented here. The server answers with the revision the client asked for
# when it knows it, and with its own otherwise — never with a false one.
VERSIONS_PROTOCOLE: tuple[str, ...] = ("2024-11-05", "2025-03-26", "2025-06-18")
VERSION_PROTOCOLE: str = VERSIONS_PROTOCOLE[-1]

METHODE_INITIALIZE = "initialize"
METHODE_TOOLS_LIST = "tools/list"
METHODE_TOOLS_CALL = "tools/call"
METHODE_NOTIFICATION = "notifications/initialized"
METHODES: frozenset[str] = frozenset(
    {
        METHODE_INITIALIZE,
        METHODE_TOOLS_LIST,
        METHODE_TOOLS_CALL,
        METHODE_NOTIFICATION,
    }
)

ERREUR_PARSE = -32700
ERREUR_REQUETE = -32600
ERREUR_METHODE = -32601
ERREUR_PARAMETRES = -32602
ERREUR_INTERNE = -32603


class ErreurProtocole(Exception):
    """A protocol-level error the session raises — invalid params, mostly.

    It carries a standard JSON-RPC code, so the answer stays inside the
    protocol instead of leaking as an opaque exception.
    """

    def __init__(self, code: int, message: str, data: Any | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

    def en_erreur(self) -> Erreur:
        return Erreur(code=self.code, message=self.message, data=self.data)


@dataclass(frozen=True, slots=True)
class Erreur:
    """The error member of a JSON-RPC response."""

    code: int
    message: str
    data: Any | None = None

    def en_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            payload["data"] = self.data
        return payload


@dataclass(frozen=True, slots=True)
class Requete:
    """One decoded JSON-RPC request."""

    id: str | int | None = None
    methode: str = ""
    params: dict[str, Any] = field(default_factory=dict)
    notification: bool = False


@dataclass(frozen=True, slots=True)
class Reponse:
    """One JSON-RPC response: exactly one of `resultat` / `erreur`."""

    id: str | int | None = None
    resultat: Any = None
    erreur: Erreur | None = None

    def en_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"jsonrpc": JSONRPC, "id": self.id}
        if self.erreur is not None:
            payload["error"] = self.erreur.en_payload()
        else:
            payload["result"] = self.resultat
        return payload


@runtime_checkable
class SessionProtocole(Protocol):
    """What the protocol layer needs from a session.

    `sas.mcp.serveur.SessionMCP` implements it; the protocol tests use a fake.
    """

    def traiter(self, requete: Requete) -> Any:
        """Answer a request. Raise `ErreurProtocole` for an invalid request."""

    def notifier(self, requete: Requete) -> None:
        """Handle a notification. A notification never gets an answer."""


def decoder(ligne: str) -> Requete | Erreur | None:
    """One line -> one request, one protocol error, or None for a blank line.

    Blank lines are tolerated on purpose: NDJSON streams often carry them.
    """
    texte = ligne.strip()
    if not texte:
        return None
    try:
        donnees = json.loads(texte)
    except ValueError as exc:
        return Erreur(ERREUR_PARSE, "JSON illisible", {"detail": str(exc)})
    return _requete_de(donnees)


def encoder(reponse: Reponse) -> str:
    """One response -> one NDJSON line, without the trailing newline."""
    return json.dumps(reponse.en_payload(), ensure_ascii=False, separators=(",", ":"))


def traiter(ligne: str, session: SessionProtocole) -> str | None:
    """The testable core: one line in, one JSON line out — or None.

    No I/O happens here. The session does the work; this function only frames
    it and never lets an exception escape as an opaque crash.
    """
    requete = decoder(ligne)
    if requete is None:
        return None
    if isinstance(requete, Erreur):
        return encoder(Reponse(id=None, erreur=requete))
    if requete.methode not in METHODES:
        if requete.notification:
            return None
        return encoder(
            Reponse(
                id=requete.id,
                erreur=Erreur(ERREUR_METHODE, f"méthode inconnue : {requete.methode}"),
            )
        )
    try:
        if requete.notification:
            session.notifier(requete)
            return None
        resultat = session.traiter(requete)
    except ErreurProtocole as exc:
        return encoder(Reponse(id=requete.id, erreur=exc.en_erreur()))
    except Exception as exc:
        return encoder(
            Reponse(
                id=requete.id,
                erreur=Erreur(
                    ERREUR_INTERNE,
                    "erreur interne du serveur MCP",
                    {"type": type(exc).__name__, "detail": str(exc)},
                ),
            )
        )
    return encoder(Reponse(id=requete.id, resultat=resultat))


def _requete_de(donnees: Any) -> Requete | Erreur:
    if not isinstance(donnees, dict):
        return Erreur(ERREUR_REQUETE, "une requête JSON-RPC est un objet")
    if donnees.get("jsonrpc") != JSONRPC:
        return Erreur(ERREUR_REQUETE, "« jsonrpc » doit valoir « 2.0 »")
    methode = donnees.get("method")
    if not isinstance(methode, str) or not methode:
        return Erreur(ERREUR_REQUETE, "« method » est obligatoire")
    params = donnees.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        return Erreur(ERREUR_PARAMETRES, "« params » doit être un objet")
    notification = "id" not in donnees
    identifiant = donnees.get("id")
    if not notification and not _identifiant_valide(identifiant):
        return Erreur(ERREUR_REQUETE, "« id » doit être une chaîne, un entier ou null")
    return Requete(
        id=identifiant,
        methode=methode,
        params=params,
        notification=notification,
    )


def _identifiant_valide(identifiant: Any) -> bool:
    if identifiant is None:
        return True
    if isinstance(identifiant, bool):
        return False
    return isinstance(identifiant, (str, int))
