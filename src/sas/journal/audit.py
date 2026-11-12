"""The audit of a received export (lot 7): the third party's side of the format.

This module is the **published** format, implemented on the auditor's side.
It deliberately imports nothing from Sas: the whole point of the format is
that a third party — an auditor, an insurer, another agent — can check the
integrity of an exported journal with the standard library alone, **without
executing the producer**. An audit that reuses the producer's own code proves
only that the producer is consistent with itself.

The rules implemented here are the ones written in `docs/FORMAT-JOURNAL.en.md`:

* the projection of an entry is the entry **minus** its two chain fields
  (`empreinte`, `empreinte_prec`);
* the canonical form is `json.dumps(v, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False)`, encoded UTF-8;
* the fingerprint of an entry is `sha256:` + the SHA-256 of the canonical form
  of `{"prec": <previous fingerprint>, "entree": <canonical projection>}`;
* the chain restarts on an empty fingerprint at each new session;
* the fingerprint of the whole export is the SHA-256 of the canonical form of
  the ordered list of the entry fingerprints.

Everything is verified from the **text** of the export: the envelope on the
first line, the entries as JSON Lines below it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

#: The formats this auditor knows how to read. An unknown version is refused,
#: never guessed.
FORMATS_SUPPORTEES: tuple[str, ...] = ("sas-journal-export/1",)

#: The two fields excluded from the projection (the chain fields themselves).
CHAMPS_CHAINE: tuple[str, ...] = ("empreinte", "empreinte_prec")

#: The hash algorithm this auditor implements, and the prefix it prints.
HACHAGE = "sha256"
PREFIXE = "sha256:"

#: The chain starts empty at each session.
GRAIN = ""

#: The canonical form: sorted keys, no whitespace, non-ASCII kept as is.
CANONIQUE: dict[str, Any] = {
    "cles_triees": True,
    "separateurs": [",", ":"],
    "ensure_ascii": False,
    "encodage": "utf-8",
}

#: The fields an entry must carry to be auditable.
CHAMPS_ENTREE: tuple[str, ...] = ("id", "session_id", "empreinte", "empreinte_prec")

#: The fields the envelope must carry for the export to be complete.
CHAMPS_ENVELOPPE: tuple[str, ...] = (
    "format_version",
    "algorithme",
    "sessions",
    "entrees",
    "empreinte_export",
)


@dataclass(frozen=True, slots=True)
class RapportAudit:
    """What the auditor concludes about a received export.

    `motif` is a stable machine code (empty when the export is intact) and
    `message` says what to do about it — a refusal nobody can act on is a
    refusal nobody acts on.
    """

    integre: bool
    entrees: int = 0
    sessions: int = 0
    premiere_rupture: str | None = None
    index_rupture: int | None = None
    session_rupture: str | None = None
    motif: str = ""
    message: str = ""


# --------------------------------------------------------------------------- #
# The entry point
# --------------------------------------------------------------------------- #


def auditer(texte: str) -> RapportAudit:
    """Judge the **text** of an export, as a third party would receive it."""
    lignes = [ligne for ligne in texte.splitlines() if ligne.strip()]
    if not lignes:
        return _refus("export-vide", "L'export reçu est vide : il n'y a rien à vérifier.")
    enveloppe = _lire_objet(lignes[0])
    if enveloppe is None:
        return _refus(
            "enveloppe-invalide",
            "La première ligne n'est pas un objet JSON : l'enveloppe est illisible.",
        )
    refus = _verifier_enveloppe(enveloppe)
    if refus is not None:
        return refus
    entrees, message = _lire_entrees(lignes[1:])
    if entrees is None:
        return _refus("entree-invalide", message)
    rupture = _verifier_chaines(entrees)
    if rupture is not None:
        return rupture
    refus = _verifier_completude(enveloppe, entrees)
    if refus is not None:
        return refus
    sessions = len(_par_session(entrees))
    return RapportAudit(
        integre=True,
        entrees=len(entrees),
        sessions=sessions,
        message=f"Export intact : {len(entrees)} entrée(s), {sessions} session(s).",
    )


# --------------------------------------------------------------------------- #
# The envelope
# --------------------------------------------------------------------------- #


def _verifier_enveloppe(enveloppe: dict[str, Any]) -> RapportAudit | None:
    """Check the envelope: known version, known algorithm, expected fields."""
    if "format_version" not in enveloppe:
        return _refus(
            "format-inconnu",
            "L'enveloppe ne porte pas de version de format : ce n'est pas un export Sas "
            "(ou son enveloppe a été retirée).",
        )
    version = enveloppe.get("format_version")
    if version not in FORMATS_SUPPORTEES:
        return _refus(
            "format-inconnu",
            f"Version de format inconnue : {version!r}. "
            f"Versions supportées : {', '.join(FORMATS_SUPPORTEES)}.",
        )
    manquants = [champ for champ in CHAMPS_ENVELOPPE if champ not in enveloppe]
    if manquants:
        return _refus(
            "enveloppe-incomplete",
            f"Le champ {manquants[0]!r} manque dans l'enveloppe : l'export est incomplet.",
        )
    return _verifier_algorithme(enveloppe.get("algorithme"))


def _verifier_algorithme(algorithme: Any) -> RapportAudit | None:
    """The algorithm is self-describing: refuse to check what we cannot check."""
    if not isinstance(algorithme, dict):
        return _refus("algorithme-inconnu", "L'algorithme déclaré est illisible.")
    for cle, valeur in (("empreinte", HACHAGE), ("prefixe", PREFIXE)):
        if algorithme.get(cle) != valeur:
            return _refus(
                "algorithme-inconnu",
                f"L'algorithme déclaré ({cle}={algorithme.get(cle)!r}) n'est pas celui que cet "
                f"auditeur implémente ({valeur!r}) : audit refusé plutôt qu'approximé.",
            )
    canonique = algorithme.get("canonique")
    if not isinstance(canonique, dict):
        return _refus("algorithme-inconnu", "La forme canonique déclarée est illisible.")
    for cle, valeur in CANONIQUE.items():
        if canonique.get(cle) != valeur:
            return _refus(
                "algorithme-inconnu",
                f"La forme canonique déclarée ({cle}={canonique.get(cle)!r}) n'est pas celle que "
                f"cet auditeur implémente ({valeur!r}) : audit refusé.",
            )
    projection = algorithme.get("projection")
    exclus = projection.get("champs_exclus") if isinstance(projection, dict) else None
    if list(exclus or []) != list(CHAMPS_CHAINE):
        return _refus(
            "algorithme-inconnu",
            f"La projection déclarée ne retire pas {list(CHAMPS_CHAINE)} : audit refusé.",
        )
    liaison = algorithme.get("liaison")
    if not isinstance(liaison, dict) or liaison.get("graine") != GRAIN:
        return _refus(
            "algorithme-inconnu",
            f"La chaîne déclarée ne repart pas de la graine {GRAIN!r} : audit refusé.",
        )
    return None


# --------------------------------------------------------------------------- #
# The entries
# --------------------------------------------------------------------------- #


def _lire_entrees(lignes: list[str]) -> tuple[list[dict[str, Any]] | None, str]:
    """Read the entries (JSON Lines). `None` means the export is not readable."""
    entrees: list[dict[str, Any]] = []
    for numero, ligne in enumerate(lignes, start=1):
        entree = _lire_objet(ligne)
        if entree is None:
            return None, f"La ligne d'entrée {numero} n'est pas un objet JSON : export illisible."
        manquants = [champ for champ in CHAMPS_ENTREE if champ not in entree]
        if manquants:
            return None, f"La ligne d'entrée {numero} ne porte pas {manquants} : export illisible."
        entrees.append(entree)
    return entrees, ""


def _par_session(entrees: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Group the entry indices by session, keeping the order of the file."""
    groupes: dict[str, list[int]] = {}
    for index, entree in enumerate(entrees):
        groupes.setdefault(str(entree["session_id"]), []).append(index)
    return groupes


