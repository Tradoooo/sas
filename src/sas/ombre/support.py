"""`SupportOmbre` — the only surface the gateway talks to (lot 2 contract).

The shadow environment is a **replica**: same structure, same names, synthetic
data. It has no route to the outside (§20.5): there is no outbound method here,
so a guest that wants to send something out must go through the gateway, which
denies it.

The signature of every method is frozen by `docs/CONTRACTS.md`: the orchestrator
(lot 5) and the demo guests (lot 3) depend on it. All of them return
JSON-serialisable dicts, because the gateway journals them as they are.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sas.identifiants import empreinte
from sas.ombre.leurres import est_leurre
from sas.types import EnvironnementOmbre, Leurre, RessourceOmbre

ERREUR_INCONNUE = "ressource inconnue"


@dataclass(slots=True)
class EtatRessource:
    """Mutable state of one replicated resource."""

    type: str
    objets: dict[str, str] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    leurre: Leurre | None = None


def normaliser(ressource: str) -> str:
    """One key per resource, whatever the spelling the guest used."""
    cible = ressource.strip()
    for prefixe in ("arn:aws:s3:::", "s3://", "arn:aws:dynamodb:"):
        if cible.startswith(prefixe):
            cible = cible[len(prefixe) :]
    return cible.rstrip("/")


class SupportOmbre:
    """Read, list, write and search inside one shadow environment."""

    def __init__(self, ombre: EnvironnementOmbre, graine: int) -> None:
        self._ombre = ombre
        self._graine = graine
        self._etats: dict[str, EtatRessource] = {}
        self._initial: dict[str, EtatRessource] = {}
        self._construire()

    # -- contrat gelé ------------------------------------------------------ #
    @property
    def environnement(self) -> EnvironnementOmbre:
        return self._ombre

    @property
    def graine(self) -> int:
        return self._graine

    def lire(self, ressource: str, chemin: str = "") -> dict[str, Any]:
        cle = normaliser(ressource)
        etat = self._etats.get(cle)
        if etat is None:
            return self._refus(f"{ERREUR_INCONNUE}: {ressource}")
        if etat.type == "table":
            return {
                "ok": True,
                "contenu": None,
                "structure": etat.structure,
                "marqueur": None,
                "sensible": False,
                "leurre": False,
                "erreur": "",
            }
        cible = chemin.strip() or cle
        if cible not in etat.objets:
            trouve = _chercher_objet(etat, cible)
            if trouve is None:
                return self._refus(f"objet absent de la réplique: {cible}")
            cible = trouve
        return {
            "ok": True,
            "contenu": etat.objets[cible],
            "marqueur": etat.leurre.marqueur if etat.leurre else None,
            "sensible": bool(etat.leurre and etat.leurre.sensible),
            "leurre": etat.leurre is not None,
            "erreur": "",
        }

    def lister(self, ressource: str, prefixe: str = "") -> dict[str, Any]:
        cle = normaliser(ressource)
        etat = self._etats.get(cle)
        if etat is None:
            return {"ok": False, "objets": [], "erreur": f"{ERREUR_INCONNUE}: {ressource}"}
        objets = sorted(k for k in etat.objets if k.startswith(prefixe.strip()))
        return {"ok": True, "objets": objets, "erreur": ""}

    def ecrire(self, ressource: str, chemin: str, contenu: str) -> dict[str, Any]:
        cle = normaliser(ressource)
        etat = self._etats.get(cle)
        if etat is None:
            return {"ok": False, "erreur": f"{ERREUR_INCONNUE}: {ressource}"}
        if etat.type == "table":
            lignes = list(etat.structure.get("lignes", []))
            lignes.append({"contenu": contenu, "cle": chemin})
            etat.structure = {**etat.structure, "lignes": lignes}
            return {"ok": True, "erreur": ""}
        etat.objets[chemin.strip() or cle] = contenu
        return {"ok": True, "erreur": ""}

    def chercher(self, index: str, requete: str) -> dict[str, Any]:
        cle = normaliser(index)
        etat = self._etats.get(cle)
        if etat is None:
            return {"ok": False, "resultats": [], "erreur": f"{ERREUR_INCONNUE}: {index}"}
        termes = [t for t in requete.lower().split() if len(t) > 3][:4]
        resultats = [
            {"id": identifiant, "extrait": contenu[:160]}
            for identifiant, contenu in sorted(etat.objets.items())
            if not termes or any(terme in contenu.lower() for terme in termes)
        ]
        return {"ok": True, "resultats": resultats[:10], "erreur": ""}

    def reinitialiser(self) -> None:
        """§14.6 — a replay never benefits from the state of the previous one."""
        self._etats = {cle: _copier(etat) for cle, etat in self._initial.items()}

    def inventaire(self) -> dict[str, int]:
        """resource -> number of objects. Feeds the destruction proof."""
        return {cle: len(etat.objets) for cle, etat in sorted(self._etats.items())}

    def detruire(self) -> None:
        """ENF-06 — after this, nothing is readable and nothing is left."""
        self._etats = {}
        self._initial = {}

    # -- interne ----------------------------------------------------------- #
    def _construire(self) -> None:
        for ressource in self._ombre.ressources:
            cle = normaliser(ressource.ressource)
            contenus = dict(ressource.structure.get("contenus", {}))
            etat = EtatRessource(
                type=ressource.type,
                objets={objet: str(contenus.get(objet, "")) for objet in ressource.objets},
                structure={k: v for k, v in ressource.structure.items() if k != "contenus"},
            )
            self._etats[cle] = etat
        for leurre in self._ombre.leurres:
            cle = normaliser(leurre.ressource)
            contenu = _contenu_leurre(leurre, self._graine)
            self._etats[cle] = EtatRessource(type="s3", objets={cle: contenu}, leurre=leurre)
        self._initial = {cle: _copier(etat) for cle, etat in self._etats.items()}

    def _refus(self, erreur: str) -> dict[str, Any]:
        return {
            "ok": False,
            "contenu": None,
            "marqueur": None,
            "sensible": False,
            "leurre": False,
            "erreur": erreur,
        }


def _copier(etat: EtatRessource) -> EtatRessource:
    return EtatRessource(
        type=etat.type,
        objets=dict(etat.objets),
        structure={**etat.structure, "lignes": list(etat.structure.get("lignes", []))}
        if etat.structure
        else {},
        leurre=etat.leurre,
    )


def _chercher_objet(etat: EtatRessource, cible: str) -> str | None:
    for identifiant in etat.objets:
        if identifiant.endswith(cible) or cible.endswith(identifiant):
            return identifiant
    return None


def _contenu_leurre(leurre: Leurre, graine: int) -> str:
    from sas.ombre.donnees import contenu_leurre

    return contenu_leurre(graine, leurre.marqueur, leurre.chemin)


def empreinte_inventaire(inventaire: dict[str, int]) -> str:
    """A single hash of the environment's shape: two shadows with the same seed
    share it (ENF-11, R15)."""
    return empreinte(inventaire)


def ressources_declarees(ombre: EnvironnementOmbre) -> tuple[RessourceOmbre, ...]:
    return ombre.ressources


def leurres_de(ombre: EnvironnementOmbre) -> tuple[Leurre, ...]:
    return ombre.leurres


def marqueur_de(support: SupportOmbre, ressource: str) -> Leurre | None:
    return est_leurre(ressource, support.environnement.leurres)
