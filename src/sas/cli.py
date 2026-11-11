"""Command line entry point: `sas smoke`, `sas demo`, `sas attestation`.

Everything runs **offline** against the local AgentCore backend, on synthetic
data, with no AWS account and no model call. That is what CI executes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from sas import constantes
from sas.cli_demo import executer_demo
from sas.cli_smoke import executer_smoke

RACINE = Path(__file__).resolve().parents[2]


def construire_parseur() -> argparse.ArgumentParser:
    parseur = argparse.ArgumentParser(
        prog="sas",
        description="Sas — homologation and controlled execution of third-party AI agents.",
    )
    sous = parseur.add_subparsers(dest="commande", required=True)

    smoke = sous.add_parser("smoke", help="one shadow campaign, 2 scenarios, complete journal")
    smoke.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT, help="replays per scenario")
    smoke.add_argument("--graine", type=int, default=7)

    demo = sous.add_parser("demo", help="the 3-minute demo: 3 synthetic guests, 3 verdicts")
    demo.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT)
    demo.add_argument("--graine", type=int, default=11)
    demo.add_argument(
        "--agent", default="", help="run a single guest (demo-conforme|demo-bavard|demo-curieux)"
    )
    demo.add_argument("--scenarios", default="", help="comma separated scenario ids (default: the eight)")

    return parseur


def main(argv: Sequence[str] | None = None) -> int:
    args = construire_parseur().parse_args(list(argv) if argv is not None else None)
    if args.commande == "smoke":
        return executer_smoke(rejeux=args.rejeux, graine=args.graine)
    if args.commande == "demo":
        scenarios = tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
        return executer_demo(rejeux=args.rejeux, graine=args.graine, agent=args.agent, scenarios=scenarios)
    return 2


if __name__ == "__main__":
    sys.exit(main())
