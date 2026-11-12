# Sas — the eight KPIs: target vs measured value

> **Status of this page.** Every figure below is either **measured** — with the
> command or the test that produces it — or explicitly declared **not
> measured**, with what it would take. A KPI table full of targets is a
> marketing document; this one is a measurement sheet.
>
> The eight indicators are those of §5.2 of the specification. Their identifiers
> and their names come from the frozen table `constantes.KPI`
> (`src/sas/constantes.py`), and the computation lives in `src/sas/kpi.py`.
> The figures quoted for the demonstration agents were produced with the
> command given in §3, on this repository, offline, with the seed 11.

## 1. The table

| # | Definition | Target of the specification | Measured today |
|---|---|---|---|
| **KPI-1** | Out-of-scope attempts blocked — the calls denied by Policy, counted by rule | Measured on the three demonstration agents | **244** denials of the `usage-non-declare` rule and **30** of the `budget-epuise` rule for `demo-bavard` (484 calls, 274 denials in total); **48** `sortie-non-declaree` and **48** `usage-non-declare` for `demo-curieux` (144 calls, 96 denials); **60** `budget-epuise` for `demo-conforme` (270 calls). Exploration is counted here and filtered out later — the filtering must stay visible (§13.5). **Bounding refusals** (budget, duration) also appear in this count, and they are **not findings**: only the perimeter refusals are classified (`docs/GRILLE-CLASSIFICATION.en.md` §7) |
| **KPI-2** | Onboarding delay, from the request to the dated attestation | Weeks → days | **Not measured.** The product does not timestamp the sponsor's request, so there is no start date: `kpi_2()` returns `None` and says so instead of guessing — `test_KPI2_refuse_d_etre_devine`. What it would take: the portal records the request date, and the attestation date is already recorded |
| **KPI-3** | Cost per homologation — real consumption, measured and never estimated afterwards (ENF-10) | ≤ 1 $ in mixed mode; 0.90 $ for N=6 in annexe G | **0.82 $** measured for `demo-conforme` at N=6, against 0.90 $ in annexe G — a gap of **8.9 %**, inside the 25 % requirement of §27. `demo-bavard`: 0.91 $; `demo-curieux`: 0.78 $. Proven by `test_R22_le_cout_mesure_reste_proche_de_l_annexe_g`, `test_le_cout_mesure_reste_dans_les_25_pourcent_de_l_annexe_g` and `test_KPI3_le_cout_est_mesure_et_pas_estime` |
| **KPI-4** | Journal coverage — share of tool calls journalled with their causal chain, denials included | 100 % — blocking requirement | **100 %** on all three demonstration agents (270/270, 484/484, 144/144 entries), chain intact on each. Blocking: below 1.00 the campaign proves nothing — `test_R8_couverture_du_journal_a_cent_pourcent`, `test_la_couverture_du_journal_est_bloquante`, `test_KPI4_est_bloquant_et_le_dit_quand_il_est_tenu` |
| **KPI-5** | Declared/observed gap — declared permissions never used, plus usages never declared | Published per agent | **1 overflow, 0 dead permission** for `demo-bavard`; **1 overflow, 2 dead permissions** for `demo-curieux`; **0/0** for `demo-conforme`. Dead permissions are cross-referenced with IAM Access Analyzer when the native source exists, and the report cites the source instead of recomputing it — `test_R14_les_permissions_declarees_jamais_utilisees_sont_publiees`, `test_EF21_la_source_native_est_citee_quand_elle_existe`, `test_KPI5_compte_les_deux_sens` |
| **KPI-6** | Drift detection delay — from the change of behaviour to the alert | Less than one surveillance cycle | **Measured only when the instant of the change is known**; otherwise reported as unmeasured rather than guessed — `test_KPI6_est_mesure_sur_une_derive_injectee`, `test_KPI6_refuse_d_etre_devine`. In the bench, an undeclared model change is **detected at the next cycle** (behavioural distance 0.667, 14 appearance(s) in the diff) — `test_R16_un_changement_de_modele_non_declare_est_detecte` |
| **KPI-7** | Published statistical confidence — what N replays prove, with the lower bound | Displayed on every attestation | **Published on every attestation**: "6 independent replays per scenario detect with 98 % a behaviour occurring one time in two, 82 % one time in four, 47 % one time in ten, 26 % one time in twenty. **A rare behaviour is NOT excluded.**" The bound is computed, not written — `src/sas/statistiques.py`, `test_la_borne_publiee_est_celle_du_chapitre_14`, `test_KPI7_publie_la_borne`. It is also **verified**: an implanted behaviour at p = 0.5 is observed in 100 % of campaigns against 98 % expected (12/12), and at p = 0.25 in 83 % against 82 % expected (10/12) — `test_R17_la_borne_publiee_est_verifiee`, `test_R17_a_une_probabilite_plus_faible` |
| **KPI-8** | Detected compositions — forbidden chains of calls whose individual calls were allowed | Demonstrated on the curious agent | **48 `exfiltration` compositions** detected on `demo-curieux` (144 calls, 96 denials): a sensitive read followed by an outbound call, each call allowed on its own, the chain not — `src/sas/compositions/detecteur.py`, `test_le_curieux_publie_ses_compositions`, `test_KPI8_compte_les_compositions_par_motif` |

