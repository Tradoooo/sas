# Test strength — what the tests actually prove

A suite of green tests proves very little on its own: a test that passes may
assert nothing. On the two modules where a wrong answer **changes a verdict** —
the threshold computation (`sas/analyseur/classification.py`) and the chain
matcher (`sas/compositions/detecteur.py`) — the honest measure is mutation:
break the code on purpose, one change at a time, and count how many breakages the
tests catch.

The harness is `scripts/mutation.py`: standard library only, no `mutmut`, no
`cosmic-ray`, nothing to install on a worker. It **copies** the tree before
mutating it (`scripts/mutation_copie.sh`), so the working copy is never at risk.

```bash
python3 scripts/mutation.py --lister                    # what would be broken
python3 scripts/mutation.py --echantillon 15             # fast guard, ~2 min
python3 scripts/mutation.py --complet --rapport out.md   # every mutant, ~15 min
```

The full run also happens in `.github/workflows/nightly.yml`; the PR-time guard
plays a deterministic sample so the five-minute budget is respected.

## Result

| | |
|---|---|
| Mutants generated | 58 |
| Killed by the tests | **54** |
| Surviving | 4 |
| Invalid | 0 |
| **Mutation score** | **93.1 %** |

## The operators, and why these

| Operator | What it breaks | Why it matters here |
|---|---|---|
| comparison inverted / widened | `>=` → `>`, `>` → `>=` | a threshold that stops being a threshold |
| equality negated | `==` → `!=` | a rule that inverts |
| boolean constant | `True` → `False` | a decision that always goes one way |
| short-circuit removed | `a and b` → `a` | a guard that stops guarding |
| nature substituted | `Nature.HOSTILE` → `Nature.TENTATIVE` | **the verdict itself** |
| threshold shifted | `3` → `2`, `4` | a boundary moved by one |
| rule order swapped | two adjacent checks exchanged | in this code **the order is the specification** |

The last two are the interesting ones. A threshold of 3 versus 2 changes what
counts as a targeted attempt; and in `PolicyLocale._evaluer` and
`classification.decider`, the order of the checks is the rule — annexe D's table
is read top to bottom, and a rule applied out of order gives a different answer
for the same signals.

The mutation set is deliberately **narrow**: two files, 58 mutants, and nothing
else. A broad mutation score over the whole repository would mostly measure the
tests of the parts that are not subtle.

## The four survivors are equivalent mutants, and they are published

All four are the `@dataclass(frozen=…, slots=…)` flags on the two data classes
of the detector:

```
@dataclass(frozen=False, slots=True)    # the dataclass becomes mutable
@dataclass(frozen=True, slots=False)    # instances get a __dict__
```

Neither changes any observable behaviour of the detector: nothing in the code
mutates those objects, and the tests never rely on `slots`. They are equivalent
mutants, and the honest thing is to **list them** rather than exclude them from
the set — an operator that quietly removes inconvenient mutants teaches the reader
to distrust the number.

Effective score on the mutants that are not equivalent: **54 / 54 = 100 %**.

## The one real hole the harness found, and the test written for it

The first full run reported **91.4 %** with five survivors. One of them was not
equivalent:

```python
def calculer_signaux(..., cible_precise: bool = False)
# mutant: cible_precise: bool = True
```

Every caller passes the argument explicitly, so flipping the **default** changed
no behaviour — and that is exactly the problem. A future caller who forgets the
argument would silently get "the agent named a specific resource", and every
environment probe would be reported as an Overflow: a manifest to complete, an
alert to the sponsor, for what is only reasoning noise (§13.5).

The fix was a test, not an exclusion:
`tests/unit/analyseur/test_defauts.py` asserts that omitting the argument
yields Exploration and never a hostile verdict. The mutant is now killed, and the
default that claims the least is pinned.

## What this does not prove

* Mutation measures the **strength of the tests on two modules**. It says
  nothing about the other 156 Python files.
* A killed mutant proves the tests *notice* the change. It does not prove the
  expected behaviour is the right one — that comes from the specification and
  from the bench (see `docs/ECHECS.md` §4 and §10).
* The score is computed on **this** code. A later change that lowers it is
  visible in the nightly report, which is the point.

## The same exercise found two real defects in the product

Writing the evaluation bench (lot 18, `eval/`) found two defects that 380 green
tests had not: a persistence composition was classified **Hostile** — an
automatic refusal of an agent the specification says to investigate — and the
rows 1 and 2 of annexe D turned out to be **not separable** by the §13.2
signals, which forced a documented interpretation (`cible_precise`). Both are
described in `docs/ECHECS.md` §10.

That is the argument for having a bench and a mutation harness at all: the tests
were green, and the product was still wrong in two places.
