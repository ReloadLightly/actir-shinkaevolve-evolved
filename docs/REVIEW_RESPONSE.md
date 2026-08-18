# Response to the 2026-08-18 review

The review read the repository at `20ca8b4`. **All eight criticisms are fair.**
Two are worse than stated, and acting on one of them overturned this project's
headline claim.

I verified each load-bearing factual claim against the source before acting,
rather than accepting them because they were confidently expressed. Every
verification agreed with the review.

Nothing below is a rebuttal. The table says where each point stands.

| # | Criticism | Verdict | Status |
|---|---|---|---|
| — | Green status suppressed probe failures | **Fair** | Fixed |
| 1 | Not an adaptive policy program | **Fair** | Claim narrowed; not fixable at this scope |
| 2 | Actions and outcomes conflated; Lowy projection is ours, not Lowy's | **Fair** | Documented as a modelling assumption |
| 3 | Validity gate proves formatting, not coherence | **Fair** | "Coherent" withdrawn |
| 4 | Performance function cannot resolve small improvements | **Fair** | Quantified; repeats + significance margin added |
| 5 | The paid workflow does not run MAP-Elites | **Fair, fatal** | Fixed — and the result did not survive |
| 6 | The baseline cannot run | **Fair, understated** | Three configs invalid, not one; real baseline built |
| 7 | The $20 ceiling is not fail-closed | **Fair** | Judge ceiling now enforced against the ledger |
| 8 | The experiment is still DRAFT | **Fair** | A scored run now refuses to start |

---

## The finding that came out of acting on #6

This matters more than the rest, so it goes first.

The review said the random-search baseline could not run. It was right, and for
a second reason it did not mention: even with the enum repaired, the config kept
`use_text_feedback: true` and the meta recommender, so the "unguided" arm would
still have been steered by the judge's mechanism sentences.

The deeper problem is that **a blind baseline cannot be expressed in
ShinkaEvolve at all.** The engine exists to select parents and feed back
critique; every knob that turns those off still leaves an evolutionary loop. So
`scripts/random_baseline.py` implements the null model outside the engine: draw
a portfolio from the simplex, score it, keep the record. No parents, no lineage,
no feedback, nothing carried between draws.

Then I ran the comparison that had never been run. Matched on **valid**
evaluations, 6 seeds, surrogate judge, same 64-cell grid:

| arm | coverage | QD score |
|---|---|---|
| MAP-Elites | 28.9% ± 2.8% | 763 |
| fitness-driven control | 22.1% ± 4.8% | 585 |
| **random draw** | **50.5% ± 3.9%** | **1334** |

And across budgets:

| valid evaluations | MAP-Elites | random draw |
|---|---|---|
| 150 | 29.7% ± 3.1% | **52.1% ± 3.9%** |
| 400 | 50.5% ± 9.4% | **64.1% ± 1.6%** |
| 900 | 68.8% ± 5.6% | **72.4% ± 0.9%** |

**Random sampling beats MAP-Elites on coverage at every budget tested.** The gap
narrows — 22.4 points, then 13.6, then 3.6 — but never closes.

### The claim this retracts

PR #6 said, and `docs/ILLUMINATION.md` said:

> coverage MAP-Elites 48.7% ± 3.2% · fitness-driven 34.1% ± 2.3% — 6/6 seeds,
> mean 1.43×

That number is real but the comparison was **against the fitness-driven control
only**. There was no true null model, because the config that should have
provided one could not run. Set against a null, the result inverts. **The 1.43×
claim is withdrawn.**

### Why random wins, and what survives

The reason is not subtle. MAP-Elites starts at the December 2022 seed and
mutates locally, so it walks outward through the space. Uniform simplex sampling
lands everywhere immediately. On a two-dimensional projection of a
thirty-dimensional allocation, spreading out is easy, and a method with no
memory does it best.

The honest conclusion is about the **metric**, not only the algorithm:

> Coverage of a low-dimensional behaviour grid is not a defensible headline
> result, because a trivial null model beats a real algorithm on it.

What random draw cannot do is produce portfolios anyone would read as a
strategy. Its allocations are arbitrary, and — since it must not call an LLM,
that being the whole point — its rationales are the seed's, now detached from
the allocations they were written for. It fills cells with noise.

So the surviving claim has to be about **coherent** diversity: portfolios that
occupy distinct regions of policy space *and* read as arguable strategies with
mechanism-linked rationales. That is a claim about a property random sampling
structurally cannot have, and it is not yet measured. Measuring it is the real
remaining work, and it is named as such rather than assumed.

---

## What was fixed

