# actir-shinkaevolve-evolved

ShinkaEvolve evolves Japanese foreign-policy programs whose fitness is Japan's
projected Lowy Asia Power Index composite in 2030. The third experiment of
*"After 2022: Japan's Search for a Novel Foreign Policy"*.

**Authoritative spec: [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md). Build stages
and hard rules: [`KICKOFF.md`](KICKOFF.md).**

Status: **M1 run #1 complete — rubric corrected, awaiting re-approval** (2026-08-17) —
196 tests green. **The evolution loop now runs end to end offline** — 301 evaluations, $0.00, via a surrogate judge and programmatic mutation (`scripts/offline_evolution.py`), with the analysis layer built on its output. M1 ran for **$0.1869** and
found the rubric wanting: judge agreement −0.300, and the composite spread
across five opposite doctrines (0.70) smaller than the disagreement between two
judges (0.92). Rubric revision 2 addresses it; scenarios unchanged. See
[`docs/M1_FINDINGS.md`](docs/M1_FINDINGS.md). The next step is a 3-call re-test (~$0.006), not a search. See
[`docs/DECISIONS.md`](docs/DECISIONS.md), [`docs/BUDGET.md`](docs/BUDGET.md)
and [`docs/API_KEYS.md`](docs/API_KEYS.md).

**Budget: USD 15 for the whole project**, superseding KICKOFF's per-stage
figures. Enforced as `PROJECT_CEILING` in `tests/test_configs.py`.

The judge is `gpt-4.1-mini-2025-04-14` at temperature 0 — a dated snapshot in
the GPT-4.1 family, which is the newest OpenAI family that still accepts
`temperature` at all. The mutation ensemble is `gpt-4.1` + `gpt-4.1-nano`.
`claude-haiku-4-5-20251001` is the M4 judge-swap model from a different family;
both backends are implemented and send byte-identical prompts.

## Quick start

```bash
pip install -r requirements.txt
pytest -q                                    # 196 tests, no network

# Score the December 2022 seed portfolio with the mock judge
python tasks/japan_fp/evaluate.py \
    --program_path tasks/japan_fp/initial.py \
    --results_dir runs/scratch
# -> combined_score = 38.8475  (Lowy composite, 38.8 as reported)
```

38.8475 is Japan's actual 2025 composite. The mock judge returns all-zero
deltas, so the pipeline reduces to the published index — which is the point of
the check: everything downstream of the judge is Lowy's arithmetic, unmodified.

## Layout

```
tasks/japan_fp/
  lowy.py           # 8 measures, 30 submeasure dials, published weights, 2025 baseline
  schema.py         # PolicyPortfolio: the genotype
  initial.py        # the December 2022 seed, inside an EVOLVE-BLOCK
  evaluate.py       # Stage 1 validity gate -> Stage 2 frozen judge -> Lowy aggregation
  run_evo.py        # ShinkaEvolve wiring + provenance manifest (--dry-run needs no engine)
  judge/client.py   # frozen judge: MOCK by default, content-hash cache, cost ledger
  seeds/            # the four rival-school portfolios for M1 (see seeds/README.md)
  scenarios/        # S1-S3 vignettes            [M0-approved, freezes after M1]
  judge_prompt.md   # anchored delta rubric      [M0-approved, freezes after M1]
  FROZEN.json       # recorded hashes of the four frozen files
configs/            # judge.yaml, pilot.yaml (20 gens), main.yaml (30), ablations/ + baselines
scripts/freeze.py         # re-record frozen hashes under a new version
scripts/m1_calibration.py # the M1 table: 5 portfolios x 3 scenarios
analysis/           # archive_analysis.py -> report.md + SVG figures (example/ has output)
tests/              # Stage A tests + seeds, M1 harness, configs, offline pipeline
docs/               # DECISIONS.md, BUDGET.md, RUN_M1_LOCALLY.md, API_KEYS.md, ...
```

## Running things

**Everything below is free and offline. Nothing here calls an API.**

```bash
pytest -q                                                    # 196 tests
python scripts/offline_evolution.py --generations 300         # the full loop, $0.00
python analysis/archive_analysis.py                           # figures + report
python tasks/japan_fp/run_evo.py --config_path configs/pilot.yaml --dry-run
```

