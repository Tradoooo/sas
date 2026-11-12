# Sas — Regulatory evidence map

> This folder maps regulatory obligations onto **what the code actually does**,
> with the test that proves each line. It is an engineering document: an
> evidence map for a compliance officer, a DPO or an RSSI. It is **not** a legal
> opinion and it does not certify conformity.

## 1. What this folder is — and what it is not

Sas is not a conformity tool. Sas produces **evidence**: the observed envelope
of a third-party AI agent's behaviour, the gap between what it declared and what
it did, and the statistical scope of what a given number of replays can prove.

The reader of this folder is therefore a **responsible person** who owns the
obligation and who needs three things per obligation:

1. the obligation itself (article, article);
2. the Sas feature that produces the corresponding evidence;
3. the **proof** — a code path and a test name that can be run.

Where Sas produces no such evidence for an obligation, the obligation appears
in a **"Not covered"** section of the page. Nothing is quietly rounded up: a
table row without a real code path and a real test name would be a claim, not
evidence.

The legal qualification — does this map discharge the obligation, and is the
classification of the system right — belongs to a jurist. The specification says
so itself (`docs/fr/CAHIER-DES-CHARGES.md` §24 preamble, and §34 point 13:
validation of chapter 24 by a lawyer is due "before any real deployment",
explicitly out of scope for the hackathon). The pages below are written on the
same footing: `docs/ECHECS.md` records what has **not** been achieved, including
that legal review.

## 2. The four pages

| Page | Regulation | What it maps |
|---|---|---|
| [`AI-ACT.md`](AI-ACT.md) | Regulation (EU) 2024/1689 (AI Act) | Logging, transparency to the deployer, human oversight, accuracy/robustness/cybersecurity, deployer obligations, risk management, data governance, post-market monitoring |
| [`NIS2-DORA.md`](NIS2-DORA.md) | Directive (EU) 2022/2555 (NIS2) and Regulation (EU) 2022/2554 (DORA) | Supply-chain security, third-party risk management, information register, test strategy, incident handling, exit |
| [`RGPD.md`](RGPD.md) | Regulation (EU) 2016/679 (GDPR), spec §24.1 and §25 | Sub-processor qualification, data minimisation, retention and purge, absence of personal data, register of sub-processors |
| this page | — | How to read the three pages above |

Two documents sit next to this folder and are part of the same discipline:

- [`docs/ECHECS.md`](../ECHECS.md) — what we did **not** manage to do. Read it
  before reading the tables: a failures page that lies is worse than no
  failures page.
- [`docs/KPI-MESURES.md`](../KPI-MESURES.md) — the eight KPIs of §5.2, with the
  target and the **measured** value, and the command that produces each one.

## 3. How to read a row

Every obligation is written as a four-column table:

| Obligation (article) | What Sas provides | Where in the code | How it is proven |
|---|---|---|---|
| Automatic logging of events (Art. 12) | Complete, chained, immutable journal, denials included | `src/sas/journal/chaine.py` | `test_R8_couverture_du_journal_a_cent_pourcent`, `test_R9_une_rupture_de_chaine_est_detectee` |

- **Where in the code** is a real path in this repository. It exists: the guard
  test resolves it against the tree.
- **How it is proven** is the real name of a test in `tests/`. The guard test
  greps for `def <name>` and fails if the name is invented.
- A row that cannot fill the last two columns goes to the **"Not covered"**
  section of the page. There is no third column of confidence.

## 4. How to verify this folder yourself

The folder is guarded by a test, not by good intentions:

```bash
PYTHONPATH=src python3 -m pytest tests/unit/docs/test_conformite.py -q
```

It checks that:

- every file path cited in the four pages exists in the tree;
- every test name cited in the four pages exists in `tests/`;
- `docs/ECHECS.md` still carries its nine mandatory entries;
- no compliance page contains a secret-looking string or an internal IP.

The same checks can be run by hand:

```bash
grep -o '`[a-zA-Z0-9_./-]*\.\(py\|yaml\|json\|mjs\|md\)`' docs/conformite/*.md | sort -u
grep -rn "def test_" tests/ | grep -c ""
```

## 5. The three rules that make the evidence defensible

1. **The rules are applied by the gateway, not by the prompt.** The guest agent
   never receives its limits as prose: it suffers them, at Policy level, before
   the tool runs (`src/sas/agentcore/politique_manifeste.py`,
   `src/sas/agentcore/passerelle.py`).
2. **The model proposes, the code decides.** No severity, no classification, no
   amount and no verdict is ever produced by a model
   (`src/sas/analyseur/classification.py`). A disagreement with the model goes
   to human review and is recorded as a quality measure.
3. **Every deliverable lists its own limits.** The statistical bound, the
   shadow-mode blind spot, the agent that is declared *not measurable*, the fine
   covert channels that are not detected: they are printed on the report and the
   attestation (`docs/LIMITES.md`, `src/sas/rapports/rapport.py`).

## 6. Language

These pages are written in English, like the other submission deliverables
(`docs/fr/CAHIER-DES-CHARGES.md` preamble). Two documents that are meant to
circulate on their own, with clients, are bilingual:

- [`docs/FORMAT-MANIFESTE.fr.md`](../FORMAT-MANIFESTE.fr.md) /
  [`docs/FORMAT-MANIFESTE.en.md`](../FORMAT-MANIFESTE.en.md)
- [`docs/GRILLE-CLASSIFICATION.fr.md`](../GRILLE-CLASSIFICATION.fr.md) /
  [`docs/GRILLE-CLASSIFICATION.en.md`](../GRILLE-CLASSIFICATION.en.md)
