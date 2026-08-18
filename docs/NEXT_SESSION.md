# Where to pick up

Decision, 2026-08-18: **Project A now, Project B as follow-on.** Finish the
static-illumination experiment to a reportable result first, then attempt the
adaptive version with the same apparatus if time allows.

## State

347 tests green. $0.30 spent of the $20 working budget. Judge ships locked
(`mode: mock`, `stage_b_authorized: false`). Everything pushed to
`claude/project-kickoff-7sdnab`.

**The instrument layer is built and tested but NOT CONNECTED.** This is the
whole of tomorrow's first task and the reason no experiment ran today:

- all nine configs still carry `init_program_path: tasks/japan_fp/initial.py`
- `tasks/japan_fp/judge_prompt.md` has zero mentions of instruments
- nothing in `scripts/`, `configs/` or `.github/` references
  `initial_instruments.py`
- `FROZEN.json` is `0.3.0-m1-corrected`, status **DRAFT**

A run launched against `main` today would search the *outcome* layer and
reproduce the coverage result already retracted in `docs/ILLUMINATION.md`.

## The order of work

1. **Connect the layer** *(free, ~1h)*. Point `configs/pilot.yaml` and the two
   phase-1 arms at `tasks/japan_fp/initial_instruments.py`. Rewrite
   `run_evo.TASK_SYS_MSG` around the instrument catalogue — the current text
   describes 30 outcome dials and would actively mislead a model editing
   instrument intensities. `instruments.describe_catalogue()` returns exactly
   what the prompt needs.

2. **Mutation smoke on the new seed** *(~$0.10)*. No LLM has ever been asked to
   mutate `initial_instruments.py`. The last measured rates (nano 33%,
   gpt-4.1 100%) were against the *outcome* seed and do not transfer: the
   instrument block is shorter and has no 30-term arithmetic, so nano may do
   better — or may violate the fiscal envelope constantly, which the gate now
   catches. Measure before assuming.

3. **Rubric revision 3** *(free to write, needs Roland's approval)*. The judge
   currently sees an `instruments` key it was never told about. It should be
   told that it is scoring *decisions* whose outcome exposure is already
   derived, and asked for the world's response rather than for the allocation
   it can now see. Then `FROZEN.json` → `FROZEN`, which is the gate
   `run_evo.check_evaluator_is_frozen` enforces.

4. **The experiment** *(~$5–8)*. Two arms, matched on
   `matched_valid_evaluations`, real judge, `--repeats 3` so every reported
   number carries a standard error:
   - LLM-guided search over instruments (`configs/pilot.yaml`, then `main.yaml`)
   - `scripts/random_baseline.py` over instruments as the null

   **The metric is feasibility, not coverage.** Coverage is settled and dead —
   a free programmatic null beats LLM search on it, on both representations
   (`docs/INSTRUMENT_LAYER.md`). The live claim is the 91.1%-vs-1.7% gate pass
   rate: *diversity is free, feasibility is not*. `random_baseline.py` samples
   the outcome simplex today and needs an instrument-space sampler to be the
   right null for this comparison.

5. **Writeup**. `docs/REVIEW_RESPONSE.md` has the claim this repository can
   actually support; `docs/PREFLIGHT_FINDINGS.md` has the judge's measured
   resolution floor (0.17 self-noise against 0.696 doctrine effect).

## What not to redo

Two reviews have already been answered in full — see `docs/REVIEW_RESPONSE.md`
and `docs/INSTRUMENT_LAYER.md`. Both retracted a headline claim. Do not
reinstate a coverage advantage without a null model; `tests/test_mapelites.py`
fails if `docs/ILLUMINATION.md` loses its retraction notice.

Review point 1 — static portfolios, no observations, no conditional decisions —
is untouched and is Project B. Nothing in Project A should describe its output
as an adaptive strategy.