**The one thing that does cost money** lives behind a single GitHub page:

> **https://github.com/ReloadLightly/actir-shinkaevolve-evolved/actions/workflows/m1-calibration.yml**

That page shows only the M1 workflow. The **"Run workflow"** button is on the
right, above the run list. It drops down four inputs:

| Input | Use |
|---|---|
| `run_mode` | `estimate` costs nothing and checks the key. `real_compare` spends. |
| `portfolios` | `accommodation` = 3 calls ≈ $0.006. `all` = 15 calls ≈ $0.038. |
| `compare` | `no` = one judge. `yes` = both judges + rank correlation, 5× the cost. |
| `confirm_spend` | Must be exactly `RUN_M1`, or the run refuses. |

The result table is printed to the run's **Summary** page — no digging through
logs. Nothing else in the repository can spend money.

## The M1 calibration test

The next gate. Five portfolios — December 2022 plus four rival schools that
genuinely disagree (autonomous rearmament, accommodation, status-quo-plus,
middle-power internationalism) — scored across all three scenarios, producing
one table you read to decide whether the rubric is plausible enough to freeze.

```bash
python scripts/m1_calibration.py              # mock: 0 calls, $0, proves the harness
python scripts/m1_calibration.py --estimate   # ~$0.04, and preflights the key
python scripts/m1_calibration.py --real       # refuses unless Stage B is authorized
```

Each seed is aimed at a specific rubric rule, so a miscalibrated rubric fails
visibly rather than quietly — see [`tasks/japan_fp/seeds/README.md`](tasks/japan_fp/seeds/README.md).

To run it for real from your own machine, with your key never leaving it:
[`docs/RUN_M1_LOCALLY.md`](docs/RUN_M1_LOCALLY.md).

## How fitness works

One individual is a Python program whose EVOLVE-BLOCK returns a
`PolicyPortfolio`: Japan's marginal strategic effort for 2026-2030 allocated
across the Index's own 30 submeasures, one capped sentence per dial, an ordered
sequence, and free-slot custom initiatives.

**Stage 1 — validity gate** (free, instant). Shares sum to 1, dial names known,
caps respected, phases ordered and inside the horizon, defence path within the
feasibility bound. Invalid gets fitness 0 and a reason string, and no judge call
is spent.

**Stage 2 — frozen judge.** Per scenario the judge sees the 2025 baseline, the
vignette, the portfolio as JSON (never the code), and an anchored rubric. It
returns a delta per measure on the 0-100 scale plus a one-sentence mechanism.

```
composite(s) = sum_m  w_m * clip(b_m + delta_m,s , 0, 100)
fitness      = mean over the 3 scenarios
```

The judge's deltas are the only modelled step. The worst-case composite rides
along as a public metric, so robust policies are distinguishable from lucky
ones, and the mechanism sentences become `text_feedback` — which is what steers
the next mutation.

## The fail-closed rules

These are enforced in code, not by convention:

- **No real LLM call is possible** until `configs/judge.yaml` has *both*
  `mode: real` and `stage_b_authorized: true`. Either alone raises.
- **The judge is never in the mutation ensemble**, and no model that rejects
  `temperature` appears in any config. `tests/test_configs.py` enforces both.
- **The project cannot authorise more than USD 15.** `PROJECT_CEILING` sums
  every ceiling that could be spent and fails if they exceed the budget.
- **Frozen files cannot be edited in place.** `tests/test_frozen_files.py` goes
  red if `scenarios/` or `judge_prompt.md` changes without
  `python scripts/freeze.py --version <new>`.
- **Every real judge call is written to disk** — full request and response in
  `tasks/japan_fp/judge/cache/`, tokens and cost in
  `runs/ledger/judge_calls.jsonl`. The cache is the audit trail.
- **Every run writes provenance**: config snapshot, git hash, RNG seed, judge
  identity, and the frozen-file version, to `run_manifest.json`.

## What this is not

Per RESEARCH_DESIGN §6, results from this system are never to be presented as
Japan's optimal policy, as a forecast of actual Lowy Index values, or as a
recommendation to act. The judge is a world model, not the world. The system
explores and preserves possibilities; the archive is a map of alternatives, not
an answer.
