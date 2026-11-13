"""L'appel réel à Bedrock AgentCore Runtime (chantier « Bedrock AgentCore réel »).

C'est le **seul** endroit du dépôt qui exécute un invité chez AWS. Tout le
reste tourne hors ligne. Trois règles structurent ce module :

* **le drapeau d'abord** — l'exécution native facture le runtime (vCPU-seconde,
  Go-seconde) et l'invité peut lui-même appeler des modèles payants. Sans
  ``SAS_AGENTCORE_EXECUTION=1``, `executer_dans_le_runtime` n'appelle rien et
  le dit ; l'avertissement de coût accompagne le refus ;
* **boto3 n'est jamais importé ici** — le module reçoit une *session* boto3 et
  n'utilise que son ``client()``. Le contrat de l'API est donc testable hors
  ligne, avec un faux client local ;
* **les erreurs sont dites** — une erreur AWS est traduite en message qui nomme
  la cause (identifiants absents, runtime absent, refus), jamais avalée.

Le service s'appelle ``bedrock-agentcore`` : c'est le nom du service de
*données* dans botocore (le service de contrôle est ``bedrock-agentcore-control``)
et l'opération y est ``InvokeAgentRuntime``, exposée en Python sous le nom
``invoke_agent_runtime``. Il n'existe pas de service ``bedrock-agentcore-runtime``
dans le SDK Python : le dire ici évite d'écrire un appel qui ne peut pas
fonctionner.

La forme exacte de l'appel, relevée sur le modèle de service de botocore :

    invoke_agent_runtime(
        agentRuntimeArn=...,      # obligatoire : l'ARN du runtime
        runtimeSessionId=...,      # en-tête de session : une session par rejeu
        qualifier=...,             # « DEFAULT » par défaut
        payload=...,               # blob : le payload de l'invité
        contentType="application/json",
        accept="application/json",
    )

et la réponse porte ``response`` (flux), ``contentType``, ``runtimeSessionId``
et ``statusCode``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

from sas.types import Session

#: Le service boto3 qui porte l'opération ``InvokeAgentRuntime``.
SERVICE_RUNTIME = "bedrock-agentcore"

#: Le drapeau explicite : sans lui, aucune invocation native n'est tentée.
VARIABLE_AUTORISATION = "SAS_AGENTCORE_EXECUTION"

#: Les valeurs acceptées pour le drapeau.
VALEURS_AUTORISEES: frozenset[str] = frozenset({"1", "true", "oui", "yes"})

#: L'avertissement de coût, repris dans le message de refus.
AVERTISSEMENT_COUT = (
    "attention au coût : le runtime AgentCore facture la vCPU-seconde et la "
    "Go-seconde, et l'invité peut à son tour appeler des modèles payants"
)

#: Le qualificateur par défaut d'un runtime AgentCore.
QUALIFICATEUR_DEFAUT = "DEFAULT"

#: Les erreurs AWS traduites. La clé est le code que AWS renvoie
#: (``Error.Code``) ; le nom de la classe Python sert de repli.
MESSAGES_AUS: dict[str, str] = {
    "ResourceNotFoundException": "runtime AgentCore absent : « {arn} » n'existe pas (région {region})",
    "AccessDeniedException": "refus AWS : le rôle d'exécution n'a pas le droit d'invoquer « {arn} »",
    "UnauthorizedException": "identifiants AWS refusés : le rôle d'exécution n'est pas autorisé",
    "ValidationException": "requête refusée par le service AgentCore : {message}",
    "ThrottlingException": "quota de débit AgentCore atteint : réessayer plus tard",
    "ServiceQuotaExceededException": "quota AgentCore dépassé (sessions simultanées ou concurrence)",
    "RuntimeClientError": "l'invité a échoué dans le runtime : {message}",
    "InternalServerException": "erreur interne du service AgentCore",
    "NoCredentialsError": "identifiants AWS absents : l'invocation n'a pas pu être signée",
    "PartialCredentialsError": "identifiants AWS incomplets : clé ou secret manquant",
    "EndpointConnectionError": "point de terminaison AgentCore injoignable (région, VPC ou proxy)",
    "ConnectTimeoutError": "délai dépassé en joignant le point de terminaison AgentCore",
}


class ErreurExecutionAgentCore(RuntimeError):
    """L'exécution native a échoué ; la cause est dite, jamais masquée."""


class ExecutionNonAutorisee(ErreurExecutionAgentCore):
    """Le drapeau d'exécution n'est pas levé : rien n'a été appelé."""


def execution_autorisee(environ: Mapping[str, str] | None = None) -> bool:
    """Le drapeau explicite : ``SAS_AGENTCORE_EXECUTION=1``."""
    source = os.environ if environ is None else environ
    return (source.get(VARIABLE_AUTORISATION) or "").strip().lower() in VALEURS_AUTORISEES


