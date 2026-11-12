"""The perimeter policy, derived from the manifest (EF-05, annexe C).

**The policy is never written by hand.** It is generated from the signed
manifest, so the applied perimeter and the comparison baseline are the same
object and cannot diverge (§20.3). Every rule carries `origine = "manifeste"`,
which is what test R4 checks.

`PolicyLocale` evaluates annexe C, in order, on **structured facts** — never on
free text. Lot 6 (`sas.politique`) replaces it with the configurable engine
behind the same port; `sas.agentcore.fabrique` prefers that one when present.

In shadow mode there is no specific "real resource" rule here: the replica simply
does not contain any resource outside the declaration, so the gateway answers
"unknown resource" (EF-17, tested in lot 2). One mechanism, not two.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sas import constantes
from sas.ombre.replication import table_repliquees
from sas.ombre.support import normaliser
from sas.types import (
    ContexteAppel,
    Decision,
    DecisionPolitique,
    FaitsSession,
    Manifeste,
    Mode,
    Politique,
    ReglePolitique,
    StatutManifeste,
)

REFUS = Decision.REFUSE
SUSPENSIONS: dict[str, str] = {}

# Two families of denial, and only one of them is a finding.
#
# A **perimeter** denial means the agent asked for something the signed manifest
# does not grant: that is what §13 classifies, and what the report publishes.
# A **bounding** denial means the airlock stopped the session — budget spent,
# duration reached, agent suspended, manifest no longer in force. Counting those
# as out-of-scope attempts would produce exactly the false positive §16.3 warns
# about: a conforming guest that exhausts its budget on a volume scenario would
# be reported as "targeted attempts on a declared resource".
REGLES_PERIMETRE: frozenset[str] = frozenset(
    {
        "usage-non-declare",
        "ressource-hors-perimetre",
        "colonnes-hors-perimetre",
        "sortie-non-declaree",
    }
)
REGLES_BORNAGE: frozenset[str] = frozenset(
    {
        "budget-epuise",
        "duree-depassee",
        "suspension",
        "identite-revoquee",
        "manifeste-non-valide",
        "manifeste-perime",
        "politique-absente",
    }
)


def est_hors_perimetre(regle: str) -> bool:
    """True when a denial is a perimeter violation, i.e. a classifiable finding."""
    return regle in REGLES_PERIMETRE


def deriver(manifeste: Manifeste, mode: Mode = Mode.OMBRE) -> Politique:
    """Build the applied policy from a signed manifest. The only entry point."""
    declarees = tuple({normaliser(d.ressource) for d in manifeste.donnees_demandees})
    # In shadow mode the applied perimeter is the replica of the declaration:
    # the guest sees the same names, the synthetic content (spec 10.1).
    ressources = table_repliquees(declarees) if mode is Mode.OMBRE else declarees
    colonnes = tuple({c for d in manifeste.donnees_demandees for c in d.colonnes})
    regles = tuple(
        ReglePolitique(
            id=f"outil-{outil.nom}",
            outil=outil.nom,
            effet=Decision.AUTORISE,
            ressources=ressources,
            colonnes=colonnes,
            destinations=tuple(s.destination for s in manifeste.sorties_autorisees),
            condition=f"operation={outil.operation}",
            origine="manifeste",
        )
        for outil in manifeste.outils_demandes
    )
    from sas.identifiants import empreinte

    return Politique(
        agent_id=manifeste.agent_id,
        manifeste_version=manifeste.version,
        regles=regles,
        sorties_autorisees=tuple(s.destination for s in manifeste.sorties_autorisees),
        budgets=manifeste.budgets,
        mode=mode,
        empreinte=empreinte(
            {
                "regles": [r.id for r in regles],
                "ressources": list(ressources),
                "sorties": [x.destination for x in manifeste.sorties_autorisees],
                "budgets": [
                    manifeste.budgets.appels_par_execution,
                    manifeste.budgets.jetons_par_execution,
                    manifeste.budgets.duree_maximale_secondes,
                    manifeste.budgets.memoire_maximale_mio,
                ],
                "mode": mode.value,
            }
        ),
    )


class PolicyLocale:
    """Applies the derived policy. Stateless except for the kill switch."""

    def __init__(self, politique: Politique | None = None) -> None:
        self._politique = politique
        self._suspendus: set[str] = set()

    # -- port Policy ------------------------------------------------------- #
    def charger(self, politique: Politique) -> None:
        self._politique = politique

    def suspendre(self, agent_id: str, motif: str) -> None:
        """Arm the kill switch: every further call is denied (§11.4)."""
        self._suspendus.add(agent_id)
        SUSPENSIONS[agent_id] = motif

    def suspendu(self, agent_id: str) -> bool:
        return agent_id in self._suspendus

    def reprendre(self, agent_id: str) -> None:
        self._suspendus.discard(agent_id)
        SUSPENSIONS.pop(agent_id, None)

    def evaluer(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique:
        if self._politique is None:
            return _refus("politique-absente", "aucune politique chargée : rien n'est autorisé par défaut")
        return self._evaluer(contexte, faits)

    # -- annexe C, in order ------------------------------------------------ #
    def _evaluer(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique:
        # An outbound call is not a tool of the manifest: it is judged by the
        # outputs declared, not by the tool list (annexe C).
        if contexte.sortie_reseau:
            verifications = (
                self._manifeste_en_vigueur,
                self._suspension,
                self._budgets,
                self._duree,
                self._sorties,
            )
        else:
            verifications = (
                self._outil_declare,
                self._manifeste_en_vigueur,
                self._suspension,
                self._budgets,
                self._duree,
                self._ressources,
                self._colonnes,
                self._sorties,
            )
        for verification in verifications:
            decision = verification(contexte, faits)
            if decision is not None:
                return decision
        return DecisionPolitique(decision=Decision.AUTORISE, regle_appliquee="manifeste:autorise", motif="")

    def _outil_declare(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        assert self._politique is not None
        if any(regle.outil == contexte.outil for regle in self._politique.regles):
            return None
        return DecisionPolitique(
            decision=REFUS,
            regle_appliquee="usage-non-declare",
            motif=f"outil « {contexte.outil} » absent du manifeste",
            usage_non_declare=True,
        )

    def _manifeste_en_vigueur(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        if faits.manifeste_statut is not StatutManifeste.VALIDE:
            return _refus("manifeste-non-valide", f"manifeste au statut « {faits.manifeste_statut.value} »")
        if faits.manifeste_version != faits.version_courante:
            return _refus(
                "manifeste-perime",
                f"manifeste v{faits.manifeste_version} alors que l'agent est en version "
                f"{faits.version_courante}",
            )
        return None

    def _suspension(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        assert self._politique is not None
        if faits.suspension or self.suspendu(self._politique.agent_id):
            return _refus("suspension", "agent suspendu : les identifiants sont coupés")
        return None

    def _budgets(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        if faits.appels_restants <= 0:
            return _refus("budget-epuise", "budget d'appels épuisé")
        if faits.jetons_restants <= 0:
            return _refus("budget-epuise", "budget de jetons épuisé")
        return None

    def _duree(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        if faits.duree_ecoulee_secondes >= faits.duree_maximale_secondes:
            return _refus("duree-depassee", "durée maximale de session atteinte")
        return None

    def _ressources(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        assert self._politique is not None
        autorisees = _ressources_autorisees(self._politique, contexte.outil)
        for ressource in contexte.ressources:
            if not _dans_le_perimetre(normaliser(ressource), autorisees):
                return _refus(
                    "ressource-hors-perimetre", f"ressource « {ressource} » hors du périmètre déclaré"
                )
        return None

    def _colonnes(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        assert self._politique is not None
        declarees = {c for regle in self._politique.regles for c in regle.colonnes}
        if not declarees or not contexte.colonnes:
            return None
        for colonne in contexte.colonnes:
            if colonne not in declarees:
                return _refus("colonnes-hors-perimetre", f"colonne « {colonne} » non déclarée")
        return None

    def _sorties(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        if not contexte.sortie_reseau:
            return None
        assert self._politique is not None
        if contexte.destination in self._politique.sorties_autorisees:
            return None
        return _refus(
            "sortie-non-declaree",
            f"destination « {contexte.destination or 'inconnue'} » non déclarée au manifeste",
        )


def facteur_arret_budget() -> Any:
    """Annexe C: the session ends cleanly at budget x this factor."""
    return constantes.FACTEUR_ARRET_BUDGET


def _ressources_autorisees(politique: Politique, outil: str) -> Sequence[str]:
    for regle in politique.regles:
        if regle.outil == outil:
            return regle.ressources
    return ()


def _dans_le_perimetre(ressource: str, autorisees: Sequence[str]) -> bool:
    if not autorisees:
        return False
    return any(
        ressource == autorisee or ressource.startswith(autorisee.rstrip("*").rstrip("/"))
        for autorisee in autorisees
    )


def _refus(regle: str, motif: str) -> DecisionPolitique:
    return DecisionPolitique(decision=REFUS, regle_appliquee=regle, motif=motif)
