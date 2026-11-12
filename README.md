# Sas — the airlock for third-party AI agents

**Homologation and controlled execution of third-party AI agents inside the
customer's environment, sold as an MSP subscription.**

Built for the *AWS Agentic MSP Hackathon 2026*, **Track 2 — Deliver AI-Driven
Outcomes for Customers**, targeting the *Best Amazon Bedrock AgentCore
Implementation* special prize.

**Live demo (public, no account, no install):**
<https://baptistefaisy.github.io/sas/>

The page shows four synthetic guest agents going through the airlock and coming
out with four different outcomes — approved, approved with conditions, refused,
and declared not measurable — with the measured journal coverage, the declared
vs observed gaps, the detected compositions, the one-page attestation and its
statistical scope. It runs in **static mode**: GitHub Pages has no Python behind
it, so the figures come from `portal/data/demo.json`, produced by running the
real engine. The page says so, and `deploy.yml` regenerates and diffs that file
on every push to `main` — a stale public page fails the build. For a live
campaign, run `make portail` locally.

> A customer wants to plug a vendor's AI agent into its AWS environment. Its
> CISO refuses — and is right to. The agent will hold credentials, make calls,
> read data, and **nobody knows what it actually does**.
>
> Sas replaces the paper guarantee with a measurement. A third-party agent does
> not enter the customer's environment: it first enters an airlock, where it is
> executed on typed scenarios with an ephemeral identity, a declared data
> perimeter, bounded budgets and a complete journal of every tool call. What
> comes out is not an opinion — it is the **observed envelope of its behaviour**.

---

## What makes it different

| Choice | Why it matters |
|---|---|
| **Execution is the audit** | Not static analysis, not a questionnaire: we run it and record. The only method that works on a probabilistic actor. |
| **Homologation is statistical** | An agent never behaves twice the same way. Sas replays N times and publishes the envelope *with its confidence bound* — including what N replays do **not** prove (§14). |
| **Declared vs observed is the signed deliverable** | The vendor declares "read bucket tickets, write bucket reports". Sas measures what the agent actually touches and publishes the gap, in both directions: what overflows, and what is requested but never used. |
| **Compositions are detected, not just calls** | Two individually allowed tools — read a bucket, send an HTTP request — form an exfiltration. A per-tool policy cannot see it. Sas reasons over **call chains**. |
| **Exploration is filtered out** | 95 % of denied calls are normal probing. A report that dumps 4 000 raw denials kills the project. Filtering exploration is a functional requirement, not a nicety. |
| **The model proposes, the code decides** | No severity, no classification and no amount is ever stated by a model. Bedrock proposes; `classification.py` computes the retained nature from measurable signals. A disagreement goes to human review. |

## The six AgentCore components, each doing real work

| Component | Job | Removing it breaks |
|---|---|---|
| **Runtime** | one isolated session per replay | replay independence, hence the statistical bound |
| **Identity** | one ephemeral identity per session, never long-lived | instant revocation and certain attribution |
| **Policy** | the perimeter derived from the manifest, applied *before* the tool | the product itself |
| **Gateway** | the single choke point for every tool call | the exhaustive journal, hence the proof |
| **Memory** | cross-replay state, only when the guest declares it | honest homologation of stateful agents |
| **Observability** | complete journal, traces, tokens, latencies | the raw material of the report and the attestation |

Plus **Amazon Bedrock** (models, Guardrails, Data Automation), **Strands
Agents** (execution harness), **IAM Access Analyzer** (unused-access findings,
quoted rather than recomputed) and **Amazon Quick** (fleet registry, trends).

The architectural principle: **the rules are enforced by the gateway, not by
the prompt.** A third-party agent never receives its limits as prose — it
undergoes them, at Policy level, before the tool runs.

---

## Quick start (offline, no AWS account needed)

```bash
make install     # dev dependencies
make all         # lint + size guards + tests (what CI runs)
make smoke       # one shadow campaign, 2 scenarios, complete journal
make demo        # the 3-minute demo: 3 synthetic guests, 3 verdicts
make attest      # print the attestation, statistical scope included
make contest     # hackathon submission conformity check
```

