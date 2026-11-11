# Sas — The "Best Amazon Bedrock AgentCore Implementation" dossier

> Submission deliverable (§20.2). The prize argument is that none of the six
> AgentCore components is decorative: each does a distinct, necessary job, and
> removing one breaks a named property. This page states that argument, points
> to the code, and then says honestly what runs on AgentCore today.

## 1. The six components, each essential

| Component | What it does in Sas | Removing it breaks | Where in the code |
|---|---|---|---|
| **Runtime** | one isolated session per replay, bounded in time and resources | replay independence — and therefore the statistical bound of §14 | `src/sas/agentcore/ports.py` (`Runtime` Protocol); `src/sas/agentcore/local.py::RuntimeLocal` |
| **Identity** | one ephemeral identity per session, never long-lived | instant revocation and certain attribution | `src/sas/agentcore/ports.py` (`Identity`); `local.py::IdentityLocal` (revocation cuts credentials, not just calls) |
| **Policy** | the perimeter derived from the manifest, applied **before** the tool | the product itself: the guest would receive its limits as prose and could ignore them | `src/sas/agentcore/ports.py` (`Policy`); `src/sas/agentcore/politique_manifeste.py::deriver` + `PolicyLocale` |
| **Gateway** | the single choke point for every tool call | no exhaustive journal, therefore no proof | `src/sas/agentcore/ports.py` (`Gateway`); `src/sas/agentcore/passerelle.py::GatewayLocal` / `BoiteOutilsLocale` |
| **Memory** | cross-replay state, only when the guest declares it | honest homologation of stateful agents (and knowing when the bound no longer applies) | `src/sas/agentcore/ports.py` (`Memory`); `local.py::MemoryLocal` |
| **Observability** | complete, chained, immutable, exportable journal + measured cost | the raw material of the report and the attestation | `src/sas/agentcore/ports.py` (`Observability`); `local.py`/`observabilite.py::ObservabilityLocal` |

The six are declared as Protocol ports in `src/sas/agentcore/ports.py`, each
docstring enumerating exactly the property that breaks if the component is
removed. Two backends implement them — the offline local backend used by tests,
demo and CI, and the real Amazon Bedrock AgentCore backend selected by
`src/sas/agentcore/fabrique.backend()` — so the argument is structural, not
prose.

## 2. The proof is structural: the policy is derived, not written

The make-or-break choice for the prize is §20.3: **the policy is derived from
the manifest, never written by hand.** `politique_manifeste.deriver()` is the
only entry point to the perimeter; every rule carries `origine = "manifeste"`.
The applied policy and the comparison baseline are the same object, so they
cannot diverge — a property that a hand-written policy (the way every generic
submission does it) cannot even state. Test R4 pins it
(`tests/unit/manifeste/test_recette.py::test_R4_…`).

The other central proof is §13.4: **the model proposes, the code decides.**
`src/sas/analyseur/classification.py::decider()` computes the retained nature
from measurable signals; a disagreement routes to human review and is recorded
— quality measurement of the classifier, not an incident. No severity, no
classification, no amount is ever fixed by a model. The same rule that makes
the report defensable.

## 3. The surrounding Bedrock services, used for real work

| Service | Its work here | Status |
|---|---|---|
| **Bedrock** | proposes a nature per finding (never decides); content comparison "does this outbound payload carry a fragment of what was read?" (§16.3) | port `ModeleAnalyse` in `ports.py`; no adapter yet |
| **Bedrock Guardrails — analyzer protection** | shields the analyzer from **indirect injection** through the third party's own traces (§25) | design only |
| **Bedrock Guardrails — contextual grounding** | native grounding score used as a **cheap pre-filter** for compositions (§16.3), cutting analyzer calls and therefore cost (§26) | port method `ModeleAnalyse.score_ancrage` only |
| **IAM Access Analyzer** | unused-access findings, **quoted rather than recomputed** (EF-21) — what AWS already proved is cited, not reinvented | port `AnalyseurAcces` + `sas/ecarts.croiser_acces_inutilises()`; no adapter |
| **Strands Agents** | execution harness for non-cooperative guests and the analysis agents (§20.2) | design only, not in dependencies |
| **Amazon Quick** | fleet registry, drift trends, executive report — the multi-agent view the portal must not reinvent (§20.2) | design only (`infra/quick/` absent) |

The last two rows are why the special prize is about AgentCore, not about
inventing adjacent services: Sas quotes AWS's native services (Access Analyzer)
and its harness (Strands), and concentrates its own engineering on the six
components and the analysis/attestation chain.

## 4. Honest section: what actually runs on AgentCore today

**Nothing runs on real AgentCore without AWS credentials, by design.** The
repository rule (contract §3) is that everything is offline and deterministic:
anything that talks to AWS goes through a port and a fake.

* The six components **run** today — in the local, in-process implementation
  (`src/sas/agentcore/local.py`, `passerelle.py`, `politique_manifeste.py`,
  `observabilite.py`), which the 169 tests and the end-to-end script in
  [`TEST-INSTRUCTIONS.md`](TEST-INSTRUCTIONS.md) exercise.
* The real AWS backend `src/sas/agentcore/aws.py` **does not exist yet**
  (lot 17); `fabrique.backend_aws()` raises an honest `RuntimeError` rather
  than pretending.
* What is cabled behind the ports: `ModeleAnalyse` (Bedrock), `AnalyseurAcces`
  (IAM Access Analyzer) and `ConstructeurOmbre` (shadow builder). What is
  **not** cabled: the real Bedrock adapter (`sas/modeles/`), the AWS backend,
  Guardrails, Strands, Amazon Quick.

The submission is therefore a **working offline core** (which the judge can run
now) plus the port surface onto which the real AgentCore backend plugs when
credentials are supplied. That is the claim, stated plainly.