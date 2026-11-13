# Sas — RUNBOOK

Deployment, operations, emergency stop and cost control for the IaC of lots 16
and 17. The infrastructure lives in `infra/cdk/`, generated **from the code**
(`sas.store.ddl`, `sas.constantes`, `sas.quicksight`) — never from a hand-made
copy. Test it with `tests/unit/iac`, `tests/unit/aws`, `tests/unit/quick`.

---

## 1. Prerequisites

- Python 3.12, `aws-cdk-lib`, `constructs`, `boto3` (see `infra/cdk/requirements.txt`).
- `SAS_AWS_REGION` (default `eu-west-3`, fallback `eu-central-1` — §34 point 1).
- AWS credentials resolvable by the SDK (env keys or a configured profile).

The CI runner never installs `aws-cdk-lib` and never runs `cdk synth`. The IaC
business logic is importable offline; aws-cdk imports live **inside** the
builder functions.

## 2. Deploy

```bash
cd infra/cdk
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=../../src cdk synth --all
PYTHONPATH=../../src cdk deploy --all
```

`cdk.json` points to `python3 app.py`; `app.py` puts the repo root and `src/`
on `sys.path` itself, so the synth also works from `infra/cdk/` directly.

One stack per domain: `donnees` (DynamoDB + S3 preuves), `agentcore`, `orchestration`
(Step Functions), `api` (API Gateway + Cognito), `portail` (S3 + CloudFront),
`observabilite` (CloudWatch), `quick` (Amazon Quick).

## 3. Choosing the backend

The local backend runs offline by default. To use the real AWS backend:

```bash
export SAS_BACKEND=aws
export SAS_AWS_REGION=eu-west-3
```

Only `sas.agentcore.fabrique.backend_aws()` touches `sas.agentcore.aws`. If
boto3 or the credentials are missing, `backend()` raises an **honest** error —
it never silently falls back to the local backend.

## 4. Operations

- **Tables** — 15 DynamoDB tables generated from `sas.store.ddl`. A schema
  change is a single edit there; `test_ddl_sync.py` fails if the IaC drifts.
- **Journal** — append-only, chained, with `TimeToLive` on `expire_le` (ENF-12).
  Retention is configurable per tenant through the `tenants` table.
- **Shadow egress** — the shadow sandbox security group has no outbound route
  except the gateway (§20.5); any direct outbound attempt fails and is recorded
  as a tentative.
- **Regenerate Quick assets** — `PYTHONPATH=src python3 scripts/genere_assets_quick.py`
  writes `infra/quick/datasets.json` deterministically. Re-running is a no-op.

## 5. Emergency stop

1. `POST /campagnes/{id}/suspendre` — the runtime stops within 5 s (ENF-09).
2. Identity revocation cuts the ephemeral credentials, not just the calls (§11.4):
   a suspended guest cannot "finish".
3. `POST /agents/{id}/suspendre` arms the policy kill switch for production.

## 6. Cost and budget

$200 of credits. Two hundred dollars, not one more silently:

| Rule (§26.4) | Enforcement |
|---|---|
| 1. Nova Lite only in dev and recette | model id pinned to `amazon.nova-lite` in the orchestrator |
| 2. N = 2 in dev, N = 6 only for demo campaigns | `N_DEVELOPPEMENT` vs `NIVEAUX_REJEUX` |
| 3. Call budget capped in code | `BUDGETS_DEFAUT` per session and per campaign (ENF-03) |
| 4. Cost measured from the first campaign | `Observability.cout()` quotes the counters (ENF-10) |
| 5. No dedicated model endpoint, no permanent SageMaker, no GPU | serverless-only API + Lambda + DynamoDB |
| 6. Shadow environments destroyed with proof | `ConstructeurOmbre.detruire()` returns `(when, proof)` (ENF-06) |

### Testing the budget alarm

The CloudWatch budget alarm `budget-200` (in `observability.py`) fires at the
$200 credit limit with the reserve threshold surfaced as data. To test it
without spending money:

1. Synthesize the template and read the alarm definition:
   `PYTHONPATH=../../src cdk synth observabilite` and grep `budget-200`.
