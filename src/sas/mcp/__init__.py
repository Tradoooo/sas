"""WP-MCP — the Sas gateway exposed as an MCP server (stdio).

Public surface: `sas.mcp` — the pure JSON-RPC 2.0 protocol and the server that
puts the real AgentCore gateway behind it. Other lots import `sas.mcp`, never a
sub-module.

The product stays the gateway: the perimeter comes from the signed manifest
(EF-05), every call crosses the policy and is journalled, and a refusal comes
back structured — rule, motive, family — never as an opaque exception.
"""

from __future__ import annotations

from sas.mcp.protocole import (
    ERREUR_INTERNE,
    ERREUR_METHODE,
    ERREUR_PARAMETRES,
    ERREUR_PARSE,
    ERREUR_REQUETE,
    JSONRPC,
    METHODE_INITIALIZE,
    METHODE_NOTIFICATION,
    METHODE_TOOLS_CALL,
    METHODE_TOOLS_LIST,
    METHODES,
    VERSION_PROTOCOLE,
    VERSIONS_PROTOCOLE,
    Erreur,
    ErreurProtocole,
    Reponse,
    Requete,
    decoder,
    encoder,
    traiter,
)
from sas.mcp.serveur import (
    FAMILLE_AUTRE,
    FAMILLE_BORNAGE,
    FAMILLE_PERIMETRE,
    NOM_SERVEUR,
    TITRE_SERVEUR,
    VERSION_SERVEUR,
    ManifesteNonExecutable,
    ServeurMCP,
    SessionMCP,
    boucle,
    main,
)

__all__ = [
    "ERREUR_INTERNE",
    "ERREUR_METHODE",
    "ERREUR_PARAMETRES",
    "ERREUR_PARSE",
    "ERREUR_REQUETE",
    "FAMILLE_AUTRE",
    "FAMILLE_BORNAGE",
    "FAMILLE_PERIMETRE",
    "JSONRPC",
    "METHODES",
    "METHODE_INITIALIZE",
    "METHODE_NOTIFICATION",
    "METHODE_TOOLS_CALL",
    "METHODE_TOOLS_LIST",
    "NOM_SERVEUR",
    "TITRE_SERVEUR",
    "VERSIONS_PROTOCOLE",
    "VERSION_PROTOCOLE",
    "VERSION_SERVEUR",
    "Erreur",
    "ErreurProtocole",
    "ManifesteNonExecutable",
    "Reponse",
    "Requete",
    "ServeurMCP",
    "SessionMCP",
    "boucle",
    "decoder",
    "encoder",
    "main",
    "traiter",
]
