"""CDK conventions shared by every stack (lot 17).

Pure Python — no aws-cdk import here nor anywhere at module level: the CI
runner has no ``aws-cdk-lib`` installed and must stay that way. Naming, tags
and the region are single-source here so the stacks cannot diverge on labels.
"""

from __future__ import annotations

import os

PREFIXE = "sas"
REGION_DEFAUT = "eu-west-3"
REGION_REPLI = "eu-central-1"

# One stack per domain (spec §20.1): data, agent core, orchestration, api,
# portal, observability, quick.
DOMAINES: tuple[str, ...] = (
    "donnees",
    "agentcore",
    "orchestration",
    "api",
    "portail",
    "observabilite",
    "quick",
)


def env() -> str:
    """Deployment environment, from SAS_ENV (never from a hard-coded guess)."""
    return (os.environ.get("SAS_ENV", "dev") or "dev").strip()


def region() -> str:
    """AgentCore region with the documented fallback (§34 point 1)."""
    return (os.environ.get("SAS_AWS_REGION", "") or REGION_DEFAUT).strip()


def nom_ressource(domaine: str, nom: str) -> str:
    """Deterministic resource name, e.g. ``sas-donnees-journal-dev``."""
    return f"{PREFIXE}-{domaine}-{nom}-{env()}"


def nom_stack(domaine: str) -> str:
    return f"{PREFIXE}-{domaine}-{env()}"


def tags() -> dict[str, str]:
    """The single tag set applied everywhere — used for budget attribution (§26)."""
    return {"projet": "sas", "lot": "16-17", "environnement": env()}


def domaines() -> tuple[str, ...]:
    """The list of CDK stacks. Tested so a new domain cannot go untagged."""
    return DOMAINES
