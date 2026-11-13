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
    """Build the identity pool and the REST API. ``aws_cdk`` imported here only.

    The Cognito pool is deployed now: it is the identity the tokens come from
    (the tenant claim, EF-51), and it costs nothing until it is used.

    The REST API is created here too, with one resource per path segment of
    the frozen inventory (§23) — but **no method yet**: API Gateway refuses a
    REST API without a single method ("The REST API doesn't contain any
    methods"), and a method needs an integration. The integration is a Lambda
    running the real `sas.api` application; that handler is the next piece
    (lot 18), and until it exists the stack would be invalid and could not be
    deployed at all. Nothing here pretends the API is live.
    """
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_cognito as cognito

    pile = cognito.UserPool(
        scope,
        "identite-msp",
        user_pool_name="identite-msp",
        sign_in_aliases=cognito.SignInAliases(email=True, username=True),
        custom_attributes={
            "custom:tenant_id": cognito.StringAttribute(mutable=True),
            "custom:role": cognito.StringAttribute(mutable=True),
        },
        removal_policy=cdk.RemovalPolicy.DESTROY,
    )
    client = pile.add_client(
        "portail", generate_secret=False, auth_flows=cognito.AuthFlow(admin_user_password=True)
    )
    cdk.Tags.of(pile).add("projet", "sas")
    cdk.CfnOutput(scope, "UserPoolId", value=pile.user_pool_id)
    cdk.CfnOutput(scope, "UserPoolClientId", value=client.user_pool_client_id)
    return pile


def _ressource(api: Any, chemin: str, cache: dict[tuple[str, str], Any]) -> Any:
    """Kept for lot 18: the REST API is created with its Lambda integration."""
    """One API Gateway resource per path segment, shared between the routes.

    API Gateway does not accept a whole path in one part: 'manifestes/{id}/valider'
    is three resources ('manifestes', '{id}', 'valider'), and the braces are
    legal only as a whole part. Several routes share a prefix — '/manifestes'
    and '/manifestes/{id}' — so a resource already created is reused, not
    created twice (API Gateway refuses a duplicate part).
    """
    ressource = api.root
    for partie in chemin.strip("/").split("/"):
        cle = (ressource.node.path, partie)
        if cle not in cache:
            cache[cle] = ressource.add_resource(partie)
        ressource = cache[cle]
    return ressource
