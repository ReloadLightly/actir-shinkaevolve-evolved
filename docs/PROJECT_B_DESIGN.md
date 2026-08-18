# Project B: adaptive foreign-policy programs under partial observation

Decision, 2026-08-19: Project A is insufficient. Build toward the claim that
motivated choosing ShinkaEvolve in the first place.

> **ShinkaEvolve discovers executable, observation-dependent Japanese
> foreign-policy programs that outperform the December 2022 baseline and simpler
> search methods under held-out uncertain worlds.**

This document is the design. It is written to be executable by someone who has
not read the rest of the repository, because the parts that matter are new.

---

## 1. The architecture inverts, and that is the point

The single most important consequence of Project B is not adaptivity. It is
**where the LLM sits.**

M1 measured this project's central weakness: the judge's effect across five
opposite doctrines was 0.696 composite points against 0.921 of inter-judge
disagreement and 0.17 of *self*-disagreement on byte-identical input. Signal
barely above noise. `docs/ALPHAEVOLVE_COMPARISON.md` traced why — every
AlphaEvolve success had a **cheap exact verifier**, and we had inverted that by
making an LLM's opinion the fitness function.

Project A could only mitigate this by averaging. Project B fixes it structurally:

| | Project A (current) | **Project B** |
|---|---|---|
| fitness | LLM judge, noisy, $0.0069/candidate | **exact simulator, deterministic, free** |
| mutation operator | LLM | LLM |
| LLM judge's role | the objective | **validation + qualitative corpus** |

That is AlphaEvolve's actual recipe, applied for the first time in this project.
It makes the search cheaper *and* more reliable, and it turns the M1 finding from
an embarrassment into a design rationale you can state in the methods section:
*we measured that an LLM judge cannot resolve increments, so we moved it out of
the inner loop.*

The judge does not disappear. It does two jobs it is actually good at:

1. **Plausibility audit.** Show it simulated trajectories and ask whether the
   world's behaviour is credible. An LLM is a reasonable critic of "would China
   really respond that way" even when it is a poor cardinal scorer.
2. **The mechanism corpus.** The qualitative output — "if Japan does X under
   condition Y then Z because W" — remains the humanly interesting product.

---

## 2. The genotype becomes a function, not a vector

Today: `build_policy() -> PolicyPortfolio`, a static allocation, evaluated once.

Project B:

```python
# EVOLVE-BLOCK-START
def decide(obs: Observation, memory: Memory) -> Decision:
    """Called once per year, 2026 through 2030.

    obs    - what Japan can see this year, noisily and with lag
    memory - whatever this policy chose to remember from previous years
    returns - changes to instrument intensities, within inertia and budget
    """
```

The program is now run **five times per world, across many worlds**. It may
branch, hold state, infer, and commit conditionally. `collective_self_defence:
0.6` becomes something like:

```python
if memory.us_commitment_trend() < -0.05 and obs.fiscal_stress < 0.7:
    push("collective_self_defence", +0.15)
```

That is the difference between a plan and a policy, and it is the whole claim.

---

## 3. The world model

This is the new machinery, and it is most of the work. `tasks/japan_fp/world.py`.

### 3.1 What a "world" is

A world is a **draw from a parameter distribution**, not one of the three prose
vignettes. The existing `S1/S2/S3` scenarios become three named *regions* of that
space, kept for interpretation and for continuity with M1, but the search sees
sampled worlds.

Hidden parameters, fixed per world and **never observed by the policy**:

| parameter | meaning | why it matters |
|---|---|---|
| `us_decline_rate` | is US commitment eroding structurally or cyclically | the central strategic uncertainty; must be *inferred* |
| `security_dilemma_strength` | how much China's coercion responds to Japan's buildup | decides whether rearmament is self-defeating |
| `crisis_hazard` | annual probability of a Taiwan contingency | decides how much hedging is worth |
| `china_assertiveness` | baseline coercion independent of Japan | separates provoked from unprovoked pressure |
| `economic_shock_sigma` | volatility of the fiscal environment | decides how much slack to hold |

