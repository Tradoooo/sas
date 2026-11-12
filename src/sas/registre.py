"""The fleet registry (EF-43, §8) — statuses, deadlines, and vendor trust.

The offer includes a registry from three agents onwards: the inventory of every
third-party agent of a client, with its status and its deadline. Three things
make it more than a list:

* **deadlines that fire** — an attestation expires on a date *or* on any change
  of version, model or prompt, whichever comes first (§17.2), and the registry is
  what tells the sponsor which agents are about to need re-homologation;
* **a vendor trust score over time** — the same vendor homologated three times
  tells you something a single attestation cannot: does the declared perimeter
  hold, does the gap shrink or grow, do undeclared changes keep happening;
* **cross-agent comparison** for one use case, which is what a buyer actually
  asks: among three agents that read tickets, which one has the cleanest observed
  behaviour.

Nothing here decides anything. The registry informs the sponsor; the production
go-live decision stays theirs (§24.4).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sas.identifiants import maintenant
from sas.types import Agent, Attestation, Derive, Editeur, LigneRegistre, StatutAgent, Verdict

ALERTE_JOURS = 30


@dataclass(frozen=True, slots=True)
class EntreeHistorique:
    """One homologation of one agent, as the registry remembers it."""

    agent_id: str
    editeur_id: str
    version: str
    date: datetime
    verdict: Verdict
    debordements: int
    permissions_mortes: int
    compositions: int
    tentatives: int
    derive_non_declaree: bool = False
    n_rejeux: int = 0


@dataclass(frozen=True, slots=True)
class ScoreEditeur:
    """What repeated homologations say about a vendor. A reading, not a rating."""

    editeur_id: str
    homologations: int
    part_homologues: float
    debordements_moyens: float
    permissions_mortes_moyennes: float
    compositions: int
    derives_non_declarees: int
    tendance: str
    explication: str


def construire(
    agents: Sequence[Agent],
    editeurs: Sequence[Editeur],
    attestations: Sequence[Attestation],
    campagnes_par_agent: Sequence[int] | None = None,
    couts: Sequence[Decimal] | None = None,
) -> tuple[LigneRegistre, ...]:
    """Build the registry lines from what the store holds."""
    par_editeur = {e.id: e for e in editeurs}
    derniere = _dernieres_attestations(attestations)
    lignes: list[LigneRegistre] = []
    for index, agent in enumerate(agents):
        # The frozen Attestation carries `agent_nom`, not an agent id: that is
        # the key the registry matches on.
        attestation = derniere.get(agent.nom)
        lignes.append(
            LigneRegistre(
                agent=agent,
                editeur=par_editeur.get(agent.editeur_id, Editeur(id=agent.editeur_id, nom="?", contact="")),
                derniere_homologation=attestation.date if attestation else None,
                valide_jusquau=attestation.valide_jusquau if attestation else None,
                resultat=attestation.resultat if attestation else None,
                campagnes=(campagnes_par_agent[index] if campagnes_par_agent else 0),
                cout_cumule=(couts[index] if couts else Decimal("0")),
            )
        )
    return tuple(sorted(lignes, key=lambda ligne: ligne.agent.nom))


def _dernieres_attestations(attestations: Sequence[Attestation]) -> dict[str, Attestation]:
    """The most recent attestation per agent — the registry shows the current one."""
    derniere: dict[str, Attestation] = {}
    for attestation in sorted(attestations, key=lambda a: a.date):
        derniere[attestation.agent_nom] = attestation
    return derniere


@dataclass(frozen=True, slots=True)
class Echeance:
    agent_id: str
    nom: str
    editeur: str
    echeance: datetime | None
    jours_restants: int | None
    etat: str  # "echue" | "imminente" | "valide" | "sans_attestation"


def echeances(
    registre: Sequence[LigneRegistre], *, aujourdhui: datetime | None = None, fenetre: int = ALERTE_JOURS
) -> tuple[Echeance, ...]:
    """What is about to need re-homologation. Sorted: overdue first."""
    reference = aujourdhui or maintenant()
    sorties: list[Echeance] = []
    for ligne in registre:
        echeance = ligne.valide_jusquau
        if echeance is None:
            sorties.append(
                Echeance(ligne.agent.id, ligne.agent.nom, ligne.editeur.nom, None, None, "sans_attestation")
            )
            continue
        jours = (echeance - reference).days
        etat = "echue" if jours < 0 else ("imminente" if jours <= fenetre else "valide")
        sorties.append(Echeance(ligne.agent.id, ligne.agent.nom, ligne.editeur.nom, echeance, jours, etat))
    ordre = {"echue": 0, "imminente": 1, "sans_attestation": 2, "valide": 3}
    return tuple(
        sorted(
            sorties,
            key=lambda e: (ordre.get(e.etat, 9), e.jours_restants if e.jours_restants is not None else 10**6),
        )
    )


def a_rehomologuer(
    registre: Sequence[LigneRegistre], *, aujourdhui: datetime | None = None, fenetre: int = ALERTE_JOURS
) -> tuple[Echeance, ...]:
    """Only what needs an action: overdue, imminent, or never homologated."""
    return tuple(e for e in echeances(registre, aujourdhui=aujourdhui, fenetre=fenetre) if e.etat != "valide")


def score_editeur(editeur_id: str, historique: Sequence[EntreeHistorique]) -> ScoreEditeur:
    """§8 — the value of watching a vendor over time rather than once."""
    entrees = [e for e in historique if e.editeur_id == editeur_id]
    if not entrees:
        return ScoreEditeur(editeur_id, 0, 0.0, 0.0, 0.0, 0, 0, "inconnue", "aucune homologation enregistrée")
    total = len(entrees)
    homologues = sum(1 for e in entrees if e.verdict in (Verdict.HOMOLOGUE, Verdict.SOUS_CONDITIONS))
    moitie = total // 2
    debut = entrees[:moitie] or entrees
    fin = entrees[moitie:] or entrees
    ecart_debut = _taux_ecart(debut)
    ecart_fin = _taux_ecart(fin)
    if total < 2:
        tendance, explication = "inconnue", "une seule homologation : aucune tendance possible"
    elif ecart_fin < ecart_debut - 0.05:
        tendance = "amelioration"
        explication = f"l'écart déclaré/observé passe de {ecart_debut:.2f} à {ecart_fin:.2f} par homologation"
    elif ecart_fin > ecart_debut + 0.05:
        tendance = "degradation"
        explication = f"l'écart déclaré/observé passe de {ecart_debut:.2f} à {ecart_fin:.2f} par homologation"
    else:
        tendance = "stable"
        explication = f"écart déclaré/observé stable autour de {ecart_fin:.2f} par homologation"
    return ScoreEditeur(
        editeur_id=editeur_id,
        homologations=total,
        part_homologues=round(homologues / total, 4),
        debordements_moyens=round(sum(e.debordements for e in entrees) / total, 4),
        permissions_mortes_moyennes=round(sum(e.permissions_mortes for e in entrees) / total, 4),
        compositions=sum(e.compositions for e in entrees),
        derives_non_declarees=sum(1 for e in entrees if e.derive_non_declaree),
        tendance=tendance,
        explication=explication,
    )


def _taux_ecart(entrees: Sequence[EntreeHistorique]) -> float:
    return sum(e.debordements + e.permissions_mortes for e in entrees) / max(1, len(entrees))


@dataclass(frozen=True, slots=True)
class Comparaison:
    """Same use case, several agents: what the buyer actually asks."""

    agent_id: str
    nom: str
    editeur: str
    verdict: str
    appels: int
    refus: int
    debordements: int
    permissions_mortes: int
    compositions: int
    cout: Decimal
    n_rejeux: int


def comparer(comparaisons: Sequence[Comparaison]) -> tuple[Comparaison, ...]:
    """Rank agents for one use case, cleanest observed behaviour first.

    The ordering is explicit and explainable: a refusal is disqualifying, then
    fewer compositions, then fewer gaps, then fewer denials. Cost comes last on
    purpose — a cheap agent that is refused costs more than an expensive one that
    is approved.
    """

    def cle(c: Comparaison) -> tuple[int, int, int, int, Decimal]:
        bloque = 1 if c.verdict in (Verdict.REFUSE.value, Verdict.NON_MESURABLE.value) else 0
        return (bloque, c.compositions, c.debordements + c.permissions_mortes, c.refus, c.cout)

    return tuple(sorted(comparaisons, key=cle))


def resume_registre(registre: Sequence[LigneRegistre]) -> dict[str, object]:
    """The figures the account manager reads (§7, aggregated view only)."""
    statuts: dict[str, int] = {}
    for ligne in registre:
        cle = ligne.agent.statut.value
        statuts[cle] = statuts.get(cle, 0) + 1
    return {
        "agents": len(registre),
        "statuts": statuts,
        "a_rehomologuer": len(a_rehomologuer(registre)),
        "cout_cumule": float(sum((ligne.cout_cumule for ligne in registre), Decimal("0"))),
        "prochaine_echeance": min(
            (ligne.valide_jusquau for ligne in registre if ligne.valide_jusquau), default=None
        ),
    }


def statut_apres_verdict(verdict: Verdict) -> StatutAgent:
    """One mapping, used by the registry and by the API: a verdict changes the
    agent's status, and nothing else does."""
    return {
        Verdict.HOMOLOGUE: StatutAgent.HOMOLOGUE,
        Verdict.SOUS_CONDITIONS: StatutAgent.SOUS_CONDITIONS,
        Verdict.REFUSE: StatutAgent.REFUSE,
        Verdict.NON_MESURABLE: StatutAgent.NON_MESURABLE,
    }[verdict]


def derive_aggrave(derives: Sequence[Derive], seuil: int = 2) -> tuple[str, ...]:
    """Agents whose drift keeps coming back: a pattern, not an incident."""
    compte: dict[str, int] = {}
    for derive in derives:
        compte[derive.agent_id] = compte.get(derive.agent_id, 0) + 1
    return tuple(sorted(a for a, n in compte.items() if n >= seuil))


def fenetre_alerte(jours: int = ALERTE_JOURS) -> timedelta:
    return timedelta(days=jours)
