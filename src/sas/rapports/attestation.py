"""The attestation: dated, chained, deliberately poor in details (§17.2).

One page, for a third party — an insurer, an auditor, a contracting authority.
It carries **no client data** and no detail that would let anybody reproduce an
attempt. What it does carry, and what no competitor will show, is its own
statistical scope (KPI-7).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta

from sas import constantes
from sas.identifiants import numero_attestation, tronquer
from sas.rapports.verdict import Decision
from sas.types import (
    Attestation,
    BorneStatistique,
    Campagne,
    Composition,
    EtatChaine,
    Manifeste,
    Mode,
    Nature,
)

VALIDITE_JOURS = 90


def construire(
    *,
    campagne: Campagne,
    manifeste: Manifeste,
    decision: Decision,
    borne: BorneStatistique,
    etat_chaine: EtatChaine,
    compositions: Sequence[Composition],
    rang_du_jour: int,
    signataire: str,
    date: datetime,
    ombre_detruite_le: datetime | None = None,
    chemin_s3: str = "",
    remplace: str | None = None,
) -> Attestation:
    """Build the attestation. Counts only — never an exploitable detail."""
    return Attestation(
        id=f"att-{campagne.id}",
        numero=numero_attestation(date, rang_du_jour),
        campagne_id=campagne.id,
        tenant_id=campagne.tenant_id,
        agent_nom=manifeste.identite.nom,
        agent_version=manifeste.identite.version_agent,
        editeur=manifeste.identite.editeur,
        empreinte_paquet=tronquer(manifeste.identite.empreinte_paquet),
        modele_declare=f"{manifeste.identite.modele} ({manifeste.identite.version_modele})",
        mode=Mode(campagne.mode.value) if not isinstance(campagne.mode, Mode) else campagne.mode,
        manifeste_version=manifeste.version,
        scenarios=len(campagne.scenarios) or _compter_scenarios(campagne),
        n_rejeux=campagne.n_rejeux,
        sessions=_sessions(campagne, borne),
        periode_debut=campagne.debutee_le or date,
        periode_fin=campagne.terminee_le or date,
        resultat=decision.verdict,
        decouvertes={nature: decision.decouvertes.get(nature, 0) for nature in Nature},
        permissions_mortes=0,
        compositions=len(compositions),
        conditions=decision.conditions,
        borne=borne,
        empreinte_journal=tronquer(etat_chaine.empreinte_finale),
        entrees_journal=etat_chaine.entrees,
        ombre_detruite_le=ombre_detruite_le,
        valide_jusquau=date + timedelta(days=VALIDITE_JOURS),
        signataire=signataire,
        date=date,
        chemin_s3=chemin_s3,
        remplace=remplace,
    )


def _compter_scenarios(campagne: Campagne) -> int:
    return len(campagne.scenarios)


def _sessions(campagne: Campagne, borne: BorneStatistique) -> int:
    return campagne.n_rejeux * max(1, len(campagne.scenarios) or (borne.n_rejeux and 1) or 1)


def texte(a: Attestation, langue: str = "fr") -> str:
    """The one-page document, in French or in English (ENF-13)."""
    return _texte_fr(a) if langue == "fr" else _texte_en(a)


def _mode_fr(mode: Mode) -> str:
    return (
        "Ombre (réplique, données synthétiques)" if mode is Mode.OMBRE else "Observé (production journalisée)"
    )


def _mode_en(mode: Mode) -> str:
    return "Shadow (replica, synthetic data)" if mode is Mode.OMBRE else "Observed (logged production)"


def _texte_fr(a: Attestation) -> str:
    lignes = [
        f"ATTESTATION D'HOMOLOGATION{' ' * 20}{a.numero}",
        f"Date : {a.date:%Y-%m-%d}{' ' * 34}Page 1 sur 1",
        "",
        "AGENT",
        f"  Nom et version      {a.agent_nom} {a.agent_version}",
        f"  Éditeur             {a.editeur}",
        f"  Empreinte           {a.empreinte_paquet}",
        f"  Modèle déclaré      {a.modele_declare}",
        "",
        "HOMOLOGATION",
        f"  Mode                {_mode_fr(a.mode)}",
        f"  Manifeste           v{a.manifeste_version}",
        f"  Scénarios           {a.scenarios}",
        f"  Rejeux par scénario {a.n_rejeux} — {a.sessions} sessions isolées",
        f"  Période             {a.periode_debut:%Y-%m-%d %H:%M} → {a.periode_fin:%H:%M} UTC",
        "",
        "RÉSULTAT",
        f"  Verdict             {a.resultat.value.upper()}",
        "",
        "  Découvertes",
    ]
    for nature, compte in a.decouvertes.items():
        lignes.append(f"    {nature.value:<16}{compte:>6}")
    lignes += [
        f"    Compositions      {a.compositions:>6}",
        "",
    ]
    if a.conditions:
        lignes.append("  Conditions")
        lignes += [f"    {i}. {c}" for i, c in enumerate(a.conditions, start=1)]
        lignes.append("")
    lignes += [
        "PORTÉE STATISTIQUE",
        *[f"  {ligne}" for ligne in _portee(a.borne, "fr")],
        "",
        "INTÉGRITÉ",
        f"  Empreinte du journal   {a.empreinte_journal} (chaîné, {a.entrees_journal} entrées)",
        f"  Environnement Ombre    détruit le {a.ombre_detruite_le:%Y-%m-%d %H:%M} UTC"
        if a.ombre_detruite_le
        else "",
        f"  Validité               jusqu'au {a.valide_jusquau:%Y-%m-%d} ou jusqu'à tout changement",
        "                         de version, de modèle ou d'invite, au premier des deux",
        "",
        "SIGNATURE",
        f"  {a.signataire}, le {a.date:%Y-%m-%d}",
        "  Décision de mise en production : ressort exclusif du commanditaire.",
    ]
    return "\n".join(ligne for ligne in lignes if ligne is not None)


def _texte_en(a: Attestation) -> str:
    lines = [
        f"HOMOLOGATION ATTESTATION{' ' * 24}{a.numero}",
        f"Date: {a.date:%Y-%m-%d}",
        "",
        "AGENT",
        f"  Name and version    {a.agent_nom} {a.agent_version}",
        f"  Vendor              {a.editeur}",
        f"  Fingerprint         {a.empreinte_paquet}",
        f"  Declared model      {a.modele_declare}",
        "",
        "HOMOLOGATION",
        f"  Mode                {_mode_en(a.mode)}",
        f"  Manifest            v{a.manifeste_version}",
        f"  Scenarios           {a.scenarios}",
        f"  Replays per scenario {a.n_rejeux} — {a.sessions} isolated sessions",
        "",
        "RESULT",
        f"  Verdict             {a.resultat.value.upper()}",
        "",
        "  Findings",
    ]
    for nature, compte in a.decouvertes.items():
        lines.append(f"    {nature.value:<16}{compte:>6}")
    lines += [f"    Compositions      {a.compositions:>6}", ""]
    if a.conditions:
        lines.append("  Conditions")
        lines += [f"    {i}. {c}" for i, c in enumerate(a.conditions, start=1)]
        lines.append("")
    lines += [
        "STATISTICAL SCOPE",
        *[f"  {line}" for line in _portee(a.borne, "en")],
        "",
        "INTEGRITY",
        f"  Journal fingerprint {a.empreinte_journal} (chained, {a.entrees_journal} entries)",
        f"  Validity            until {a.valide_jusquau:%Y-%m-%d}, or until any change of",
        "                      version, model or prompt, whichever comes first",
        "",
        "SIGNATURE",
        f"  {a.signataire}, {a.date:%Y-%m-%d}",
        "  Production go-live decision: sole responsibility of the sponsor.",
    ]
    return "\n".join(lines)


def _portee(borne: BorneStatistique, langue: str) -> list[str]:
    from sas.statistiques import phrase_portee

    if not borne.rejeux_independants:
        return [phrase_portee(borne, langue)]
    lignes = [
        f"{borne.n_rejeux} rejeux indépendants par scénario."
        if langue == "fr"
        else f"{borne.n_rejeux} independent replays per scenario.",
    ]
    entete = "Elle détecte avec une confiance de :" if langue == "fr" else "It detects with a confidence of:"
    lignes.append(entete)
    for ligne in borne.lignes:
        if langue == "fr":
            frequence = 1 / ligne.probabilite
            lignes.append(f"    {ligne.confiance:>5.0%}  un comportement une fois sur {frequence:.0f}")
        else:
            lignes.append(
                f"    {ligne.confiance:>5.0%}  a behaviour occurring 1 time in {1 / ligne.probabilite:.0f}"
            )
    lignes.append(
        "Un comportement rare n'est PAS exclu par cette homologation."
        if langue == "fr"
        else "A rare behaviour is NOT excluded by this homologation."
    )
    lignes.append(
        "Le mode Ombre ne couvre pas les comportements dépendant de données réelles."
        if langue == "fr"
        else "Shadow mode does not cover behaviours that depend on real data."
    )
    del phrase_portee
    return lignes


def prefixe_numero() -> str:
    return constantes.ATTESTATION_PREFIXE
