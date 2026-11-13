"""Le contrat de l'appel natif à Bedrock AgentCore Runtime (hors ligne).

Aucun test de ce fichier n'atteint AWS : le client boto3 est un faux local qui
reproduit la forme de l'API (`invoke_agent_runtime`), et les erreurs AWS sont
des exceptions locales au même nom. Ce que ces tests prouvent, c'est le
**contrat** : l'opération appelée, le payload envoyé, la session isolée par
rejeu, et l'honnêteté de l'erreur remontée (identifiants absents, runtime
absent, refus).

Ils ne prouvent **pas** que l'invocation fonctionne chez AWS : cela demandait
des identifiants et un runtime déployé, et cela coûterait de l'argent. Le
chantier dit ce qui reste à confirmer (§34 point 3).
"""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from sas.agentcore import aws, runtime_bedrock
from sas.agentcore.local import AgentNonInstrumentable
from sas.identifiants import maintenant
from sas.types import Session, StatutSession

ARN = "arn:aws:bedrock-agentcore:eu-west-3:123456789012:runtime/agent-ticket"
VARIABLE = runtime_bedrock.VARIABLE_AUTORISATION


# --------------------------------------------------------------------------- #
# Les doubles : la forme de l'API, locale
# --------------------------------------------------------------------------- #


class ErreurAWS(Exception):
    """Une erreur AWS, avec le même code que le service renvoie."""

    code = "InternalServerException"

    def __init__(self, message: str = "échec") -> None:
        super().__init__(message)
        self.response = {"Error": {"Code": self.code, "Message": message}}


class ResourceNotFoundException(ErreurAWS):
    code = "ResourceNotFoundException"


class AccessDeniedException(ErreurAWS):
    code = "AccessDeniedException"


class NoCredentialsError(Exception):
    """L'erreur de botocore quand aucun identifiant n'est résoluble."""


class FauxClientRuntime:
    """Le faux client : la forme de l'API, et un carnet d'appels."""

    def __init__(self, reponse: dict[str, Any] | None = None, erreur: Exception | None = None) -> None:
        self.reponse = reponse if reponse is not None else _reponse_par_defaut()
        self.erreur = erreur
        self.appels: list[dict[str, Any]] = []

    def invoke_agent_runtime(self, **kwargs: Any) -> dict[str, Any]:
        self.appels.append(kwargs)
        if self.erreur is not None:
            raise self.erreur
        return dict(self.reponse)


