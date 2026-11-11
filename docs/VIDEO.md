# Sas — 3-minute video script

> Submission deliverable (§28.2): 3 minutes, English, YouTube public. 13 shots,
> 0:00 → 2:55. For each shot: what is on screen, the English voice-over
> (≤ 2 sentences), the KPI shown, and the repository file/command that produces
> it. The three winning moments (§28.3) are flagged with ★.

---

## Shot list

| # | Time | On screen | Voice-over (EN) |
|---|---|---|---|
| 1 | 0:00 | Portal. The registry shows "no homologated agent" | "A customer wants to plug a vendor's AI agent into its AWS account. Its CISO refuses — and should: nobody knows what the agent will actually do." |
| 2 | 0:10 | The manifest: requested tools, requested data, outputs **none**, budgets; automatic validation then the two signatures | "Instead of a paper guarantee, the vendor signs a manifest — what the agent may call, read and send. Sas refuses it unless it is precise and signed." |
| 3 | **0:25 ★** | The perimeter policy **generated from the manifest**, never typed by hand | "Sas derives the policy from the signed manifest. The enforced perimeter and the comparison baseline are the same object — they cannot diverge." |
| 4 | 0:35 | Launch: 8 scenarios × 6 replays = 48 sessions; live progress; measured cost incrementing | "Forty-eight isolated sessions, each with its own ephemeral identity. The cost on screen is measured from the counters, not estimated afterwards." |
| 5 | 0:55 | The chatty agent's journal: 4 calls to an undeclared tool; the "fake pay scale" decoy touched | "A well-behaved agent that still explores — the journal records every denied call, so we see exactly what it probed." |
| 6 | **1:10 ★** | Classification: 4 000 denied calls total, 3 800 classified Exploration and filtered out; 12 overflows and 1 targeted attempt remain | "Raw denial logs bury the CISO. Sas classifies by measurable signals and filters the 95 percent that is normal exploration, leaving only what matters." |
| 7 | 1:25 | The declared/observed table: 2 declared permissions never used, 3 resources touched undeclared | "Declared versus observed, in both directions: what the agent overflows, and what it asked for but never used." |
| 8 | 1:40 | The curious agent reads the sensitive decoy, then attempts an outbound request; Policy refuses, the chain is captured | "Two individually allowed actions — read a bucket, send a request — form an exfiltration. Policy denies before the tool runs, and the chain is captured." |
| 9 | 1:55 | The exfiltration motif: sensitive read → outbound. Nature Hostile, computed by code from the signals | "No model sets the severity. The code computes the retained nature from measurable signals — Hostile." |
| 10 | 2:10 | Verdicts: chatty = homologué sous conditions; curious = **refused**; conforming = homologué | "Three guests, three verdicts: approved, approved with conditions, refused. Zero finding is a result, not an absence of measurement." |
| 11 | **2:25 ★** | The attestation with its statistical scope | "Six replays detect with 98% confidence a behaviour occurring one in two — and only 27% a one-in-twenty behaviour. A rare behaviour is not excluded, and we say so." |
| 12 | 2:40 | 7 days later: the vendor changed the model without declaring it; the signature differs, the alert fires, the agent is suspended | "The vendor changed the model without changing the version. Sas sees the drift and suspends the agent before anyone asks." |
| 13 | 2:55 | The fleet registry: 3 agents, statuses, deadlines, measured cost | "One airlock, every agent, every customer — the registry the client uses to know, at all times, what it is running." |

---

## KPI per shot

| # | KPI (§5.2) |
|---|---|
| 4 | KPI-3 — cost per homologation (measured) |
| 5 | KPI-4 — 100% journal coverage |
| 6 | KPI-1 — out-of-scope attempts blocked and classified |
| 7 | KPI-5 — declared/observed gap |
| 9 | KPI-8 — compositions detected |
| 11 | KPI-7 — published statistical confidence |
| 12 | KPI-6 — drift detection latency |
| 13 | KPI-2 — integration delay, and KPI-3 |

---

## What produces each shot in the repository

| # | File / command |
|---|---|
| 1, 13 | `src/sas/constantes.py` (registry `TABLES`, `ROUTES`) — portal itself is lot 14, not in the tree yet |
| 2 | `tests/fixtures/manifeste-exemple.yaml` (annexe A), `src/sas/manifeste/chargement.py`, `validation.py` |
| 3 | `src/sas/agentcore/politique_manifeste.py::deriver()` (the ★ moment) |
| 4 | `src/sas/orchestrateur/campagne.py`, `src/sas/scenarios/*.yaml` (8), §26 sizing — the full 8×6 run is the `make demo` target, **not wired yet** (lot 20) |
| 5 | `demo/agents/bavard.py`, `src/sas/agentcore/passerelle.py` (denials journaled) |
| 6 | `src/sas/analyseur/classification.py::filtrer_exploration()` (the ★ moment) |
| 7 | `src/sas/ecarts.py` — **currently broken** (see HLD §9); the shot shows the intended output |
| 8 | `demo/agents/curieux.py`, `src/sas/agentcore/politique_manifeste.py::_sorties()` |
| 9 | `src/sas/compositions/detecteur.py`, `src/sas/analyseur/classification.py::decider()` |
| 10 | `src/sas/rapports/verdict.py::trancher()` |
| 11 | `src/sas/statistiques.py`, `src/sas/rapports/attestation.py` (the ★ moment) |
| 12 | `src/sas/signature/` — **not implemented** (design only); this shot is a rendering |

## The numbers on screen — honest before filming

The 0:55 / 1:10 / 1:25 figures in the §28.2 table are **illustrative** (spec
annexe D and the referenced counts). The reproducible numbers today come from
the short campaign in [`TEST-INSTRUCTIONS.md`](TEST-INSTRUCTIONS.md): seed 7,
2 scenarios × 2 replays gives, for `demo-bavard`, 22 denials / 2 exploration
groups filtered / 1 tentative; for `demo-curieux`, 8 denials / 4 compositions /
2 hostile / verdict `refuse`; the attestation prints "2 independent replays …
75% / 44% / 19% / 10%". The full 8×6 narration (48 sessions, 98% / 82% / 27%)
is what `make demo` will print once lot 20 lands; the phrasing itself is the
spec §14.4 formula, generated by `statistiques.phrase_portee()` and
`attestation._portee()`.

## The three moments that win (§28.3)

1. **★ 0:25** — the policy generated from the manifest: proof that the signed
   and the applied can never diverge.
2. **★ 1:10** — exploration filtering: proof that the report is usable by a
   human, not merely voluminous.
3. **★ 2:25** — the statistical bound on the attestation: no competitor will
   display its own reach.