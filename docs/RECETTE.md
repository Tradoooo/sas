# Sas — Acceptance matrix (R1–R24, EF-01…EF-53, ENF-01…ENF-17)

> Submission deliverable (§29). Each row reports the **real** status of the
> frozen `integration/lots` tree on 2026-11-11. Vocabulary:
> * `covered by <path>` — an acceptance test exists and passes under
>   `PYTHONPATH=src python3 -m pytest tests -q` (169 green).
> * `not covered yet` — no test exists in the tree; where the code *is* written,
>   the row says so. Where the module does not exist, the row says
>   "design only". A status is never invented.
>
> Two repository defects discovered while writing this lot, for the record:
> * **lot 9** — `src/sas/compositions/detecteur.py` resolves its default rules
>   file to `src/regles/compositions.yaml`; the real file is
>   `regles/compositions.yaml` (works with an explicit path).
> * **lot 10** — `src/sas/ecarts.py::calculer()` constructs
>   `Ecart(declaree=…, observee=…)` while the frozen dataclass has fields
>   `declare`/`observe`; it crashes as soon as one gap exists.

---

## 1. Acceptance tests R1–R24 (spec §33.2)

| # | Requirement (what is checked) | Status |
|---|---|---|
| R1 | Launch a campaign without a signed manifest → explicit refusal, no session | **covered** — `tests/unit/manifeste/test_recette.py::test_R1_lancer_sans_manifeste_signe_est_refuse` |
| R2 | Submit a manifest with "S3 access" without a prefix → validation refused, actionable reason | **covered** — `tests/unit/manifeste/test_recette.py::test_R2_manifeste_avec_acces_s3_sans_prefixe_refuse`, `tests/unit/manifeste/test_validation.py::test_R2_acces_s3_sans_prefixe_refuse` |
| R3 | Modify the manifest after signature → new version, previous attestation invalidated | **covered** — `tests/unit/manifeste/test_recette.py::test_R3_modifier_le_manifeste_apres_signature`, `tests/unit/manifeste/test_versions.py::test_R3_modifier_apres_signature_cree_une_nouvelle_version`, `tests/unit/manifeste/test_versions.py::test_R3_un_manifeste_modifie_apres_signature_ne_verifie_plus` |
| R4 | Verify the generated policy matches the manifest; no hand-written rule | **covered** — `tests/unit/manifeste/test_recette.py::test_R4_la_politique_derivee_repose_sur_une_reference_unique` |
| R5 | Run 8 scenarios × 6 replays → 48 isolated sessions, no state leak | **not covered yet** — `orchestrateur/campagne.py` loops scenarios × replays; session isolation is asserted only at the shadow level in `tests/unit/ombre/test_ombre.py::test_deux_sessions_sont_isolees` |
| R6 | Exceed the call budget → clean stop, session marked, campaign continues | **not covered yet** — code written (`sas/arret.py::CompteursBudget`, `passerelle._verifier_budget`), no test |
| R7 | Suspend during a session → stop < 5 s, credentials revoked, no later call | **not covered yet** — code written (`sas/arret.py::Interrupteur`, `passerelle._verifier_arret`), no test |
| R8 | Count emitted vs journalled calls → 100%, denials included (KPI-4) | **not covered yet** — code written (`campagne._couverture`), no test; observed 100% in the e2e run (`TEST-INSTRUCTIONS.md` §5) |
| R9 | Break the journal fingerprint chain → break detected on read | **not covered yet** — code written (`journal/chaine.py::verifier`); the chaining primitive is tested in `tests/unit/test_aleatoire.py::test_chaine_de_journal_detecte_une_modification` |
| R10 | Chatty agent touching a decoy → gap published, Débordement, Exploration filtered | **not covered yet** — guest-side behaviour asserted (`tests/unit/demo/test_agents.py::test_le_bavard_touche_le_leurre_de_configuration`, `…_ne_touche_jamais_le_leurre_sensible`); publication path broken (lot 10 defect) |
| R11 | Curious agent: sensitive read then outbound → Hostile composition, homologation refused | **not covered yet** — verified end-to-end in `TEST-INSTRUCTIONS.md` §5 (4 compositions, verdict `refuse`); guest-side asserted in `tests/unit/demo/test_agents.py::test_le_curieux_lit_le_leurre_sensible_puis_tente_une_sortie` |
| R12 | Conforming agent → zero gap, homologué, and the report says so explicitly | **not covered yet** — guest-side asserted in `tests/unit/demo/test_agents.py::test_le_conforme_n_utilise_que_les_outils_declares`; full verdict not covered by a test |
| R13 | Exploration filtering → exploration calls do not appear as findings | **not covered yet** — code written (`analyseur/classification.py::filtrer_exploration`), no test |
| R14 | Declared permissions never used → published as dead permissions | **not covered yet** — code written (`ecarts.py::permissions_mortes`), but `calculer` broken (lot 10 defect) |
| R15 | Two campaigns with the same seed → same conclusions | **not covered yet** — determinism asserted at lower levels (`ombre/test_ombre.py::test_deux_ombres_a_graine_identique_sont_identiques`, `demo/test_agents.py::test_meme_graine_meme_sequence`, `scenarios/test_scenarios.py::test_entree_pour_est_deterministe`); the full campaign conclusion is not |
| R16 | Change the model without changing the version → drift detected next cycle | **not covered yet** — `signature/` module is design only |
| R17 | Verify the published statistical bound → a p-known behaviour detected at the expected frequency | **not covered yet** — code written (`statistiques.py::verifier_borne`); the calibrated eval bench (`eval/`) is absent |
| R18 | Client A tries to read B's journal → refused and journaled | **not covered yet** — code written (`store/integrite.py::AccesInterdit`, enforced in `store/local.py`), no test |
| R19 | Generate the attestation → poor in detail, no client data, statistical scope present | **not covered yet** — code written (`rapports/attestation.py::construire`/`texte`); verified manually in `TEST-INSTRUCTIONS.md` §5 |
| R20 | Generate the editor report → no client content | **not covered yet** — editor gap report is not implemented (design only) |
| R21 | Destroy the shadow environment → proof of destruction, no residual resource | **covered** — `tests/unit/ombre/test_ombre.py::test_R21_detruire_l_environnement_ombre` |
| R22 | Consult the measured cost → deviation < 25% vs annexe G | **not covered yet** — code written (`couts.py::cout_annexe_g`), no test |
| R23 | Add a scenario and a composition rule in data → executable without code change | **covered (scenario side)** — `tests/unit/scenarios/test_scenarios.py::test_R23_ajouter_un_scenario_sans_code`. The composition-rule side is driven by `regles/compositions.yaml` (read by `detecteur.charger_regles`) but is not the subject of this test |
| R24 | Non-instrumentable agent → declared not measurable, no attestation | **covered** — `tests/unit/demo/test_agents.py::test_R24_l_agent_opaque_est_declare_non_mesurable` |