class FauxSession:
    """Le faux `boto3.Session` : un client, et le nom du service demandé."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.services: list[str] = []

    def client(self, nom: str, **_: Any) -> Any:
        self.services.append(nom)
        return self._client


class FauxInvite:
    """Un invité minimal : le protocole `AgentInvite`, sans exécution."""

    nom = "agent-ticket"
    version = "3.4.1"
    instrumentable = True

    def executer(self, outils: Any, entree: Any) -> dict[str, Any]:  # pragma: no cover
        raise AssertionError("l'invité n'est pas exécuté par le runtime AWS")


def _reponse_par_defaut() -> dict[str, Any]:
    return {
        "response": io.BytesIO(b'{"reponse": "ticket lu"}'),
        "contentType": "application/json",
        "runtimeSessionId": "sess-1",
        "statusCode": 200,
    }


def _session_sas(session_id: str = "sess-1") -> Session:
    return Session(
        id=session_id,
        tenant_id="tenant-demo",
        campagne_id="campagne-1",
        scenario_id="S1",
        numero_rejeu=1,
        graine=7,
        identite=None,
        debut=maintenant(),
        fin=None,
        statut=StatutSession.EN_COURS,
    )


def _runtime(client: FauxClientRuntime) -> aws.RuntimeAWS:
    return aws.RuntimeAWS(FauxSession(client), arn_runtime=ARN)


# --------------------------------------------------------------------------- #
# Le contrat de l'appel
# --------------------------------------------------------------------------- #


def test_le_client_vise_le_service_de_donnees_agentcore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    session = FauxSession(client)
    aws.RuntimeAWS(session, arn_runtime=ARN).executer(_session_sas(), FauxInvite(), {"ticket": "T-1"})
    assert session.services == ["bedrock-agentcore"]
    assert len(client.appels) == 1


def test_l_appel_porte_le_contrat_de_l_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    _runtime(client).executer(_session_sas(), FauxInvite(), {"ticket": "T-1"})
    appel = client.appels[0]
    assert set(appel) == {
        "agentRuntimeArn",
        "runtimeSessionId",
        "qualifier",
        "payload",
        "contentType",
        "accept",
    }
    assert appel["agentRuntimeArn"] == ARN
    assert appel["runtimeSessionId"] == "sess-1"
    assert appel["qualifier"] == "DEFAULT"
    assert appel["contentType"] == "application/json"


def test_le_payload_est_le_json_de_l_invite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    _runtime(client).executer(_session_sas(), FauxInvite(), {"ticket": "T-1", "budget": 10})
    charge = json.loads(client.appels[0]["payload"].decode("utf-8"))
    assert charge["agent"] == "agent-ticket"
    assert charge["version"] == "3.4.1"
    assert charge["session_id"] == "sess-1"
    assert charge["scenario_id"] == "S1"
    assert charge["numero_rejeu"] == 1
    assert charge["entree"] == {"ticket": "T-1", "budget": 10}


def test_chaque_rejeu_a_sa_session_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """EF-11 : deux rejeux ne partagent jamais la même session runtime."""
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    runtime = _runtime(client)
    runtime.executer(_session_sas("sess-1"), FauxInvite(), {})
    runtime.executer(_session_sas("sess-2"), FauxInvite(), {})
    sessions = [appel["runtimeSessionId"] for appel in client.appels]
    assert sessions == ["sess-1", "sess-2"]


def test_la_reponse_de_l_invite_est_lue(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    runtime = _runtime(client)
    runtime.executer(_session_sas(), FauxInvite(), {})
    reponse = runtime.derniere_reponse()
    assert reponse["status_code"] == 200
    assert reponse["content_type"] == "application/json"
    assert reponse["contenu"] == '{"reponse": "ticket lu"}'


# --------------------------------------------------------------------------- #
# Les honnestetés : ce que l'appel refuse de faire, et ce qu'il dit
# --------------------------------------------------------------------------- #


def test_sans_le_drapeau_aucun_appel_n_est_tente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VARIABLE, raising=False)
    client = FauxClientRuntime()
    with pytest.raises(runtime_bedrock.ExecutionNonAutorisee) as refus:
        _runtime(client).executer(_session_sas(), FauxInvite(), {})
    assert client.appels == []
    assert VARIABLE in str(refus.value)
    assert "coût" in str(refus.value)


def test_un_runtime_absent_est_une_erreur_honnete(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()
    runtime = aws.RuntimeAWS(FauxSession(client), arn_runtime="")
    with pytest.raises(runtime_bedrock.ErreurExecutionAgentCore, match="runtime AgentCore absent"):
        runtime.executer(_session_sas(), FauxInvite(), {})
    assert client.appels == []


def test_sans_session_boto3_l_erreur_le_dit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    with pytest.raises(runtime_bedrock.ErreurExecutionAgentCore, match="session boto3"):
        aws.RuntimeAWS(None, arn_runtime=ARN).executer(_session_sas(), FauxInvite(), {})


def test_des_identifiants_absents_sont_remontes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime(erreur=NoCredentialsError("Unable to locate credentials"))
    with pytest.raises(runtime_bedrock.ErreurExecutionAgentCore, match="identifiants AWS absents"):
        _runtime(client).executer(_session_sas(), FauxInvite(), {})


def test_un_runtime_inexistant_est_remonte_comme_tel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime(erreur=ResourceNotFoundException("runtime not found"))
    with pytest.raises(runtime_bedrock.ErreurExecutionAgentCore) as refus:
        _runtime(client).executer(_session_sas(), FauxInvite(), {})
    assert "runtime AgentCore absent" in str(refus.value)
    assert ARN in str(refus.value)


def test_un_refus_aws_est_remonte_comme_tel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime(erreur=AccessDeniedException("not authorized"))
    with pytest.raises(runtime_bedrock.ErreurExecutionAgentCore, match="refus AWS"):
        _runtime(client).executer(_session_sas(), FauxInvite(), {})


def test_un_agent_non_instrumentable_n_est_jamais_invoque(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VARIABLE, "1")
    client = FauxClientRuntime()

    class Opaque(FauxInvite):
        instrumentable = False

    with pytest.raises(AgentNonInstrumentable):
        _runtime(client).executer(_session_sas(), Opaque(), {})
    assert client.appels == []


def test_le_module_ne_demande_pas_boto3() -> None:
    """boto3 reste importé paresseusement : le module ne l'importe pas."""
    source = Path(runtime_bedrock.__file__).read_text(encoding="utf-8")
    assert "import boto3" not in source
