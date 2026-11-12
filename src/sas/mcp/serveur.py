"""The Sas gateway exposed as an MCP server (WP-MCP, lot 1).

**One MCP session = one Sas session = one ephemeral identity.** The mapping is
explicit: `SessionMCP.session` is the `sas.types.Session` the runtime created,
`SessionMCP.identite` is the credential the identity port emitted for it, and
both identifiers travel in the `initialize` answer so a reader can check the
correspondence instead of taking it on faith.

Three rules drive the whole module:

* **The tool list comes from the manifest** (EF-05): the client sees the tools
  the signed manifest declares, and nothing else.
* **`tools/call` crosses the real gateway** (`sas.agentcore.passerelle`): the
  policy is evaluated, the call is journalled — and a refusal is journalled
  too, as a structured result carrying the rule and the motive, never as an
  opaque exception.
* **A bounding refusal is not an out-of-scope attempt.** `REGLES_PERIMETRE`
  and `REGLES_BORNAGE` are two separate families
  (`sas.agentcore.politique_manifeste`): a guest that exhausts its budget has
  not tried to go out of perimeter, and the answer says so.

The stdio loop takes injectable streams: the tests never launch a subprocess.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Iterator, Sequence
from typing import Any

from sas import __version__ as VERSION_SAS
from sas import aleatoire
from sas.agentcore import fabrique
from sas.agentcore.politique_manifeste import REGLES_BORNAGE, est_hors_perimetre
from sas.arret import BudgetEpuise, Interrupteur, SessionSuspendue
from sas.manifeste.chargement import charger_manifeste
from sas.manifeste.validation import est_executable
from sas.mcp.protocole import (
    ERREUR_METHODE,
    ERREUR_PARAMETRES,
    METHODE_INITIALIZE,
    METHODE_NOTIFICATION,
    METHODE_TOOLS_CALL,
    METHODE_TOOLS_LIST,
    VERSION_PROTOCOLE,
    VERSIONS_PROTOCOLE,
    ErreurProtocole,
    Requete,
    traiter,
)
from sas.ombre import GenerateurOmbre, SupportOmbre
from sas.types import Decision, IdentiteEphemere, Manifeste, Mode, OutilDemande
from sas.types import Session as SessionSas

NOM_SERVEUR = "sas-mcp"
VERSION_SERVEUR = VERSION_SAS
TITRE_SERVEUR = "Sas — passerelle d'homologation exposée en MCP"

TENANT_PAR_DEFAUT = "tenant-mcp"
CAMPAGNE_PAR_DEFAUT = "camp-mcp"
SCENARIO_MCP = "mcp"

# The three families a denial can belong to. `perimetre` is the only one the
# classification of §13 looks at; `bornage` is the airlock stopping the
# session; `autre` is anything the manifest-derived engine does not classify.
FAMILLE_PERIMETRE = "perimetre"
FAMILLE_BORNAGE = "bornage"
FAMILLE_AUTRE = "autre"

INSTRUCTIONS = (
    "The tools below are the ones the signed agent manifest declares. "
    "Every call is evaluated by the Sas gateway and journalled, allowed or not."
)

# The arguments the gateway actually understands. They are published so an MCP
# client can fill them in; the perimeter is enforced by the policy, never by
# this description.
PROPRIETES_OUTILS: dict[str, dict[str, Any]] = {
    "lire_ticket": {"id": {"type": "string", "description": "Identifier of the ticket to read."}},
    "chercher_document": {"requete": {"type": "string", "description": "Full-text query."}},
    "ouvrir_tache": {"resume": {"type": "string", "description": "Summary of the task to open."}},
}
PROPRIETES_GENERIQUES: dict[str, Any] = {
    "ressource": {"type": "string", "description": "Resource the call applies to."},
    "chemin": {"type": "string", "description": "Path inside the resource."},
    "colonnes": {"type": "array", "items": {"type": "string"}, "description": "Columns the call reads."},
}


class ManifesteNonExecutable(Exception):
    """Raised when the manifest in force does not allow any execution (ENF-01)."""


class ServeurMCP:
    """The server: a manifest, the AgentCore backend it derives, the tools.

    It holds no session state of its own: every MCP session gets its own Sas
    session, its own ephemeral identity and its own counters.
    """

    def __init__(
        self,
        *,
        manifeste: Manifeste,
        backend: Any,
        mode: Mode = Mode.OMBRE,
        tenant_id: str = TENANT_PAR_DEFAUT,
        campagne_id: str = CAMPAGNE_PAR_DEFAUT,
        graine: int = 0,
    ) -> None:
        self._manifeste = manifeste
        self._backend = backend
        self._mode = mode
        self._tenant_id = tenant_id
        self._campagne_id = campagne_id
        self._graine = graine
        self._interrupteur = Interrupteur()
        self._sessions_crees = 0

    @classmethod
    def depuis_manifeste(
        cls,
        source: str,
        *,
        mode: Mode = Mode.OMBRE,
        tenant_id: str = TENANT_PAR_DEFAUT,
        campagne_id: str = CAMPAGNE_PAR_DEFAUT,
        graine: int = 0,
    ) -> ServeurMCP:
        """Assemble the server from a signed manifest (a path or a document).

        ENF-01: without a signed, validated manifest in force, nothing starts.
        """
        manifeste = charger_manifeste(source)
        executable, motif = est_executable(manifeste, manifeste.identite.version_agent)
        if not executable:
            raise ManifesteNonExecutable(motif)
        politique = fabrique.politique_depuis(manifeste, mode)
        ombre = GenerateurOmbre().construire(campagne_id, politique, graine)
        support = SupportOmbre(ombre, graine)
        backend = fabrique.backend(
            politique=politique,
            support=support,
            mode=mode,
            tenant_id=tenant_id,
            manifeste_statut=manifeste.statut,
            version_courante=manifeste.version,
        )
        return cls(
            manifeste=manifeste,
            backend=backend,
            mode=mode,
            tenant_id=tenant_id,
            campagne_id=campagne_id,
            graine=graine,
        )

    # -- read-only surface -------------------------------------------------- #
    @property
    def manifeste(self) -> Manifeste:
        return self._manifeste

    @property
    def backend(self) -> Any:
        return self._backend

    @property
    def mode(self) -> Mode:
        return self._mode

    @property
    def agent_id(self) -> str:
        return self._backend.politique.agent_id

    @property
    def interrupteur(self) -> Interrupteur:
        """EF-15 — the kill switch; arming it cuts every call of every session."""
        return self._interrupteur

    def outils(self) -> tuple[dict[str, Any], ...]:
        """The MCP tool list — built from the manifest, never by hand (EF-05)."""
        return tuple(_descrire_outil(outil) for outil in self._manifeste.outils_demandes)

    def nouvelle_session(self) -> SessionMCP:
        """Open one MCP session: one Sas session, one ephemeral identity.

        Each connection is its own isolated replay (ENF-05, ENF-16): the seed
        is derived per session so two connections never share a session
        identifier, and the sequence stays reproducible from the server seed.
        """
        self._sessions_crees += 1
        numero = self._sessions_crees
        session = self._backend.runtime.creer_session(
            campagne_id=self._campagne_id,
            scenario_id=SCENARIO_MCP,
            numero_rejeu=numero,
            graine=aleatoire.graine_derivee(self._graine, SCENARIO_MCP, numero),
            mode=self._mode,
        )
        identite = self._backend.identite.emettre(session, self._backend.politique)
        cadre = self._backend.passerelle.ouvrir_session(session, identite)
        cadre.interrupteur = self._interrupteur
        boite = self._backend.passerelle.boite_outils(session, identite)
        return SessionMCP(
            serveur=self,
            session=session,
            identite=identite,
            boite=boite,
        )


class SessionMCP:
    """One MCP session, bound to one Sas session and one ephemeral identity."""

    def __init__(
        self,
        *,
        serveur: ServeurMCP,
        session: SessionSas,
        identite: IdentiteEphemere,
        boite: Any,
    ) -> None:
        self._serveur = serveur
        self._session = session
        self._identite = identite
        self._boite = boite
        self._initialisee = False

    # -- read-only surface -------------------------------------------------- #
    @property
    def serveur(self) -> ServeurMCP:
        return self._serveur

    @property
    def session(self) -> SessionSas:
        """The Sas session this MCP session runs in."""
        return self._session

    @property
    def identite(self) -> IdentiteEphemere:
        """The ephemeral identity issued for that session (ENF-02)."""
        return self._identite

    @property
    def initialisee(self) -> bool:
        return self._initialisee

    # -- protocol ----------------------------------------------------------- #
    def traiter(self, requete: Requete) -> Any:
        if requete.methode == METHODE_INITIALIZE:
            return self._initialize(requete)
        if requete.methode == METHODE_TOOLS_LIST:
            return self._liste_outils()
        if requete.methode == METHODE_TOOLS_CALL:
            return self._appel_outil(requete)
        if requete.methode == METHODE_NOTIFICATION:
            return {}
        raise ErreurProtocole(ERREUR_METHODE, f"méthode inconnue : {requete.methode}")

    def notifier(self, requete: Requete) -> None:
        """`notifications/initialized` and friends: acknowledged, never answered."""

    # -- methods ------------------------------------------------------------ #
    def _initialize(self, requete: Requete) -> dict[str, Any]:
        if self._initialisee:
            raise ErreurProtocole(ERREUR_PARAMETRES, "session déjà initialisée")
        self._initialisee = True
        return {
            "protocolVersion": _version_demandee(requete.params.get("protocolVersion")),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": NOM_SERVEUR,
                "version": VERSION_SERVEUR,
                "title": TITRE_SERVEUR,
            },
            "instructions": INSTRUCTIONS,
            "_meta": self._meta_session(),
        }

    def _liste_outils(self) -> dict[str, Any]:
        self._exiger_initialisation()
        return {"tools": list(self._serveur.outils()), "_meta": self._meta_session()}

    def _appel_outil(self, requete: Requete) -> dict[str, Any]:
        self._exiger_initialisation()
        nom = requete.params.get("name")
        if not isinstance(nom, str) or not nom:
            raise ErreurProtocole(ERREUR_PARAMETRES, "« name » est obligatoire")
        arguments = requete.params.get("arguments", {})
        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ErreurProtocole(ERREUR_PARAMETRES, "« arguments » doit être un objet")
        return self._appeler(nom, arguments)

    # -- internals ---------------------------------------------------------- #
    def _exiger_initialisation(self) -> None:
        if not self._initialisee:
            raise ErreurProtocole(ERREUR_PARAMETRES, "« initialize » est requis avant cet appel")

    def _appeler(self, nom: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Cross the real gateway: the policy decides, the journal records."""
        try:
            brut = self._boite.appeler(nom, arguments)
        except BudgetEpuise as exc:
            return self._refus("budget-epuise", exc.motif, journalise=True)
        except SessionSuspendue as exc:
            return self._refus("suspension", exc.motif, journalise=False)
        return self._reponse(brut)

    def _reponse(self, brut: dict[str, Any]) -> dict[str, Any]:
        decision = str(brut.get("decision", ""))
        regle = str(brut.get("regle", ""))
        famille = _famille(regle)
        payload = {
            "ok": bool(brut.get("ok")),
            "decision": decision,
            "regle": regle,
            "motif": str(brut.get("motif", "")),
            "famille": famille,
            "hors_perimetre": famille == FAMILLE_PERIMETRE,
            "resultat": brut.get("resultat", {}),
            "session_id": self._session.id,
        }
        return self._enveloppe(
            payload,
            is_error=decision == Decision.REFUSE.value,
            appel_id=str(brut.get("appel_id", "")),
        )

    def _refus(self, regle: str, motif: str, *, journalise: bool) -> dict[str, Any]:
        """A refusal the gateway could not turn into a result: still structured."""
        famille = _famille(regle)
        payload = {
            "ok": False,
            "decision": Decision.REFUSE.value,
            "regle": regle,
            "motif": motif,
            "famille": famille,
            "hors_perimetre": famille == FAMILLE_PERIMETRE,
            "journalise": journalise,
            "session_id": self._session.id,
        }
        return self._enveloppe(payload, is_error=True)

    def _enveloppe(self, payload: dict[str, Any], *, is_error: bool, appel_id: str = "") -> dict[str, Any]:
        return {
            "content": [{"type": "text", "text": _texte(payload)}],
            "isError": is_error,
            "_meta": {
                "sas.session_id": self._session.id,
                "sas.decision": payload.get("decision", ""),
                "sas.regle": payload.get("regle", ""),
                "sas.motif": payload.get("motif", ""),
                "sas.famille": payload.get("famille", FAMILLE_AUTRE),
                "sas.hors_perimetre": payload.get("hors_perimetre", False),
                "sas.appel_id": appel_id,
            },
        }

    def _meta_session(self) -> dict[str, Any]:
        """The correspondence, published: MCP session = Sas session = identity."""
        return {
            "sas.session_id": self._session.id,
            "sas.identite": self._identite.reference,
            "sas.identite_expire_le": self._identite.expire_le.isoformat(),
            "sas.agent_id": self._serveur.agent_id,
            "sas.mode": self._serveur.mode.value,
            "sas.manifeste_version": self._serveur.manifeste.version,
        }


