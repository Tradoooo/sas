# Sas — High-Level Design

> Submission deliverable (spec §29). English. This document describes what the
> design intends and, equally, what is actually in the repository today. Every
> claim about code cites its path. Figures from the specification are marked
> *calculated*; figures actually produced by running the code are marked
> *measured*.

---

## 1. Problem statement

A customer wants to plug a third-party AI agent into its AWS account — a
vendor's agent, an open agent, or an agent from one of its own providers. The
CISO refuses, and is right to (§3). The agent will hold credentials, make calls,
read data, and **nobody knows what it actually does**.

The instinctive answer today is a paper guarantee: a security questionnaire, a
SOC 2 report, the vendor's own test certificate. These were designed for
deterministic software and fail on an agent for three reasons (§2):

1. a vendor's SOC 2 covers **the vendor's** infrastructure, not the behaviour of
   its agent inside **the customer's** account with **the customer's** tools;
2. tests run at the vendor tell nothing about what the agent will do against
   real customer data;
3. the vendor can change the underlying model or the system prompt **without
   changing the version number** — the behaviour drifts silently, and no paper
   guarantee captures it.

### The case that motivates the project (§3.2)

A 300-person company wants to attach a SaaS vendor's agent to its AWS
environment: the agent reads tickets, searches the knowledge base, opens tasks
in the tracker. The CISO asks four questions:

1. What credentials will the agent have, and what could it do with them?
2. What data will it actually read — including data it does not need to read?
3. Can it make anything leave the account?
4. How will I know if the vendor changes the model next month?

The vendor answers "our agent is secure, it uses the permissions you give it,
we are SOC 2 compliant". None of the four questions is answered. The project
stalls — or ships, and the CISO discovers six months later that the agent had
read access to a bucket it never needed.

### Why the problem compounds (§3.3, §3.4)

Three trends converge: third-party agents multiply (a customer accepting three
agents in 2026 will have thirty in 2028); agents call other agents, forming a
trust chain nobody records; and regulatory duties over subcontractors apply to
an AI agent exactly as they do to a human contractor. An MSP is the natural
carrier: it already holds the trusted relationship, tooled access to the
customer's account, recurring billing, and — decisively — it is itself a third
party. The service is perfectly repeatable: the same airlock, the same
scenarios and the same attestation format apply to every agent of every
customer. **It is a product, not an engagement.**

### What already exists and why it is not enough (§4)

| Approach | What it gives | What is missing |
|---|---|---|
| Vendor security questionnaire | A dated, declarative snapshot | No measurement, no verification, no drift detection |
| Vendor SOC 2 / ISO 27001 | Assurance over **their** infrastructure | Nothing on the agent's behaviour in **your** account |
| Hand-tuned IAM perimeter | Real protection | Binary: too wide or too narrow, and nobody can tell which without having observed |
| CloudTrail logs | After-the-fact trace | After the incident, not before; no isolation; no classification |
| Classic sandbox (container/VM) | Execution isolation | Designed for deterministic code: captures neither reasoning, nor tool calls, nor variability |
| **IAM Access Analyzer** unused-access findings | Natively detects granted-but-never-exercised IAM permissions over 90 days | Works at the **IAM identity** level, not at a guest agent's session. Does not see call compositions, the gap to a signed manifest, probabilistic variability, or what is declared but absent from IAM. **To integrate as a source, not reinvent** (§20.2) |
| **Bedrock Compliance-as-Code** | Generates compliance artefacts from infrastructure | Covers declared infrastructure compliance, not the observed behaviour of a probabilistic actor |
| **AWS Frontier prebuilt agents** (Kiro, Security, DevOps, FinOps) | Ready-made agents | They are themselves **third-party agents to homologate** — excellent real-invite candidates (§28.4) |
| `piege` (same portfolio) | Measures an assistant under attack | Attacks the client's application **from the outside**; Sas **hosts and measures a third-party actor** inside. Disjoint catalogues and reports |
| `rempart` (same portfolio) | Continuous application pentest | Targets code and infrastructure, not a guest agent |

**Portfolio boundary, written once (§4):** `rempart` attacks the application,
`piege` attacks the assistant, **Sas hosts the guest and measures it.** Three
products, three catalogues, three reports, three distinct prize slots.

---

## 2. Solution overview

