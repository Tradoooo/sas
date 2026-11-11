# CONTRACTS — frozen interfaces and lot ownership

This file is the **contract** between the lots. It is written before any
development (spec §31) and it is the only place where a lot may look up what
another lot produces.

Rules, repeated to every sub-agent:

1. **A lot owns its files and nothing else.** Never edit a file owned by
   another lot, never edit a frozen file. Need a change? Open a contract
   change (a PR touching only this file plus the frozen file) and say so in
   the PR body.
2. Files < **500 lines**, functions < **50 lines** (`make limits`).
3. CI ≤ **5 minutes**, everything offline: no network, no AWS, no model call.
   Anything that talks to AWS goes through a port and a fake.
4. Tests are part of the lot. A lot without tests is refused.
5. **Mergify is the only merge driver.** No direct push on `main`.
6. After three failed attempts on the same point: leave it and answer `KO`.

---

## Frozen surface (lot 0 — nobody edits these)

| File | What it freezes |
|---|---|
| `src/sas/types.py` | Every domain dataclass and enumeration |
| `src/sas/constantes.py` | Thresholds, budgets, tariffs, KPI ids, table names, route inventory, demo constants |
| `src/sas/i18n.py` | Bilingual labels and `traduire(cle, langue)` |
| `src/sas/agentcore/ports.py` | The six AgentCore component ports + `AgentInvite`, `BoiteOutils`, `ModeleAnalyse`, `ConstructeurOmbre`, `AnalyseurAcces` |
| `src/sas/store/base.py` | The `Depot` storage port (tenant-scoped) |
| `src/sas/store/ddl.py` | DynamoDB table definitions, read by both the IaC and the local backend |
| `pyproject.toml`, `Makefile` | Tooling, pytest markers, ruff config |
| `.github/**`, `.mergify.yml` | CI, guards, Mergify queue, conflict agent |
| `scripts/check_limits.py`, `scripts/check_contest.py` | Size guard and submission conformity guard |

Adding a field to a frozen dataclass is a **contract change**: one PR, nothing
else in it, merged before the lots that need it are started.

---

## Lot ownership map

| Lot | Branch | Owns | Depends on |
|---|---|---|---|
| **0** | `main` | everything in the frozen table above, `docs/CONTRACTS.md`, `docs/fr/` | — |
| **1** | `lot/manifeste` | `src/sas/manifeste/` (schema, validator, versioning, signature), `schemas/manifeste.schema.json`, `tests/unit/manifeste/` | 0 |
| **2** | `lot/ombre` | `src/sas/ombre/` (shadow generator, marked decoys, reset, destruction proof), `tests/unit/ombre/` | 0, 1 |
| **3** | `lot/agents-demo` | `demo/agents/` (the three synthetic guests), `demo/__init__.py`, `tests/unit/demo/` | 0 |
| **4** | `lot/scenarios` | `scenarios/*.yaml`, `src/sas/scenarios.py` (loader + validator), `tests/unit/scenarios/` | 0 |
| **5** | `lot/orchestrateur` | `src/sas/orchestrateur/` (replays, sessions, ephemeral identity, budgets), `src/sas/agentcore/local.py`, `src/sas/agentcore/fabrique.py`, `tests/fakes/`, `tests/unit/orchestrateur/` | 2, 4 |
| **6** | `lot/politique` | `src/sas/politique/` (policy derived from the manifest, conditional denials, kill switch), `tests/unit/politique/` | 1, 5 |
| **7** | `lot/journal` | `src/sas/journal/` (chained, complete, exportable), `tests/unit/journal/` | 5 |
| **8** | `lot/analyseur` | `src/sas/analyseur/` (deterministic aggregation, proposed classification, `classification.py` decision), `src/sas/modeles/` (Bedrock adapters + fakes), `tests/unit/analyseur/` | 7 |
| **9** | `lot/compositions` | `src/sas/compositions/`, `regles/*.yaml`, `tests/unit/compositions/` | 7 |
| **10** | `lot/ecarts` | `src/sas/ecarts/` (declared vs observed both ways, dead permissions, Access Analyzer cross-reference), `tests/unit/ecarts/` | 1, 8 |
| **11** | `lot/signature` | `src/sas/signature/` (behavioural signature, distance, drift detection and alerts), `tests/unit/signature/` | 8 |
| **12** | `lot/statistiques` | `src/sas/statistiques.py`, `src/sas/couts.py`, `tests/unit/statistiques/`, `tests/unit/couts/` | 5 |
| **13** | `lot/observe` | `src/sas/observe/` (observed mode, kill switch, quotas, latency measurement), `tests/unit/observe/` | 6, 7 |
| **14** | `lot/api` | `src/sas/api/`, `src/sas/store/local.py`, `portal/` (static portal), `src/sas/registre.py`, `src/sas/auth.py`, `tests/unit/api/` | 8, 10, 11 |
| **15** | `lot/rapports` | `src/sas/rapports/` (report FR/EN, attestation, editor gap report), `tests/unit/rapports/` | 8, 10, 12 |
| **16** | `lot/quick` | `infra/quick/` (Amazon Quick datasets, fleet registry, trends), `tests/unit/quick/` | 14 |
| **17** | `lot/iac` | `infra/cdk/`, `src/sas/agentcore/aws.py`, `src/sas/lambdas/`, `docs/RUNBOOK.md`, `tests/unit/iac/`, `tests/unit/aws/` | 6, 14 |
| **18** | `lot/eval` | `eval/` (20 faulty + 20 benign agents, 100 labelled attempts, `genere-agents.mjs`, calibrated agent), `tests/unit/eval/` | 3, 8 |
| **19** | `lot/docs` | `README.md`, `docs/ARCHITECTURE.md`, `docs/HLD.md`, `docs/SUBMISSION.md`, `docs/TEST-INSTRUCTIONS.md`, `docs/VIDEO.md`, `docs/RECETTE.md`, `docs/PRIX-AGENTCORE.md` | tout |
| **20** | `lot/cli` | `src/sas/cli.py`, `src/sas/demo.py`, `media/`, `tests/unit/cli/` | 14, 15 |

