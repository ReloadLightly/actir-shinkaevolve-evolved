# Budget: USD 15 for the whole project

Roland set the total project budget at **USD 15** on 2026-08-17. This
supersedes the per-stage figures in `KICKOFF.md`, which total 261 (Stage B 1,
Stage C 10, Stage D 250). **Where KICKOFF and this number disagree, this one
wins.** KICKOFF is left unedited as the original spec; the supersession is
recorded here and in `DECISIONS.md`.

`tests/test_configs.py` enforces the 15 as `PROJECT_CEILING`. It is the check
that would have caught the original configs, which authorised **USD 290**
against it — seven Stage D runs at USD 40 each plus a USD 10 pilot. Nothing
was ever spent; the breach was latent in the configuration.

## What one evaluation costs

An evaluation is one mutation proposal plus three judge calls (one per
scenario). The judge side is fixed at **$0.038** — three calls to
`gpt-4.1-2025-04-14` at roughly 3,500 in / 700 out each.

The mutation side is where the money goes, exactly as RESEARCH_DESIGN §3
predicted. At roughly 10,000 in / 5,000 out per proposal:

| Mutation model | Per proposal | Per evaluation | Evaluations for $12 |
|---|---|---|---|
| `claude-opus-5` | $0.175 | **$0.213** | 56 |
| `claude-sonnet-5` | $0.105 | **$0.143** | 84 |
| `claude-haiku-4-5-20251001` | $0.035 | **$0.073** | 164 |
| `gpt-4.1-mini` | $0.012 | **$0.050** | 240 |

Those last two columns are the whole problem in one line. **The ensemble
choice decides whether the study gets 56 or 240 evaluations in total** — not
per run, in total, across every run that will ever happen.

## What the design asks for, versus what fits

RESEARCH_DESIGN §4 wants main + 2 baselines + 3 ablations, at 150 evaluations
each: **900 evaluations**. Against $12 of search budget that is 16× over at the
cheapest tier and 60× over at the current opus-led ensemble.

So the study had to be re-cut. The current allocation:

| Line | Ceiling | Note |
|---|---|---|
| M1 calibration | $0.25 | judge only, 15 calls, actual estimate $0.19 |
| Pilot | $1.00 | 20 generations |
| Stage D — main | $2.00 | 30 generations |
| Stage D — baseline: random search | $2.00 | matched |
| Stage D — baseline: hill climbing | $2.00 | matched |
| Stage D — ablation: parent selection | $2.00 | matched |
| Stage D — ablation: ensemble | $2.00 | matched |
| Stage D — ablation: novelty | $2.00 | matched |
| M4 judge-swap re-scoring | $0.50 | top-20 archive, 60 calls on Haiku |
| Contingency | $1.25 | |
| **Total** | **$15.00** | |

Matched budget across the six Stage D arms is preserved, because §4's
comparisons measure mechanism only if spend is held equal.

**At $2.00 per arm, the ensemble decides what that buys:**

| Ensemble tier | Evaluations per arm |
|---|---|
| opus-led (current) | **9** |
| sonnet | 14 |
| haiku | 27 |
| `gpt-4.1-mini` | 40 |

Nine evaluations per arm is not a search; it is nine samples. The current
ensemble has to change or the Stage D comparisons will be noise.

## The open decision

Three ways to spend $15, in the order I would recommend them:

**A — Stage-gate it (recommended).** Run M1 ($0.19), then the pilot ($1.00).
The ledger then reports the *actual* cost per evaluation rather than my
estimate, and the trajectory shows whether 30 generations produces any signal
at all. Commit the remaining ~$13 only after seeing both. This matches
KICKOFF's own stage-gate structure and costs nothing to choose.

**B — Six thin arms.** Keep the full comparative structure at ~30–40
evaluations per arm, with a cheap ensemble. Preserves every comparison §4 asks
for; each one is statistically weak.

**C — Two deep arms.** Main plus one baseline at ~$6 each, ~120 evaluations
each. A trajectory strong enough to show something, and one honest comparison,
at the cost of dropping the ablations.

B and C are genuinely different papers. B says "here is the full ablation
structure, underpowered". C says "here is one real search against one real
baseline". I would take A now and decide between B and C with the pilot's
numbers in hand.

## The ensemble has to be re-picked regardless

`configs/*.yaml` still name four models:

```yaml
llm_models:
  - "claude-opus-5"          # $0.213/eval — unaffordable at this budget
  - "claude-sonnet-5"        # $0.143/eval — affordable only for a single arm
  - "gpt-5.4"                # placeholder, does not exist
  - "gemini-3-flash-preview" # placeholder, unverified
```

Two are too expensive and two do not resolve. `tests/test_configs.py` carries
the placeholders in `UNVERIFIED_MODEL_IDS` with a strict xfail, so the suite
flips red the moment they are fixed and the marker cannot be left behind.

One constraint when re-picking: `claude-haiku-4-5-20251001` is the M4
judge-swap model. Using it as a mutator too would weaken that check, since the
swap judge would have written some of what it re-scores. `gpt-4.1-2025-04-14`
is barred outright by hard rule 2 — it is the judge.

## Standing rules

- Ceilings may be **lowered** freely. Raising one is Roland's decision alone
  (KICKOFF hard rule 4).
- On reaching 90% of any ceiling, stop and report.
- Every real call is written to `runs/ledger/judge_calls.jsonl` with its token
  counts, its cost, and the price table used — so the ledger stays truthful
  even if list prices change, and a wrong estimate is recoverable after the
  fact rather than lost.
- The OpenAI price rows in `judge/client.py` are **unverified**, flagged in
  code and by `--estimate`. Confirm them against the account before relying on
  any figure on this page.
