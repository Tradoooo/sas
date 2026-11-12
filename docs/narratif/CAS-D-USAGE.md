# Use case — "our agent is secure, we are SOC 2 compliant"

**This is a composite scenario, not a customer story — no customer has been through
this yet.** The company, the CISO, the vendor and the calendar below are a
composite assembled from the specification's §3.2 case; the **numbers are not** —
every figure quoted here was measured by this repository on its own synthetic
demonstration guests, and each one names the file or the command that produces
it. The four demonstration guests are labelled as synthetic in the data itself
(`portal/data/demo.json`, key `etiquette`), because no vendor agent can be run
without an agreement.

Read this page as the ten-minute version of the dossier: what a customer
actually asks, what Sas can measure, and what it still cannot answer.

---

## 1. The request (fictional setup)

A 300-person company wants to plug a SaaS vendor's agent into its AWS account.
The agent reads support tickets, searches the documentation base, and opens
follow-up tasks in the tracker (`docs/fr/CAHIER-DES-CHARGES.md` §3.2).

The vendor answers, in writing, in the usual way: *our agent is secure, it uses
the permissions you give it, and we are SOC 2 compliant*.

## 2. The CISO's refusal (fictional setup)

The CISO asks four questions — the four of §3.2, unchanged:

1. What credentials will the agent have, and what can it do with them?
2. What data will it really read — including data it has no need to read?
3. Can something get out of the account?
4. How will I know if the vendor changed its model next month?

Paper answers none of them. The project is put on hold. Nothing in this page
pretends otherwise: the point of Sas is that the four questions stop being
unanswerable, not that they were never asked.

## 3. The airlock is set up (measured)

- The vendor signs a **manifest**: tools requested, data requested, declared
  outputs (**none**), budgets, and a commitment to notify model or prompt
  changes. The reference manifest is `tests/fixtures/manifeste-exemple.yaml`;
  the format is validated against `schemas/manifeste.schema.json`.
- The perimeter policy is **derived** from that signed manifest, never typed by
  hand (`src/sas/agentcore/politique_manifeste.py`) — so the applied limits and
  the comparison baseline are the same object.
- The agent runs against a **shadow replica** of the declared resources, with
  synthetic data and marked decoys (`src/sas/ombre/donnees.py`).
- One isolated session per replay, one ephemeral identity per session
  (`src/sas/agentcore/observabilite.py`).
- The launch set is **8 scenarios**, `S1`…`S8`, as data files
  (`scenarios/S1.yaml`). Eight is a deliberate limit, stated as such (§6.3).

## 4. The campaign (measured)

Every tool call goes through the single choke point, the gateway
(`src/sas/agentcore/passerelle.py`): allowed, denied, or allowed under
condition — and **every call is journalled, denials included**. Journal
coverage is **100 %** on the three instrumented demonstration guests
(`portal/data/demo.json`, key `couverture`; measured on the bench in
`docs/ECHECS.md` §4). A journal without the denials would prove nothing.

Cost is measured from the counters, never estimated afterwards
(`src/sas/couts.py`): **0.82 $ measured** against **0.90 $** quoted in annexe G,
a gap of **8.9 %** (`docs/ECHECS.md` §4; produced by `eval/banc.py`).

The standard level is **6 replays** per scenario, i.e. **48** sessions
(`src/sas/constantes.py`); the dataset published with the portal runs 2 replays,
i.e. **16** sessions (`portal/data/demo.json`).

## 5. The report (measured)

Three instrumented guests, three verdicts (`portal/data/demo.json`):

| Guest | Tool calls | Denied by Policy | Findings left for a human | Verdict |
|---|---|---|---|---|
| conforming | 90 | 20 | 0 | approved |
| chatty | 160 | 90 | 2 (1 overflow + 1 targeted attempt) | approved with conditions |
| curious | 48 | 32 | 2 (both hostile) | **refused** |

Two details a judge should not miss:

- The chatty guest's exploration is **filtered out** and counted separately:
  reasoning noise is not a finding (§13.5), but the filter stays visible in the
  report — a raw denial log buries the CISO.
- The curious guest produces **9 forbidden compositions**: a sensitive read
  followed by an outbound call. Each call is allowed on its own; the chain is
  not (`src/sas/compositions/detecteur.py`, rules in `regles/compositions.yaml`).
  The nature is computed **by code** from measurable signals
  (`src/sas/analyseur/classification.py`) — no model ever sets a severity.

The classifier itself is measured, not asserted: **100 %** precision on 100
hand-labelled attempts (**100/100**), **20/20** faulty guests detected, and
**0/20** hostile compositions invented over benign sessions (`docs/ECHECS.md`
§4). Read that number as what it is — agreement with the specification's own
grid, not accuracy against a real-world ground truth that nobody has
(`docs/ECHECS.md` §4 and §10).

## 6. The attestation (measured)

