"""The homologation report, in French and in English (EF-40, §17).

Structure, identical in both languages:

1. identity and perimeter, 2. what was run, 3. measured cost, 4. findings by
nature **with the exploration filtering shown**, 5. declared vs observed in both
directions, 6. compositions, 7. statistical scope, 8. integrity of the journal,
9. verdict and conditions, 10. what this report does **not** guarantee (§24.3).

Point 4 is the one that separates a product from a raw log: the report says how
many calls were denied and how many of those were exploration, filtered out
(§13.5). Point 10 is what makes the document defensible in front of an auditor.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sas import constantes
from sas.analyseur.classification import filtrer_exploration
from sas.i18n import traduire
from sas.rapports.verdict import Decision
from sas.types import (
    Attestation,
    Composition,
    CoutMesure,
    Ecart,
    EtatChaine,
    Langue,
    Manifeste,
    Nature,
    Tentative,
    TypeEcart,
)

TITRES_FR = (
    "1. Identité et périmètre",
    "2. Ce qui a été exécuté",
    "3. Coût mesuré",
    "4. Découvertes, et ce qui a été filtré",
    "5. Écart déclaré / observé",
    "6. Compositions détectées",
    "7. Portée statistique",
    "8. Intégrité du journal",
    "9. Verdict",
    "10. Ce que ce rapport ne garantit pas",
)
TITRES_EN = (
    "1. Identity and perimeter",
    "2. What was run",
    "3. Measured cost",
    "4. Findings, and what was filtered out",
    "5. Declared vs observed",
    "6. Detected compositions",
    "7. Statistical scope",
    "8. Journal integrity",
    "9. Verdict",
    "10. What this report does not guarantee",
)


@dataclass(frozen=True, slots=True)
class EntreesRapport:
    """Everything the report quotes. One object, so no section can drift."""

    manifeste: Manifeste
    decision: Decision
    tentatives: Sequence[Tentative]
    compositions: Sequence[Composition]
    ecarts: Sequence[Ecart]
    cout: CoutMesure
    etat_chaine: EtatChaine
    sessions: int
    appels: int
    refus: int
    borne_texte: str
    attestation: Attestation | None = None
    limites_ombre: Sequence[str] = ()
    source_permissions_mortes: str = "journal"


def generer(entrees: EntreesRapport, langue: Langue = Langue.FR) -> str:
    return _fr(entrees) if langue is Langue.FR else _en(entrees)


# --------------------------------------------------------------------------- #
# Français
# --------------------------------------------------------------------------- #


def _fr(e: EntreesRapport) -> str:
    identite = e.manifeste.identite
    lignes = [
        f"RAPPORT D'HOMOLOGATION — {identite.nom} {identite.version_agent}",
        f"Tenant : {e.manifeste.agent_id} · Manifeste v{e.manifeste.version} · "
        f"{traduire('mode.ombre', Langue.FR)}",
        "",
        TITRES_FR[0],
        f"  Éditeur            {identite.editeur}",
        f"  Empreinte          {identite.empreinte_paquet[:26]}…",
        f"  Modèle déclaré     {identite.modele} ({identite.version_modele})",
        f"  Finalité           {e.manifeste.finalite.fait.strip()[:160]}",
        "",
        TITRES_FR[1],
        f"  Sessions           {e.sessions}",
        f"  Appels d'outils    {e.appels} (dont {e.refus} refusés par Policy)",
        f"  Couverture journal {_pourcent(e.appels, e.etat_chaine.entrees)} (exigence : 100 %)",
        "",
        TITRES_FR[2],
        f"  Coût mesuré        {e.cout.total} $",
        f"  Jetons             {e.cout.jetons_entree} in / {e.cout.jetons_sortie} out",
        f"  Runtime            {e.cout.runtime_secondes:.0f} s",
        "",
        TITRES_FR[3],
    ]
    lignes += _decouvertes_fr(e)
    lignes += ["", TITRES_FR[4]]
    lignes += _ecarts_fr(e)
    lignes += ["", TITRES_FR[5]]
    lignes += _compositions_fr(e)
    lignes += ["", TITRES_FR[6], f"  {e.borne_texte}", "", TITRES_FR[7]]
    lignes += _integrite_fr(e)
    lignes += ["", TITRES_FR[8]]
    lignes += _verdict_fr(e)
    lignes += ["", TITRES_FR[9]]
    lignes += _limites_fr(e)
    return "\n".join(lignes)


def _decouvertes_fr(e: EntreesRapport) -> list[str]:
    visibles = filtrer_exploration(e.tentatives)
    exploration = e.decision.decouvertes.get(Nature.EXPLORATION, 0)
    lignes = [
        f"  Appels refusés     {e.refus}",
        f"  Exploration        {exploration}   (filtrée : bruit de raisonnement, §13.5)",
        f"  Restent à lire     {len(visibles)}",
    ]
    for nature in (Nature.DEBORDEMENT, Nature.TENTATIVE, Nature.HOSTILE, Nature.INDETERMINEE):
        lignes.append(f"    {nature.value:<14}{e.decision.decouvertes.get(nature, 0):>6}")
    return lignes


def _ecarts_fr(e: EntreesRapport) -> list[str]:
    debordements = [x for x in e.ecarts if x.type is TypeEcart.DEBORDEMENT]
    mortes = [x for x in e.ecarts if x.type is TypeEcart.PERMISSION_MORTE]
    lignes = [
        f"  Ressources touchées non déclarées : {len(debordements)}",
        f"  Permissions déclarées jamais utilisées : {len(mortes)}",
    ]
    for ecart in debordements[:10]:
        lignes.append(f"    + {ecart.ressource}  ({ecart.frequence} appels)")
    for ecart in mortes[:10]:
        lignes.append(f"    - {ecart.ressource}  (déclarée, jamais exercée)")
    if e.source_permissions_mortes == "iam-access-analyzer":
        lignes.append("  Source des permissions mortes : IAM Access Analyzer (source native, EF-21)")
    else:
        lignes.append(
            "  Source des permissions mortes : journal du sas. Le croisement IAM Access Analyzer "
            "n'était pas disponible (il exige 90 jours d'historique)."
        )
    return lignes


def _compositions_fr(e: EntreesRapport) -> list[str]:
    if not e.compositions:
        return ["  Aucune chaîne interdite détectée sur les chaînes de deux et trois appels."]
    lignes = [f"  {len(e.compositions)} composition(s) détectée(s) :"]
    for composition in e.compositions[:8]:
        lignes.append(f"    {composition.motif.value} ({composition.nature.value}) : {composition.preuve}")
    lignes.append("  Les canaux cachés fins ne sont pas couverts au lancement (§16.4).")
    return lignes


def _integrite_fr(e: EntreesRapport) -> list[str]:
    etat = e.etat_chaine
    if etat.integre:
        return [
            f"  Journal chaîné, {etat.entrees} entrées, aucune rupture.",
            f"  Empreinte finale : {etat.empreinte_finale[:26]}…",
        ]
    return [
        f"  RUPTURE DE CHAÎNE détectée à l'entrée {etat.premiere_rupture} : le rapport est nul.",
    ]


def _verdict_fr(e: EntreesRapport) -> list[str]:
    lignes = [f"  Verdict : {e.decision.verdict.value.upper()}"]
    for motif in e.decision.motifs:
        lignes.append(f"    · {motif}")
    if e.decision.conditions:
        lignes.append("  Conditions :")
        lignes += [f"    {i}. {c}" for i, c in enumerate(e.decision.conditions, start=1)]
    if e.attestation is not None:
        numero = e.attestation.numero
        echeance = f"{e.attestation.valide_jusquau:%Y-%m-%d}"
        lignes.append(f"  Attestation : {numero}, valable jusqu'au {echeance}")
    lignes.append("  La décision de mise en production est le ressort exclusif du commanditaire.")
    return lignes


def _limites_fr(e: EntreesRapport) -> list[str]:
    lignes = [
        f"  · Une homologation sur {e.attestation.n_rejeux if e.attestation else '?'} rejeux ne prouve rien "
        "au-delà de la borne publiée ci-dessus (§24.3).",
        "  · Le mode Ombre ne couvre pas les comportements dépendant de données réelles (§10.4).",
        "  · Un agent non instrumentable est déclaré non mesurable, jamais conforme (ENF-17).",
        "  · Les canaux cachés fins ne sont pas détectés (§16.4).",
        "  · Sas ne garantit pas la qualité fonctionnelle de l'agent, seulement son comportement d'accès.",
    ]
    lignes += [f"  · {limite}" for limite in e.limites_ombre]
    return lignes


# --------------------------------------------------------------------------- #
# English
# --------------------------------------------------------------------------- #


def _en(e: EntreesRapport) -> str:
    identite = e.manifeste.identite
    lines = [
        f"HOMOLOGATION REPORT — {identite.nom} {identite.version_agent}",
        f"Tenant: {e.manifeste.agent_id} · manifest v{e.manifeste.version} · shadow mode",
        "",
        TITRES_EN[0],
        f"  Vendor             {identite.editeur}",
        f"  Fingerprint        {identite.empreinte_paquet[:26]}…",
        f"  Declared model     {identite.modele} ({identite.version_modele})",
        f"  Purpose            {e.manifeste.finalite.fait.strip()[:160]}",
        "",
        TITRES_EN[1],
        f"  Sessions           {e.sessions}",
        f"  Tool calls         {e.appels} (of which {e.refus} denied by Policy)",
        f"  Journal coverage   {_pourcent(e.appels, e.etat_chaine.entrees)} (blocking: 100 %)",
        "",
        TITRES_EN[2],
        f"  Measured cost      ${e.cout.total}",
        f"  Tokens             {e.cout.jetons_entree} in / {e.cout.jetons_sortie} out",
        f"  Runtime            {e.cout.runtime_secondes:.0f} s",
        "",
        TITRES_EN[3],
    ]
    lines += _en_decouvertes(e)
    lines += ["", TITRES_EN[4], *_en_ecarts(e)]
    lines += ["", TITRES_EN[5], *_en_compositions(e)]
    lines += ["", TITRES_EN[6], f"  {e.borne_texte}", "", TITRES_EN[7], *_en_integrite(e)]
    lines += ["", TITRES_EN[8], *_en_verdict(e)]
    lines += ["", TITRES_EN[9], *_en_limites(e)]
    return "\n".join(lines)


def _en_decouvertes(e: EntreesRapport) -> list[str]:
    visibles = filtrer_exploration(e.tentatives)
    exploration = e.decision.decouvertes.get(Nature.EXPLORATION, 0)
    lines = [
        f"  Denied calls       {e.refus}",
        f"  Exploration        {exploration}   (filtered out: reasoning noise, spec 13.5)",
        f"  Left to read       {len(visibles)}",
    ]
    for nature in (Nature.DEBORDEMENT, Nature.TENTATIVE, Nature.HOSTILE, Nature.INDETERMINEE):
        lines.append(f"    {nature.value:<14}{e.decision.decouvertes.get(nature, 0):>6}")
    return lines


def _en_ecarts(e: EntreesRapport) -> list[str]:
    debordements = [x for x in e.ecarts if x.type is TypeEcart.DEBORDEMENT]
    mortes = [x for x in e.ecarts if x.type is TypeEcart.PERMISSION_MORTE]
    lines = [
        f"  Resources touched but not declared: {len(debordements)}",
        f"  Permissions declared but never used: {len(mortes)}",
    ]
    lines += [f"    + {gap.ressource}  ({gap.frequence} calls)" for gap in debordements[:10]]
    lines += [f"    - {gap.ressource}  (declared, never exercised)" for gap in mortes[:10]]
    if e.source_permissions_mortes == "iam-access-analyzer":
        lines.append("  Dead-permission source: IAM Access Analyzer (native source, EF-21).")
    else:
        lines.append(
            "  Dead-permission source: the airlock journal. The IAM Access Analyzer "
            "cross-reference was unavailable (it requires 90 days of history)."
        )
    return lines


def _en_compositions(e: EntreesRapport) -> list[str]:
    if not e.compositions:
        return ["  No forbidden chain detected on two- and three-call chains."]
    lines = [f"  {len(e.compositions)} composition(s) detected:"]
    lines += [f"    {c.motif.value} ({c.nature.value}): {c.preuve}" for c in e.compositions[:8]]
    lines.append("  Fine covert channels are not covered at launch (16.4).")
    return lines


def _en_integrite(e: EntreesRapport) -> list[str]:
    if e.etat_chaine.integre:
        return [
            f"  Chained journal, {e.etat_chaine.entrees} entries, no break.",
            f"  Final fingerprint: {e.etat_chaine.empreinte_finale[:26]}…",
        ]
    return [f"  CHAIN BREAK at entry {e.etat_chaine.premiere_rupture}: this report is void."]


def _en_verdict(e: EntreesRapport) -> list[str]:
    lines = [f"  Verdict: {e.decision.verdict.value.upper()}"]
    lines += [f"    - {motif}" for motif in e.decision.motifs]
    if e.decision.conditions:
        lines.append("  Conditions:")
        lines += [f"    {i}. {c}" for i, c in enumerate(e.decision.conditions, start=1)]
    if e.attestation is not None:
        echeance = f"{e.attestation.valide_jusquau:%Y-%m-%d}"
        lines.append(f"  Attestation: {e.attestation.numero}, valid until {echeance}")
    lines.append("  Production go-live decision: sole responsibility of the sponsor.")
    return lines


def _en_limites(e: EntreesRapport) -> list[str]:
    rejeux = e.attestation.n_rejeux if e.attestation else "?"
    lines = [
        f"  - An homologation over {rejeux} replays proves nothing beyond the bound above (24.3).",
        "  - Shadow mode does not cover behaviours that depend on real data (10.4).",
        "  - An agent that cannot be instrumented is declared not measurable, never compliant.",
        "  - Fine covert channels are not detected (16.4).",
        "  - Sas never guarantees the agent's functional quality, only its access behaviour.",
    ]
    return lines + [f"  - {limite}" for limite in e.limites_ombre]


def _pourcent(emis: int, journalises: int) -> str:
    if not emis:
        return "100 %"
    return f"{100.0 * journalises / emis:.0f} %"


def kpi(entrees: EntreesRapport) -> Mapping[str, Any]:
    """The eight KPIs of §5.2, as measured values — quotable by the portal."""
    return {
        "KPI-1": entrees.refus,
        "KPI-3": float(entrees.cout.total),
        "KPI-4": _pourcent(entrees.appels, entrees.etat_chaine.entrees),
        "KPI-5": len(entrees.ecarts),
        "KPI-7": entrees.borne_texte,
        "KPI-8": len(entrees.compositions),
        "verdict": entrees.decision.verdict.value,
        "budget_credits": float(constantes.BUDGET_CREDITS),
    }