Summary: **7 of 24 acceptance tests have a named `test_R<n>`** (R1–R4, R21, R23, R24).

---

## 2. Functional requirements EF-01…EF-53

Statuses reflect the test corpus only (the same rule the conformity guard
applies: an identifier quoted by at least one test). "Code written" records
where the implementation exists without a test.

| ID | Requirement (short) | Status |
|---|---|---|
| EF-01 | Enter, validate and version a manifest | **covered** — `tests/unit/manifeste/test_recette.py`, `test_chargement.py`, `tests/unit/test_constantes.py` |
| EF-02 | Refuse a manifest whose permissions are not fine-grained | **covered** — `tests/unit/manifeste/test_recette.py`, `test_validation.py` |
| EF-03 | Require editor signature and sponsor validation | **covered** — `tests/unit/manifeste/test_validation.py`, `test_versions.py` |
| EF-04 | Refuse any execution without a signed, validated, current manifest | **covered** — `tests/unit/manifeste/test_recette.py`, `test_validation.py` |
| EF-05 | Derive the perimeter policy from the manifest, never hand-written | **covered** — `tests/unit/manifeste/test_recette.py`, `test_versions.py` |
| EF-10 | Build a shadow environment from the manifest declaration | **covered** — `tests/unit/ombre/test_ombre.py` |
| EF-11 | Run the guest in an isolated session with ephemeral identity | **not covered yet** — code written |
| EF-12 | Run N replays per scenario with controlled seed and dispersion | **not covered yet** — code written |
| EF-13 | Bound each execution (calls, tokens, duration, memory); clean stop | **not covered yet** — code written |
| EF-14 | Journal 100% of tool calls with causal chain | **not covered yet** — code written; observed 100% in `TEST-INSTRUCTIONS.md` §5 |
| EF-15 | Immediate suspension, shadow and observed | **not covered yet** — code written |
| EF-16 | Isolate sessions (no state leak except declared memory) | **covered** — `tests/unit/ombre/test_ombre.py::test_deux_sessions_sont_isolees` |
| EF-17 | Destroy the shadow environment with proof | **covered** — `tests/unit/ombre/test_ombre.py` (R21) |
| EF-20 | Compute the behaviour envelope | **not covered yet** (the observed/aggregated shape exists in `sas/analyseur/agregation.py`) |
| EF-21 | Declared/observed gap both ways; cross-reference IAM Access Analyzer | **not covered yet** — `ecarts.py` broken (lot 10 defect), Access Analyzer port-only |
| EF-22 | Classify each out-of-scope attempt (grid of §13) | **not covered yet** — code written (`analyseur/classification.py`) |
| EF-23 | Detect forbidden compositions on chains of 2–3 calls | **not covered yet** — code written (`compositions/detecteur.py`); verified manually in `TEST-INSTRUCTIONS.md` §5 |
| EF-24 | Publish the statistical confidence bound for N replays | **not covered yet** — code written (`statistiques.py`) |
| EF-25 | A model never fixes a final severity/classification (proposes, code decides) | **not covered yet** — code written (`classification.py::trancher`) |
| EF-30 | Keep a reference envelope per homologated version | **design only** |
| EF-31 | Replay scenarios periodically and compare to the reference | **design only** |
| EF-32 | Alert on new attempts, vanished behaviour, budget overshoot | **design only** |
| EF-33 | Detect an undeclared version/model change | **design only** |
| EF-34 | Auto-suspend an agent whose drift exceeds the threshold | **design only** |
| EF-40 | Produce a complete homologation report, FR and EN | **not covered yet** — verdict + attestation implemented, full report not |
| EF-41 | Produce a dated, chained, exportable, deliberately-poor attestation | **not covered yet** — code written (`rapports/attestation.py`); verified in `TEST-INSTRUCTIONS.md` §5 |
| EF-42 | Produce a gap report for the editor, without client data | **design only** |
| EF-43 | Keep a registry of every third-party agent | **design only** (`depot.registre` types + `agents` table + demo `AGENTS` only) |
| EF-44 | Replay a specific scenario from a finding | **not covered yet** — `scenarios`/`campagne` allow it, no test |
| EF-50 | Strictly isolate tenants | **not covered yet** — code written (`store/integrite.py`) |
| EF-51 | Derive tenant identity from the token, never free text | **covered** — `tests/unit/test_constantes.py` (route inventory asserts no tenant parameter) |
| EF-52 | Bound and expose per-tenant cost | **not covered yet** — code written (`couts.py`, `store/local.py::cout_cumule`) |
| EF-53 | Let an editor see only its own gap report | **design only** |

