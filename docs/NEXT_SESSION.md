# Where to pick up

**Decision, 2026-08-19: Project B.** Roland reconsidered overnight — Project A
(static illumination) is insufficient for the paper's purpose. Build toward
observation-dependent policy programs evaluated on held-out uncertain worlds.

**Read [`docs/PROJECT_B_DESIGN.md`](PROJECT_B_DESIGN.md) first.** It is the
design; this page is only the order of work and the state of the tree.

## State of the tree

347 tests green. **$0.30 spent** of the $20 working budget. Judge ships locked
(`mode: mock`, `stage_b_authorized: false`). All work pushed to
`claude/project-kickoff-7sdnab`.

Yesterday's Project A wiring was deliberately **not** completed, and should not
be completed now: the configs still point at `initial.py`, the judge prompt has
no mention of instruments, and `FROZEN.json` is still DRAFT. Under Project B the
judge leaves the inner loop entirely, so freezing that rubric is no longer on
the critical path.

## The one thing that changes everything

Project B moves the LLM **out of the fitness function**. An exact, free,
deterministic simulator becomes the objective; the LLM stays as the mutation
operator. That is AlphaEvolve's actual recipe, and it is the structural fix for
the finding that has shadowed this project since M1 — a judge whose effect
across five opposite doctrines (0.696) barely exceeds its disagreement with
itself on identical input (0.17).

Consequences worth holding in mind while working:

- **The search becomes nearly free.** Spend drops to LLM mutation plus a few
  dozen judge calls for trajectory auditing. Project B plausibly costs *less*
  than Project A would have.
- **`instruments.py` was the right thing to build yesterday.** It is Project B's
  action space, and `lead_time_years` — inert under A — becomes load-bearing.
- **The three prose scenarios become a distribution.** S1/S2/S3 survive as named
  regions of parameter space for interpretation, not as the evaluation battery.

## Order of work

1. **`tasks/japan_fp/world.py`** — state, annual dynamics, counterpart response,
   world sampling. Design §3. The counterpart response is the part that makes
   this a strategic problem rather than open-loop control: China's coercion
   responds to Japan's buildup, US commitment responds to burden-sharing.

2. **`tasks/japan_fp/observation.py`** — the partial, lagged, noisy view.
   Japan sees its own state exactly, the world's with noise and a year's lag,
   and the hidden parameters never. That is what makes memory worth having.

3. **`scripts/qualify_world.py` — THE GATE, and it is free.** Design §4.
   Optimise the best *constant* policy and the best *simple adaptive* policy
   numerically, no LLM, and compare on **held-out** worlds.

   > If adaptive does not beat best-constant by more than seed noise, the world
   > contains no experiment. **Redesign the dynamics. Do not proceed.**

   This is the step most likely to be skipped under deadline pressure and the
   one that decides whether any of the rest is worth doing. It costs nothing.

4. **`tasks/japan_fp/initial_adaptive.py`** — December 2022 rewritten as a
   *conditional* policy, seeding from the real status quo as RESEARCH_DESIGN §1
   rule 4 requires.

5. **`tasks/japan_fp/evaluate_adaptive.py`** — run a program across worlds,
   aggregate mean and worst case.

6. **Mutation smoke on the adaptive seed** (~$0.10) before any full run. Writing
   branching stateful code against a typed API is harder than editing an
   instrument dictionary; expect nano's 33% to fall and gpt-4.1 to be needed.

7. **Baselines, configs, prompt, and the run.** Design §5.

## Do not redo

Two reviews have been answered in full, each costing a headline claim. See
`docs/REVIEW_RESPONSE.md` and `docs/INSTRUMENT_LAYER.md`.

- **Coverage is settled and dead** as a headline metric. A free programmatic
  null beats LLM-guided search on it, on both representations tested.
  `tests/test_mapelites.py` fails if `docs/ILLUMINATION.md` loses its retraction.
- **The Lowy projection is ours, not Lowy's** — adding an LLM-estimated delta to
  Japan's fixed 2025 scores while holding 26 countries implicit is a model, and
  only the weights are Lowy's. Stated in `lowy.py`; it applies unchanged to the
  simulator, which inherits the same caveat.
- **"Coherent" is withdrawn** in favour of "well-formed" for anything the gate
  checks.

## The fallback, if the deadline closes in

Project B is three to five focused days, not one. If time runs short, the
fallback is **not** to revert to Project A. It is to report step 3's
qualification result as the finding: a specification of a policy environment,
plus a measurement of whether adaptivity pays in it, with the evolutionary
search named as future work.

That is a real contribution, it is free, and it is reachable in a day.