2. In the console, create a temporary budget at `$1` with a CloudWatch alarm
   action, point it at a test SNS topic, and confirm the email/hook fires when
   the (demo) spend crosses it — then delete both.
3. The threshold values are pure data in `observability.alarmes()`, so the test
   `test_alarme_disponibilite_et_budget` exists without any AWS call.

## 7. Honest limits

- AgentCore **Policy** conditional-refusal syntax is `TODO(confirm)` — §34 point
  2. Until confirmed, the lot-6 policy engine enforces the broad perimeter in
  front of the Gateway (§32 line 1). This fallback is documented, not hidden.
- AgentCore **Runtime** executing an arbitrary third-party image is `TODO(confirm)`
  — §34 point 3. The three demo guests are synthetic and labelled as such.
- Drift detection does not cover fine hidden channels (§16.4); an unmeasurable
  agent is declared unmeasurable, never compliant (ENF-17).

## 8. The runners (the repository is public)

`Tradoooo/sas` is a **public** repository, and a public repository may only use
the organisation's self-hosted runners if their runner group allows public
repositories. So the runners are split, and the split is deliberate:

| Jobs | Runner | Why |
|---|---|---|
| `ci`, `ci-budget`, `stale-base-guard`, `hermes-lite`, `conflict-resolver` | **GitHub-hosted** (`ubuntu-latest`, variable `CI_RUNNER_PR`) | a pull request is untrusted code: it runs in an ephemeral VM, never on an organisation machine — and it does not queue behind the whole organisation |
| `nightly` (mutation, bench, fuzzing, campagne N=6, couverture, conformité, données portail) | **self-hosted**, group `sas`, runner `r630-sas-01` (variable `CI_RUNNER`) | those jobs are calibrated for the r630 (the longest, the coverage, takes ~2 min there) |

The `sas` runner group is **selected** (`Tradoooo/sas` only) and allows public
repositories; the organisation's `Default` group keeps
`allows_public_repositories: false`, so the shared r630 fleet stays closed to
the other public repositories of the organisation.

Runner service (on r630):

```bash
systemctl --user status actions-runner-r630-sas-01.service
systemctl --user restart actions-runner-r630-sas-01.service
```

If it is offline, the nightly queues; the light CI keeps working on
GitHub-hosted. A runner that shows up in the group but never picks a job is
usually a label mismatch: the workflows ask for `self-hosted` **and**
`sas-worker`.

## 9. Déployer et prouver dans un vrai environnement

The submission must not only *claim* a deployment. This is the sequence that
produced a real one, with the three traps it holds.

```bash
cd infra/cdk
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cdk bootstrap aws://<compte>/eu-west-3 --region eu-west-3   # une fois
cdk synth                                                  # les 7 piles
cdk deploy sas-donnees-dev --region eu-west-3 --require-approval never
```

Then the demonstration writes into the deployed tables, and the tests prove it:

```bash
PYTHONPATH=src python3 -m sas.cli demo --store dynamodb --tenant tenant-demo
PYTHONPATH=src python3 -m pytest tests/unit/aws -m aws -v
```

**The three traps, each of which cost a deployment:**

1. **A REST API without a method is invalid.** CloudFormation rejects
   `sas-api-dev` with *"The REST API doesn't contain any methods"*. The `api`
   stack therefore carries the Cognito pool, and the Lambda that would give the
   API its methods does not exist yet (lot 18). Deploying the stack before
   writing the Lambda is how this trap is met.
2. **The physical names must be written down.** CloudFormation generates
   `sas-donnees-dev-journalDF5B…` if the table has no explicit name, and the
   adapter would then address a table that does not exist. The names are
   deterministic (`sas-donnees-<table>-<env>`) and published as the stack's
   outputs; the adapter reads **those outputs**, never a guess.
3. **A scan is one page.** `scan()` returns one megabyte at a time and the
   filter applies inside the page: reading only the first page silently drops
   rows, which turns a complete journal into a partial one and makes the chain
   verification lie. The adapter walks the scan to its end.

**The credentials.** The tests marked `aws` need an account and the deployed
stack; without them they **skip** (never silently pass). The nightly job
`store-reel` runs them when the runner has credentials, and says so in the log
when it does not.