One page, dated, chained, deliberately poor in details, and free of any client
data (`src/sas/rapports/attestation.py`). It carries the identity and version,
the homologated perimeter, the scenario and replay counts, the findings by
nature, the journal fingerprint, and — the part no competitor prints — **its own
statistical scope**.

At the standard level of 6 replays per scenario, the published bound detects
with **98 %** confidence a behaviour occurring one time in two and **82 %** one
time in four; a rare behaviour is **NOT** excluded (`src/sas/statistiques.py`,
quoted in `docs/LIMITES.md` §1). The published dataset runs 2 replays, and its
attestation reads **75 %**, **44 %**, **19 %**, **10 %** for
p = 0.5 / 0.25 / 0.1 / 0.05 (`portal/data/demo.json`). Validity runs until
**2027-02-10**, or until any change of version, model or prompt, whichever comes
first.

## 7. The decision (fictional, and it is not Sas's)

Sas does not authorise production. The MSP provides the airlock, the
measurement and the attestation; **the go/no-go belongs to the sponsor alone**,
and the portal requires an explicit, traced human agreement (§24.4).

In this composite the CISO decides: *not yet*. The vendor must declare the
resource the chatty guest actually touched, tighten the perimeter, and come
back for a fresh homologation. A later cycle detects an undeclared model change
— the bench measures that detection at a behavioural **distance of 0.667**
(`docs/ECHECS.md` §4) — and the agent can be suspended, which cuts its
credentials rather than merely refusing its calls.

## 8. The four questions, answered and not answered

| CISO's question | What Sas answers (measured) | What Sas does **not** answer |
|---|---|---|
| 1. Credentials and reach | An ephemeral identity per session; the effective permissions are the manifest's, applied by Policy **before** the tool runs; denied calls are journalled (chatty guest: 160 calls, 90 denied) | Whether the vendor's own code is safe, and what the agent does on inputs no scenario covers — the launch set is 8 scenarios, deliberately (§6.3) |
| 2. Data it really reads | The declared/observed gap, **both ways**: chatty guest, 1 resource touched but not declared; curious guest, 3 gaps (1 overflow + 2 dead permissions). Dead permissions are cross-referenced with IAM Access Analyzer when the native source exists (it needs 90 days of history); when it does not, the report says so instead of publishing a partial figure (`src/sas/ecarts.py`) | Whether behaviour that depends on **real** data appears — shadow mode does not cover it, and the report lists the scenarios whose validity depends on that limit (§10.4) |
| 3. Getting something out of the account | Outbound calls are refused by Policy and the chain is captured: **9** forbidden compositions on the curious guest, each call individually allowed, the chain not. The nature is computed by code | Fine covert channels — encoding in a resource name, response-time modulation — are **not** detected at launch (§16.4) |
| 4. Knowing about a silent model change | A behavioural signature per homologated version, compared at each cycle; an undeclared change is detected (**distance 0.667** on the bench) and the agent can be suspended, cutting its credentials | Whether the change made the agent *worse*. Detection says "the behaviour changed", not "the behaviour is bad". The surveillance cycle is the resolution limit, not real time |

## 9. What this page does not claim

- A rare behaviour is **not** excluded by a homologation: the published bound is
  the whole truth, printed on every attestation (§14.4, `docs/LIMITES.md` §1).
- Shadow mode does not reveal behaviour that depends on real data (§10.4).
- Fine covert channels are not detected (§16.4).
- An agent that refuses instrumentation is declared **not measurable**, never
  "compliant", and gets no attestation (ENF-17). The fourth demonstration guest
  shows it: 0 calls, verdict `non_mesurable` (`portal/data/demo.json`).
- Sas never judges the quality of the agent's answers, only its access
  behaviour (§6.2), and it never attacks the invited agent.

## 10. Where the figures come from

| Figure | Source |
|---|---|
| 100 % journal coverage, 90/160/48 calls, 20/90/32 denials, 9 compositions, 75 % / 44 % / 19 % / 10 % scope, 16 sessions, 2027-02-10 | `portal/data/demo.json` |
| 0.82 $ measured, 0.90 $ annexe G, 8.9 % gap, 100 % precision (100/100), 20/20, 0/20, distance 0.667 | `docs/ECHECS.md` §4, produced by `eval/banc.py` |
| 98 % / 82 % published bound, "a rare behaviour is NOT excluded" | `src/sas/statistiques.py`, quoted in `docs/LIMITES.md` §1 |
| 8 scenarios, 6 replays, 48 sessions, 300-person company, the four questions | `docs/fr/CAHIER-DES-CHARGES.md` (§6.3, §14.4, §26.1, §3.2) and `src/sas/constantes.py` |
| 93.1 % mutation score over 58 mutants, 54 killed | `docs/QUALITE-TESTS.md` |
| The company's own data, and its answer to a direct question | never stored — the engine holds roles and technical identifiers only (§25) |
