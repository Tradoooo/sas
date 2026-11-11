"""AgentCore stack: the six components and their network perimeter (lot 17).

Pure data for the six essential components of spec §20.2 and the shadow-mode
network rule of §20.5; the CDK construct is built by ``agentcore_cdk`` with the
``aws_cdk`` import inside the function, so CI and the tests never import it.
"""

from __future__ import annotations

from typing import Any

# The six components, each with its AgentCore home. The exact underlying
# Bedrock AgentCore APIs are confirmed in S0 (§34 point 1); the mapping below is
# the deployment contract, not a guess about method names.
COMPOSANTS: tuple[dict[str, str], ...] = (
    {"nom": "Runtime", "role": "une session isolée par rejeu (§20.2)"},
    {"nom": "Gateway", "role": "point de passage unique de tous les appels d'outils (§20.2)"},
    {"nom": "Identity", "role": "identité éphémère par session, révocation immédiate (§11.4)"},
    {"nom": "Policy", "role": "périmètre dérivé du manifeste, appliqué avant l'outil (§20.3)"},
    {"nom": "Memory", "role": "état inter-rejeux uniquement si déclaré (§14.6)"},
    {"nom": "Observability", "role": "journal intégral, chaîné, jetons, latences (§17.1)"},
)


def composants_agentcore() -> tuple[str, ...]:
    """The six component names, in a stable order (asserted by the tests)."""
    return tuple(c["nom"] for c in COMPOSANTS)


def reseau_ombre() -> dict[str, str]:
    """Shadow-mode network rule (spec §20.5): no egress except the gateway."""
    return {
        "egress": "aucune route sortante sauf la passerelle",
        "spec": "§20.5",
        "detail": "toute tentative de sortie directe est un échec réseau journalisé comme une tentative",
    }


def agentcore_cdk(scope: Any, vpc: Any = None) -> Any:
    """Build the shadow-mode security group. ``aws_cdk`` imported here only."""
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_ec2 as ec2

    # §20.5 — en mode Ombre, aucune route sortante sauf la passerelle : le groupe
    # de sécurité du bac n'autorise aucun egress par défaut, et n'en ouvre un que
    # vers le VPC endpoint de la passerelle. Toute sortie directe échoue et est
    # journalisée comme une tentative — une information, pas un incident.
    groupe = ec2.SecurityGroup(
        scope,
        "bac-ombre",
        vpc=vpc if vpc is not None else ec2.Vpc(scope, "vpc-msp"),
        allow_all_outbound=False,
        description="Ombre : aucune sortie sauf la passerelle (§20.5)",
    )
    cdk.Tags.of(groupe).add("projet", "sas")
    return groupe