def boucle(entree: Iterable[str], sortie: Any, session: SessionMCP) -> int:
    """The stdio loop, with injectable streams: no subprocess, ever.

    Returns the number of answers written; a line that carries nothing produces
    no output.
    """
    reponses = 0
    for ligne in _lignes(entree):
        reponse = traiter(ligne, session)
        if reponse is None:
            continue
        sortie.write(reponse + "\n")
        _vider(sortie)
        reponses += 1
    return reponses


def main(
    argv: Sequence[str] | None = None,
    entree: Iterable[str] | None = None,
    sortie: Any = None,
) -> int:
    """Entry point: `python -m sas.mcp.serveur <manifeste.yaml>`.

    The streams are injectable, so the entry point is testable without spawning.
    """
    arguments = _arguments(argv)
    if arguments is None:
        return 2
    mode = Mode.OBSERVE if arguments.mode == "observe" else Mode.OMBRE
    try:
        serveur = ServeurMCP.depuis_manifeste(
            arguments.manifeste, mode=mode, tenant_id=arguments.tenant, graine=arguments.graine
        )
    except Exception as exc:
        print(f"{NOM_SERVEUR}: {exc}", file=sys.stderr)
        return 2
    session = serveur.nouvelle_session()
    boucle(
        entree if entree is not None else sys.stdin,
        sortie if sortie is not None else sys.stdout,
        session,
    )
    return 0


