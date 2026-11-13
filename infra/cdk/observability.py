"""CloudWatch availability and budget alarms (lot 17).

The availability alarm keeps the public URL alive until the 22 January 2027
deadline (§32), the budget alarm enforces the 200 $ credit budget of §26.4.
Both are described as pure data so the tests can assert they exist, and built
by ``observabilite_cdk`` with the ``aws_cdk`` import inside the function.
"""

from __future__ import annotations

from typing import Any

from sas import constantes

# The six budget-keeping rules of §26.4, quoted here so the RUNBOOK and the
# stack cannot drift apart.
REGLES_BUDGET: tuple[str, ...] = (
    "développement et recette en Nova Lite uniquement (§26.4.1)",
    "N = 2 en développement, N = 6 seulement pour les campagnes de démonstration (§26.4.2)",
    "budget d'appels plafonné dans le code par session et par campagne (§26.4.3, ENF-03)",
    "coût mesuré dès la première campagne, jamais découvert en fin de mois (§26.4.4, ENF-10)",
    "aucun endpoint de modèle dédié, aucun SageMaker permanent, aucune GPU (§26.4.5)",
    "environnements Ombre détruits en fin de campagne avec preuve (§26.4.6, ENF-06)",
)


def alarmes() -> tuple[dict[str, Any], ...]:
    """Availability + budget alarms, as data."""
    return (
        {
            "nom": "disponibilite-api",
            "metrique": "5xxErrorRate",
            "seuil": 1,
            "evaluation_periodes": 5,
            "spec": "§32 — l'URL publique ne doit pas tomber avant le 22 janvier 2027",
        },
        {
            "nom": "budget-200",
            "seuil_usd": int(constantes.BUDGET_CREDITS),
            "seuil_alerte": int(constantes.BUDGET_CREDITS) - int(constantes.RESERVE_INFRASTRUCTURE),
            "spec": "§26.4 — budget de 200 $ de crédits",
        },
    )


def regles_budget() -> tuple[str, ...]:
    """The six budget-keeping rules of §26.4, in the RUNBOOK too."""
    return REGLES_BUDGET


def observabilite_cdk(scope: Any) -> Any:
    """Build CloudWatch alarms. ``aws_cdk`` imported here only."""
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_cloudwatch as cloudwatch

    for alarme in alarmes():
        cloudwatch.Alarm(
            scope,
            alarme["nom"],
            metric=_metrique(alarme),
            threshold=alarme.get("seuil", alarme.get("seuil_alerte")),
            evaluation_periods=alarme.get("evaluation_periodes", 1),
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
    cdk.Tags.of(scope).add("projet", "sas")
    return None


def _metrique(alarme: dict[str, Any]) -> Any:
    """The metric an alarm watches.

    An alarm without a metric does not exist (CloudWatch refuses it), so each
    declared alarm names the metric it watches: the API's 5xx rate for the
    availability rule, the estimated charges for the budget rule (§26.4).
    """
    from aws_cdk import aws_cloudwatch as cloudwatch

    if "metrique" in alarme:
        return cloudwatch.Metric(
            namespace="AWS/ApiGateway",
            metric_name=alarme["metrique"],
            statistic="Sum",
        )
    return cloudwatch.Metric(
        namespace="AWS/Billing",
        metric_name="EstimatedCharges",
        statistic="Maximum",
    )