def _verifier_chaines(entrees: list[dict[str, Any]]) -> RapportAudit | None:
    """Walk every session chain; report the first break, with its id and index."""
    for session, indices in _par_session(entrees).items():
        attendu = GRAIN
        for index in indices:
            entree = entrees[index]
            if str(entree["empreinte_prec"]) != attendu:
                return _rupture(
                    entrees,
                    index,
                    session,
                    "liaison-rompue",
                    f"L'entrée {entree['id']!r} (index {index}) déclare une empreinte précédente "
                    f"{entree['empreinte_prec']!r} alors que la chaîne attend {attendu!r} : "
                    "une entrée a été supprimée ou déplacée.",
                )
            calcule = _empreinte(attendu, _projection(entree))
            if calcule != entree["empreinte"]:
                return _rupture(
                    entrees,
                    index,
                    session,
                    "empreinte-incoherente",
                    f"L'entrée {entree['id']!r} (index {index}) porte l'empreinte "
                    f"{entree['empreinte']!r} mais le recalcul donne {calcule!r} : "
                    "l'entrée a été modifiée après coup.",
                )
            attendu = str(entree["empreinte"])
    return None


def _verifier_completude(enveloppe: dict[str, Any], entrees: list[dict[str, Any]]) -> RapportAudit | None:
    """The export must contain every declared session, complete and in order."""
    sessions = enveloppe.get("sessions")
    if not isinstance(sessions, list):
        return _refus("enveloppe-incomplete", "Le bloc « sessions » de l'enveloppe est illisible.")
    groupes = _par_session(entrees)
    declares = {}
    for session in sessions:
        if not isinstance(session, dict) or "session_id" not in session:
            return _refus("enveloppe-incomplete", "Une session déclarée est illisible.")
        declares[str(session["session_id"])] = session
    for session in sorted(set(groupes) | set(declares)):
        refus = _comparer_session(session, groupes, declares, entrees)
        if refus is not None:
            return refus
    total = _entier(enveloppe.get("entrees"))
    if total is not None and total != len(entrees):
        return _refus(
            "export-incomplet",
            f"L'enveloppe déclare {total} entrée(s) mais {len(entrees)} sont présentes.",
        )
    calcule = _empreinte_export(entrees)
    if enveloppe.get("empreinte_export") != calcule:
        return _refus(
            "empreinte-export-incoherente",
            f"L'empreinte de l'export vaut {calcule!r} alors que l'enveloppe déclare "
            f"{enveloppe.get('empreinte_export')!r} : le fichier a été modifié après coup.",
        )
    return None


