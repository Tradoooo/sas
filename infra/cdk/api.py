"""API Gateway + Lambda + Cognito config (lot 17).

Every route of ``sas.constantes.ROUTES`` gets exactly one declared handler — a
deterministic ``sas.api`` name — so no route of spec §23 (the frozen inventory)
can ship without an implementation. The tenant never comes from a path: it is
derived from the Cognito token claim (EF-51, §25).
"""

from __future__ import annotations

from typing import Any

from sas import constantes


def _handler_nom(methode: str, chemin: str) -> str:
    """Deterministic handler name from a route — stable, no hand-made mapping."""
    parties = "".join(c if c.isalnum() else "_" for c in chemin).strip("_")
    return f"sas.api.{methode.lower()}:{parties or 'racine'}"


def handlers() -> tuple[dict[str, str], ...]:
    """One declared handler per route of the frozen inventory (§23)."""
    return tuple(
        {"methode": methode, "chemin": chemin, "handler": _handler_nom(methode, chemin)}
        for methode, chemin in constantes.ROUTES
    )


def cognito() -> dict[str, Any]:
    """Cognito user pool config: the tenant id comes from the token, never the URL."""
    return {
        "nom": "identite-msp",
        "attribut_tenant": "custom:tenant_id",
        "regle_cle": "EF-51 — aucune route n'accepte un tenant en paramètre",
    }


def api_cdk(scope: Any) -> Any:
    """Build the API. ``aws_cdk`` imported here only."""
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_apigateway as apigw

    api = apigw.RestApi(scope, "portail", description="API du portail Sas (§23)")
    for handler in handlers():
        api.root.add_resource(handler["chemin"].lstrip("/"))
    cdk.Tags.of(api).add("projet", "sas")
    return api
