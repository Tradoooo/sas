"""A bounding denial is not a finding (§13, §16.3).

Regression guard for a real defect: a conforming guest that exhausts its call
budget on a volume scenario used to be reported as "targeted attempts on a
declared resource", because every denial was classified. The airlock stopping a
session is the airlock doing its job — it is not the agent asking for something
the manifest refuses. Counting it invents exactly the false positive §16.3 warns
would kill the product's credibility.
"""

from __future__ import annotations

from dataclasses import replace

from sas.agentcore.politique_manifeste import REGLES_BORNAGE, REGLES_PERIMETRE, est_hors_perimetre
from sas.analyseur.agregation import agreger
from sas.analyseur.classification import grouper
from sas.cli_partage import charger_contexte, invite, lancer
from sas.homologation import analyser
from sas.orchestrateur import Campagne, nouvelle_campagne
from sas.types import Nature


def test_les_deux_familles_de_refus_sont_disjointes_et_couvertes() -> None:
    assert not (REGLES_PERIMETRE & REGLES_BORNAGE)
    assert est_hors_perimetre("ressource-hors-perimetre") is True
    assert est_hors_perimetre("sortie-non-declaree") is True
    assert est_hors_perimetre("budget-epuise") is False
    assert est_hors_perimetre("suspension") is False


def test_R12_un_agent_conforme_sur_les_huit_scenarios_est_homologue() -> None:
    """R12 — zero gap is a result, and the report says so explicitly."""
    contexte = charger_contexte()
    assert len(contexte.scenarios) == 8
    dossier = lancer(agent=invite("demo-conforme"), contexte=contexte, rejeux=2, graine=11)
    assert dossier.decision.verdict.value == "homologue"
    assert dossier.decision.decouvertes[Nature.TENTATIVE] == 0
    assert dossier.decision.decouvertes[Nature.HOSTILE] == 0
    assert dossier.ecarts == ()


def test_un_refus_de_budget_ne_devient_pas_une_decouverte() -> None:
    """The budget stop is counted in the journal, not in the findings."""

    class InviteInsatiable:
        """Keeps calling a *declared* tool past the budget: the airlock stops it."""

        nom = "invite-insatiable"
        version = "1.0.0"
        instrumentable = True

        def executer(self, outils, entree):
            for index in range(14):
                outils.appeler("lire_ticket", {"id": f"T-{index + 1:04d}"})
            return {"appels": 14}

    contexte = charger_contexte(("S6",))
    petit = replace(
        contexte.manifeste,
        budgets=replace(contexte.manifeste.budgets, appels_par_execution=8),
        signature=replace(contexte.manifeste.signature, empreinte_document=""),
    )
    campagne = nouvelle_campagne(
        tenant_id="tenant-demo",
        agent_id=petit.agent_id,
        manifeste=petit,
        n_rejeux=2,
        graine=11,
        scenarios=["S6"],
    )
    resultat = Campagne(
        campagne=campagne, manifeste=petit, agent=InviteInsatiable(), scenarios=contexte.scenarios
    ).executer()

    agregat = agreger(resultat.entrees)
    assert agregat.refus > 0, "le budget doit avoir été atteint"
    assert agregat.regles["budget-epuise"] > 0
    assert any(s.budget_depasse for s in resultat.sessions), "R6 — arrêt propre, session marquée"

    groupees = grouper(agregat.tentatives)
    assert groupees == {}, "un refus de bornage n'est pas une tentative hors périmètre"

    dossier = analyser(
        resultat, manifeste=petit, tenant_id="tenant-demo", ressources_sensibles=(), leurres=(), graine=11
    )
    assert dossier.decision.decouvertes[Nature.TENTATIVE] == 0
    assert dossier.decision.decouvertes[Nature.HOSTILE] == 0


def test_un_refus_de_perimetre_reste_une_decouverte() -> None:
    """The fix must not swallow real findings: the chatty guest is still caught."""
    contexte = charger_contexte(("S1", "S4", "S5", "S8"))
    dossier = lancer(agent=invite("demo-bavard"), contexte=contexte, rejeux=2, graine=11)
    assert dossier.decision.verdict.value == "homologue_sous_conditions"
    assert dossier.decision.decouvertes[Nature.EXPLORATION] > 0
    assert dossier.ecarts, "le leurre de configuration doit produire un écart"


def test_le_curieux_est_toujours_refuse() -> None:
    contexte = charger_contexte(("S5", "S8"))
    dossier = lancer(agent=invite("demo-curieux"), contexte=contexte, rejeux=2, graine=11)
    assert dossier.decision.verdict.value == "refuse"
    assert dossier.decision.decouvertes[Nature.HOSTILE] > 0
    assert any(c.motif.value == "exfiltration" for c in dossier.compositions)


def test_les_regles_de_bornage_sont_toutes_connues_du_moteur() -> None:
    """Every rule name the policy can emit is classified into one family."""
    import inspect

    from sas.agentcore import politique_manifeste as pm

    source = inspect.getsource(pm)
    emises = {
        "usage-non-declare",
        "manifeste-non-valide",
        "manifeste-perime",
        "suspension",
        "budget-epuise",
        "duree-depassee",
        "ressource-hors-perimetre",
        "colonnes-hors-perimetre",
        "sortie-non-declaree",
        "politique-absente",
    }
    for regle in emises:
        assert regle in source, f"règle {regle} absente du moteur"
        assert est_hors_perimetre(regle) or regle in REGLES_BORNAGE, regle
