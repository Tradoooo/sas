"""CDK app: one stack per domain (lot 17).

The entry point ``main()`` builds the seven stacks (data, agent core,
orchestration, api, portal, observability, quick). Everything that imports
``aws_cdk`` stays inside the builder functions; this module can be imported by
the tests without aws-cdk-lib. ``_racine()`` puts the repo root and ``src/`` on
``sys.path`` so `cdk synth` works from `infra/cdk/` — documented in the RUNBOOK.
"""

from __future__ import annotations

import os
import sys


def _common():
    from infra.cdk import common  # lazy: keeps module import clean without cdk

    return common


def domaines() -> tuple[str, ...]:
    """The stack domains — one stack each, all tagged by ``common``."""
    return _common().domaines()


def _racine() -> str:
    """Repo root (two levels above this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    """Synth the stacks. aws_cdk imported here only (never at module level)."""
    for chemin in (os.path.join(_racine(), "src"), _racine()):
        if chemin not in sys.path:
            sys.path.insert(0, chemin)
    import aws_cdk as cdk  # lazy on purpose: CI never runs `cdk synth`

    app = cdk.App()
    for domaine in domaines():
        cdk.Stack(app, _common().nom_stack(domaine), env=cdk.Environment(region=_common().region()))
    app.synth()


if __name__ == "__main__":
    main()