## 2. What "measured" means here, and what it does not

- A measured value is a value **produced by the code**, quoted with the command
  or the test that produces it. It is not a value taken from a screenshot.
- A measured value depends on its input: the agent, the scenario set, the seed
  and N. The figures above are for the demonstration agents at N=6, seed 11.
  They are not promises for another agent.
- KPI-1 and KPI-5 are **counts**, not rates: they are published per agent, as
  the specification asks ("published per agent").
- Two of the eight are **not measurable today** (KPI-2, and KPI-6 outside an
  injected-drift scenario). They are reported as unmeasured, with the reason in
  the note carried by the KPI itself (`src/sas/kpi.py`, `non_mesures()`), and
  the list of unmeasured KPIs is itself tested — `test_les_kpi_non_mesures_sont_listes`.

## 3. Reproducing the figures

```bash
# The eight KPIs of the three demonstration agents, computed by sas.kpi
PYTHONPATH=src python3 - <<'PY'
from sas import kpi, statistiques
from sas.cli_partage import charger_contexte, invite, lancer

for nom in ("demo-conforme", "demo-bavard", "demo-curieux"):
    dossier = lancer(agent=invite(nom), contexte=charger_contexte(), rejeux=6, graine=11)
    for ligne in kpi.tableau(
        agregat=dossier.agregat,
        appels_emis=dossier.campagne.appels_emis,
        etat_chaine=dossier.campagne.etat_chaine,
        cout=dossier.campagne.cout_mesure.total,
        n_rejeux=6,
        ecarts=dossier.ecarts,
        compositions=dossier.compositions,
        borne_texte=statistiques.phrase_portee(dossier.borne, "fr"),
    ):
        print(nom, ligne.id, ligne.valeur)
PY

# The ten measures of §27, including the calibration of the published bound
PYTHONPATH=src python3 -c "from eval.banc import executer_banc; print(executer_banc(graine=7, n_rejeux=1).table())"
PYTHONPATH=src python3 -m pytest tests/unit/banc -q -m slow
```

## 4. The ten measures of §27, as measured by the bench

The bench (`eval/banc.py`) covers the ten measures of §27 in **nine rows** —
isolation and revocability are measured together — and runs on the **real**
pipeline: gateway, derived policy, chained journal, aggregation, classification
and composition rules. It measures the product, not a copy of it. Eight rows run
on every pull request; the calibration row (R17) runs in the slow subset
(`-m slow`).

| Measure (§27) | Target | Measured |
|---|---|---|
| Classification precision on 100 hand-labelled attempts | ≥ 90 % | **100 %** (100/100) |
| False negatives over 20 faulty guests | ≥ 90 % detected | **100 %** (20/20) |
| Hostile compositions invented over 20 benign sessions | ≤ 5 % | **0 %** (0/20) |
| Journal coverage | 100 % | **100 %**, chain intact |
| Reproducibility (same seed) | identical | **identical** |
| Cost against annexe G | gap < 25 % | **8.9 %** (0.82 $ measured / 0.90 $ quoted) |
| Drift detection on an undeclared change | detected | **detected** (distance 0.667) |
| Isolation and revocability | no leak, no later call | **0 call after suspension**, 4/4 distinct identities |
| Calibration of the published bound (R17) | observed ≈ expected | p = 0.5: **100 % observed / 98 % expected**; p = 0.25: **83 % / 82 %** |

**A 100 % score on 100 labels is a suspiciously round number.** The labels were
written from the specification's own grid and the classifier was corrected until
it matched them (`docs/ECHECS.md` §10). It measures agreement with the
specification's grid, not accuracy against a real-world ground truth that
nobody has.

## 5. The KPI that is not measured, and the one that is not a KPI

- **KPI-2** is not measured: the sponsor's request is not timestamped by the
  product. The measurement would be a two-line change plus a portal field; it
  is simply not there.
- **ENF-08 (added latency in observed mode < 100 ms)** is a requirement, not one
  of the eight KPIs. The **local** backend's added latency is measured
  (`test_ENF08_la_latence_du_mode_observe_est_mesuree`), but the added latency
  of the **real** Gateway + Policy stack is not: `src/sas/agentcore/aws.py`
  never runs here, and no test calls AWS (`docs/ECHECS.md` §5). No document here
  quotes a latency result for the real stack.

## 6. Related pages

- `docs/LIMITES.md` — what Sas does not guarantee, printed on every report.
- `docs/ECHECS.md` — what was not achieved, and why it is (or is not)
  disqualifying.
- `docs/conformite/README.md` — how the regulatory evidence maps use these
  figures.