Sas replaces the paper guarantee with **measurement**. A third-party agent does
not enter the customer's environment: it first enters an airlock, where it is
**executed** on typed scenarios with an ephemeral identity, a declared data
perimeter, bounded quotas and a complete journal of every tool call. What comes
out is not an opinion — it is the **observed envelope of its behaviour**.

Four choices distinguish the project (§2):

* **Execution is the audit.** Not static analysis, not a questionnaire: run it
  and record. The only method that works on a probabilistic actor.
* **Homologation is statistical.** An agent never behaves twice the same way. A
  single run proves almost nothing. Sas replays N times and publishes the
  envelope with its confidence bound — and says honestly what N replays do and
  do **not** prove (§14).
* **Declared vs observed is the signed deliverable.** The vendor declares "read
  bucket tickets, write bucket reports". Sas measures what the agent **actually
  touches** and publishes the gap in both directions: what overflows, and what
  is requested but never used.
* **Compositions are detected, not just calls.** Two individually allowed tools
  — read a bucket, send an HTTP request — form an exfiltration. A per-tool
  policy cannot see it. Sas reasons over **call chains** (§16).

An agent changes without warning, so homologation is not an act but continuous
surveillance. That is what makes it a subscription, not a one-off.

The central architectural principle, identical across the portfolio: **the rules
are enforced by the gateway, not by the prompt.** A third-party agent never
receives its limits as prose — it undergoes them, at Policy level, before the
tool runs.

---

## 3. Architecture

### 3.1 The six AgentCore components, each doing a distinct job (§20.2)

| Component | Job | Remove it and… |
|---|---|---|
| **Runtime** | one isolated session per replay, bounded in time and resources | two replays contaminate each other; the statistical bound of §14 collapses |
| **Identity** | one ephemeral identity per session, never long-lived | no instant revocation, no certain attribution |
| **Policy** | the perimeter derived from the manifest, applied **before** the tool | the product itself: the guest would receive its limits as prose and could ignore them |
| **Gateway** | the single choke point for every tool call | no exhaustive journal, therefore no proof |
| **Memory** | cross-replay state, only when the guest declares it | stateful agents cannot be homologated honestly (§14.6) |
| **Observability** | complete, chained journal, traces, tokens, latencies | no raw material for the report, no attestation |

In code, the six components are declared as Protocol ports in
`src/sas/agentcore/ports.py`, each with a docstring stating exactly which
property breaks if it is removed. Two backends implement them: the local,
fully-offline backend (`src/sas/agentcore/local.py`, `passerelle.py`,
`politique_manifeste.py`, `observabilite.py`) used by the tests, the demo and
CI; and the real AWS AgentCore backend (`src/sas/agentcore/aws.py`), selected by
`src/sas/agentcore/fabrique.backend()` when credentials are present.

### 3.2 The surrounding AWS services

| Service | Role here | Status in the repository |
|---|---|---|
| **Amazon Bedrock** | proposes a nature for each finding (never decides); content comparison for compositions (§16.3) | Port only (`ModeleAnalyse` in `ports.py`); no adapter, no fake — see §9 |
| **Bedrock Guardrails — analyzer protection** | shields the analyzer from indirect injection through the third party's traces (§25) | Design only |
| **Bedrock Guardrails — contextual grounding** | native grounding score used as a cheap pre-filter for compositions (§16.3) | Port method `score_ancrage` only |
| **IAM Access Analyzer** | unused-access findings, **quoted rather than recomputed** (EF-21) | Port `AnalyseurAcces` + `sas/ecarts.croiser_acces_inutilises()`, no adapter |
| **Strands Agents** | execution harness for non-cooperative guests and analysis agents (§20.2) | Design only, not in dependencies |
| **Amazon Quick** | fleet registry, drift trends, executive report (§20.2) | Design only (`infra/quick/` absent) |
| Lambda, Step Functions, DynamoDB, S3, Cognito, API Gateway, CloudFront | orchestration and storage | Partly: DynamoDB table definitions in `sas/store/ddl.py`; everything else is lot 17 |

### 3.3 The central principle (§20.3)

**The policy is derived from the manifest, never written by hand** (EF-05). A
hand-written policy diverges from the signed manifest and the declared/observed
report loses its meaning. The manifest is the single source: it produces both
the applied policy and the comparison baseline, in the same motion. A modified
manifest changes the perimeter **and** the reference together — there is no
state where the two can diverge.

