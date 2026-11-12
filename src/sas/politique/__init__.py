"""The configurable policy engine (lot 6): the additive rule program.

Public surface: `MoteurPolitique` (the engine `fabrique.moteur_politique`
picks up), the `Programme` loader and the `ErreurPolitique` it raises.
"""

from __future__ import annotations

from sas.politique.moteur import MoteurPolitique
from sas.politique.programme import ErreurPolitique, Programme, charger_programme

__all__ = ["ErreurPolitique", "MoteurPolitique", "Programme", "charger_programme"]
