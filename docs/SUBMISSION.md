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
| Deployed URL | GitHub Pages (public) | 🟢 **https://tradoooo.github.io/sas/** — the portal is published on every push to `main` by `.github/workflows/deploy.yml` | a CloudFront URL with the live API (no AWS account here) |
| Repository | GitHub, public | 🟢 repo exists; CI green; `main` protected (Mergify is the only merge driver) | — |
| Video | 3 min, YouTube public, English | 🟡 [`docs/VIDEO.md`](VIDEO.md) written (13 shots, EN voice-over) | **film and publish** |
| Diagram | Mermaid + SVG | 🟢 [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (Mermaid) + [`docs/architecture.svg`](architecture.svg) | — |
| HLD | high-level design | 🟢 [`docs/HLD.md`](HLD.md) | — |

### Honest gaps that remain

* **No live API behind the public URL.** GitHub Pages serves static files, so
  `https://tradoooo.github.io/sas/` runs in **static mode**: it shows
  `portal/data/demo.json`, which was produced by running the real engine on the
  synthetic demo data. The page says so in a banner. To launch a campaign live,
  run `make portail` locally (or deploy `infra/cdk`, which maps the same routes
  to API Gateway + Lambda behind CloudFront).
* **Nothing runs on real Amazon Bedrock AgentCore today.** The six ports and the
  AWS backend (`src/sas/agentcore/aws.py`) are written; `SAS_BACKEND=aws` needs
  credentials, and the real AgentCore Policy syntax is still to be confirmed by
  a test (spec §34, point 2 — the only blocking item of the project).
* **No model call anywhere.** Pass 2 of the analyser (the model's proposal) is a
  port with no live adapter yet; classification runs with `proposition=None`, so
  the code decides alone. That is the conservative direction, not a weakening:
  §13.4 forbids a model from setting a nature anyway.
* **The video is not shot.** [`docs/VIDEO.md`](VIDEO.md) is the shot-by-shot
  script (13 shots, English voice-over).
* **Lot 18 (evaluation bench)** — the 20 faulty + 20 benign agents, the 100
  hand-labelled attempts and the calibrated agent that verifies the published
  bound (R17) — is specified but not delivered.
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