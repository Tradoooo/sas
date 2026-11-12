"""Human-readable labels for the interfaces, built from `sas.i18n`.

The portal must never show a raw enumeration value to a reader: `HOMOLOGUE_SOUS_
CONDITIONS` is an identifier, "Homologué sous conditions" is a verdict. The
labels live once, in `sas.i18n`; this module projects them into the two shapes
the front end needs (the static dataset and the API health response), so there
is no second copy to drift.
"""

from __future__ import annotations

from typing import Any

from sas.i18n import CLES
from sas.types import Langue, Nature, Verdict

FAMILLES: dict[str, tuple[str, ...]] = {
    "verdict": tuple(v.value for v in Verdict),
    "nature": tuple(n.value for n in Nature),
}


def _cle(famille: str, valeur: str) -> str:
    return f"{famille}.{valeur}"


def libelles(langue: Langue = Langue.FR) -> dict[str, dict[str, str]]:
    """`{famille: {valeur: libellé}}` for one language."""
    sortie: dict[str, dict[str, str]] = {}
    for famille, valeurs in FAMILLES.items():
        sortie[famille] = {
            valeur: CLES[_cle(famille, valeur)][0 if langue is Langue.FR else 1] for valeur in valeurs
        }
    return sortie


def tous() -> dict[str, Any]:
    """Both languages at once — what the portal dataset and /health carry."""
    return {"fr": libelles(Langue.FR), "en": libelles(Langue.EN), "mode": _modes()}


def _modes() -> dict[str, dict[str, str]]:
    return {
        langue.value: {
            "ombre": CLES["mode.ombre"][0 if langue is Langue.FR else 1],
            "observe": CLES["mode.observe"][0 if langue is Langue.FR else 1],
        }
        for langue in (Langue.FR, Langue.EN)
    }


def verdict(valeur: str, langue: Langue = Langue.FR) -> str:
    """One label, with the identifier as fallback rather than a crash."""
    table = libelles(langue)["verdict"]
    return table.get(valeur, valeur)


def nature(valeur: str, langue: Langue = Langue.FR) -> str:
    table = libelles(langue)["nature"]
    return table.get(valeur, valeur)
