# What AlphaEvolve's results imply for this project

Written 2026-08-17 after reading Novikov, Vũ, Eisenberger et al. (2025) via the
neuroevolution book's §13.3.4. ShinkaEvolve is the sample-efficient successor to
that architecture, so their results are the closest thing we have to a prior on
whether this design can work.

**Short version: one observation reframes the whole project, and one changed the
configuration today.**

---

## The observation that reframes it

Look at what AlphaEvolve actually succeeded on:

| Domain | How fitness was computed |
|---|---|
| Matrix multiplication (4×4 in 48 scalar multiplications, beating Strassen) | **Count the multiplications. Verify the identity algebraically.** |
| ~50 open maths problems — kissing numbers, Erdős minimum overlap | **Verify the construction.** A packing of 593 spheres either is valid or is not. |
| Google data-centre scheduling (0.7% fleet recovery) | **Measure stranded resources.** |
| Gemini kernels (23% speedup), FlashAttention (32%) | **Time the kernel.** |

Every one has a **cheap, exact, automatic verifier**. The evaluator runs code and
returns ground truth. In AlphaEvolve the LLM is the *mutation operator* — never
the *fitness function*.

**We inverted exactly that.** Our fitness is an LLM's opinion about a policy
portfolio. There is no ground truth to check it against, and M1 measured what
that costs: an effect size of 0.696 composite points across five deliberately
opposite doctrines, against inter-judge disagreement reaching 0.921.

That is not a defect peculiar to our rubric. It is the predictable consequence
of removing the one property every AlphaEvolve success depended on.

### Why this is good news for the paper

The natural reading of a −0.300 rank correlation is "our judge was bad". The
better reading, now that the comparison is explicit, is:

> **AlphaEvolve demonstrated the recipe where the evaluator is exact. This
> project tests whether the recipe survives when the evaluator is an LLM — and
> measures where it stops.**

That is a boundary condition on a celebrated result, not a failed replication of
it. It is also directly useful: every prospective application of LLM-driven
evolution to a domain without a verifier — policy, strategy, design, most of the
social sciences — inherits our number, not AlphaEvolve's.

The 75%-rediscovered / 20%-improved figures belong to ground-truth domains and
**must not be imported as expectations here.** Stating that plainly is part of
the contribution.

---

## What changed in the configuration today

The book notes AlphaEvolve "employs both **MAP-Elites** and **island-based
evolutionary strategies**" to promote quality *and* diversity. MAP-Elites is
literally an *illumination* algorithm — Mouret and Clune's term — and
illumination is precisely what Roland stated the goal to be: map a near-infinite
space, surface options nobody wrote down.

Checking our own configuration against that revealed a mismatch:

```yaml
archive_criteria:
  combined_score: 1.0      # what we had
```

ShinkaEvolve's `archive_criteria` is a **weighted, rank-normalised dict over
public metrics**, and its database docstring says it "supports MAP-Elites style
feature-based organization". With one criterion, the archive is a *leaderboard*:
it keeps whatever the judge ranked highest. That is the single quantity M1 showed
to be unreliable, and it is the opposite of illumination.

Worse, the natural MAP-Elites axes — effort share per Lowy measure — were being
written into **private** metrics, where the archive cannot see them at all.

### …and the fix I tried does not work, which is itself the finding

The obvious repair is to widen the criteria:

```yaml
archive_criteria:
  combined_score: 1.0
  worst_case_composite: 0.5      # survive the bad scenario
  effort_concentration: -0.3     # prefer spread allocations
```

**That silently does nothing, and worse than nothing.** Reading
`ProgramDatabase._get_criterion_value` shows it resolves exactly six names:
`combined_score`, plus `loc`, `lloc`, `complexity`, `maintainability` and
`nesting` from code-analysis metadata. **It never reads `public_metrics` at
all.** An unrecognised criterion hits

```python
logger.warning(f"Unknown archive criterion: {criterion}")
return 0.0
```

so both new terms would return a constant 0.0 for every program, contribute a
flat rank to the normalisation, and produce a log line nobody reads — all while
looking like diversity pressure in the config.