**These are the held-out dimension.** Train on one region, test on another.

### 3.2 State

*Japan (fully observed by the policy):*
`capability[8]` — the Lowy measures, starting from the real 2025 baseline;
`instrument_level[21]` — current intensity of each catalogue instrument;
`fiscal_space`; `political_capital`.

*World (partially observed):*
`us_commitment`, `china_coercion`, `partner_alignment`, `economic_conditions`,
`crisis_active`.

### 3.3 The annual step

1. Policy observes: own state exactly; world state with **noise and one-year
   lag**; hidden parameters never.
2. Policy returns instrument-intensity changes.
3. **Inertia**: no instrument may move more than a per-instrument cap per year.
   Procurement and legislation cannot swing overnight, and this is what makes
   early commitment costly to reverse — the property that makes adaptivity
   worth anything.
4. Costs deducted. Fiscal and political envelopes from `instruments.py` become
   *per-period* budgets with limited carryover.
5. Capabilities update from instrument exposure, **with lead-time lag** — the
   `lead_time_years` field in the catalogue finally does work.
6. **Counterparts respond.** This is the part that makes it a strategic problem
   rather than an open-loop control problem:
   - `china_coercion` rises with Japan's military buildup scaled by
     `security_dilemma_strength`, falls with `china_engagement`;
   - `us_commitment` rises with burden-sharing (`host_nation_support`,
     `defence_budget`) and falls at `us_decline_rate`;
   - `partner_alignment` rises with `official_security_assistance` and
     `minilateral_formats`;
   - `crisis_hazard` is modulated by the coercion/commitment gap.
7. Exogenous shocks drawn from `economic_shock_sigma`.

### 3.4 Objective

Lowy composite at 2030 via the existing `lowy.py`, reported as **mean across
worlds and worst case across worlds**, exactly as the current three-scenario
battery does. Robustness is a first-class output, not a footnote.

### 3.5 The honest caveat, stated once and prominently

**The dynamics are ours.** This is a simulation study, and its result is "search
finds good policies in *our model* of East Asian strategic interaction". The
defences are the same discipline already applied to the instrument exposure
vectors: every coefficient declared in one place, sourced where a source exists,
sensitivity-analysed, and audited by the LLM judge against the literature. State
it in the abstract, not the limitations section.

---

## 4. The gate that decides whether Project B exists — and it is free

**Do not write a line of LLM integration until this passes.**

A world that does not reward adaptivity contains no experiment, however elegant
the simulator. Before any spending:

1. Optimise the **best constant policy** — a fixed instrument vector, no
   observation — over the training worlds, with a free numeric optimiser (CMA-ES,
   or random search plus hill-climbing; no LLM).
2. Optimise the **best simple adaptive policy** over a small parameterised class
   (say a handful of threshold rules on observed trends) over the same worlds.
3. Evaluate both on **held-out** worlds.

**The gate:** adaptive must beat best-constant on held-out worlds by more than
seed-to-seed noise. Report the effect size and the noise band, as
`docs/PREFLIGHT_FINDINGS.md` does for the judge.

Three outcomes:

| result | meaning | action |
|---|---|---|
| adaptive ≫ constant | the world contains a real search problem | proceed |
| adaptive ≈ constant | uncertainty resolves too slowly, or inertia is too weak | **redesign the world**, do not proceed |
| brute force finds the optimum immediately | the space is too small to need evolution | enlarge the instrument set or the horizon |

This is the qualification step the second review asked for, and it costs
**nothing**. It is also the step most likely to be skipped under deadline
pressure, which is why it is written here in its own section.

---

## 5. Experimental design

Only after §4 passes.

**Arms**, all matched on valid evaluations:

| arm | what it tests |
|---|---|
| ShinkaEvolve + LLM mutation over adaptive programs | the claim |
| best constant policy (numerically optimised) | **does adaptivity buy anything?** |
| random program draw | is search doing work? |
| hill-climbing over programs | is *evolutionary* search doing work? |
| December 2022 encoded as a constant policy | the human baseline |