---

## 3. Non-functional requirements ENF-01…ENF-17

| ID | Requirement (short) | Status |
|---|---|---|
| ENF-01 | No execution without a signed, validated, current manifest | **covered** — `tests/unit/manifeste/test_recette.py`, `test_validation.py` |
| ENF-02 | Ephemeral identity per session, never long-lived | **not covered yet** — code written (`agentcore/local.py::IdentityLocal`) |
| ENF-03 | Call/token/duration/memory budgets enforced with clean stop | **not covered yet** — code written (`arret.py`) |
| ENF-04 | 100% journalling, chained and immutable | **not covered yet** — code written (`journal/chaine.py`) |
| ENF-05 | Strict isolation between sessions and tenants | **not covered yet** — code written (sessions in `local.py`, tenants in `store/integrite.py`) |
| ENF-06 | Shadow destroyed at campaign end, with proof | **covered** — `tests/unit/ombre/test_ombre.py` |
| ENF-07 | No real personal data in the demo set | **covered** — `tests/unit/ombre/test_ombre.py::test_aucune_donnee_personnelle_reelle` |
| ENF-08 | Added latency < 100 ms per call in observed mode | **design only / to confirm** (`observe/` absent) |
| ENF-09 | Kill switch effective < 5 s | **not covered yet** — code written (`arret.py::Interrupteur`) |
| ENF-10 | Measured, exposed cost, never estimated afterwards | **not covered yet** — code written (`couts.py`) |
| ENF-11 | Reproducibility: same scenarios, same seed, same conclusions | **covered** — `tests/unit/demo/test_agents.py`, `tests/unit/ombre/test_ombre.py`, `tests/unit/scenarios/test_scenarios.py` |
| ENF-12 | Configurable journal retention, effective and provable purge | **not covered yet** — code written (`journal/chaine.py::purger_avant`) |
| ENF-13 | FR/EN interface and reports; English submission deliverables | **covered** — `tests/unit/test_gardes.py` (bilingual label integrity) |
| ENF-14 | Files < 500 lines, functions < 50, CI ≤ 5 min | **covered** — `tests/unit/test_gardes.py` + `scripts/check_limits.py` (passes) |
| ENF-15 | Reproducible IaC deployment, no undocumented manual step | **design only** (`infra/cdk/` absent) |
| ENF-16 | Solution stays online free until 2027-01-22 | **design only** (deployment) |
| ENF-17 | A non-instrumentable agent is declared not measurable, never compliant | **covered** — `tests/unit/demo/test_agents.py` (R24) |

Summary: **9 / 33 EF, 6 / 17 ENF, 7 / 24 R** are covered by tests in the tree —
the same figures the conformity guard (`scripts/check_contest.py`) reports
(traceability 9/33 EF, 6/17 ENF, 11/24 R by its looser substring count).