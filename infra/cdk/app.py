"""CDK app: one stack per domain (lot 17).

The entry point ``main()`` builds the seven stacks (data, agent core,
orchestration, api, portal, observability, quick). Everything that imports
``aws_cdk`` stays inside the builder functions; this module can be imported by
the tests without aws-cdk-lib. ``_racine()`` puts the repo root and ``src/`` on
``sys.path`` so `cdk synth` works from `infra/cdk/` — documented in the RUNBOOK.

**The constructors exist but were never called**: until now `cdk synth`
produced seven *empty* stacks ("Resources section must exist and be non-empty"),
and the deployment had never happened. `_construire()` is where the
infrastructure becomes real — every resource comes from the builder of its
domain, and the tables come from `sas.store.ddl`, never from a hand-made copy.
"""

from __future__ import annotations

import os
import sys
from typing import Any


def _common():
    from infra.cdk import common  # lazy: keeps module import clean without cdk

    return common


def domaines() -> tuple[str, ...]:
    """The stack domains — one stack each, all tagged by ``common``."""
    return _common().domaines()


def _racine() -> str:
    """Repo root (two levels above this file)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _construire(piles: dict[str, Any]) -> None:
    """Build the resources of each stack.

    One call per domain, each one in its own stack: a domain can only create
    what belongs to it, and the tables are read from the DDL.
    """
    from infra.cdk import agentcore, api, data, observability, orchestration, portal, quick

    tables = data.tables_depuis_ddl()
    data.tables_cdk(piles["donnees"], tables)
    seau = data.seau_preuves_cdk(piles["donnees"])
    data.sorties_cdk(piles["donnees"], tables, seau)
    agentcore.agentcore_cdk(piles["agentcore"])
    orchestration.orchestration_cdk(piles["orchestration"])
    api.api_cdk(piles["api"])
    portal.portail_cdk(piles["portail"])
    observability.observabilite_cdk(piles["observabilite"])
    quick.quick_cdk(piles["quick"])


def main() -> None:
    """Synth the stacks. aws_cdk imported here only (never at module level)."""
    for chemin in (os.path.join(_racine(), "src"), _racine()):
        if chemin not in sys.path:
            sys.path.insert(0, chemin)
    import aws_cdk as cdk  # lazy on purpose: CI never runs `cdk synth`

    app = cdk.App()
    piles: dict[str, Any] = {}
    for domaine in domaines():
        pile = cdk.Stack(app, _common().nom_stack(domaine), env=cdk.Environment(region=_common().region()))
        for cle, valeur in _common().tags().items():
            cdk.Tags.of(pile).add(cle, valeur)
        piles[domaine] = pile
    _construire(piles)
    app.synth()


if __name__ == "__main__":
    main()
