"""Sas — homologation and controlled execution of third-party AI agents.

The package is organised around one principle: **the rules are applied by the
gateway, not by the prompt**. The guest agent never receives its limits as
prose — it undergoes them, at Policy level, before the tool runs.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
