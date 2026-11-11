"""Loading a manifest from YAML or JSON into the frozen types (spec §9).

One subtlety is worth its own paragraph: **an absent `sorties_autorisees` key
and an empty one are not the same thing.** Annexe A requires the validator to
refuse the absence ("no output declared at all" is a deliberate statement, a
missing key is an oversight). The loader therefore records which optional keys
were missing, and `validation.valider` uses that list.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sas.manifeste.schema import BLOCS, BLOCS_LISTES, valider_structure
from sas.manifeste.versions import avec_empreinte
from sas.types import (
    Budgets,
    DonneeDemandee,
    Engagements,
    Finalite,
    IdentiteAgent,
    Manifeste,
    Mode,
    OutilDemande,
    ScenarioRef,
    SignatureEditeur,
    SortieAutorisee,
    StatutManifeste,
    ValidationClient,
)

VRAIS = {"vrai", "true", "oui", "yes", "1", "on"}
FAUX = {"faux", "false", "non", "no", "0", "off"}
CLEFS_TRACEES: tuple[str, ...] = ("sorties_autorisees",)


class ErreurManifeste(Exception):
    """Raised when the document cannot even be read as a manifest."""

    def __init__(self, message: str, problemes: tuple[Any, ...] = ()) -> None:
        super().__init__(message)
        self.problemes = problemes


@dataclass(frozen=True, slots=True)
class Chargement:
    manifeste: Manifeste
    cles_absentes: tuple[str, ...]
    source: str


def charger(source: str | Path) -> Chargement:
    """Read a manifest from a path or from a literal YAML/JSON string."""
    if isinstance(source, Path) or (isinstance(source, str) and "\n" not in source and Path(source).exists()):
        chemin = Path(source)
        texte = chemin.read_text(encoding="utf-8")
        nom = str(chemin)
    else:
        texte = str(source)
        nom = "<texte>"
    return charger_depuis_texte(texte, source=nom)


def charger_depuis_texte(texte: str, *, source: str = "<texte>") -> Chargement:
    donnees = _analyser(texte, source)
    rapport = valider_structure(donnees)
    if not rapport.valide:
        raise ErreurManifeste(f"manifeste structurellement invalide ({source})", rapport.problemes)
    cles_absentes = tuple(c for c in CLEFS_TRACEES if c not in donnees)
    # The fingerprint is computed on loading: a manifest always carries its own
    # canonical hash, so `est_executable` can compare it with the sealed one.
    return Chargement(
        manifeste=avec_empreinte(_construire(donnees)),
        cles_absentes=cles_absentes,
        source=source,
    )


def charger_manifeste(source: str | Path) -> Manifeste:
    """Convenience wrapper for callers that only need the manifest."""
    return charger(source).manifeste


def _analyser(texte: str, source: str) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:
        import json

        try:
            return json.loads(texte)
        except ValueError as exc:
            raise ErreurManifeste(f"PyYAML absent et JSON invalide ({source}): {exc}") from exc
    try:
        donnees = yaml.safe_load(texte)
    except yaml.YAMLError as exc:
        raise ErreurManifeste(f"YAML illisible ({source}): {exc}") from exc
    if not isinstance(donnees, dict):
        raise ErreurManifeste(f"le document {source} n'est pas un objet")
    return donnees


def _construire(d: dict[str, Any]) -> Manifeste:
    entete = d.get("manifeste", {})
    return Manifeste(
        agent_id=str(d.get("identite", {}).get("nom", "")).lower().replace(" ", "-"),
        version=int(entete.get("version", 1)),
        date=_date(entete.get("date")),
        identite=_identite(d.get("identite", {})),
        finalite=_finalite(d.get("finalite", {})),
        outils_demandes=tuple(_outil(o) for o in d.get("outils_demandes", ())),
        donnees_demandees=tuple(_donnee(x) for x in d.get("donnees_demandees", ())),
        sorties_autorisees=tuple(_sortie(s) for s in d.get("sorties_autorisees", ()) or ()),
        budgets=_budgets(d.get("budgets", {})),
        scenarios=tuple(_scenario(s) for s in d.get("scenarios", ())),
        interdictions_explicites=tuple(str(i) for i in d.get("interdictions_explicites", ())),
        engagements=_engagements(d.get("engagements", {})),
        memoire_persistante=_booleen(d.get("memoire", {}).get("persistante", False)),
        signature=_signature(d.get("signature")),
        validation_client=_validation(d.get("validation_client")),
        statut=_statut(d),
    )


def _statut(d: dict[str, Any]) -> StatutManifeste:
    if d.get("validation_client"):
        return StatutManifeste.VALIDE
    if d.get("signature"):
        return StatutManifeste.SIGNE_EDITEUR
    return StatutManifeste.BROUILLON


def _identite(b: dict[str, Any]) -> IdentiteAgent:
    return IdentiteAgent(
        nom=str(b.get("nom", "")),
        editeur=str(b.get("editeur", "")),
        version_agent=str(b.get("version_agent", "")),
        empreinte_paquet=str(b.get("empreinte_paquet", "")),
        modele=str(b.get("modele", "")),
        version_modele=str(b.get("version_modele", "")),
        engagement_notification_modele=_booleen(b.get("engagement_notification_modele", False)),
    )


def _finalite(b: dict[str, Any]) -> Finalite:
    return Finalite(
        fait=str(b.get("fait", "")).strip(), ne_fait_pas=tuple(str(x) for x in b.get("ne_fait_pas", ()))
    )


def _outil(b: dict[str, Any]) -> OutilDemande:
    return OutilDemande(
        nom=str(b.get("nom", "")),
        operation=str(b.get("operation", "")),  # type: ignore[arg-type]
        justification=str(b.get("justification", "")),
    )


def _donnee(b: dict[str, Any]) -> DonneeDemandee:
    return DonneeDemandee(
        type=str(b.get("type", "")),  # type: ignore[arg-type]
        ressource=str(b.get("ressource", "")),
        justification=str(b.get("justification", "")),
        colonnes=tuple(str(c) for c in b.get("colonnes", ())),
        prefixes=tuple(str(p) for p in b.get("prefixes", ())),
        sensible=_booleen(b.get("sensible", False)),
    )


def _sortie(b: dict[str, Any]) -> SortieAutorisee:
    return SortieAutorisee(
        destination=str(b.get("destination", "")),
        protocole=str(b.get("protocole", "")),  # type: ignore[arg-type]
        justification=str(b.get("justification", "")),
    )


def _budgets(b: dict[str, Any]) -> Budgets:
    return Budgets(
        appels_par_execution=_entier(b.get("appels_par_execution")),
        jetons_par_execution=_entier(b.get("jetons_par_execution")),
        duree_maximale_secondes=_entier(b.get("duree_maximale_secondes")),
        memoire_maximale_mio=_entier(b.get("memoire_maximale_mio")),
    )


def _scenario(b: dict[str, Any]) -> ScenarioRef:
    sensibilite = str(b.get("sensibilite", "ordinaire"))
    if sensibilite not in ("ordinaire", "elevee"):
        sensibilite = "ordinaire"
    return ScenarioRef(id=str(b.get("id", "")), nom=str(b.get("nom", "")), sensibilite=sensibilite)  # type: ignore[arg-type]


def _engagements(b: dict[str, Any]) -> Engagements:
    return Engagements(
        notification_changement_modele=str(b.get("notification_changement_modele", "")),
        notification_changement_invite=str(b.get("notification_changement_invite", "")),
        delai_correction_critique=str(b.get("delai_correction_critique", "")),
        contact=str(b.get("contact", "")),
    )


def _signature(b: Any) -> SignatureEditeur | None:
    if not isinstance(b, dict):
        return None
    return SignatureEditeur(
        signataire=str(b.get("signataire", "")),
        qualite=str(b.get("qualite", "")),
        date=_date(b.get("date")),
        empreinte_document=str(b.get("empreinte_document", "")),
    )


def _validation(b: Any) -> ValidationClient | None:
    if not isinstance(b, dict):
        return None
    mode = str(b.get("mode_autorise", "")).lower()
    choisi = Mode.OBSERVE if mode.startswith("observ") else Mode.OMBRE
    return ValidationClient(
        commanditaire=str(b.get("commanditaire", "")),
        date=_date(b.get("date")),
        perimetre_approuve=str(b.get("perimetre_approuve", "")),
        mode_autorise=choisi,
    )


def _booleen(valeur: Any) -> bool:
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return bool(valeur)
    return str(valeur).strip().lower() in VRAIS and str(valeur).strip().lower() not in FAUX


def _entier(valeur: Any) -> int:
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return 0


def _date(valeur: Any) -> datetime:
    if isinstance(valeur, datetime):
        return valeur if valeur.tzinfo else valeur.replace(tzinfo=UTC)
    if isinstance(valeur, date):
        return datetime(valeur.year, valeur.month, valeur.day, tzinfo=UTC)
    if isinstance(valeur, str) and valeur.strip():
        try:
            return datetime.fromisoformat(valeur.strip()).replace(tzinfo=UTC)
        except ValueError:
            return datetime(1970, 1, 1, tzinfo=UTC)
    return datetime(1970, 1, 1, tzinfo=UTC)


def blocs_attendus() -> tuple[str, ...]:
    """Names of the declared blocks, in the order of annexe A."""
    return tuple(BLOCS)


def blocs_listes() -> tuple[str, ...]:
    return tuple(BLOCS_LISTES)
