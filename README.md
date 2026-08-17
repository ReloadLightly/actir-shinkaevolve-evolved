# actir-shinkaevolve-evolved

ShinkaEvolve evolves Japanese foreign-policy programs whose fitness is Japan's
projected Lowy Asia Power Index composite in 2030. The third experiment of
*"After 2022: Japan's Search for a Novel Foreign Policy"*.

**Authoritative spec: [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md). Build stages
and hard rules: [`KICKOFF.md`](KICKOFF.md).**

Status: **Stage A complete, M0 approved, M1 inputs ready** (2026-08-17) —
API-free foundation, 88 tests green, no network call possible. The five M1
portfolios (December 2022 plus four rival schools) are written and pass the
gate. Scenarios and rubric are approved but deliberately still `DRAFT`; they
freeze after the M1 smoke test. Stage B — the first real judge calls, ~$0.11
against a $1 ceiling — needs an explicit go and an `ANTHROPIC_API_KEY`. See
[`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/API_KEYS.md`](docs/API_KEYS.md).

## Quick start

```bash
pip install -r requirements.txt
pytest -q                                    # 43 tests, no network

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
  run_evo.py        # ShinkaEvolve wiring + run provenance manifest
  judge/client.py   # frozen judge: MOCK by default, content-hash cache, cost ledger
  seeds/            # the four rival-school portfolios for M1 (see seeds/README.md)
  scenarios/        # S1-S3 vignettes            [M0-approved, freezes after M1]
  judge_prompt.md   # anchored delta rubric      [M0-approved, freezes after M1]
  FROZEN.json       # recorded hashes of the four frozen files
configs/            # judge.yaml, pilot.yaml (30 gens), main.yaml (150), ablations/
scripts/freeze.py         # re-record frozen hashes under a new version
scripts/m1_calibration.py # the M1 table: 5 portfolios x 3 scenarios
tests/              # Stage A tests + the seed and M1-harness tests
docs/               # DECISIONS.md, API_KEYS.md, JUDGE_MODEL_NOTE.md, OPEN_QUESTIONS.md
```

## The M1 calibration test

The next gate. Five portfolios — December 2022 plus four rival schools that
genuinely disagree (autonomous rearmament, accommodation, status-quo-plus,
middle-power internationalism) — scored across all three scenarios, producing
one table you read to decide whether the rubric is plausible enough to freeze.

```bash
python scripts/m1_calibration.py              # mock: 0 calls, $0, proves the harness
python scripts/m1_calibration.py --estimate   # ~$0.11 against the $1 ceiling
python scripts/m1_calibration.py --real       # refuses unless Stage B is authorized
```

Each seed is aimed at a specific rubric rule, so a miscalibrated rubric fails
visibly rather than quietly — see [`tasks/japan_fp/seeds/README.md`](tasks/japan_fp/seeds/README.md).

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
- **The judge is never in the mutation ensemble** — check any config in
  `configs/`.
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
