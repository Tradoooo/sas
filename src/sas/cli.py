"""Command line entry point: `sas smoke`, `sas demo`, `sas attestation`.

Everything runs **offline** against the local AgentCore backend, on synthetic
data, with no AWS account and no model call. That is what CI executes.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

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
    _commande_smoke(sous)
    _commande_demo(sous)
    _commande_portail(sous)
    _commande_attestation(sous)
    _commande_mcp(sous)
    return parseur


def _commande_smoke(sous: Any) -> None:
    smoke = sous.add_parser("smoke", help="one shadow campaign, 2 scenarios, complete journal")
    smoke.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT, help="replays per scenario")
    smoke.add_argument("--graine", type=int, default=7)


def _commande_demo(sous: Any) -> None:
    demo = sous.add_parser("demo", help="the 3-minute demo: 3 synthetic guests, 3 verdicts")
    demo.add_argument("--rejeux", type=int, default=constantes.N_DEVELOPPEMENT)
    demo.add_argument("--graine", type=int, default=11)
    demo.add_argument(
        "--agent", default="", help="run a single guest (demo-conforme|demo-bavard|demo-curieux)"
    )
    demo.add_argument("--scenarios", default="", help="comma separated scenario ids (default: the eight)")
    demo.add_argument(
        "--store",
        default="memoire",
        choices=("memoire", "dynamodb"),
        help="où la campagne est écrite : rien (défaut) ou les vraies tables DynamoDB",
    )
    demo.add_argument("--tenant", default="tenant-demo", help="tenant de la campagne (store réel)")
    demo.add_argument("--region", default="eu-west-3", help="région AWS du store réel")
    demo.add_argument("--pile", default="sas-donnees-dev", help="pile CloudFormation du store réel")


def _commande_portail(sous: Any) -> None:
    portail = sous.add_parser("portail", help="serve the portal and the API on one origin")
    portail.add_argument("--port", type=int, default=8123)
    portail.add_argument("--hote", default="127.0.0.1")


def _commande_attestation(sous: Any) -> None:
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


def _commande_mcp(sous: Any) -> None:
    mcp = sous.add_parser(
        "mcp",
        help="expose the gateway as an MCP server on stdio (any MCP agent plugs in)",
    )
    mcp.add_argument("manifeste", help="chemin du manifeste signé (YAML ou JSON)")
    mcp.add_argument("--mode", default="ombre", choices=("ombre", "observe"))
    mcp.add_argument("--tenant", default="tenant-demo")
    mcp.add_argument("--graine", type=int, default=0)


def _ouvrir_store(args: object) -> object:
    """The real store, opened from the deployed stack's own outputs.

    The table names are read from the CloudFormation stack, so the demo cannot
    write to a table that does not exist — and a wrong stack name fails loudly
    instead of writing nowhere.
    """
    from sas.store.dynamodb import ouvrir

    return ouvrir(
        getattr(args, "tenant", "tenant-demo"),
        region=getattr(args, "region", "eu-west-3"),
        pile=getattr(args, "pile", "sas-donnees-dev"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = construire_parseur().parse_args(list(argv) if argv is not None else None)
    if args.commande == "smoke":
        return executer_smoke(rejeux=args.rejeux, graine=args.graine)
    if args.commande == "demo":
        scenarios = tuple(s.strip() for s in args.scenarios.split(",") if s.strip())
        depot = _ouvrir_store(args) if getattr(args, "store", "memoire") == "dynamodb" else None
        return executer_demo(
            rejeux=args.rejeux,
            graine=args.graine,
            agent=args.agent,
            scenarios=scenarios,
            depot=depot,
            tenant_id=args.tenant,
        )
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
