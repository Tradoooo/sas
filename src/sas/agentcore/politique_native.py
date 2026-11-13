"""La syntaxe native de la policy AgentCore, en JSON (annexe C, §34 point 2).

Le cahier des charges demande « la syntaxe réelle d'AgentCore Policy pour un
refus conditionnel sur un outil », et il dit aussi **comment** y répondre : un
test, pas une lecture. Ce module n'est pas ce test — il n'a jamais parlé à
AWS. C'est la grammaire, et la preuve de concordance :

* **la grammaire** — un document JSON qui porte le périmètre (outils,
  ressources, colonnes, sorties, budgets) et que `PolicyNative` évaluate ;
* **la concordance** — le moteur natif rend la **même décision** que
  `PolicyLocale` pour les mêmes faits : même verdict, même nom de règle (ce
  que le journal note et ce que §13 classe), même marqueur d'usage non
  déclaré. Le test `test_les_deux_moteurs_concordent_sur_les_scenarios` le
  vérifie sur les huit scénarios du dépôt.

Ce qui manque, et qui reste écrit dans `docs/ECHECS.md` : la confirmation par
AWS de cette syntaxe. Tant qu'aucun test n'a été exécuté contre la vraie API
AgentCore Policy, `PolicyAWS.evaluer_agentcore_natif()` rend `None` et le
moteur local reste la référence.

Le document n'est jamais écrit à la main : il est dérivé du manifeste (EF-05),
comme la politique locale — la dérivation est *partagée*, seule l'évaluation
est propre au moteur natif.

La forme du document :

```json
{
  "version": "1",
  "id": "perimetre-agent-1",
  "description": "Périmètre dérivé du manifeste (EF-05).",
  "default": "deny",
  "agent": "agent-1",
  "manifest": {"version": 1, "statut": "valide"},
  "tools": [
    {"id": "lire_ticket", "resources": ["client-tickets-ombre/entree"], "columns": ["id"]}
  ],
  "outputs": [],
  "budgets": {"appels": 25, "jetons": 60000, "duree_secondes": 180}
}
```

Une clé que le moteur ne lit pas est une règle qui ne s'applique pas : le
document est donc refusé quand il porte une clé inconnue, jamais récrit.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from sas.agentcore.politique_manifeste import deriver
from sas.ombre.support import normaliser
from sas.types import (
    ContexteAppel,
    Decision,
    DecisionPolitique,
    FaitsSession,
    Manifeste,
    Mode,
    Politique,
    StatutManifeste,
)

#: Le format de document que ce moteur lit. Un format inconnu est refusé.
VERSION_FORMAT = "1"

#: Les clés racine acceptées. Le reste est refusé.
CLES_RACINE: frozenset[str] = frozenset(
    {
        "version",
        "id",
        "description",
        "default",
        "agent",
        "manifest",
        "tools",
        "outputs",
        "budgets",
    }
)
CLES_OUTIL: frozenset[str] = frozenset({"id", "resources", "columns"})
CLES_MANIFESTE: frozenset[str] = frozenset({"version", "statut"})
CLES_BUDGETS: frozenset[str] = frozenset({"appels", "jetons", "duree_secondes"})

#: L'effet par défaut d'une policy native : refuser.
EFFET_PAR_DEFAUT = "deny"

#: Les statuts de manifeste qu'un document peut déclarer.
STATUTS_MANIFESTE: frozenset[str] = frozenset(statut.value for statut in StatutManifeste)


class ErreurSyntaxeNative(ValueError):
    """Un document qui n'est pas une policy native lisible est refusé, jamais réparé."""


# --------------------------------------------------------------------------- #
# Le document : sa grammaire et sa lecture
# --------------------------------------------------------------------------- #


def document_natif(politique: Politique) -> dict[str, Any]:
    """Le document natif dérivé de la politique — jamais écrit à la main (EF-05)."""
    budgets = politique.budgets
    return {
        "version": VERSION_FORMAT,
        "id": f"perimetre-{politique.agent_id}",
        "description": "Périmètre dérivé du manifeste (EF-05) — généré, jamais écrit à la main.",
        "default": EFFET_PAR_DEFAUT,
        "agent": politique.agent_id,
        "manifest": {"version": politique.manifeste_version, "statut": StatutManifeste.VALIDE.value},
        "tools": [
            {"id": regle.outil, "resources": list(regle.ressources), "columns": list(regle.colonnes)}
            for regle in politique.regles
        ],
        "outputs": list(politique.sorties_autorisees),
        "budgets": {
            "appels": budgets.appels_par_execution if budgets else 0,
            "jetons": budgets.jetons_par_execution if budgets else 0,
            "duree_secondes": budgets.duree_maximale_secondes if budgets else 0,
        },
    }


def document_natif_depuis_manifeste(manifeste: Manifeste, mode: Mode = Mode.OMBRE) -> dict[str, Any]:
    """Le document natif, dérivé du manifeste par la dérivation partagée."""
    return document_natif(deriver(manifeste, mode))


def vers_json(document: Mapping[str, Any]) -> str:
    """Le document natif en JSON : la forme qui circule."""
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)