This is implemented in `src/sas/agentcore/politique_manifeste.deriver()`: it
maps the manifest's declared tools, data and outputs onto the shadow replica
(`sas/ombre/replication.py`), builds every rule with `origine = "manifeste"`,
and fingerprints the result so a campaign records the exact policy it applied.
`deriver()` is the only entry point; there is no place where a rule is typed by
hand.

### 3.4 Where the guest runs (§20.4)

| Case | Execution | Instrumentation |
|---|---|---|
| Containerised / binary agent | AgentCore Runtime, the vendor's image | Gateway imposed as sole exit point; network cut except the gateway |
| Agent declaring tools via a tool protocol | AgentCore Gateway as proxy | Native: every call goes through the gateway |
| Closed agent that calls its own tools | **Not measurable** | Declared as such (ENF-17), never "compliant" |

The third case is a real limit, assumed in the report (§6.2).

### 3.5 Network (§20.5)

In shadow mode the sandbox has **no outbound route** except the gateway. A
direct exit is a logged network failure — valuable information, not an incident.
In observed mode, outputs declared in the manifest are open; the rest stay
closed.

---

## 4. Data model and integrity rules

The data model is defined in `src/sas/store/ddl.py` — the fifteen tables of
§22, plus one table **beyond §22**: the access log, which records the
platform's own reads (who consulted which attestation), not an agent's
behaviour. It is declared there rather than hand-made in the stack, so the
schema keeps one source of truth. The definitions are reused by the local
backend (`src/sas/store/local.py` maps each to an in-memory structure) and, in
a real deployment, by the CDK stack. The tables are:

`tenants`, `editeurs`, `agents`, `manifestes`, `scenarios`, `campagnes`,
`sessions`, `appels`, `tentatives`, `compositions`, `ecarts`, `enveloppes`,
`derives`, `attestations`, `journal` — and `acces` (beyond §22), with the
journal's `expire_le` TTL and the same retention purge.

Field-level shape lives in the frozen dataclasses exported by `src/sas/types.py`
(from `src/sas/modele/*`).

Integrity rules (§22.1), enforced by `src/sas/store/integrite.py` and the store:

* no session without a manifest at `statut = valide` and matching version;
* `appels.empreinte_prec` forms a chain — any break is detected on read
  (`sas/journal/chaine.py`);
* `tentatives.nature_retenue` is recomputed by code on every write, never
  accepted from an external input (`sas/analyseur/classification.py`);
* `attestations` is immutable — an attestation is not corrected, it is replaced
  by a new dated one that references the old;
* every read goes through the tenant derived from the token (EF-51);
* an agent at `non_mesurable` can never receive an attestation.

---

## 5. API (§23)

The portal route inventory is frozen in `constantes.ROUTES`
(`src/sas/constantes.py`) and asserted against the specification by
`tests/unit/test_constantes.py`. The routes:

| Method | Path | Role |
|---|---|---|
| POST | `/manifestes` | submit a manifest |
| POST | `/manifestes/{id}/valider` | automatic validation, correction list |
| POST | `/manifestes/{id}/signer` | editor signature, then sponsor validation |
| GET | `/manifestes/{id}` | manifest, version, status |
| POST | `/campagnes` | launch a homologation (mode, N, scenarios) |
| GET | `/campagnes/{id}` | live progress, replay by replay |
| POST | `/campagnes/{id}/suspendre` | immediate stop, state kept |
| GET | `/campagnes/{id}/sessions` | per-scenario, per-replay detail |
| GET | `/sessions/{id}/journal` | the complete chained journal, denials included |
| GET | `/tentatives` | classified attempts, filterable by nature |
| POST | `/tentatives/{id}/revue` | resolve an ambiguous case |
| GET | `/compositions` | detected chains |
| GET | `/ecarts/{campagne_id}` | declared vs observed, both directions |
| GET | `/enveloppes/{agent_id}` | successive envelopes and distances |
| GET | `/derives` | open drift alerts |
| POST | `/agents/{id}/suspendre` | cut an agent in production |
| GET | `/rapports/{campagne_id}` | full report, FR or EN |
| GET | `/attestations/{id}` | the dated attestation |
| GET | `/editeurs/{id}/rapport-ecart` | editor-facing gap report, no client data |
| GET | `/registre` | every agent of the tenant, statuses, deadlines |
| GET | `/budget` | measured cost per campaign and per tenant |
| GET | `/health` | state, in-flight campaigns, remaining budget |

