"""DynamoDB generated from ``sas.store.ddl`` + the S3 evidence bucket (lot 17).

The table definitions are the single source of truth: ``tables_depuis_ddl()``
reads ``sas.store.ddl.DEFINITIONS`` and the CDK tables are built from exactly
that list — never from a hand-written copy — so a schema change cannot drift
between the infrastructure and the code. ``test_ddl_sync.py`` enforces it.

``tables_cdk`` and ``seau_preuves_cdk`` hold the ``aws_cdk`` import **inside**
the function: the module stays importable on an offline runner without
aws-cdk-lib, and ``python3 -m pytest`` never imports aws_cdk.
"""

from __future__ import annotations

from typing import Any

from sas.store import ddl


def tables_depuis_ddl() -> list[dict[str, Any]]:
    """Read the 15 table definitions of ``sas.store.ddl`` into plain dicts.

    Each dict carries: ``nom``, ``partition``, ``tri`` (sort key or None),
    ``index`` (the global secondary indexes) and ``ttl`` (attr name or None).
    """
    resultats: list[dict[str, Any]] = []
    for nom in ddl.TABLES:
        definition = ddl.DEFINITIONS[nom]
        resultats.append(
            {
                "nom": definition.nom,
                "partition": definition.attributs_cles[0],
                "tri": definition.attributs_cles[1] if len(definition.attributs_cles) > 1 else None,
                "index": [{"nom": attribut, "cle": attribut} for attribut, _ in definition.index],
                "ttl": definition.ttl,
                "notes": definition.notes,
            }
        )
    return resultats


def noms_tables() -> tuple[str, ...]:
    """The 15 table names, from the definitions (asserted equal to TABLES)."""
    return tuple(t["nom"] for t in tables_depuis_ddl())


def tables_cdk(scope: Any, tables: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the real DynamoDB tables. ``aws_cdk`` imported here, nowhere else."""
    import aws_cdk as cdk  # lazy on purpose: CI never synths CDK
    from aws_cdk import aws_dynamodb as dynamodb

    construites: dict[str, Any] = {}
    for definition in tables:
        cle = dynamodb.Attribute(name=definition["partition"], type=dynamodb.AttributeType.STRING)
        table = dynamodb.Table(
            scope,
            definition["nom"],
            partition_key=cle,
            sort_key=_cle_tri(definition),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            point_in_time_recovery=True,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            time_to_live_attribute=definition["ttl"],
        )
        _index_cdk(table, definition["index"])
        cdk.Tags.of(table).add("source", "sas.store.ddl")
        construites[definition["nom"]] = table
    return construites


def _cle_tri(definition: dict[str, Any]) -> Any:
    from aws_cdk import aws_dynamodb as dynamodb  # lazy

    if definition["tri"] is None:
        return None
    return dynamodb.Attribute(name=definition["tri"], type=dynamodb.AttributeType.STRING)


def _index_cdk(table: Any, index: list[dict[str, str]]) -> None:
    from aws_cdk import aws_dynamodb as dynamodb  # lazy

    for indice in index:
        table.add_global_secondary_index(
            partition_key=dynamodb.Attribute(name=indice["cle"], type=dynamodb.AttributeType.STRING),
            index_name=indice["nom"],
        )


def seau_preuves() -> dict[str, Any]:
    """The evidence bucket config: journals, shadow-destruction proofs, attestations."""
    return {"nom": "preuves", "chiffrement": True, "versionnage": True}


def seau_preuves_cdk(scope: Any) -> Any:
    """Build the S3 evidence bucket. ``aws_cdk`` imported here, nowhere else."""
    import aws_cdk as cdk  # lazy
    from aws_cdk import aws_s3 as s3

    seau = s3.Bucket(
        scope,
        "preuves",
        versioned=True,
        encryption=s3.BucketEncryption.S3_MANAGED,
        enforce_ssl=True,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    )
    cdk.Tags.of(seau).add("projet", "sas")
    return seau