def _valider(document: Any) -> dict[str, Any]:
    """Un document natif lisible, ou une erreur qui dit ce qui manque."""
    if not isinstance(document, Mapping):
        raise ErreurSyntaxeNative("la policy native doit être un objet JSON")
    inconnues = set(document) - CLES_RACINE
    if inconnues:
        raise ErreurSyntaxeNative(
            f"clés inconnues dans la policy native : {', '.join(sorted(inconnues))}. "
            "Une clé que le moteur ne lit pas est une règle qui ne s'applique pas."
        )
    version = str(document.get("version", ""))
    if version != VERSION_FORMAT:
        raise ErreurSyntaxeNative(
            f"format de policy natif inconnu : « {version} » (attendu : {VERSION_FORMAT})"
        )
    effet = str(document.get("default", EFFET_PAR_DEFAUT))
    if effet != EFFET_PAR_DEFAUT:
        raise ErreurSyntaxeNative(
            f"effet par défaut « {effet} » refusé : une policy native refuse par défaut"
        )
    return {
        "version": version,
        "id": _texte_obligatoire(document.get("id", ""), "id"),
        "description": str(document.get("description", "")),
        "default": effet,
        "agent": _texte_obligatoire(document.get("agent", ""), "agent"),
        "manifest": _manifeste(document.get("manifest")),
        "tools": _outils(document.get("tools", ())),
        "outputs": _liste_de_textes(document.get("outputs", ()), "outputs"),
        "budgets": _budgets(document.get("budgets", {})),
    }


def _texte_obligatoire(valeur: Any, cle: str) -> str:
    texte = str(valeur).strip()
    if not texte:
        raise ErreurSyntaxeNative(f"« {cle} » est obligatoire dans une policy native")
    return texte


def _manifeste(valeur: Any) -> dict[str, Any]:
    if not isinstance(valeur, Mapping):
        raise ErreurSyntaxeNative("« manifest » doit être un objet {version, statut}")
    inconnues = set(valeur) - CLES_MANIFESTE
    if inconnues:
        raise ErreurSyntaxeNative(f"clés inconnues dans « manifest » : {', '.join(sorted(inconnues))}")
    version = valeur.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        raise ErreurSyntaxeNative("« manifest.version » doit être un entier positif")
    statut = str(valeur.get("statut", ""))
    if statut not in STATUTS_MANIFESTE:
        raise ErreurSyntaxeNative(
            f"« manifest.statut » inconnu : « {statut} » (attendu : {', '.join(sorted(STATUTS_MANIFESTE))})"
        )
    return {"version": version, "statut": statut}


def _outils(valeur: Any) -> list[dict[str, Any]]:
    if not isinstance(valeur, Sequence) or isinstance(valeur, (str, bytes)):
        raise ErreurSyntaxeNative("« tools » doit être une liste d'outils")
    outils: list[dict[str, Any]] = []
    vus: set[str] = set()
    for entree in valeur:
        if not isinstance(entree, Mapping):
            raise ErreurSyntaxeNative("un outil de « tools » doit être un objet")
        inconnues = set(entree) - CLES_OUTIL
        if inconnues:
            raise ErreurSyntaxeNative(f"clés inconnues dans un outil : {', '.join(sorted(inconnues))}")
        identifiant = _texte_obligatoire(entree.get("id", ""), "tools[].id")
        if identifiant in vus:
            raise ErreurSyntaxeNative(f"outil en double dans « tools » : « {identifiant} »")
        vus.add(identifiant)
        outils.append(
            {
                "id": identifiant,
                "resources": _liste_de_textes(entree.get("resources", ()), f"tools[{identifiant}].resources"),
                "columns": _liste_de_textes(entree.get("columns", ()), f"tools[{identifiant}].columns"),
            }
        )
    return outils


def _liste_de_textes(valeur: Any, cle: str) -> list[str]:
    if not isinstance(valeur, Sequence) or isinstance(valeur, (str, bytes)):
        raise ErreurSyntaxeNative(f"« {cle} » doit être une liste de textes")
    return [str(item) for item in valeur]


def _budgets(valeur: Any) -> dict[str, int]:
    if not isinstance(valeur, Mapping):
        raise ErreurSyntaxeNative("« budgets » doit être un objet")
    inconnues = set(valeur) - CLES_BUDGETS
    if inconnues:
        raise ErreurSyntaxeNative(f"clés inconnues dans « budgets » : {', '.join(sorted(inconnues))}")
    budgets: dict[str, int] = {}
    for cle in sorted(CLES_BUDGETS):
        nombre = valeur.get(cle, 0)
        if not isinstance(nombre, int) or isinstance(nombre, bool) or nombre < 0:
            raise ErreurSyntaxeNative(f"« budgets.{cle} » doit être un entier positif ou nul")
        budgets[cle] = nombre
    return budgets


# --------------------------------------------------------------------------- #
# Le moteur
# --------------------------------------------------------------------------- #


