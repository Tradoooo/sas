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

    portail = sous.add_parser("portail", help="serve the portal and the API on one origin")
    portail.add_argument("--port", type=int, default=8123)
    portail.add_argument("--hote", default="127.0.0.1")

    attestation = sous.add_parser(
        "attestation", help="print or export the attestation of a campaign (text, html or pdf)"
    )
    attestation.add_argument("--agent", default="demo-conforme")
    attestation.add_argument("--scenarios", default="S1,S4")
    attestation.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT)
    attestation.add_argument("--graine", type=int, default=7)
    attestation.add_argument("--langue", default="fr", choices=("fr", "en"))
    attestation.add_argument("--format", dest="fmt", default="texte", choices=("texte", "html", "pdf"))
    attestation.add_argument("--sortie", default="", help="output file (default: <numero>.pdf|.html)")
    attestation.add_argument("--derniere", action="store_true", help="accepted for symmetry; no store yet")

    mcp = sous.add_parser(
        "mcp",
        help="expose the gateway as an MCP server on stdio (any MCP agent plugs in)",
    )
    mcp.add_argument("manifeste", help="chemin du manifeste signé (YAML ou JSON)")
    mcp.add_argument("--mode", default="ombre", choices=("ombre", "observe"))
    mcp.add_argument("--tenant", default="tenant-demo")
    mcp.add_argument("--graine", type=int, default=0)

    return parseur


def main(argv: Sequence[str] | None = None) -> int:
    args = construire_parseur().parse_args(list(argv) if argv is not None else None)
    if args.commande == "smoke":
        return executer_smoke(rejeux=args.rejeux, graine=args.graine)
    if args.commande == "demo":
        scenarios = tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
        return executer_demo(rejeux=args.rejeux, graine=args.graine, agent=args.agent, scenarios=scenarios)
    if args.commande == "portail":
        from sas.cli_portail import servir

        return servir(port=args.port, hote=args.hote)
    if args.commande == "attestation":
        from sas.cli_attestation import executer_attestation

        return executer_attestation(
            agent=args.agent,
            scenarios=tuple(s.strip() for s in args.scenarios.split(",") if s.strip()),
            rejeux=args.rejeux,
            graine=args.graine,
            langue=args.langue,
            sortie=args.sortie,
            fmt=args.fmt,
        )
    if args.commande == "mcp":
        from sas.mcp.serveur import main as mcp_main

        return mcp_main(
            [
                args.manifeste,
                "--mode",
                args.mode,
                "--tenant",
                args.tenant,
                "--graine",
                str(args.graine),
            ]
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
