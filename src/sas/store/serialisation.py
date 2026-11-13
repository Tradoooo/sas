"""Sas — dataclasses to JSON, for the DynamoDB backend (lot 18).

The local backend keeps the objects in memory; the DynamoDB backend must write
them and read them back. This module is that bridge, and it is **generic**:
it walks the dataclass fields themselves, so a new field is persisted without
touching a single line here — the type of the field says how it is written and
how it is read back.

Two rules, both from the data model of §22:

* an enum is written by its **value** (never by its name), so a renamed
  enumeration does not orphan the rows already written;
* a datetime is written in ISO-8601, and a `Decimal` as a string, so no float
  ever appears in the evidence (a binary float would not round-trip).
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import types
import typing
from collections.abc import Mapping
from decimal import Decimal
from enum import Enum
from typing import Any

VIDE = object()


def vers_json(objet: Any) -> str:
    """Serialize any domain object to a canonical JSON string."""
    return json.dumps(_vers_json(objet), sort_keys=True, ensure_ascii=False, default=str)


def depuis_json(texte: str, classe: type) -> Any:
    """Rebuild a domain object from its JSON form. The class drives the rebuild."""
    return _depuis_json(json.loads(texte), classe)


def _vers_json(valeur: Any) -> Any:
    if dataclasses.is_dataclass(valeur) and not isinstance(valeur, type):
        return {champ.name: _vers_json(getattr(valeur, champ.name)) for champ in dataclasses.fields(valeur)}
    if isinstance(valeur, Enum):
        return valeur.value
    if isinstance(valeur, dt.datetime):
        return valeur.astimezone(dt.UTC).isoformat()
    if isinstance(valeur, dt.date):
        return valeur.isoformat()
    if isinstance(valeur, Decimal):
        return f"dec:{valeur}"
    if isinstance(valeur, Mapping):
        return {str(cle): _vers_json(item) for cle, item in valeur.items()}
    if isinstance(valeur, (list, tuple, set, frozenset)):
        return [_vers_json(item) for item in valeur]
    return valeur


def _depuis_json(valeur: Any, type_: Any) -> Any:
    """Rebuild one value, guided by the declared type."""
    if type_ is Any or type_ is None or type_ is VIDE:
        return valeur
    origine = typing.get_origin(type_)
    if origine in (typing.Union, types.UnionType):
        return _depuis_union(valeur, typing.get_args(type_))
    if origine in (tuple, list, set, frozenset):
        return _depuis_collection(valeur, type_, origine)
    if origine in (dict, Mapping) or origine is dict:
        return _depuis_mapping(valeur, typing.get_args(type_))
    if isinstance(type_, type) and dataclasses.is_dataclass(type_):
        return _depuis_dataclass(valeur, type_)
    if isinstance(type_, type) and issubclass(type_, Enum):
        return type_(valeur)
    if type_ is dt.datetime:
        return dt.datetime.fromisoformat(valeur)
    if type_ is dt.date:
        return dt.date.fromisoformat(valeur)
    if type_ is Decimal:
        return Decimal(str(valeur).removeprefix("dec:"))
    return valeur


def _depuis_union(valeur: Any, options: tuple[Any, ...]) -> Any:
    """`Optional[X]` and friends: the first option that accepts the value wins."""
    if valeur is None and type(None) in options:
        return None
    for option in options:
        if option is type(None):
            continue
        try:
            return _depuis_json(valeur, option)
        except (TypeError, ValueError, KeyError):
            continue
    return valeur


def _depuis_collection(valeur: Any, type_: Any, origine: Any) -> Any:
    arguments = typing.get_args(type_)
    type_item = arguments[0] if arguments else Any
    elements = [_depuis_json(item, type_item) for item in valeur]
    if origine is list:
        return elements
    if origine is set:
        return set(elements)
    if origine is frozenset:
        return frozenset(elements)
    return tuple(elements)


def _depuis_mapping(valeur: Any, arguments: tuple[Any, ...]) -> Any:
    type_valeur = arguments[1] if len(arguments) > 1 else Any
    return {cle: _depuis_json(item, type_valeur) for cle, item in valeur.items()}


def _depuis_dataclass(valeur: Any, classe: type) -> Any:
    if valeur is None:
        return None
    indices = typing.get_type_hints(classe)
    noms = {champ.name for champ in dataclasses.fields(classe)}
    arguments = {nom: _depuis_json(valeur[nom], indices.get(nom, Any)) for nom in valeur if nom in noms}
    return classe(**arguments)