**Fail-closed everywhere it was fail-open.** Probe scripts exit non-zero and a
verdict step fails the job, so a green run means something. Three configs named
parent-selection strategies ShinkaEvolve does not dispatch — the review found
`random`; `best` and `hill_climbing` were also invalid, and all three would have
raised `ValueError` mid-run after spending. `--dry-run` had reported them valid
because the name is only resolved when a parent is first sampled, so the enum is
now checked before launch, against the pinned commit
`6ec47cdddf2f7aea64848d872b8d9a1f7ce17bcd`.

**The judge now has a ceiling.** `max_api_costs` meters only ShinkaEvolve's own
calls; the judge is an external client the engine never sees, at three calls per
candidate. Every config declares `judge_max_cost_usd` and `run_max_cost_usd`,
and `JudgeClient` enforces the judge ceiling against the **ledger** before each
uncached call — the ledger, not an in-process counter, because `evaluate.py`
runs as a subprocess per candidate and an in-memory total would reset every
evaluation and enforce nothing.

The test suite had the same blind spot: every budget test read `max_api_costs`,
so it was policing about half the real spend. With the judge counted, the old
per-arm numbers totalled **$54 against a $50 hard ceiling**. Per-arm all-in is
now $6.50: phase 1 = $19.00 of $20 working, phase 2 = $45.00 of $50 hard.

**A DRAFT rubric can no longer start a scored run.** `FROZEN.json` had said
"NEEDS ROLAND'S RE-APPROVAL before any scored run" since revision 2 and nothing
read it.

**MAP-Elites can now use the real judge**, with `--judge real` fail-closed
behind `--confirm-spend`, an armed judge config, and a mandatory ceiling.
Provenance is stamped from the backend that actually scored, instead of a
hardcoded `surrogate: True` that would have mislabelled every real record.

**Repeated judging.** `--repeats n` makes the score a mean with a reported
standard error, bypassing the cache so the draws are genuinely independent — a
cache hit would return the same number n times and manufacture an SEM of exactly
zero, the most dangerous possible answer. And `Grid.consider` now requires a
challenger to beat the incumbent by more than the noise: the pooled standard
error when measured, otherwise the judge's measured 0.17 composite self-noise.
Displacements inside the noise are counted and reported rather than silently
applied.

**Arms are matched on valid evaluations**, not dollars or generations. A dollar
buys a different number of scored candidates depending on which model UCB1
favours, and a generation may produce nothing the gate accepts.

---

## What is not fixed, and cannot be at this scope

**#1, adaptivity.** The genotype is a static allocation. It takes no
observations, holds no state, and makes no conditional decisions, so "improves
over time" means later generations score higher with the same judge — not that
Japanese policy adapts across 2026–2030. Making it adaptive means a different
genotype (a policy *function*, not a policy *vector*) and a different evaluator.
That is a different project. The writeup must say "portfolio", never "strategy
that learns".

**#2, actions versus outcomes.** Effort is allocated directly to Lowy
submeasures, which are measured capabilities and outcomes, not instruments; the
instruments live in the free-text `how` strings the gate only length-checks.
And the review's sharper point stands: Lowy's Index is a *relative*,
distance-to-frontier comparison across 27 countries and 131 indicators, so
**adding an LLM-estimated delta to Japan's fixed 2025 score while holding every
other country implicit is our model, not Lowy's published procedure.** Only the
weights are genuinely Lowy's. This is now stated as a modelling assumption
wherever a projected composite appears. "Projected Japan's Lowy score" is not a
claim this design can make.

**#3, coherence.** The gate checks dial names, arithmetic, text lengths, phase
ordering and a defence-spending bound. It says nothing about fiscal
feasibility, legal authority, instrument conflict, implementation capacity,
domestic politics or causal consistency. Gate-valid means **well-formed**, and
the word "coherent" is withdrawn.

**#4/#9, uncertainty.** The machinery for repeats and significance now exists
and is tested. It has not been *run* against the real judge, so no reported
number yet carries a standard error.

---

## The claim this repository can support

Not "ShinkaEvolve discovered Japan's superior novel foreign policy", and not
"projected Japan's Lowy score". Something narrower, and true:

> An LLM-driven evolutionary loop over a structured policy genotype produces
> well-formed, behaviourally distinct foreign-policy portfolios under an
> LLM-estimated objective — and the evaluator's own uncertainty (0.17 composite
> points of self-disagreement on identical input, against 0.696 of effect across
> five opposite doctrines) sets a measurable floor on which comparisons that
> loop can support. It resolves doctrines, not increments.

With the coverage result above attached as a boundary condition: on a
low-dimensional behaviour grid, random sampling is a stronger illumination
baseline than the algorithm, so coverage alone cannot carry the argument.
