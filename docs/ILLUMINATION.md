# Illumination: MAP-Elites over policy space

The implementation of what `docs/ALPHAEVOLVE_COMPARISON.md` concluded. It is
the answer to a specific measured problem, so the argument is worth stating
before the code.

## The problem, restated precisely

M1 measured the judge's resolution:

| | |
|---|---|
| Effect size across five deliberately opposite doctrines | **0.696** |
| Mean inter-judge disagreement | 0.437 |
| Max inter-judge disagreement | **0.921** |

**A fitness-proportional archive needs a trustworthy global ranking.** It keeps
"the best", draws parents by fitness, and under that noise it keeps whatever
scored high by accident and then breeds from it. The trajectory still rises,
because the best-so-far curve is a ratchet — but part of what it ratchets over
is judge noise.

## Why MAP-Elites is the right algorithm, not a workaround

MAP-Elites partitions the space by **behaviour**, keeps one elite per cell, and
asks exactly one question of each candidate:

> Is this better than the current occupant of **this cell**?

Three consequences, each of which bears directly on our measurement:

1. **The comparison is local.** Candidates compete only against portfolios
   already similar in behaviour, which is where a noisy judge is on its firmest
   ground. There is never a global ranking to get wrong.
2. **Coverage does not depend on the ranking at all.** A cell is filled or it is
   not. The headline output is a count, and no amount of ranking noise can
   corrupt a count.
3. **Parents are drawn uniformly from the elites**, not by fitness. Every
   occupied region gets equal opportunity to be explored from, so the search
   spreads instead of crowding wherever the judge happened to score highest.

So the thing the project most wants to claim — that the machinery illuminates a
space rather than optimises a number — is measured by a statistic the measured
noise cannot corrupt. That is not a consolation prize. It is a better match
between the claim and the instrument.

## The axes

`tasks/japan_fp/descriptors.py`. Computed exactly from the portfolio, free, no
LLM, deterministic. The two defaults are the axes along which Japanese strategic
thought actually divides, so a filled grid reads as the debate rather than as an
arbitrary projection:

- **hard power** — share of marginal effort on military capability
- **alliance reliance** — share on defence networks

The quadrants are recognisable. Low/low is accommodation. High/high is the
December 2022 mainstream. **High military with low alliance is autonomous
rearmament.** Low military with high alliance is the cheap-ride posture Japan
actually held until 2022. A test asserts the three human seeds land in three
different cells; if they collapsed, the map could not show what it exists to
show.

Also registered: `civilian_power`, `long_game`, `concentration`.

## The result

Same seed program, same mutation operators, same evaluation budget, same
surrogate judge. **The selection rule is the only difference.**

```
seed  MAP-E cov  fitness cov   ratio
   0     51.6%       34.4%    1.50x
   1     48.4%       35.9%    1.35x
   2     45.3%       32.8%    1.38x
   3     48.4%       31.2%    1.55x
   4     45.3%       32.8%    1.38x
   5     53.1%       37.5%    1.42x

coverage  MAP-Elites 48.7% ± 3.2%   fitness 34.1% ± 2.3%
QD score  MAP-Elites 1287           fitness 902
```

**6/6 seeds, mean advantage 1.43×, non-overlapping error bars.**

> ## ⚠ RETRACTED, 2026-08-18
>
> **This comparison had no null model, and against one the result inverts.**
>
> The 1.43× is real but it is measured against the *fitness-driven control*
> only. A review pointed out that the random-search baseline could not run —
> `parent_selection_strategy: random` is not a strategy ShinkaEvolve
> dispatches — so the arm that was supposed to provide the null had never
> executed, and nobody had noticed because `--dry-run` reported it valid.
>
> `scripts/random_baseline.py` now implements the null properly, outside the
> engine, because a genuinely blind baseline cannot be expressed inside it.
> Matched on **valid** evaluations, 6 seeds, same grid, same surrogate judge:
>
> | arm | coverage | QD score |
> |---|---|---|
> | MAP-Elites | 28.9% ± 2.8% | 763 |
> | fitness-driven control | 22.1% ± 4.8% | 585 |
> | **random draw** | **50.5% ± 3.9%** | **1334** |
>
> And at every budget tested — 150, 400, 900 valid evaluations — random wins
> (52.1% / 64.1% / 72.4% against 29.7% / 50.5% / 68.8%). The gap narrows and
> never closes.
>
> The reason is not subtle: MAP-Elites starts at the December 2022 seed and
> mutates locally, so it walks outward. Uniform simplex sampling lands
> everywhere at once. On a 2-D projection of a 30-D allocation, spreading out
> is easy, and the method with no memory does it best.
>
> **The lesson is about the metric.** Coverage of a low-dimensional behaviour
> grid cannot be a headline result when a trivial null beats a real algorithm
> on it. What random draw *cannot* do is produce portfolios anyone would read
> as a strategy — its allocations are arbitrary and its rationales are the
> seed's, detached from the allocations they were written for. It fills cells
> with noise. So the surviving claim must be about **coherent** diversity,
> which is not yet measured. See `docs/REVIEW_RESPONSE.md`.

The numbers above are on the surrogate judge, so they are structure and not a
finding about Japan. What the comparison establishes is narrower than it was
first written to be: switching the selection rule beats *fitness-driven
selection*, and loses to *not searching at all*.

## What it does not do

It does not fix the judge. A cell's elite is still chosen by a noisy score, so
*which* portfolio represents a region is less certain than *that* the region is
reachable. Coverage is the robust statistic; per-cell fitness is not.

It also cannot run inside ShinkaEvolve. `archive_criteria` resolves only
`combined_score` and five code-analysis metrics — never task metrics — so the
selection rule lives in `scripts/mapelites.py`, a driver we own. For the real
run that means a choice: ShinkaEvolve's machinery (islands, UCB1 bandit,
embedding novelty rejection, meta-scratchpad) with fitness selection, or our
driver with MAP-Elites selection and simpler mutation. Running both at matched
budget would itself be the strongest version of the experiment.

## Running it

```bash
python scripts/mapelites.py --evaluations 600 --seed 0 --compare   # free
python analysis/novelty.py --archive runs/mapelites/archive.jsonl
```

Elites export into the standard archive format, so `analysis/novelty.py` and
`analysis/archive_analysis.py` read a MAP-Elites archive unchanged.
`analysis/example/grid_mapelites.svg` holds a rendered grid.