The comparison that carries the paper is **adaptive vs best-constant on held-out
worlds**. If the evolved program does not beat a well-optimised constant policy,
adaptivity bought nothing and the honest result is that finding — which is still
publishable, and is the same shape as the coverage retraction: a claim that met a
real baseline and lost.

**Three seeds per arm.** Report mean, worst case, and the seed band. Any
difference smaller than the seed band is not a result.

**Held-out generalisation** is the headline metric, not training performance.
A static plan tuned to the training worlds will look excellent there. That gap
*is* the experiment.

---

## 6. What carries over unchanged

The apparatus survives, which is why this is a rewrite and not a restart:

| kept | why it still fits |
|---|---|
| `instruments.py` — 21 instruments, costs, legal gates, lead times, exposure | **This is Project B's action space.** Built yesterday for A; it is worth more here. `lead_time_years` finally does work. |
| `lowy.py` | outcome measurement, unchanged |
| fiscal and political envelopes | become per-period budgets |
| `coherence_report` | becomes a per-step action-legality check |
| ShinkaEvolve launcher, provenance, manifests, engine pin | unchanged |
| cost ledger, cache, judge budget enforcement | unchanged, and now barely exercised |
| MAP-Elites, descriptors | descriptors become **behavioural**: how reactive is this policy, what does it do under fiscal stress, does it hedge or commit |
| 347 tests, CI, fail-closed gates | unchanged |
| `docs/PREFLIGHT_FINDINGS.md` | its measurement of judge noise is the *rationale* for the architecture inversion |

## 7. What is new, in build order

1. `tasks/japan_fp/world.py` — state, dynamics, counterpart response, world sampling
2. `tasks/japan_fp/observation.py` — the partial, lagged, noisy view
3. `scripts/qualify_world.py` — §4's free gate, with the constant/adaptive/brute-force comparison
4. `tasks/japan_fp/initial_adaptive.py` — the seed program: December 2022 written as a *conditional* policy
5. `tasks/japan_fp/evaluate_adaptive.py` — run a program across worlds, aggregate mean and worst case
6. Baseline optimisers for the constant and hill-climbing arms
7. Config and prompt changes for ShinkaEvolve
8. The judge's new job: trajectory plausibility audit

## 8. Effort and risk, honestly

**Three to five focused days**, not one. Steps 1–3 are most of it, and step 3
is the gate that decides whether the rest happens.

**Cost is no longer the constraint.** The search runs on a free simulator. The
remaining spend is LLM mutation (~$0.0017/candidate on nano) plus the judge's
audit role, which is a few dozen calls. A full Project B experiment plausibly
costs **less** than Project A's, which is a genuine argument for it.

**The three ways this fails, in order of likelihood:**

1. **The world does not reward adaptivity** (§4 gate fails). Most likely, and
   cheapest to discover. Mitigation: run §4 first, and be willing to redesign
   the dynamics rather than to proceed anyway.
2. **The LLM cannot write competent conditional policy code.** The mutation
   models managed instrument dictionaries; branching stateful logic against a
   typed observation API is harder. Mitigation: a mutation smoke test on the
   adaptive seed, exactly as `scripts/mutation_smoke.py` does now, before any
   full run. Expect gpt-4.1 to be needed and nano to fail more.
3. **The simulator is unfalsifiable.** Everything is our model, so the result is
   about our model. Mitigation: §3.5 — declare, source, sensitivity-analyse, and
   use the judge as an external critic of trajectories.

**The deadline judgement.** Project A was reachable in one day. Project B is
not. If the submission date is close, the fallback is not "run A instead" — it is
**report §4's qualification result as the finding**: a specification of a policy
environment plus a measurement of whether adaptivity pays in it, with the search
left as future work. That is a real contribution, it is free, and it is
reachable in a day even if nothing else is.
