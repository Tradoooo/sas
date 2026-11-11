"""Building the shadow environment (spec §10.1, §21.2, annexe F.2).

Implements the `ConstructeurOmbre` port. The replica is derived from the
declaration — same names, same structures — filled with synthetic data generated
from the seed, so two campaigns with the same seed build the same shadow
byte for byte (ENF-11, R15).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from sas import aleatoire, constantes
from sas.identifiants import maintenant, nouveau
from sas.ombre import donnees
from sas.ombre.leurres import leurres_par_defaut
from sas.ombre.support import normaliser
from sas.types import EnvironnementOmbre, Leurre, Politique, RessourceOmbre

RESSOURCE_TICKETS = "s3://client-tickets-ombre/entree/"
RESSOURCE_DOCUMENTATION = "kb-documentation-ombre"
RESSOURCE_SUIVI = "dynamodb:suivi-ombre"


class GenerateurOmbre:
    """Builds, resets and destroys one shadow environment."""

    def __init__(
        self,
        *,
        tickets: int = constantes.TICKETS_OMBRE,
        injections: int = constantes.TICKETS_AVEC_INJECTION,
        documents: int = constantes.DOCUMENTS_OMBRE,
        leurres: Iterable[Leurre] | None = None,
    ) -> None:
        self._tickets = tickets
        self._injections = injections
        self._documents = documents
        self._leurres = tuple(leurres) if leurres is not None else leurres_par_defaut()

    # -- port ConstructeurOmbre -------------------------------------------- #
    def construire(self, campagne_id: str, politique: Politique | None, graine: int) -> EnvironnementOmbre:
        ressources = self._ressources(graine)
        ressources += tuple(self._ressources_declarees(politique, ressources))
        return EnvironnementOmbre(
            id=nouveau("env", graine=graine, cle=campagne_id),
            campagne_id=campagne_id,
            graine=graine,
            ressources=ressources,
            leurres=self._leurres,
            cree_le=maintenant(),
        )

    def reinitialiser(self, ombre: EnvironnementOmbre) -> EnvironnementOmbre:
        """A structurally identical environment, as if nothing had happened."""
        return EnvironnementOmbre(
            id=ombre.id,
            campagne_id=ombre.campagne_id,
            graine=ombre.graine,
            ressources=ombre.ressources,
            leurres=ombre.leurres,
            cree_le=ombre.cree_le,
        )

    def detruire(self, ombre: EnvironnementOmbre) -> tuple[datetime, str]:
        from sas.ombre.destruction import detruire

        return detruire(ombre)

    # -- interne ----------------------------------------------------------- #
    def _ressources(self, graine: int) -> tuple[RessourceOmbre, ...]:
        tickets = donnees.tickets_synthetiques(graine, self._tickets, self._injections)
        documents = donnees.documents_synthetiques(graine, self._documents)
        return (
            RessourceOmbre(
                ressource=RESSOURCE_TICKETS,
                type="s3",
                structure={
                    "prefixe": "entree/",
                    "contenus": {t["id"]: t["contenu"] for t in tickets},
                    "injections": [t["id"] for t in tickets if t["injection"]],
                },
                objets=tuple(t["id"] for t in tickets),
            ),
            RessourceOmbre(
                ressource=RESSOURCE_DOCUMENTATION,
                type="index",
                structure={"contenus": {d["id"]: f"{d['titre']}\n{d['contenu']}" for d in documents}},
                objets=tuple(d["id"] for d in documents),
            ),
            RessourceOmbre(
                ressource=RESSOURCE_SUIVI,
                type="table",
                structure=donnees.structure_table_suivi(),
                objets=(),
            ),
        )

    def _ressources_declarees(
        self, politique: Politique | None, existantes: tuple[RessourceOmbre, ...]
    ) -> tuple[RessourceOmbre, ...]:
        """Mirror any declared resource the demo set does not already contain.

        Comparison runs on the **normalised** name: a policy derived in shadow
        mode carries `client-tickets-ombre/entree` while the replica declares
        `s3://client-tickets-ombre/entree/`. Without normalising, the same
        resource is added twice and the empty copy overwrites the filled one.
        """
        if politique is None:
            return ()
        connues = {normaliser(r.ressource) for r in existantes} | {
            normaliser(leurre.ressource) for leurre in self._leurres
        }
        ajoutees: list[RessourceOmbre] = []
        for regle in politique.regles:
            for ressource in regle.ressources:
                if ressource and normaliser(ressource) not in connues:
                    connues.add(normaliser(ressource))
                    ajoutees.append(
                        RessourceOmbre(ressource=ressource, type="s3", structure={"contenus": {}}, objets=())
                    )
        return tuple(ajoutees)

    # -- accès utiles aux tests -------------------------------------------- #
    @property
    def leurres(self) -> tuple[Leurre, ...]:
        return self._leurres

    def graines_attendues(self) -> dict[str, int]:
        return {"tickets": self._tickets, "injections": self._injections, "documents": self._documents}


def dispersion(graine: int, flux: str, valeurs: Iterable[Any]) -> list[Any]:
    """Re-exported for callers that shuffle shadow inputs reproducibly."""
    return aleatoire.disperser(graine, flux, valeurs)
