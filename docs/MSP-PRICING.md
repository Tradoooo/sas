# Sas — MSP pricing

> Submission deliverable (§8, §26.3, annexe G). The offer is a **subscription**,
> not an engagement, for a structural reason (§8): a third-party agent is never
> homologated once and for all. Figures below come from the specification,
> marked *calculated* (annexe G); they are not rounded differently than the
> annexe.

## 1. The five service levels (§8)

| Level | Content | Frequency | Billing |
|---|---|---|---|
| **Homologation** | manifest, sandbox, scenarios, N replays, declared/observed report, attestation | once per agent and per version | flat, per agent |
| **Hosting** | the sandbox stays available, the agent runs in observed mode, complete journal, quotas | continuous | monthly subscription, per agent |
| **Surveillance** | periodic scenario replay, drift detection, alert, re-homologation | weekly + at each declared version | included in the subscription |
| **Third-party attestation** | dated document for an insurer, auditor or contracting authority | on demand | per act |
| **Registry** | inventory of every third-party agent, statuses, deadlines, perimeters | continuous | included from 3 agents |

## 2. Why a subscription, not an engagement (§8)

An agent changes: its tools change, its model changes, the data it meets
changes. Homologation is therefore never a one-off act — it is continuous
surveillance. The subscription is not a billing trick; it is the only form in
which the service makes sense (exactly as for `piege`). Second: the service is
sold **per agent** — a customer that accepts three agents pays three times, so
revenue grows with the number of agents in the customer's estate, the market's
structural trend.

## 3. The structural margin (§26.3)

In real operations the **guest agent's tokens are charged to the editor or to
the customer**, not to the MSP: the agent is the editor's, running on its model
or the customer's account. Sas's marginal cost therefore collapses to the
analyser:

| Analyser | Cost per homologation (*calculated*, annexe G.4) |
|---|---|
| Nova Lite | **$0.013** |
| Strong model | **$0.72** |

In production the service costs a few cents per homologation and is sold as a
flat fee. The margin is not a hypothesis, it is structural — a classic MSP
arbitrage: heavy variable cost (the guest's compute) sits on the customer's
side of the invoice, while the repeatable, cheap analysis stays with the MSP.
This is the number shown in the executive report (§26.3), and the measured
figure is exposed by `src/sas/couts.py` (ENF-10).

## 4. Full homologation cost and the paid replay levels (annexe G.4, G.7)

| Strategy | Cost per homologation (*calculated*) |
|---|---|
| 100% Nova Lite | **$0.20** |
| Mixed: guests on Nova Lite, analyser on a strong model | **$0.90** |
| 100% strong model | **$10.80** |

| Level | N | Sessions | Mixed cost (*calculated*) | Confidence at p = 0.25 |
|---|---|---|---|---|
| Standard | 6 | 48 | **$0.90** | 82% |
| Reinforced | 12 | 96 | **$1.81** | 97% |
| Deep | 29 | 232 | **$4.36** | 99.97% |

The cost is linear in N, the confidence is not — an arbitrage presented to the
customer, never a default. The threshold tariffs themselves
(`amazon.nova-lite`, `modele-fort`) live as data in `src/sas/constantes.py`
and are flagged "to confirm against the pricing console".

## 5. Pricing honesty

* Every cost in the running system is **measured from counters**, never
  estimated afterwards (`src/sas/couts.py`; ENF-10). A short verified campaign
  measured **$0.06** (*measured*, `TEST-INSTRUCTIONS.md` §5).
* The §26.4 budget governance is a cost story too: N=2 during development,
  N=6 only for demonstrations, call budgets capped in code, the 200 $ credit
  budget (net of an 80 $ infrastructure reserve) buying **133 full mixed-mode
  homologations** (*calculated*, annexe G.6).