def _comparer_session(
    session: str,
    groupes: dict[str, list[int]],
    declares: dict[str, dict[str, Any]],
    entrees: list[dict[str, Any]],
) -> RapportAudit | None:
    """One session must be present, complete, and end on the declared fingerprint."""
    if session not in groupes:
        return _refus(
            "export-incomplet",
            f"La session {session!r} est déclarée dans l'enveloppe mais absente des entrées.",
        )
    if session not in declares:
        return _refus(
            "export-incomplet",
            f"La session {session!r} figure dans les entrées mais n'est pas déclarée dans l'enveloppe.",
        )
    declare = declares[session]
    attendu = _entier(declare.get("entrees"))
    if attendu is not None and attendu != len(groupes[session]):
        return _refus(
            "export-incomplet",
            f"La session {session!r} déclare {attendu} entrée(s) mais {len(groupes[session])} "
            "sont présentes : l'export est tronqué.",
        )
    finale = _derniere_empreinte(groupes[session], entrees)
    declaree = declare.get("empreinte_finale")
    if declaree is not None and finale != declaree:
        return _refus(
            "export-incomplet",
            f"La session {session!r} se termine par l'empreinte {finale!r} alors que l'enveloppe "
            f"déclare {declaree!r}.",
        )
    return None


# --------------------------------------------------------------------------- #
# The published computation, implemented from the document alone
# --------------------------------------------------------------------------- #


def _canonique(valeur: Any) -> str:
    """The canonical form: sorted keys, no padding, non-ASCII kept as is."""
    return json.dumps(valeur, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _projection(entree: dict[str, Any]) -> dict[str, Any]:
    """What the chain commits to: the entry without its two chain fields."""
    return {cle: valeur for cle, valeur in entree.items() if cle not in CHAMPS_CHAINE}


def _empreinte(precedente: str, projection: dict[str, Any]) -> str:
    """The next link of the chain, computed from the published rules only."""
    corps = _canonique({"prec": precedente, "entree": _canonique(projection)})
    return PREFIXE + hashlib.sha256(corps.encode("utf-8")).hexdigest()


def _empreinte_export(entrees: list[dict[str, Any]]) -> str:
    """The fingerprint of the whole file: the ordered list of entry fingerprints."""
    empreintes = [str(entree["empreinte"]) for entree in entrees]
    return PREFIXE + hashlib.sha256(_canonique(empreintes).encode("utf-8")).hexdigest()


def _derniere_empreinte(indices: list[int], entrees: list[dict[str, Any]]) -> str:
    return str(entrees[indices[-1]]["empreinte"]) if indices else GRAIN


def _entier(valeur: Any) -> int | None:
    """An integer field, or `None` when it is absent or not a number."""
    return valeur if isinstance(valeur, int) and not isinstance(valeur, bool) else None


# --------------------------------------------------------------------------- #
# The two ways to answer
# --------------------------------------------------------------------------- #


def _refus(motif: str, message: str) -> RapportAudit:
    """A refusal: the export is not accepted, and here is why."""
    return RapportAudit(integre=False, motif=motif, message=message)


def _rupture(
    entrees: list[dict[str, Any]],
    index: int,
    session: str,
    motif: str,
    message: str,
) -> RapportAudit:
    """A break in the chain: which entry, at which index, in which session."""
    return RapportAudit(
        integre=False,
        entrees=len(entrees),
        sessions=len(_par_session(entrees)),
        premiere_rupture=str(entrees[index]["id"]),
        index_rupture=index,
        session_rupture=session,
        motif=motif,
        message=message,
    )


def _lire_objet(ligne: str) -> dict[str, Any] | None:
    """Read one JSON object; `None` when the line is not one."""
    try:
        valeur = json.loads(ligne)
    except json.JSONDecodeError:
        return None
    return valeur if isinstance(valeur, dict) else None