def client_runtime(session: Any) -> Any:
    """Le client du service de données AgentCore.

    ``session`` est une session boto3 ; le module n'importe jamais boto3, ce
    qui rend l'appel testable hors ligne avec un faux client.
    """
    if session is None:
        raise ErreurExecutionAgentCore("Runtime AgentCore : aucune session boto3 fournie")
    return session.client(SERVICE_RUNTIME)


def payload_invite(session: Session, agent: Any, entree: Mapping[str, Any]) -> bytes:
    """Le payload de l'invité : du JSON UTF-8, et rien d'autre.

    Il porte l'identité de l'invité et celle de la session (pour rattacher la
    trace à un rejeu), puis l'entrée telle que l'a produite le générateur de
    scénarios.
    """
    document = {
        "agent": agent.nom,
        "version": agent.version,
        "session_id": session.id,
        "campagne_id": session.campagne_id,
        "scenario_id": session.scenario_id,
        "numero_rejeu": session.numero_rejeu,
        "entree": dict(entree),
    }
    return json.dumps(document, ensure_ascii=False, sort_keys=True).encode("utf-8")


def executer_dans_le_runtime(
    session_boto3: Any,
    session: Session,
    agent: Any,
    entree: Mapping[str, Any],
    *,
    arn_runtime: str,
    qualifier: str = QUALIFICATEUR_DEFAUT,
    region: str = "",
) -> dict[str, Any]:
    """Exécute l'invité dans une session isolée du runtime AgentCore.

    L'appel est réel : ``InvokeAgentRuntime`` du service ``bedrock-agentcore``.
    Il n'a lieu que si le drapeau est levé, qu'un ARN de runtime est connu et
    qu'une session boto3 existe ; sinon l'erreur dit ce qui manque, sans
    facturer quoi que ce soit.
    """
    if not execution_autorisee():
        raise ExecutionNonAutorisee(
            f"exécution native non autorisée : lever {VARIABLE_AUTORISATION}=1 pour l'autoriser "
            f"— {AVERTISSEMENT_COUT}"
        )
    if not arn_runtime.strip():
        raise ErreurExecutionAgentCore(
            "runtime AgentCore absent : aucun ARN de runtime n'est configuré "
            "(arn:aws:bedrock-agentcore:<région>:<compte>:runtime/<nom>)"
        )
    client = client_runtime(session_boto3)
    charge = payload_invite(session, agent, entree)
    reponse = _invoquer(
        client,
        arn_runtime=arn_runtime,
        session_id=session.id,
        charge=charge,
        qualifier=qualifier,
        region=region,
    )
    return _resultat(reponse, session)


def _invoquer(
    client: Any,
    *,
    arn_runtime: str,
    session_id: str,
    charge: bytes,
    qualifier: str,
    region: str,
) -> dict[str, Any]:
    """L'appel lui-même, et la traduction de toute erreur en message honnête."""
    try:
        return dict(
            client.invoke_agent_runtime(
                agentRuntimeArn=arn_runtime,
                runtimeSessionId=session_id,
                qualifier=qualifier,
                payload=charge,
                contentType="application/json",
                accept="application/json",
            )
        )
    except Exception as exc:
        raise _erreur_honete(exc, arn=arn_runtime, region=region) from exc


def _resultat(reponse: Mapping[str, Any], session: Session) -> dict[str, Any]:
    """Ce que l'invocation rend : la session, le statut et le contenu."""
    return {
        "runtime_session_id": str(reponse.get("runtimeSessionId") or session.id),
        "status_code": reponse.get("statusCode"),
        "content_type": str(reponse.get("contentType") or ""),
        "contenu": lire_reponse(reponse),
    }


def lire_reponse(reponse: Mapping[str, Any]) -> str:
    """Le corps de la réponse de l'invité : du texte, jamais un blob opaque."""
    corps = reponse.get("response")
    if corps is None:
        return ""
    lecture = getattr(corps, "read", None)
    brut = lecture() if callable(lecture) else corps
    if isinstance(brut, bytes):
        return brut.decode("utf-8", errors="replace")
    return str(brut)


def _erreur_honete(exc: Exception, *, arn: str, region: str) -> ErreurExecutionAgentCore:
    """La cause AWS, en français, avec l'ARN et la région en contexte."""
    code = _code_erreur(exc)
    detail = str(exc).strip() or code
    gabarit = MESSAGES_AUS.get(code)
    if gabarit is None:
        return ErreurExecutionAgentCore(f"échec de l'invocation AgentCore ({code}) : {detail}")
    return ErreurExecutionAgentCore(gabarit.format(arn=arn, region=region or "inconnue", message=detail))


def _code_erreur(exc: Exception) -> str:
    """Le code d'erreur AWS, ou le nom de la classe quand AWS n'en donne pas."""
    reponse = getattr(exc, "response", None)
    if isinstance(reponse, Mapping):
        erreur = reponse.get("Error")
        if isinstance(erreur, Mapping):
            code = erreur.get("Code")
            if isinstance(code, str) and code:
                return code
    return type(exc).__name__