Everything runs offline against the local AgentCore backend
(`src/sas/agentcore/local.py`). The real AWS backend
(`src/sas/agentcore/aws.py`) implements the very same ports and is selected by
`sas.agentcore.fabrique` when credentials are present — no lot may import a
backend directly.

## Repository layout

```
src/sas/
  types.py            frozen domain types (public surface)
  modele/             the same types, split to stay under 500 lines
  constantes.py       thresholds, budgets, tariffs, KPI ids, route inventory
  aleatoire.py        deterministic randomness — one seed drives everything
  identifiants.py     ids and canonical SHA-256 fingerprints
  i18n.py             French / English labels
  agentcore/          ports + local backend + AWS backend
  store/              storage port + DynamoDB definitions
  manifeste/          schema, validator, versioning, signature
  ombre/              shadow environment generator and marked decoys
  scenarios.py        scenario loader and validator
  orchestrateur/      replays, sessions, ephemeral identity, budgets
  politique/          policy derived from the manifest, kill switch
  journal/            complete, chained, immutable, exportable
  analyseur/          aggregation, proposed classification, code decision
  compositions/       forbidden call chains, rules as data
  ecarts/             declared vs observed, dead permissions
  signature/          behavioural signature and drift detection
  statistiques.py     what N replays prove
  couts.py            measured cost, never estimated afterwards
  observe/            observed mode: logged production, quotas, kill switch
  api/  portail/      HTTP API and the static portal
  rapports/           report FR/EN, attestation, editor gap report
  registre.py         the fleet registry
demo/agents/          three synthetic guest agents (labelled as such)
scenarios/            the eight homologation scenarios, as data
regles/               composition rules, as data
eval/                 20 faulty + 20 benign agents, 100 labelled attempts
infra/cdk/            infrastructure as code
infra/quick/          Amazon Quick datasets
docs/                 HLD, architecture, runbook, submission, video script
docs/fr/CAHIER-DES-CHARGES.md the source specification (French, unmodified)
```

## Documentation

| Document | What it is |
|---|---|
| [`docs/HLD.md`](docs/HLD.md) | High-level design |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Architecture diagram (Mermaid + SVG) |
| [`docs/CONTRACTS.md`](docs/CONTRACTS.md) | Frozen interfaces and lot ownership |
| [`docs/TEST-INSTRUCTIONS.md`](docs/TEST-INSTRUCTIONS.md) | How a judge reproduces the results |
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Deployment and operation |
| [`docs/RECETTE.md`](docs/RECETTE.md) | Acceptance test results (R1–R24) |
| [`docs/SUBMISSION.md`](docs/SUBMISSION.md) | Submission checklist |
| [`docs/VIDEO.md`](docs/VIDEO.md) | 3-minute video script |
| [`docs/fr/CAHIER-DES-CHARGES.md`](docs/fr/CAHIER-DES-CHARGES.md) | The French source specification |

## Engineering rules

* Files < **500 lines**, functions < **50 lines** — enforced by
  `scripts/check_limits.py` on every pull request.
* CI verdict in **≤ 5 minutes** per job — enforced by
  `.github/ci-budget/check_timeouts.py`.
* **Mergify is the only merge driver** (rebase queue, batch ≤ 3). Conflicts are
  resolved by the InferHub conflict agent (`.github/inferhub/`), which never
  touches `.github/` or `.mergify.yml` and never pushes a resolution that does
  not compile.
* No secret ever reaches the tree: `scripts/check_contest.py` scans every
  tracked file.

## Honesty section

Sas states its own limits, in the report and on the attestation:

* an homologation over N replays proves nothing beyond the published bound;
* shadow mode does not cover behaviours that depend on real data;
* an agent that cannot be instrumented is declared **not measurable**, never
  compliant;
* fine covert channels (encoding in a resource name, response-time modulation)
  are not detected;
* Sas never guarantees the functional quality of the agent — only its access
  behaviour.

The three demo guests are **synthetic** and labelled as such. No real vendor
agent is used: that would require the vendor's agreement.

## Licence

MIT — see [LICENSE](LICENSE).
