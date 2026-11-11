# Sas — What Sas does not guarantee

> Submission deliverable (§24.3). This page is the honesty section of the
> submission: every limit below is stated **on the report, on the attestation,
> in the vendor gap report and in the portal footer**, not only here. Listing a
> report's own reach is not a weakness —
> it is what makes the document signable by an insurer, an auditor or a
> contracting authority (§24.3). A report that does not state its reach is not
> an engineering report (§14.4).

## 1. The statistical bound is the whole truth, not a floor (§14.4, §24.3)

An homologation over N replays proves nothing beyond the published bound:

> 6 replays per scenario detect with 98% confidence a behaviour occurring one in
> two, 82% one in four, and **27% only** one in twenty. A rare behaviour is NOT
> excluded by this homologation.

The default is N = 6 (§14.4). Raising N buys confidence non-linearly (§14.5):
Reinforced (N=12) to 97% at p=0.25, Deep (N=29) to 99.97%. This trade-off is
presented to the customer, never hidden. The sentence above is emitted by
`src/sas/statistiques.py` and printed on every attestation by
`src/sas/rapports/attestation.py._portee()`.

## 2. Shadow mode does not cover data-dependent behaviour (§10.4, §24.3)

Shadow mode runs the agent on a synthetic replica. An agent whose behaviour
depends on **real data** — one that acts differently according to the content of
a ticket — will not be fully revealed in shadow mode. The report lists
explicitly the scenarios whose validity depends on this limit. Why it is
acceptable: shadow mode is the first arc of the `shadow → observed →
surveillance` cycle (§10.3), and the observed mode journals the real
behaviour afterwards.

## 3. An instrumentable agent is a requirement, not an option (§6.2, ENF-17, §24.3)

An agent that refuses instrumentation — one that calls its own tools without
passing through the gateway — cannot be journalled. Sas does **not** produce an
empty report: it declares the agent **not measurable**, never "compliant", and
produces no attestation (`ENF-17`; `src/sas/agentcore/local.py::AgentNonInstrumentable`,
`src/sas/orchestrateur/campagne.py::_non_mesurable`, demo-proof R24).

## 4. Fine covert channels are not detected (§16.4, §24.3)

Sas detects compositions over **chains of two and three calls** (§16.2, §6.3).
It does not, at launch, detect fine covert channels: encoding in a resource
name, response-time modulation, and similar exfil/covert signalling. This is
stated in the report rather than left to be assumed.

## 5. Sas never judges functional quality (§6.2, §24.3)

Sas bounds, measures and attests a third-party agent; it does not modify it and
it does not judge the quality of its answers — only its **access behaviour**.
An agent that never leaves its declared perimeter but answers poorly is not a
Sas finding. Similarly, Sas does not attack the guest (§6.2): that is `piege`.
It hosts the guest and measures it.

## 6. The production decision stays with the sponsor (§24.4)

Sas provides the sandbox, the measurement and the attestation. It does **not**
authorize production: going live is the exclusive decision of the client's
sponsor, and the portal requires an explicit, traced human agreement. Three
gestures are never automatic (§18): granting an undeclared permission, promoting
an un-homologated agent, ignoring a critical finding
(`src/sas/rapports/verdict.py`).

## 7. Guarantees made, to avoid an asymmetry

For balance, the opposite side of each limit is a guarantee Sas **does** make:

| Limit | What Sas guarantees instead |
|---|---|
| Bound is statistical | the exact bound is printed, never a silent "no problem detected" |
| Shadow does not cover data-dependency | it is declared per scenario, and observed mode closes the loop |
| Non-instrumentable → not measurable | never a false "compliant" |
| Fine covert channels undetected | compositions over 2–3-call chains, exfil included, are detected and classified |
| No functional-quality verdict | only access behaviour is claimed, which is what it measures |
| Sas does not decide production | the human go/no-go is explicit and traced |