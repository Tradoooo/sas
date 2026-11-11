# Sas — Submission checklist

> Submission deliverable (§29). This table tracks the real state of every
> hackathon deliverable on 2026-11-11 and what remains to be done. Deadlines at
> the end.

## 1. Deliverables (§29)

| Deliverable | Where | Real state | Remaining |
|---|---|---|---|
| Track | form | 🟢 Track **2** — Deliver AI-Driven Outcomes for Customers | — |
| AWS AI service | form + README | 🟡 AgentCore (6 components) ported and running **offline** (`src/sas/agentcore/`); real AWS backend (`aws.py`) not written (lot 17) | lot 17 (AWS backend, IaC) |
| Description | Devpost, English | 🟢 `README.md`, `docs/HLD.md` (this lot) | paste into Devpost |
| Deployed URL | CloudFront | 🔴 no portal yet (lot 14) | deploy portal with judge credentials |
| Repository | GitHub, private, shared with the two rule-book addresses | 🟢 repo exists; CI green | share with the two addresses; keep `main` protected (Mergify) |
| Video | 3 min, YouTube public, English | 🟡 [`docs/VIDEO.md`](VIDEO.md) written (13 shots, EN voice-over) | **film and publish** |
| Diagram | Mermaid + SVG | 🟢 [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (Mermaid) + [`docs/architecture.svg`](architecture.svg) | — |
| HLD | high-level design | 🟢 [`docs/HLD.md`](HLD.md) | — |

### Honest gaps that block the judge's experience

* **Portal** (`portal/`) and **API** (`src/sas/api/`) are not in the tree
  (lot 14): there is no deployed URL to share yet.
* **`make demo`/`make smoke`/`make attest`** are not wired (lot 20): the CLI
  imports `sas.cli_demo`/`sas.cli_smoke`, which do not exist. The judge can
  reproduce the pipeline with the script in `TEST-INSTRUCTIONS.md` §5.
* **`make contest`** reports 6 blockers on 2026-11-11: the 5 submission
  documents this lot writes, in place from this delivery, plus a lot-9/lot-0
  mismatch on `regles/` (the guard expects 3+ YAML files; lot 9 delivered the 3
  rules in one file).
* Two **code defects** recorded during this lot: `sas/ecarts.calculer` crashes
  on its own keyword mismatch; `sas/compositions.detecteur` mis-resolves its
  default rules path. Neither is owned by this lot.

## 2. The four judging criteria (§29.1) and how the submission maps

| Criterion | Weight | Where it is argued |
|---|---|---|
| Technological Implementation | 25% | each of the six AgentCore components does a distinct, necessary job — [`docs/PRIX-AGENTCORE.md`](PRIX-AGENTCORE.md) |
| Design | 25% | manifest is a format, scenarios and composition rules are data, multi-tenant is native, IaC deployment — [`docs/ARCHITECTURE.md`](ARCHITECTURE.md), [`docs/HLD.md`](HLD.md) |
| Potential Impact | 25% | structurally low marginal cost, per-agent billing, a deliverable the client can put into a contract (the attestation) — [`docs/MSP-PRICING.md`](MSP-PRICING.md) |
| Innovation | 25% | execution-as-audit, statistical homologation with a published bound, composition detection, exploration filtering as a functional requirement — [`docs/HLD.md`](HLD.md) §2, [`docs/LIMITES.md`](LIMITES.md) |

## 3. Deadlines

| When | What |
|---|---|
| **2026-12-11 12:00 PT** (= **21:00 Paris**) | submission deadline |
| **2026-12-31** | the **200 $** hackathon credits expire — spending governed by §26.4 (N=2 in development, N=6 for demonstrations only) |
| **2027-01-22** | end of judging; ENF-16 requires the solution to stay online free until then |

## 4. Open items for the lots still in flight

| Owner | Item |
|---|---|
| lot 14 | portal + API + registry (`registre.py`) + Cognito/CloudFront deploy |
| lot 17 | real AgentCore backend (`aws.py`), CDK stack, `lambdas/`, Guardrails/Strands wiring |
| lot 16 | `infra/quick/` (Amazon Quick datasets) |
| lot 18 | `eval/` bench (20 faulty + 20 benign + 100 labelled + calibrated agent) |
| lot 20 | `cli_smoke.py`, `cli_demo.py` so `make smoke`/`demo`/`attest` work |
| lot 9 / lot 0 | reconcile `regles/` with the `check_contest` guard (single file vs 3 files) |
| video | **film and publish** (script ready) |