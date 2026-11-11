"""`sas smoke` — one shadow campaign, two scenarios, complete journal.

This is the command CI runs. It must prove, in a few seconds and with no network,
that the whole chain works: manifest -> derived policy -> shadow replica ->
N replays -> chained journal -> aggregation -> classification -> gaps -> verdict.
"""

from __future__ import annotations

import sys

from sas.cli_partage import charger_contexte, lancer
from sas.homologation import resume


def executer_smoke(*, rejeux: int = 2, graine: int = 7) -> int:
    contexte = charger_contexte(("S1", "S4"))
    if len(contexte.scenarios) != 2:
        print(f"ERREUR: {len(contexte.scenarios)} scénario(s) trouvé(s), 2 attendus", file=sys.stderr)
        return 1

    print("Sas — smoke : une campagne Ombre, 2 scénarios, hors ligne")
    print(f"  manifeste    v{contexte.manifeste.version} signé et validé, {contexte.manifeste.identite.nom}")
    print(f"  scénarios    {', '.join(s.id for s in contexte.scenarios)} x {rejeux} rejeux")

    dossier = lancer(agent=_agent(), contexte=contexte, rejeux=rejeux, graine=graine)
    synthese = resume(dossier)

    print(f"  sessions     {synthese['sessions']}")
    print(f"  appels       {synthese['appels']} (dont {synthese['refus']} refusés par Policy)")
    print(f"  couverture   {synthese['couverture']:.2f} du journal — exigence bloquante 1.00")
    print(f"  chaîne       {'intègre' if synthese['chaine_integre'] else 'ROMPUE'}")
    print(f"  découvertes  {synthese['decouvertes']}")
    print(f"  écarts       {synthese['ecarts']} · compositions {synthese['compositions']}")
    print(f"  coût mesuré  {synthese['cout']:.2f} $")
    print(f"  verdict      {synthese['verdict'].upper()}")

    if synthese["couverture"] < 1.0:
        print("ERREUR: la couverture du journal n'est pas de 100 % (KPI-4)", file=sys.stderr)
        return 1
    if not synthese["chaine_integre"]:
        print("ERREUR: la chaîne d'empreintes du journal est rompue", file=sys.stderr)
        return 1
    print("SMOKE OK")
    return 0


def _agent() -> object:
    from sas.cli_partage import invite

    return invite("demo-bavard")