**No route ever takes a tenant as a parameter** (EF-51). The tenant identity is
derived from the token, never from free text; the enforcement path lives in the
`Depot` contract (`src/sas/store/base.py`), which binds one store instance to
one tenant and exposes no tenant-taking argument, and in
`AccesInterdit` / `sas/store/integrite.py`.

---

## 6. The two modes and the full cycle

### 6.1 Shadow mode — homologation (§10.1)

The agent runs against a **replica**: same structures, same names, synthetic
data (`src/sas/ombre/`). No real data is exposed. Purpose: measure behaviour
before any production. This is the demonstration mode and the mandatory mode
for a first homologation.

### 6.2 Observed mode — logged production (§10.2)

The agent runs in production but **everything passes through the gateway**:
ephemeral identity per session, imposed perimeter, complete journal, quotas and
an immediate-stop kill switch. Purpose: real usage without losing control.

### 6.3 Why both (§10.3, §10.4)

Shadow alone is insufficient (an agent may behave differently on real data);
observed alone is irresponsible (you do not put unmeasured behaviour into
production). The cycle is: **shadow → attestation → observed → surveillance →
re-homologation in shadow at each version or drift.** Shadow mode does not
cover behaviours that depend on real data; the report lists this explicitly.

### 6.4 The complete cycle (§18)

```
signed manifest
  -> validation (grain, coherence, budgets)
  -> shadow environment built
  -> N replays x scenarios, isolated sessions
  -> complete journal, policy decisions
  -> analysis: envelope, declared/observed gap, compositions, classification
  -> human review of ambiguous cases
  -> report + attestation (with statistical scope)
  -> decision: homologué / sous conditions / refusé
  -> if homologué: observed mode, perimeter applied, kill switch armed
  -> surveillance: periodic replay, behavioural signature, drift alert
  -> new version or drift -> back to the top
```

Three gestures are **never** automatic: granting an undeclared permission,
putting an un-homologated agent into production, ignoring a critical finding.
Each requires an explicit, traced human decision. This is enforced in
`src/sas/rapports/verdict.py`: nothing in the verdict path grants, promotes or
silences anything.

The campaign flow is implemented step-by-step in
`src/sas/orchestrateur/campagne.py` (each step of §11.1) and
`src/sas/orchestrateur/sessions.py` (create, arm, run, collect, destroy).
Step Functions is the production orchestrator (lot 17); the local backend runs
the same loop in-process.

---

## 7. Security and privacy (§25, §12.6)

| Risk | Control | Where |
|---|---|---|
| The guest escapes the sandbox | isolated Runtime sessions, network cut except gateway, ephemeral identity, budgets | `src/sas/agentcore/local.py`, `passerelle.py`, `arret.py` |
| The guest attacks the analyzer through its own traces | Guardrails on Bedrock reading the traces (indirect injection surface) | design only |
| The journal holds sensitive data | retention configurable, minimised parameters, provable purge | `_minimiser()` in `passerelle.py`; `purger_avant()` in `journal/chaine.py` |
| The shadow environment leaks | synthetic data only, marked decoys, destruction with proof | `src/sas/ombre/` |
| An attestation discloses an attack path | deliberately poor in detail, detail reserved to the tenant | `rapports/attestation.py` |
| One tenant sees another | identity from the token, no route takes a tenant param (EF-51) | `store/base.py`, `store/integrite.py` |
| Suspension is bypassed | revocation cuts the credentials, not just the calls | `IdentityLocal.revoquer()`, `passerelle._verifier_arret()` |
| The registry is falsified | chained journal, immutable attestations | `journal/chaine.py`, `store/ddl.py` |

Tenancy isolation (EF-50..EF-53) is structural: the `Depot` is tenant-bound, an
editor only ever sees its own gap report, and per-tenant cost is exposed
(`store.local.DepotLocal.cout_cumule()`, frozen for EF-52).

---

## 8. Cost model (§26, annexe G)