Launch order (spec §31): `0` alone, then `{1,3,4}`, then `{2,5}`, then `{6,7}`,
then `{8,9,10,12}`, then `{11,13,14}`, then `{15,16,17,18}`, then `{19,20}`.

---

## Cross-lot agreements

These are the points where two lots could otherwise disagree. They are settled
here once and for all.

### A. One entry point per lot

Every lot exposes its public surface through its package `__init__.py`. Other
lots import `sas.<lot>`, never `sas.<lot>.<module>`. This keeps the internal
split (needed for the 500-line rule) free.

### B. Determinism

`graine` (seed) drives everything random: shadow data generation, guest agent
dispersion, model fakes. Two campaigns with the same seed produce the same
conclusions (ENF-11, R15). Use `sas.aleatoire.genereur(graine)` — never
`random` directly.

### C. No model ever decides

`ModeleAnalyse.proposer_nature()` returns a `PropositionModele`. The retained
nature is computed by `sas.analyseur.classification.decider(signaux, seuils)`.
A disagreement sets `Tentative.desaccord = True` and routes to human review
(§13.4, EF-25).

### D. Timestamps and ids

`datetime` objects are timezone-aware UTC. Ids are produced by
`sas.identifiants.nouveau(prefixe, graine=None)`: deterministic when a seed is
given, unique otherwise. Never `uuid4()` inline.

### E. Money

`Decimal`, quantized to the cent. Never `float`. Costs are *measured* from
token and runtime counters (`sas.couts`), never estimated afterwards.

### F. Tests

* unit tests in `tests/unit/<lot>/`, integration in `tests/integration/`;
* fakes in `tests/fakes/` (owned by lot 5, read by everybody);
* a test that needs AWS is marked `@pytest.mark.aws` and never runs in CI;
* each acceptance test of spec §33.2 is named `test_R<n>_...` so the
  traceability matrix can be generated by `scripts/check_contest.py`.

### G. Portal

`portal/` is a static site (no build step, no external CDN, no network at
runtime). It reads the API described in spec §23. The route inventory is
frozen in `constantes.ROUTES`; a route may not be renamed.

### H. Language

Code, identifiers, docstrings and commit messages: **English or French, but
one file stays consistent**. User-facing strings go through `sas.i18n`.
Submission deliverables (`README.md`, `docs/ARCHITECTURE.md`, `docs/HLD.md`,
`docs/SUBMISSION.md`, `docs/TEST-INSTRUCTIONS.md`, `docs/VIDEO.md`) are in
**English** (spec preamble). `docs/fr/CAHIER-SAS.md` is the source document
and stays in French, unmodified.