class PolicyNative:
    """Le moteur natif : il ne lit que le document JSON.

    Il ne connaît ni `Politique` ni `PolicyLocale` : le document est sa seule
    source de vérité, comme le sera la policy native chez AWS. Il implémente
    le port `Policy` pour pouvoir être branché un jour sur la passerelle.
    """

    def __init__(self, document: Mapping[str, Any], *, suspendus: frozenset[str] = frozenset()) -> None:
        self._document = _valider(document)
        self._suspendus: set[str] = set(suspendus)
        self._motifs: dict[str, str] = {}

    @classmethod
    def depuis_json(cls, texte: str) -> PolicyNative:
        """La policy native telle qu'elle circule : du JSON."""
        try:
            document = json.loads(texte)
        except json.JSONDecodeError as exc:
            raise ErreurSyntaxeNative(f"policy native illisible : {exc}") from exc
        return cls(document)

    # -- lecture du document ------------------------------------------------ #
    def document(self) -> dict[str, Any]:
        """Le document, tel que le moteur l'a compris."""
        return dict(self._document)

    def version_manifeste(self) -> int:
        """La version de manifeste dont le document est dérivé."""
        return int(self._document["manifest"]["version"])

    def agent(self) -> str:
        """L'agent dont ce document est le périmètre."""
        return str(self._document["agent"])

    def outils(self) -> tuple[str, ...]:
        """Les outils déclarés, dans l'ordre du document."""
        return tuple(str(outil["id"]) for outil in self._document["tools"])

    def budgets(self) -> dict[str, int]:
        """Les plafonds déclarés (0 : non déclaré)."""
        return dict(self._document["budgets"])

    # -- port Policy -------------------------------------------------------- #
    def charger(self, politique: Politique) -> None:
        """Le port Policy : le document natif est dérivé de la politique."""
        self._document = _valider(document_natif(politique))

    def suspendre(self, agent_id: str, motif: str) -> None:
        """Le coupe-circuit : toute requête suivante est refusée (§11.4)."""
        self._suspendus.add(agent_id)
        self._motifs[agent_id] = motif

    def suspendu(self, agent_id: str) -> bool:
        return agent_id in self._suspendus

    def reprendre(self, agent_id: str) -> None:
        self._suspendus.discard(agent_id)
        self._motifs.pop(agent_id, None)

    def evaluer(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique:
        """L'annexe C, dans l'ordre, lue dans le document natif."""
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

    # -- les vérifications de l'annexe C ------------------------------------ #
    def _outil_declare(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del faits
        if contexte.outil in self.outils():
            return None
        return DecisionPolitique(
            decision=Decision.REFUSE,
            regle_appliquee="usage-non-declare",
            motif=f"outil « {contexte.outil} » absent du périmètre déclaré",
            usage_non_declare=True,
        )

    def _manifeste_en_vigueur(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del contexte
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
        del contexte
        if faits.suspension or self.suspendu(self.agent()):
            return _refus("suspension", "agent suspendu : les identifiants sont coupés")
        return None

    def _budgets(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del contexte
        if faits.appels_restants <= 0:
            return _refus("budget-epuise", "budget d'appels épuisé")
        if faits.jetons_restants <= 0:
            return _refus("budget-epuise", "budget de jetons épuisé")
        return None

    def _duree(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del contexte
        if faits.duree_ecoulee_secondes >= faits.duree_maximale_secondes:
            return _refus("duree-depassee", "durée maximale de session atteinte")
        return None

    def _ressources(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del faits
        autorisees = self._ressources_de(contexte.outil)
        for ressource in contexte.ressources:
            if not _dans_le_perimetre(normaliser(ressource), autorisees):
                return _refus(
                    "ressource-hors-perimetre", f"ressource « {ressource} » hors du périmètre déclaré"
                )
        return None

    def _colonnes(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del faits
        declarees = {colonne for outil in self._document["tools"] for colonne in outil["columns"]}
        if not declarees or not contexte.colonnes:
            return None
        for colonne in contexte.colonnes:
            if colonne not in declarees:
                return _refus("colonnes-hors-perimetre", f"colonne « {colonne} » non déclarée")
        return None

    def _sorties(self, contexte: ContexteAppel, faits: FaitsSession) -> DecisionPolitique | None:
        del faits
        if not contexte.sortie_reseau:
            return None
        if contexte.destination in self._document["outputs"]:
            return None
        return _refus(
            "sortie-non-declaree",
            f"destination « {contexte.destination or 'inconnue'} » non déclarée au manifeste",
        )

    def _ressources_de(self, outil: str) -> tuple[str, ...]:
        for declare in self._document["tools"]:
            if declare["id"] == outil:
                return tuple(declare["resources"])
        return ()


def _dans_le_perimetre(ressource: str, autorisees: Sequence[str]) -> bool:
    """Une ressource est dans le périmètre si elle est déclarée, ou sous un préfixe déclaré."""
    if not autorisees:
        return False
    return any(
        ressource == autorisee or ressource.startswith(autorisee.rstrip("*").rstrip("/"))
        for autorisee in autorisees
    )


def _refus(regle: str, motif: str) -> DecisionPolitique:
    return DecisionPolitique(decision=Decision.REFUSE, regle_appliquee=regle, motif=motif)
