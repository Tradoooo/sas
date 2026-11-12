"""The configurable policy engine (lot 6): `MoteurPolitique`.

This is the engine `sas.agentcore.fabrique.moteur_politique` looks for: when
this module exists, the whole product evaluates its policy through it.

It **composes**, in one direction only. The manifest perimeter — what the guest
is allowed to touch — is still evaluated by `PolicyLocale` (lot 5), and a
refusal there wins with its own rule name, so the classification of §13 never
changes. On an *allowed* call, the additive rules of `regles/politique.yaml`
run, in order: a rule may refuse (narrow the perimeter, never widen it) or
authorize under a condition (`Decision.AUTORISE_SOUS_CONDITION`), which the
journal records with the rule that decided it. A rule can target one scenario
through the `scenario` fact, so the program does not change when a scenario
does.

**There is no wider path.** An additive rule has exactly two effects — refuse,
or authorise-under-condition. It cannot authorise a call the manifest has not
declared, because on a non-declared call `PolicyLocale` refuses before the
additive rules run. That is the difference between a configurable engine and a
hand-written policy, and a test pins it.

The kill switch (`suspendre`/`suspendu`) is shared with the base engine, so a
scenario-scoped view never isolates the suspension the way it isolates the
rules.
"""

from __future__ import annotations

from sas.agentcore.politique_manifeste import PolicyLocale
from sas.politique.programme import Programme, charger_programme, etat
from sas.types import (
    ContexteAppel,
    Decision,
    DecisionPolitique,
    FaitsSession,
    Politique,
)


class MoteurPolitique(PolicyLocale):
    """The Policy port, with an additive, data-driven layer on top of the base.

    The constructor keeps the base signature (`MoteurPolitique(politique)`) so
    `fabrique.moteur_politique` can pick it up without a change; the program,
    the scenario and the extra state are keyword-only.
    """

    def __init__(
        self,
        politique: Politique | None = None,
        *,
        programme: Programme | None = None,
        scenario_id: str | None = None,
    ) -> None:
        super().__init__(politique)
        self._programme = programme
        self._scenario_id = scenario_id

    # -- port Policy ------------------------------------------------------- #
    def evaluer(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique:
        """The base perimeter first; the additive program on top of an allow."""
        base = super().evaluer(contexte, faits)
        if base.decision is Decision.REFUSE:
            return base
        if self._programme is None:
            self._programme = charger_programme()
        etats = etat(contexte, faits, scenario_id=self._scenario_id)
        for regle in self._programme.regles:
            if not regle.declenche(etats):
                continue
            if regle.effet == "refuser":
                return DecisionPolitique(
                    decision=Decision.REFUSE,
                    regle_appliquee=regle.regle_appliquee,
                    motif=regle.motif,
                )
            return DecisionPolitique(
                decision=Decision.AUTORISE_SOUS_CONDITION,
                regle_appliquee=regle.regle_appliquee,
                motif=regle.motif,
            )
        return base

    # -- the program, and the scenario ------------------------------------- #
    def pour_scenario(self, scenario_id: str) -> MoteurPolitique:
        """The same engine, seen through the rules of one scenario.

        The suspension state is shared with the parent: suspending the agent
        suspends it for every scenario (EF-15), only the additive rules scoping
        changes.
        """
        partage = MoteurPolitique(
            self._politique,
            programme=self._programme if self._programme is not None else charger_programme(),
            scenario_id=scenario_id,
        )
        partage._suspendus = self._suspendus
        return partage

    def regles_additives(self) -> tuple[str, ...]:
        """The additive rules this engine applies — for the report and tests."""
        programme = self._programme if self._programme is not None else charger_programme()
        return tuple(regle.id for regle in programme.regles)


__all__ = ["MoteurPolitique"]