# --------------------------------------------------------------------------- #
# Internals
# --------------------------------------------------------------------------- #


def _arguments(argv: Sequence[str] | None) -> argparse.Namespace | None:
    analyseur = argparse.ArgumentParser(prog="sas.mcp.serveur", description="Sas gateway as an MCP server.")
    analyseur.add_argument("manifeste", help="path to the signed agent manifest (YAML or JSON)")
    analyseur.add_argument("--mode", default="ombre", choices=("ombre", "observe"))
    analyseur.add_argument("--tenant", default=TENANT_PAR_DEFAUT)
    analyseur.add_argument("--graine", type=int, default=0)
    try:
        return analyseur.parse_args(list(argv) if argv is not None else None)
    except SystemExit:
        return None


def _descrire_outil(outil: OutilDemande) -> dict[str, Any]:
    justification = outil.justification.strip() or f"outil « {outil.nom} »"
    return {
        "name": outil.nom,
        "description": f"{justification} [{outil.operation}]",
        "inputSchema": _schema_outil(outil.nom),
    }


def _schema_outil(nom: str) -> dict[str, Any]:
    proprietes = dict(PROPRIETES_GENERIQUES)
    specifiques = PROPRIETES_OUTILS.get(nom, {})
    proprietes.update(specifiques)
    return {
        "type": "object",
        "properties": proprietes,
        "required": list(specifiques),
        "additionalProperties": False,
    }


def _famille(regle: str) -> str:
    """Which family a refusal belongs to — perimeter, bounding, or neither."""
    if regle in REGLES_BORNAGE:
        return FAMILLE_BORNAGE
    if est_hors_perimetre(regle):
        return FAMILLE_PERIMETRE
    return FAMILLE_AUTRE


def _version_demandee(demandee: Any) -> str:
    if isinstance(demandee, str) and demandee in VERSIONS_PROTOCOLE:
        return demandee
    return VERSION_PROTOCOLE


def _texte(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _lignes(entree: Iterable[str]) -> Iterator[str]:
    for ligne in entree:
        if isinstance(ligne, bytes):
            ligne = ligne.decode("utf-8", errors="replace")
        yield ligne


def _vider(sortie: Any) -> None:
    vider = getattr(sortie, "flush", None)
    if callable(vider):
        vider()


if __name__ == "__main__":  # pragma: no cover — the entry point is exercised in-process
    raise SystemExit(main())