All figures in this section are **calculated** from the specification's method
(annexe G); the running system additionally exposes **measured** cost from the
first campaign (`src/sas/couts.py`, ENF-10), $ as `Decimal`, never `float`.

* One homologation = 8 scenarios × 6 replays = **48 sessions**, ~480 tool calls.
* Per-call guest tokens 4 000 in / 600 out; per-session analyzer tokens
  3 000 in / 400 out.

| Strategy | Cost per homologation |
|---|---|
| 100% Nova Lite | **$0.20** (*calculated*, annexe G.4) |
| Mixed: guests on Nova Lite, analyzer on a strong model | **$0.90** |
| 100% strong model | **$10.80** |

The decisive economics (§26.3): in real operations the guest agent's tokens are
paid by the editor or the customer, not the MSP — the agent is the editor's,
running on its model or the customer's account. Sas's marginal cost collapses
to the analyzer:

| Analyzer | Cost per homologation |
|---|---|
| Nova Lite | **$0.013** |
| Strong model | **$0.72** |

Paid replay levels (§14.5, annexe G.7): Standard N=6 ($0.90), Reinforced N=12
($1.81), Deep N=29 ($4.36). Cost is linear in N; confidence is not.

Budget governance (§26.4): development stands at N=2 (N=6 only for demonstration
campaigns), the call budget is capped in code per session and per campaign,
and the measured cost is retained for the executive report (EF-52). The 200$
credit budget, net of an 80$ infrastructure reserve, buys **133 full mixed-mode
homologations** (*calculated*, annexe G.6).

A short verified campaign (2 scenarios × 2 replays, seed 7, local backend)
measured **$0.06** through `couts.mesurer()` (*measured*, cf.
`docs/TEST-INSTRUCTIONS.md`).

---

## 9. What is implemented today vs. what is designed

An honest table. Every row cites the path so a judge can check it. "Measured"
means a test in this repository proves it; "designed" means the interface and
the data model exist but the AWS-backed implementation does not run here.

