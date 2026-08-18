# actir-evolve-pre

**Evolutionary search over Japanese foreign-policy portfolios, with an LLM as
the world model.** The third experiment of *"After 2022: Japan's Search for a
Novel Foreign Policy"*.

The purpose is not to find Japan's optimal foreign policy. It is to **illuminate
a near-infinite space of well-formed alternatives** and surface robust or novel
options a human author would not have written down — and to measure honestly how
far an LLM judge can be trusted to guide that search.

> **Read [`docs/REVIEW_RESPONSE.md`](docs/REVIEW_RESPONSE.md) before any claim
> in this README.** A review on 2026-08-18 found eight defects, all fair, and
> acting on one of them **retracted this project's headline coverage result**:
> against a real random baseline, which had never run, MAP-Elites loses. The
> word *coherent* is deliberately not used above: the validity gate proves a
> portfolio is **well-formed**, never that it is fiscally, legally or
> politically coherent.

**Authoritative spec: [`RESEARCH_DESIGN.md`](RESEARCH_DESIGN.md). Build stages
and hard rules: [`KICKOFF.md`](KICKOFF.md). What the evidence supports:
[`docs/WHAT_WE_CAN_CLAIM.md`](docs/WHAT_WE_CAN_CLAIM.md).**

---

## How it works

One individual is a Python program whose `EVOLVE-BLOCK` returns a
`PolicyPortfolio`: Japan's marginal strategic effort for 2026–2030 allocated
across the **Lowy Asia Power Index's own 30 submeasures**, one capped sentence
per dial saying what the effort buys, an ordered sequence of phases, and
free-slot custom initiatives. LLMs rewrite that block; the result is scored.

The objective is borrowed, never invented — the same authority that defines the
score also defines the coordinate system.

**Stage 1 — validity gate.** Free and instant. Shares sum to 1.0, dial names
known, text caps respected, phases ordered inside the horizon, defence path
within a feasibility bound. Invalid gets fitness 0 and a readable reason, and
**no judge call is spent** — which is what makes a cheap mutation model
affordable.

**Stage 2 — frozen judge.** Per scenario the judge sees Japan's 2025 baseline,
one of three scenario vignettes, the portfolio as JSON (never the code), and an
anchored rubric. It returns a delta per measure plus a one-sentence causal
mechanism.

```
composite(s) = Σ_m  w_m · clip(b_m + delta_m,s , 0, 100)
fitness      = mean over the three scenarios
```

Japan's 2025 composite is **38.8475**. Under the mock judge every portfolio
scores exactly that, because every delta is zero — which is the point of the
check: everything downstream of the judge is Lowy's arithmetic, unmodified.

The mechanism sentences become `text_feedback`, which is what steers the next
mutation. Accumulated over a run they are an auditable corpus of *"if Japan does
X then Y because Z"*, each tied to one specific allocation.

---

## Status

**The pipeline runs end to end. The judge's resolution is the open question.**

| | |
|---|---|
| Tests | **234**, all offline, no network |
| Offline evolution | Works. 400 evaluations, $0.00, reproducible from a seed |
| Real ShinkaEvolve | Installed and **verified** — all 9 configs construct against it |
| Real judge | Ran once (M1, $0.1869) |
| Spent to date | **$0.1869** of a $20 working budget |

### What M1 found

Two judges from the same family, both at temperature 0, ranked five
deliberately-opposite doctrines at Spearman **−0.300**:

| | |
|---|---|
| `gpt-4.1` spread across five opposite doctrines | **0.696** |
| Mean inter-judge disagreement | **0.437** |
| Max inter-judge disagreement | **0.921** |

**The disagreement between judges is larger than the range the stronger judge
assigns to the entire doctrinal space.** M1 also exposed a structural bug: rubric
rule 5 asked the judge to score a portfolio *differently across scenarios*, but
each call only ever shows it **one** scenario — we asked for a comparison and
supplied one side of it. Rubric revision 2 fixes that and awaits re-approval.

Full analysis: [`docs/M1_FINDINGS.md`](docs/M1_FINDINGS.md).

This is why the claim is about *diversity*, not ranking. A resolution floor that
would sink "the champion is best" barely touches "the archive is diverse".

**But diversity alone does not survive either.** Against a genuine null model —
independent random draws, no parents, no feedback — MAP-Elites loses on coverage
at every budget tested (29.7% vs 52.1% at 150 valid evaluations; 68.8% vs 72.4%
at 900). Coverage of a low-dimensional behaviour grid cannot be a headline
result when a trivial null beats the algorithm on it. What the null *cannot* do
is produce portfolios anyone would read as a strategy, so the surviving claim is
about **coherent** diversity — and that is not yet measured.

---

## Running it

### Free — everything here is offline and calls no API

```bash
pip install -r requirements.txt
pytest -q                                                     # 234 tests

python scripts/offline_evolution.py --generations 400          # the full loop, $0.00
python analysis/archive_analysis.py                            # trajectory + figures
python analysis/novelty.py                                     # diversity + the frontier
python tasks/japan_fp/run_evo.py --config_path configs/pilot.yaml --dry-run
```