I wrote that config, and `tests/test_configs.py` caught it before it ran. The
test is now written the other way round: it pins the six names the engine can
actually resolve and fails on anything else.

So the docstring's "MAP-Elites style feature-based organization" refers to the
island and embedding-cluster machinery, **not** to arbitrary task descriptors.
MAP-Elites over *policy* behaviour space is not available through
`archive_criteria` in this release.

### What we do instead

Illumination happens **post hoc, in `analysis/novelty.py`**, over the finished
archive: distance from every human seed, greedy single-link families, the
novel-and-robust Pareto frontier, per-measure coverage. That is Mouret and
Clune's illumination as a *reading* of the archive rather than as a selection
rule — weaker, because it cannot steer the search, but honest and already built.

The behaviour descriptors stay public regardless of `archive_criteria`, because
`analysis/novelty.py` and `analysis/shinka_adapter.py` both read them and they
are what turn a finished archive into a map: `evaluate.py` publishes
`effort_<measure>` for all eight measures plus `effort_concentration`, a
Herfindahl index over the 30 dials where 1/30 ≈ 0.033 is perfectly even and 1.0
is everything on one dial.

**The in-selection version is future work**, and worth naming as such: steering
a search toward unoccupied policy regions needs either a ShinkaEvolve change or
a custom database, and would be a materially stronger design than reading
diversity off the end.

---

## Sample efficiency does not rescue us

ShinkaEvolve's advertised advantage over AlphaEvolve is sample efficiency:
comparable discoveries for far fewer evaluations. That is genuinely useful here,
where the working budget is $20 rather than a Google datacentre.

But it is **orthogonal to our binding constraint**. Sample efficiency helps when
each sample is informative. When inter-judge noise exceeds the effect size, more
efficient search converges *faster on noise*. Efficiency buys us more of the
space per dollar — which serves the illumination goal — and buys us nothing at
all toward reliable ranking.

Worth saying explicitly in the methods section, because a reader who knows
ShinkaEvolve will otherwise assume sample efficiency addresses the problem M1
found. It does not.

---

## What else is worth borrowing

**Exactness wherever it is available.** The deepest lesson from the table above
is not "LLM judges are bad" but "put the exact thing in the loop wherever one
exists". We already do this in two places and should keep pressing:

- the **validity gate** is exact, free, and rejects before any judge call — which
  is what makes a cheap mutation model affordable at all;
- the **behaviour descriptors** added today are exact and free.

Anything computable from the portfolio without asking an LLM belongs in the
public metrics, because it is signal that costs nothing and cannot be noisy.

**What we should not borrow: an invented objective.** It is tempting to add an
exact scalar — allocation coherence, feasibility margin — and optimise it because
it is reliable. That would violate the design's core commitment that the
objective is borrowed from Lowy and never invented (§2.1). Exact quantities enter
as *descriptors* and *gates*, never as fitness. The distinction is what keeps the
result interpretable.

**Diff-based edits.** AlphaEvolve's LLMs emit SEARCH/REPLACE blocks rather than
whole files, which is more sample-efficient and less error-prone on long
programs. Our configs already set `patch_types: [diff, full, cross]` with diff
weighted 0.6, so this is already in place — but it is worth watching in the pilot
whether diff edits preserve the shares-sum-to-1.0 invariant better or worse than
full rewrites. `scripts/mutation_smoke.py` currently tests full rewrites only.

---

## Summary of changes this analysis caused

| | |
|---|---|
| `evaluate.py` | publishes 8 `effort_<measure>` descriptors + `effort_concentration` |
| all 9 run configs | `archive_criteria` left at `combined_score` — the widening I tried is unresolvable and would have added constant-zero terms |
| `tests/test_configs.py` | now pins the six criterion names ShinkaEvolve can actually resolve |
| framing | the project tests a **boundary condition** of AlphaEvolve's recipe, not a weaker version of it |
| expectations | AlphaEvolve's 75%/20% belong to ground-truth domains and are not a prior for this one |