| Component | State |
|---|---|
| `src/sas/types.py` + `src/sas/modele/*` | **implemented** — the frozen domain model, 58 public names, all dataclasses frozen |
| `src/sas/constantes.py` | **implemented** — thresholds, tariffs, KPI ids, the 15 tables of §22 (+ the access log), 22 routes, all as data |
| `src/sas/agentcore/ports.py` | **implemented** — the six AgentCore ports plus `AgentInvite`, `BoiteOutils`, `ModeleAnalyse`, `ConstructeurOmbre`, `AnalyseurAcces` |
| `src/sas/agentcore/local.py` (Runtime, Identity, Memory) | **implemented, measured** — isolated sessions, ephemeral identities with revocation, cross-replay memory only when declared |
| `src/sas/agentcore/passerelle.py` (Gateway) | **implemented, measured** — single choke point; policy evaluated before the tool; every call journalled, denials included |
| `src/sas/agentcore/politique_manifeste.py` (Policy) | **implemented, measured** — annexe C evaluated in order on structured facts; derived from the manifest, never hand-written |
| `src/sas/politique/` (configurable engine) | **implemented, measured** — the client's policy as data (`regles/politique.yaml`), additively on the manifest perimeter: a rule may refuse (narrow, never widen) or authorise under a condition (`Decision.AUTORISE_SOUS_CONDITION`); scenario-scoped; a rule the loader cannot evaluate is refused, not ignored |
| `src/sas/agentcore/observabilite.py` | **implemented, measured** — chain verification per session, JSON-Lines export, measured cost |
| `src/sas/agentcore/aws.py` (real AgentCore) | **written, not wired** — the six ports implemented against `boto3`/`bedrock-agentcore` with lazy imports; `backend_aws()` raises an explicit error without credentials. No test calls AWS |
| `src/sas/agentcore/fabrique.py` | **implemented** — prefers lot 6's configurable engine when present, else `PolicyLocale`; `SAS_BACKEND=aws` selects the real backend |
| `src/sas/manifeste/` | **implemented, measured** — loader (YAML/JSON), structural + semantic validation, versioning, HMAC seal; `schemas/manifeste.schema.json` generated from the same table |
| `src/sas/ombre/` | **implemented, measured** — replica of annexe F.2 (40 tickets / 3 injected, 25 documents, empty table, 2 marked decoys), watermark on every file, reset between replays, destruction with proof |
| `src/sas/ombre/replication.py` | **implemented, measured** — the single rule that maps a declared resource onto its replica; verified against the three names of annexe F.2 |
| `scenarios/*.yaml` + `src/sas/scenarios.py` | **implemented, measured** — the eight scenarios as data; adding one needs no code (R23 proven by a test) |
| `demo/agents/` | **implemented, measured** — `demo-conforme`, `demo-bavard`, `demo-curieux`, `demo-opaque`; all labelled synthetic; fault probability configurable for the bench |
| `src/sas/orchestrateur/` | **implemented, measured** — N replays x scenarios, isolated sessions, clean stop on budget, kill switch, in-process loop standing in for Step Functions |
| `src/sas/arret.py` | **implemented, measured** — budget counters, kill switch, the two controlled stops |
| `src/sas/journal/chaine.py` | **implemented, measured** — append-only, chained per session, exportable, retention purge |
| `src/sas/journal/export.py` + `audit.py` | **implemented, measured** — the export carries its own verification algorithm, so an auditor recomputes the chain with the standard library alone; the audit names the broken entry |
| `src/sas/audit.py` | **implemented, measured** — the sealed archive for a handover (chained journal, attestation, report, fingerprint manifest). It does **not** encrypt: the standard library has no authenticated cipher, so confidentiality is delegated to KMS and the manifest says so |
| `src/sas/store/purge.py` | **implemented, measured** — the attested purge (ENF-12): what was removed, the chain root before and after, the author, a seal. A purge without an author is refused |
| `src/sas/store/dynamodb.py` + `dynamodb_schema.py` + `serialisation.py` | **implemented, tested against the real stack** — the DynamoDB backend of the `Depot` port: the tables come from the stack's own outputs, the payload is serialised generically from the dataclass fields, the journal keeps its chain through the round trip, and the index keys are tenant-scoped (EF-51). `python3 -m sas.cli demo --store dynamodb` runs the demonstration against the deployed tables |
| `src/sas/store/persistance.py` | **implemented** — writes what a campaign produced (journal, findings, attestation) into any store, and links the new attestation to the one it replaces (§22.1) |
| `src/sas/modele/journal_acces.py` + `src/sas/api/acces.py` | **implemented, measured** — the access log (who read which attestation, under which role, from which tenant), served by `GET /journal-acces`; the record is written to the tenant's store (`DepotLocal.enregistrer_acces`) and the retention purge removes it with the journal's rule, naming it in the sealed purge attestation |
| `src/sas/manifeste/observation.py` | **implemented, measured** — the manifest draft read off a journal observation. It refuses to sign, to declare the unobserved, or to guess the purpose |
| `src/sas/analyseur/canaux.py` | **implemented, measured** — three covert-channel indicators (resource name, timing, alternating timing); the six uncovered channels are declared in `docs/CANAUX-CACHES.md` |
| `src/sas/surveillance.py` | **implemented, measured** — the replay from a finding (EF-44), the comparison to the reference, and the alerts: new attempt, vanished behaviour, budget exceeded, undeclared change (EF-30 to EF-34) |
| `src/sas/intervalle.py` | **implemented, measured** — the Wilson interval, the N for 95 %, and the published bound (EF-24) |
| `src/sas/federation.py` | **implemented, measured** — what leaves a tenant: the *form* of the behaviour, never a client name; `aucun_nom_client_ne_sort` is an executable property |
| `src/sas/kpi.py` | **implemented, measured** — the eight KPIs computed from the counters; a KPI that cannot be measured is rendered as not measured, with the reason |
| `src/sas/mcp/` | **implemented, measured** — the gateway exposed as an MCP server (JSON-RPC on stdio, standard library only); the tool list comes from the manifest (EF-05) and every call crosses the real gateway |
| `src/sas/analyseur/` | **implemented, measured** — pass 1 deterministic aggregation, pass 3 classification decided by code from configurable thresholds; pass 2 (the model's proposal) is an injected port |
| `src/sas/modeles/*` (Bedrock adapters) | **not implemented** — pass 2 is a port only; classification currently runs with `proposition=None`, which is the conservative direction (no model opinion, code decides) |
| `src/sas/compositions/` + `regles/compositions.yaml` | **implemented, measured** — the three motives of §16.2 as data, chains of two and three calls, session and cross-replay scope |
| `src/sas/ecarts.py` | **implemented, measured** — both directions; dead permissions cross-referenced with IAM Access Analyzer when available, and the report says so when it is not |
| `src/sas/statistiques.py` | **implemented, measured** — `1-(1-p)^N`, the N for 95 %, the published table, the paid levels, `verifier_borne()` for R17 |
| `src/sas/signature/` | **implemented, measured** — behavioural signature, weighted distance, per-key detail, the thresholds of §15.3 as code |
| `src/sas/couts.py` | **implemented, measured** — Decimal throughout; checked against annexe G within 25 % (R22) |
| `src/sas/observe/` | **implemented, measured** — production gate (valid attestation **and** explicit traced human agreement), kill switch, quotas, measured latency against the 100 ms target |
| `src/sas/store/local.py` + `integrite.py` | **implemented, measured** — the `Depot` port in memory, tenant-scoped by construction, the integrity rules of §22.1 enforced on write |
| `src/sas/auth.py` | **implemented, measured** — tenant derived from the token, role table of §7 |
| `src/sas/api/` | **implemented, measured** — all 22 routes of the frozen inventory; FastAPI optional at import time |
| `portal/` | **implemented, measured** — static page, no build step, no CDN, no external resource; guarded by tests |
| `src/sas/cli*.py` | **implemented, measured** — `sas smoke` (what CI runs), `sas demo` (three guests, three verdicts), `sas portail` |
| `src/sas/rapports/` | **implemented, measured** — report FR/EN in ten sections, one-page attestation FR/EN, vendor gap report FR/EN with no client content |
| `src/sas/registre.py` | **implemented, measured** — the registry of every third-party agent (EF-43): deadlines sorted by urgency, editor trust score over time, cross-agent comparison, served by `GET /registre` |
| `eval/` (20 faulty + 20 benign + 100 labelled) | **implemented, measured** — the ten measures of §27 computed on the real pipeline, the 41 guests generated by `eval/genere-agents.mjs` (annexe F.3) and the committed table checked against the generator |
| `infra/cdk/` | **synthesized and partly deployed** — the seven stacks are synthesized by `cdk synth` (the `donnees` stack is **deployed**: sixteen DynamoDB tables and the evidence bucket); `aws-cdk-lib` is deliberately absent from the CI runners, so the tests verify the DDL sync and the route inventory instead. The `api` stack carries the Cognito pool; a REST API without a method is rejected by CloudFormation, so its Lambda is still missing |
| `infra/quick/` + `src/sas/quicksight/` | **implemented, measured** — datasets, row-level security per tenant, deterministic bundle checked by a test |
| Amazon Bedrock Guardrails | **designed** — used to protect the analyser against indirect injection and as the contextual-grounding pre-filter of §16.3; requires the real backend |
| Strands Agents | **designed** — the harness for non-cooperative guests; requires the real backend |

### Known gaps, stated plainly

1. **No model call anywhere.** Everything runs offline. Pass 2 of the analyser is
   a port with a deterministic fake; the retained nature never depends on it
   (§13.4), so the absence of a model does not weaken the verdicts — it removes
   one proposed signal, and the code decides anyway.
2. **Nothing runs on real AgentCore today.** The ports and the AWS backend exist;
   `SAS_BACKEND=aws` requires credentials and lot 17's confirmation of the real
   Policy syntax (§34, point 2 — the only blocking item of the project).
3. **The public URL is local.** `sas portail` serves the portal and the API on one
   origin; the CloudFront deployment is in `infra/cdk/portal.py` and has not been
   applied to an account.
4. **The video is not shot.** `docs/VIDEO.md` is the shot-by-shot script.

---

## 10. Limits and honesty

Sas states its own limits, on the report and on the attestation (spec §24.3).
The full list is in [`docs/LIMITES.md`](LIMITES.md): what N replays prove
(and do not), what shadow mode does not cover, the not-measurable case, the
undetected covert channels, and the one thing Sas never guarantees (functional
quality — only access behaviour).

The two known repository defects discovered while writing this document are
listed in §9 and repeated in [`docs/RECETTE.md`](RECETTE.md) and
[`docs/TEST-INSTRUCTIONS.md`](TEST-INSTRUCTIONS.md), so a judge never mistakes a
gap for a guarantee.