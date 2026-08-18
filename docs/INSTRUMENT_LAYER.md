# The instrument layer, and what it settles

Built 2026-08-18 in response to the second review, which named this the deeper
of two foundational errors:

> "economic size", "demographic resources 2050" and "cultural influence" are
> not actions Japan can select. They are outcomes produced by many instruments
> and external conditions.

Correct. The precise version is sharper, and it matters for the fix.

**The instruments were never missing. They were in the wrong layer.** The
December 2022 seed says "Rapidus, TSMC Kumamoto, chip subsidies", "43 trillion
yen procurement", "2% of GDP by 2027". Those are instruments. They lived in
free-text `how` strings that the validity gate only length-checked and that the
search could only rewrite as prose, while the structured, searched object was an
allocation over *outcomes*. So the LLM mutated numbers attached to outcomes and
wrote sentences about instruments — it was searching the layer Japan does not
control, and narrating the layer it does.

`tasks/japan_fp/instruments.py` promotes the instruments and makes the Lowy
allocation **derived**:

```
instruments (chosen)  →  exposure map (declared)  →  Lowy measures (judge scores)
```

21 instruments, each drawn from Japan's actual 2022–2026 debate and named so a
specialist can dispute it individually: `counterstrike`, `defence_exports`,
`economic_security_regime`, `semiconductor_policy`, `immigration_liberalisation`,
`china_engagement`, `collective_self_defence`, `nuclear_latency_posture`, and so
on. Each carries a fiscal cost in % of GDP, a political-capital cost, the legal
authority it needs (cabinet decision → Diet legislation → treaty →
constitutional amendment), a lead time, and a signed exposure vector onto the
eight Lowy measures.

The exposure vectors are **ours and declared as such**. They are coefficients of
a stated model, not measurements, and writing them down is the point: a reader
can attack any one of them by name instead of attacking a black box.

## What this unlocked

**Preserve–rewrite held.** `instruments.to_portfolio()` turns instrument
decisions into an ordinary `PolicyPortfolio`, so the judge, validity gate,
behaviour descriptors, MAP-Elites, archive adapter, novelty analysis, cache and
cost ledger all keep working untouched. Engine and steering replaced; chassis,
instrumentation and safety equipment kept. `to_dict()` omits the new key when
empty, so no cached judge call in the repository is invalidated.

**Feasibility became checkable — review point 3.** An allocation over outcomes
*cannot* be fiscally infeasible, because outcomes have no price. Instruments do.
The envelopes are calibrated against history, which is the only defensible way
to set them:

| | fiscal (% GDP/yr) | political capital |
|---|---|---|
| envelope | 2.20 | 3.00 |
| **December 2022, encoded** | **1.98** | **2.60** |

The real decision comes out **feasible**, because it happened, and **stretched**,
because it nearly broke the government that took it. An envelope that ruled the
actual historical decision infeasible would not be a strict model, it would be a
wrong one — the first draft said 1.60 for political capital and did exactly that.

**Prose can no longer drift from allocation**, because each dial's `how` is
generated from the instruments actually pointed at that measure, and the
defence-spending path is derived from the `defence_budget` intensity. In the old
representation those were independent and nothing checked them against
each other.

**The nuclear question became expressible.** In preflight 32086108143
`gpt-4.1-nano` tried to invent `military_capability.nuclear_deterrence` and had
its whole portfolio discarded. It was reaching for something real that Lowy's
ontology has no dial for. `nuclear_latency_posture` is now in the catalogue,
priced at 0.85 political capital with negative exposure to diplomatic influence
and defence networks.

## The finding: this layer contains a search problem, and the old one did not

| | outcome layer | instrument layer |
|---|---|---|
| feasible fraction of uniform draws | **100%** | **1.0%** |

In the old representation every point of the simplex was valid, which is exactly
why `scripts/random_baseline.py` beat MAP-Elites on coverage: with nothing to
satisfy, sampling everywhere at once is the optimal strategy. Instruments have
prices, so the feasible set is a thin region.

Matched at 100 valid evaluations, 4 seeds, surrogate judge:

| arm | coverage | draws needed | gate pass rate |
|---|---|---|---|
| MAP-Elites over instruments | 12.1% ± 1.5% | 110 | **91.1%** |
| random draw over instruments | 30.5% ± 2.7% | 6000 | **1.7%** |

Random still spreads better. It needs **55× more draws** to do it.

### Which arm "wins" depends entirely on what a draw costs

| framing | winner |
|---|---|
| matched on **valid evaluations** | random, 2.5× |
| matched on **cost**, if draws are LLM mutation calls | MAP-Elites, 4.9× |
| matched on **cost**, with a *programmatic* random sampler (draws free) | random, 3.2× |

The third row is the honest one, because a random sampler genuinely needs no LLM.
So:

> **Coverage is not a metric LLM-driven search can win.** Not on the outcome
> layer, not on the instrument layer. A free programmatic null spreads better,
> on both representations, and no amount of budget changes that.

This is now confirmed twice over, on two different genotypes. Any illumination
claim resting on coverage is dead, and `docs/ILLUMINATION.md` carries the
retraction.

### What the search *can* do, that random cannot

**91.1% versus 1.7%.** The evolutionary loop stays inside the feasible region;
random sampling flails outside it 98% of the time. That is a real, measured
competence, and it is about **feasibility**, not spread.

Which reframes the whole claim, and this time in a direction that survives:

> Diversity is free. Feasibility is not. The contribution of LLM-guided search
> here is not that it finds *more* of the policy space, but that what it finds
> is affordable, legally available and internally consistent — while a null
> model that covers more of the space produces almost nothing Japan could do.

That is a claim a free random sampler structurally cannot contest, it is
measurable with the machinery already built, and it is what the remaining budget
should be spent testing.

## What this does not fix

**Review point 1 stands untouched.** These are still static portfolios. A
portfolio takes no observations, holds no state, and makes no conditional
decisions. `collective_self_defence: 0.6` means "push this hard", not "push this
hard *if* US commitment weakens *and* fiscal stress stays below a threshold".
Instruments make the *action space* real; they do not make the *policy* adaptive.
That is the remaining foundational question and it is a genuine fork, not a
patch.
