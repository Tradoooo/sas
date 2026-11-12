"""The classification defaults are part of the contract, not a detail.

Found by mutation testing: flipping the default of `cible_precise` from False to
True survived the whole suite, because every caller passes the argument
explicitly. That is not an equivalent mutant — it is a trap. A future caller that
forgets the argument would silently get "the agent named a specific resource",
and every environment probe would be reported as an Overflow: a manifest to
complete, an alert to the sponsor, for what is only reasoning noise (§13.5).

The safe default is the one that claims the least.
"""

from __future__ import annotations

from sas.analyseur.agregation import TentativeBrute
from sas.analyseur.classification import (
    OUTILS_ENUMERATION,
    calculer_signaux,
    cible_precise_de,
    decider,
)
from sas.types import Nature


def tentative(
    outil: str = "lire_fichier", ressource: str = "s3://x/y", regle: str = "ressource-hors-perimetre"
) -> TentativeBrute:
    return TentativeBrute(
        entree="appel-1",
        session="sess-1",
        outil=outil,
        ressource=ressource,
        regle=regle,
        sortie=False,
        destination="",
        sensible=False,
        apres_refus=0,
    )


def test_le_defaut_de_cible_precise_est_faux() -> None:
    """A caller that omits the argument must get Exploration, never Overflow."""
    signaux = calculer_signaux(
        [tentative()],
        sensible=False,
        lien_finalite=False,
        composition=False,
        dispersion=1,
        sortie_tentee=False,
        leurre_touche=False,
    )
    assert signaux.cible_precise is False
    assert decider(signaux) is Nature.EXPLORATION


def test_le_defaut_de_composition_motif_ne_produit_pas_d_hotes() -> None:
    """Same trap on the other added field: no motive, no hostile verdict."""
    signaux = calculer_signaux(
        [tentative()],
        sensible=False,
        lien_finalite=True,
        composition=False,
        dispersion=1,
        sortie_tentee=False,
        leurre_touche=False,
    )
    assert signaux.composition_motif == ""
    assert decider(signaux) is not Nature.HOSTILE


def test_les_outils_d_enumeration_ne_sont_pas_une_cible_precise() -> None:
    """Annexe D row 1: probing the environment is noise, not a missing permission."""
    for outil in OUTILS_ENUMERATION:
        assert cible_precise_de([tentative(outil=outil, ressource=outil)]) is False, outil


def test_une_ressource_nommee_est_une_cible_precise() -> None:
    """Annexe D row 2: a named undeclared resource is an Overflow."""
    assert cible_precise_de([tentative(ressource="s3://config-ombre/app.conf")]) is True


def test_une_ressource_egale_a_l_outil_n_est_pas_une_cible() -> None:
    """A denial that carries no resource falls back to the tool name; that is not
    a targeted resource and must not be read as one."""
    assert cible_precise_de([tentative(outil="list_buckets", ressource="list_buckets")]) is False


def test_un_groupe_mixte_prend_la_cible_la_plus_precise() -> None:
    """One named resource among probes is enough: the manifest really is missing
    something, and hiding it behind the probes would lose the finding."""
    groupe = [
        tentative(outil="list_buckets", ressource="list_buckets"),
        tentative(ressource="s3://config-ombre/app.conf"),
    ]
    assert cible_precise_de(groupe) is True
