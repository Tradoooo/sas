"""From a declared resource to its shadow replica (spec §10.1, §21.2).

A shadow campaign never touches the real resource: the policy derived from the
manifest is **mapped onto the replica**, so the guest sees the same names with
the tenant suffix replaced by `-ombre`, and the same structures with synthetic
content.

One rule, one place. Annexe F.2 follows it exactly:

    arn:aws:s3:::client-tickets/entree/*  ->  client-tickets-ombre/entree
    kb-documentation-client               ->  kb-documentation-ombre
    dynamodb:suivi-client                 ->  dynamodb:suivi-ombre
"""

from __future__ import annotations

from sas.ombre.support import normaliser

SUFFIXE_CLIENT = "-client"
SUFFIXE_OMBRE = "-ombre"
SEPARATEURS_TABLE = (":",)


def replique(ressource: str) -> str:
    """The shadow name of a declared resource."""
    cible = normaliser(ressource)
    if SUFFIXE_OMBRE in cible:
        return cible
    for separateur in SEPARATEURS_TABLE:
        if separateur in cible:
            prefixe, reste = cible.split(separateur, 1)
            return f"{prefixe}{separateur}{_ombree(reste)}"
    premier, _, suite = cible.partition("/")
    ombre = _ombree(premier)
    return f"{ombre}/{suite.rstrip('*').rstrip('/')}" if suite else ombre


def _ombree(nom: str) -> str:
    racine = nom[: -len(SUFFIXE_CLIENT)] if nom.endswith(SUFFIXE_CLIENT) else nom
    return f"{racine}{SUFFIXE_OMBRE}"


def est_replique(ressource: str) -> bool:
    return SUFFIXE_OMBRE in normaliser(ressource)


def table_repliquees(ressources: tuple[str, ...]) -> tuple[str, ...]:
    """Map a whole declaration onto the replica, keeping the order."""
    return tuple(replique(r) for r in ressources)
