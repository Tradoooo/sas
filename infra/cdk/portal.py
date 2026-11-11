"""Static portal: S3 + CloudFront (lot 17).

The portal is a static site (no build step, no external CDN, no runtime
network — spec §26.4 rule 5: no permanent model endpoint, no GPU). It reads the
API of §23; the route inventory is frozen in ``sas.constantes.ROUTES``.
"""

from __future__ import annotations

from typing import Any


def portail() -> dict[str, Any]:
    """The static-site config: S3 origin + CloudFront, everything encrypted."""
    return {
        "origine": "s3:portail",
        "cdn": "cloudfront",
        "https": "obligatoire",
        "index": "index.html",
    }


def portail_cdk(scope: Any) -> Any:
    """Build S3 + CloudFront. ``aws_cdk`` imported here only."""
    import aws_cdk as cdk  # lazy on purpose
    from aws_cdk import aws_cloudfront as cloudfront
    from aws_cdk import aws_s3 as s3

    seau = s3.Bucket(
        scope,
        "portail",
        website_index_document="index.html",
        encryption=s3.BucketEncryption.S3_MANAGED,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
    )
    dist = cloudfront.Distribution(
        scope,
        "portail-distribution",
        default_behavior=cloudfront.BehaviorOptions(origin=cloudfront.S3Origin(seau)),
    )
    cdk.Tags.of(dist).add("projet", "sas")
    return dist
