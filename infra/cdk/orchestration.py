"""Step Functions orchestration of the replays (spec §21.3).

The replay path is expressed as pure data: for each scenario, for each replay,
create the session, arm the ephemeral identity, reset the shadow, run, collect
the journal, destroy — with bounded parallelism and a global budget check at
every iteration, plus a clean stop on suspension.
"""

from __future__ import annotations

from typing import Any

ETAPES_REJEU: tuple[str, ...] = (
    "creer_session",
    "armer_identite",
    "reinitialiser_ombre",
    "executer",
    "collecter_journal",
    "detruire",
)

PARALLELISME_BORNE = 4


def etapes_rejeu() -> tuple[str, ...]:
    """The six steps of a single replay (§21.3)."""
    return ETAPES_REJEU


def definition_sfn() -> dict[str, Any]:
    """The deterministic state-machine definition, JSON-able and stable."""
    etats: dict[str, Any] = {}
    for index, etape in enumerate(ETAPES_REJEU):
        etats[etape] = {
            "Type": "Task",
            "Resource": "arn:aws:states:::lambda:invoke",
            "Parameters": {"FunctionName": f"sas-lambdas-{etape}"},
        }
        if index < len(ETAPES_REJEU) - 1:
            etats[etape]["Next"] = ETAPES_REJEU[index + 1]
        else:
            etats[etape]["End"] = True
    return {
        "Comment": "Parcours des rejeux d'homologation - spec §21.3",
        "StartAt": "VerifierBudget",
        "States": {
            "VerifierBudget": {
                "Type": "Choice",
                "Choices": [{"Variable": "$.budget_restant", "NumericGreaterThan": 0, "Next": "ParScenario"}],
                "Default": "Suspendu",
            },
            "ParScenario": {
                "Type": "Map",
                "ItemsPath": "$.scenarios",
                "MaxConcurrency": PARALLELISME_BORNE,
                "Iterator": {
                    "StartAt": "ParRejeu",
                    "States": {
                        "ParRejeu": {
                            "Type": "Map",
                            "ItemsPath": "$.rejeux",
                            "MaxConcurrency": PARALLELISME_BORNE,
                            "Iterator": {"StartAt": ETAPES_REJEU[0], "States": etats},
                            "End": True,
                        }
                    },
                },
                "End": True,
            },
            "Suspendu": {"Type": "Pass", "End": True},
        },
    }


def orchestration_cdk(scope: Any, definition: dict[str, Any] | None = None) -> Any:
    """Build the state machine. ``aws_cdk`` imported here only."""
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_stepfunctions as sfn

    machine = sfn.StateMachine(
        scope,
        "orchestrateur-rejeux",
        definition_body=sfn.DefinitionBody.from_string(str(definition or definition_sfn())),
    )
    cdk.Tags.of(machine).add("projet", "sas")
    return machine
