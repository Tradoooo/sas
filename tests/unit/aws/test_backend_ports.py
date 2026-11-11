"""The AWS backend satisfies the six port Protocols, offline (lot 17).

Nothing here imports boto3 or calls AWS: the classes are built with doubles (or
plain ``None``) and checked with ``isinstance`` against the frozen protocols,
plus the module is scanned so each AgentCore component is really named in it
(the check ``scripts/check_contest.py`` runs for the special prize).
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from sas.agentcore import aws, ports

AGENTCORE = ("Runtime", "Gateway", "Identity", "Policy", "Memory", "Observability")


def test_six_composants_nommes_dans_le_module() -> None:
    source = Path(aws.__file__).read_text(encoding="utf-8")
    for composant in AGENTCORE:
        assert composant in source


def test_runtime_satisfait_le_port() -> None:
    assert isinstance(aws.RuntimeAWS(), ports.Runtime)


def test_identity_satisfait_le_port() -> None:
    assert isinstance(aws.IdentityAWS(), ports.Identity)


def test_policy_satisfait_le_port() -> None:
    assert isinstance(aws.PolicyAWS(), ports.Policy)


def test_gateway_satisfait_le_port() -> None:
    passerelle = aws.GatewayAWS(aws.PolicyAWS(), aws.IdentityAWS(), aws.ObservabilityAWS())
    assert isinstance(passerelle, ports.Gateway)


def test_memory_satisfait_le_port() -> None:
    assert isinstance(aws.MemoryAWS(), ports.Memory)


def test_observabilite_satisfait_le_port() -> None:
    assert isinstance(aws.ObservabilityAWS(), ports.Observability)


def test_region_defaut_et_repli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SAS_AWS_REGION", raising=False)
    assert aws.region_config() == "eu-west-3"


def test_region_explicite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SAS_AWS_REGION", "eu-east-1")
    assert aws.region_config() == "eu-east-1"


def _faux_boto3_sans_identifiants() -> SimpleNamespace:
    return SimpleNamespace(Session=lambda **kwargs: SimpleNamespace(get_credentials=lambda: None))


def test_detection_identifiants_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "cle")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert aws._identifiants_presents(_faux_boto3_sans_identifiants()) is True


def test_sans_identifiants_detecte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert aws._identifiants_presents(_faux_boto3_sans_identifiants()) is False


def test_backend_leve_une_erreur_honnete_sans_identifiants(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(aws, "_boto3", lambda: object())
    monkeypatch.setattr(aws, "_identifiants_presents", lambda _boto3: False)
    with pytest.raises(aws.ErreurBackendAWS, match="identifiants AWS"):
        aws.backend()


def test_backend_leve_une_erreur_honnete_sans_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    def sans_boto3() -> None:
        raise aws.ErreurBackendAWS("le backend AWS exige boto3")

    monkeypatch.setattr(aws, "_boto3", sans_boto3)
    with pytest.raises(aws.ErreurBackendAWS, match="boto3"):
        aws.backend()
