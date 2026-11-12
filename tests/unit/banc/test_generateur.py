"""The bench table is generated, and the committed copy matches the generator.

Annexe F.3 makes bench reproducibility an acceptance requirement: the 41 guests
are produced by a script, not written by hand. These tests keep that promise
honest — a hand-edited table, or a generator changed without regenerating, fails
here rather than silently diverging.

Node is not guaranteed on a CI worker, so the regeneration check is marked slow
and skips cleanly when `node` is absent; the structural checks always run.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from eval import agents as banc_agents
from eval.agents import _tableau
from eval.agents.modele import AgentBanc

RACINE = Path(__file__).resolve().parents[3]
GENERATEUR = RACINE / "eval" / "genere-agents.mjs"
TABLEAU = RACINE / "eval" / "agents" / "_tableau.py"


def test_le_generateur_existe() -> None:
    assert GENERATEUR.is_file(), "eval/genere-agents.mjs est exigé par l'annexe F.3"


def test_le_tableau_est_marque_comme_genere() -> None:
    """A generated file that does not say so gets hand-edited sooner or later."""
    entete = TABLEAU.read_text(encoding="utf-8")[:600]
    assert "GÉNÉRÉ" in entete
    assert "ne pas éditer à la main" in entete
    assert "genere-agents.mjs" in entete


def test_le_recensement_du_banc() -> None:
    compte = banc_agents.compter()
    assert compte["fautifs"] == 20
    assert compte["benins"] == 20
    assert compte["total"] == 40
    assert compte["avec_calibre"] == 41


def test_chaque_agent_du_tableau_est_bien_forme() -> None:
    for agent in banc_agents.tous():
        assert isinstance(agent, AgentBanc)
        assert agent.nom and agent.nom == agent.nom.strip()
        if agent.benin:
            assert agent.nature_attendue is None
            assert agent.faute == ""
        else:
            assert agent.faute.strip(), f"{agent.nom} sans faute décrite"
            assert agent.nature_attendue is not None
        assert agent.script or agent.scripts_par_rejeu


def test_les_noms_sont_uniques_et_numerotes_sans_trou() -> None:
    """A stable, gap-free naming: the bench is a census, not a sample."""
    noms = [a.nom for a in banc_agents.tous()]
    assert len(set(noms)) == len(noms) == 40
    fautifs = sorted(int(n.split("-")[1]) for n in noms if n.startswith("fautif-"))
    benins = sorted(int(n.split("-")[1]) for n in noms if n.startswith("benin-"))
    assert fautifs == list(range(1, 21))
    assert benins == list(range(1, 21))


def test_le_seul_agent_a_rejeux_multiples_est_celui_de_persistance() -> None:
    """§16.2 — persistence spans two sessions; nothing else needs to."""
    multiples = [a.nom for a in banc_agents.tous() if a.rejeux_requis > 1]
    assert multiples == ["fautif-18"]
    assert banc_agents.par_nom("fautif-18").composition_attendue == "persistence"


def test_les_ressources_du_tableau_sont_celles_de_l_ombre() -> None:
    """A bench that plays against resources the shadow does not hold would prove
    nothing: every named resource must exist in the replica (annexe F.2)."""
    from sas.ombre import GenerateurOmbre, SupportOmbre
    from sas.ombre.support import normaliser

    ombre = GenerateurOmbre().construire("camp-test", None, 7)
    support = SupportOmbre(ombre, 7)
    connues = set(support.inventaire())
    for nom in (
        "s3://rh-ombre/grille-2026.csv",
        "s3://config-ombre/app.conf",
        "s3://client-tickets-ombre/entree/",
        "kb-documentation-ombre",
        "dynamodb:suivi-ombre",
    ):
        assert normaliser(nom) in connues, nom


@pytest.mark.slow
def test_le_tableau_commite_est_ce_que_le_generateur_produit() -> None:
    """The reproducibility requirement itself.

    The regenerated copy is written **inside the repository**, not in /tmp: ruff
    decides what is first-party from `pyproject.toml`, so formatting the same
    file outside the tree produces a different import layout and the comparison
    would fail on configuration rather than on content.
    """
    if shutil.which("node") is None:
        pytest.skip("node absent du runner : la régénération est vérifiée en CI nocturne")
    sortie = TABLEAU.with_name("_tableau_regenere.py")
    try:
        resultat = subprocess.run(
            ["node", str(GENERATEUR), "--sortie", str(sortie)],
            capture_output=True,
            text=True,
            check=False,
            cwd=str(RACINE),
        )
        assert resultat.returncode == 0, resultat.stderr[-400:]
        # Le fichier committé passe par ruff comme le reste du dépôt : la
        # comparaison se fait après la même mise en forme, sinon le contrôle
        # échouerait sur de la seule typographie — et un contrôle qui échoue
        # pour rien apprend à tout le monde à l'ignorer.
        for commande in (
            ["python3", "-m", "ruff", "format", str(sortie)],
            ["python3", "-m", "ruff", "check", "--fix", "--select", "I,F401", str(sortie)],
            ["python3", "-m", "ruff", "format", str(sortie)],
        ):
            subprocess.run(commande, capture_output=True, text=True, check=False, cwd=str(RACINE))
        assert sortie.read_text(encoding="utf-8") == TABLEAU.read_text(encoding="utf-8"), (
            "eval/agents/_tableau.py est périmé : relancer `node eval/genere-agents.mjs` "
            "puis `ruff format eval/agents/_tableau.py`"
        )
    finally:
        sortie.unlink(missing_ok=True)


def test_le_module_tableau_ne_contient_aucune_logique() -> None:
    """A generated file must hold data only — logic belongs in `modele.py`."""
    source = TABLEAU.read_text(encoding="utf-8")
    assert "def " not in source
    assert "class " not in source
    assert _tableau.FAUTIFS is banc_agents.FAUTIFS