The offline loop uses a **surrogate judge** — a deterministic closed-form
stand-in with no LLM and no claim to represent anything about Japan. It exists
so the archive, selection, lineage and analysis could be built and debugged
before a cent was spent. Everything it produces is stamped `NOT A RESULT`.

### Paid — three pages, and nothing else can spend

| Workflow | What it does | Cost |
|---|---|---|
| [**Preflight**](../../actions/workflows/preflight.yml) | Judge determinism · genotype observability · rubric-v2 re-test · can the ensemble mutate | ~$0.06 |
| [**Pilot**](../../actions/workflows/pilot.yml) | The first real evolutionary run: LLMs write policy, the real judge scores it | ~$2.00 |
| [**M1 calibration**](../../actions/workflows/m1-calibration.yml) | The five-doctrine comparison table | ~$0.04 |

Each gates on a typed confirmation (`RUN_PREFLIGHT`, `RUN_PILOT`, `RUN_M1`).
Leave it blank and you get a free estimate that validates everything and spends
nothing. Results are published to the run's **Summary** page, not buried in logs.

---

## Budget

**$20 working, $50 hard ceiling.** Both enforced as `WORKING_BUDGET` and
`PROJECT_CEILING` in `tests/test_configs.py`; a config set that authorises more
fails the build.

Phase 1 is **two arms, deep** — the main run and its matched random-search
baseline, which together *are* the diversity comparison. Phase 2 (one more
baseline, three ablations) is costed and matched but runs only if phase 1 earns
it. Two deep arms beat six thin ones: novelty discovery needs one archive with
enough evaluations to populate the space.

The mutation model dominates cost, so the cheap tier does the exploring:

| Mutation model | $/evaluation | Evaluations per $7 arm |
|---|---|---|
| `gpt-4.1` | $0.0416 | 168 |
| `gpt-4.1-nano` | **$0.0093** | **755** |

Details and the full allocation: [`docs/BUDGET.md`](docs/BUDGET.md).

---

## Layout

```
tasks/japan_fp/
  lowy.py            8 measures, 30 dials, published weights, 2025 baseline
  schema.py          PolicyPortfolio — the genotype
  initial.py         the December 2022 seed, inside an EVOLVE-BLOCK
  seeds/             four rival schools, for calibration (see seeds/README.md)
  evaluate.py        validity gate → frozen judge → Lowy aggregation
  run_evo.py         ShinkaEvolve wiring + provenance (--dry-run needs no engine)
  judge/client.py    the frozen judge: mock by default, cached, cost-ledgered
  judge/surrogate.py deterministic offline stand-in — never a result
  scenarios/         S1 grinding status quo · S2 Taiwan · S3 US retrenchment
  judge_prompt.md    the anchored delta rubric
  FROZEN.json        recorded hashes of the four frozen files

scripts/
  m1_calibration.py   five doctrines × three scenarios, with judge comparison
  preflight_probes.py determinism and genotype-observability probes
  mutation_smoke.py   can the ensemble emit a portfolio the gate accepts?
  offline_evolution.py the whole loop, surrogate-scored, free
  freeze.py           re-record frozen hashes under a new version

analysis/
  archive_analysis.py  trajectory, operator effectiveness, hand-drawn SVG figures
  novelty.py           distance from human seeds, families, the novel+robust frontier
  shinka_adapter.py    normalises a real ShinkaEvolve run into the same format

configs/    judge.yaml · pilot.yaml · main.yaml · ablations/ + baselines
docs/       DECISIONS · BUDGET · M1_FINDINGS · WHAT_WE_CAN_CLAIM · API_KEYS · …
tests/      234 tests
```

---

## The fail-closed rules

Enforced in code and in CI, not by convention:

- **No real LLM call is possible** until `configs/judge.yaml` carries *both*
  `mode: real` and `stage_b_authorized: true`. Either alone raises before the
  network is touched. The committed config is asserted locked on every push, and
  arming happens only through a gitignored local file.
- **The judge is never in the mutation ensemble**, and no model that rejects the
  `temperature` parameter appears in any config — which rules out the entire
  GPT-5 series, since both the judge and the ensemble depend on sending it.
- **The project cannot authorise more than its budget.** Every ceiling that
  could be spent is summed and checked.
- **Frozen files cannot be edited in place.** Changing a scenario or the rubric
  without `python scripts/freeze.py --version <new>` turns the suite red.
- **Every real judge call is written to disk** — request and response in the
  cache, tokens and cost in the ledger. The cache is the audit trail.
- **Every run writes provenance**: config snapshot, git hash, RNG seed, judge
  identity, frozen-file version — and whether the judge was mocked, because a
  mock run and a real run that found no effect produce identical numbers and
  mean opposite things.

---

## What this is not

Per RESEARCH_DESIGN §6, nothing here is to be presented as Japan's optimal
policy, as a forecast of actual Lowy Index values, or as a recommendation to
act. **The judge is a world model, not the world.** Three scenarios do not span
the relevant uncertainty. The system explores and preserves possibilities; the
archive is a map of alternatives, not an answer.
