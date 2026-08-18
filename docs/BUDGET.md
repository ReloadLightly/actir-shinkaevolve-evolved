# Budget: USD 20 working, USD 50 hard ceiling

Roland raised the hard ceiling to **USD 50** on 2026-08-17, and immediately
added the qualification that matters: *"$50 is my ceiling, I never said that I
WANT to spend that much."* So the plan is **USD 20**, staged, with the rest
reachable only if phase 1 earns it.

Both numbers are enforced. `tests/test_configs.py` carries `WORKING_BUDGET =
20.0` for what phase 1 may authorise and `PROJECT_CEILING = 50.0` as the hard
limit nothing may exceed.

| | Ceiling | Arms | Evaluations each |
|---|---|---|---|
| **Phase 1** — authorised | $20.00 | main + random-search baseline | ~168–755 |
| **Phase 2** — only if phase 1 earns it | $48.00 total | + hill-climbing, parent, ensemble, novelty | matched |

**Phase 1 is two arms, deep, not six arms, thin.** That pair *is* the RQ3
comparison — "does the machinery hold diversity, an option map rather than one
answer?" — and novelty discovery needs one archive with enough evaluations to
populate the space. Six archives of 57 evaluations would contain nothing.

## Cheap models, because the target is coverage

The mutation model dominates cost, and for *exploration* the thing that matters
is how many evaluations happen, not how eloquent any single proposal is.

| Mutation model | $/proposal | $/evaluation | Evaluations per $7 arm |
|---|---|---|---|
| `gpt-4.1` | $0.0340 | $0.0416 | 168 |
| `gpt-4.1-nano` | $0.0017 | **$0.0093** | **755** |

**4.5× the coverage for the same money.** And the downside of a cheap model is
smaller than it looks: a candidate whose 30 shares do not sum to 1.0 is rejected
by the validity gate *before any judge call is spent*, so a miss costs $0.0017
rather than $0.0093.

The pilot therefore runs `gpt-4.1-nano` alone — it is a smoke test, not an
experimental arm, and 215 evaluations tells us far more than 48. The Stage D
arms keep both tiers, because RESEARCH_DESIGN §3 asks for a mixed ensemble and
the UCB1 bandit needs something to choose between.

`num_generations` is now set generously (700 on the arms) so that
`max_api_costs` is the binding constraint. A cheap ensemble then runs *longer*
for the same money instead of stopping early at an arbitrary generation count.

`tests/test_configs.py` enforces the 15 as `PROJECT_CEILING`. It is the check
that would have caught the original configs, which authorised **USD 290**
against it — seven Stage D runs at USD 40 each plus a USD 10 pilot. Nothing
was ever spent; the breach was latent in the configuration.

## What one evaluation costs

An evaluation is one mutation proposal plus three judge calls (one per
scenario). The judge side is fixed at **$0.0076** — three calls to
`gpt-4.1-mini-2025-04-14` at roughly 3,500 in / 700 out each.

The mutation side is where the money goes, exactly as RESEARCH_DESIGN §3
predicted. At roughly 10,000 in / 5,000 out per proposal:

| Mutation model | Per proposal | Per evaluation | Evaluations for $12 |
|---|---|---|---|
| `claude-opus-5` *(was configured)* | $0.175 | $0.183 | 65 |
| `claude-sonnet-5` *(was configured)* | $0.105 | $0.113 | 106 |
| `gpt-4.1` | $0.060 | $0.068 | 177 |
| `gpt-4.1-nano` | $0.003 | **$0.0106** | **1,136** |

**The ensemble choice decides whether the study gets 65 or 1,136 evaluations
in total** — not per run; in total, across every run that will ever happen.

Prices verified 2026-08-17 against published OpenAI pricing. An earlier
revision of this page used figures from memory, including three model ids
(`gpt-5-mini`, `gpt-5-nano`, `gpt-5`) that do not exist.

## What the design asks for, versus what fits

RESEARCH_DESIGN §4 wants main + 2 baselines + 3 ablations, at 150 evaluations
each: **900 evaluations**. Against $12 of search budget that was 14× over on
the original opus-led ensemble. On the re-picked ensemble it is roughly 3×
over — still a re-cut, but a far smaller one.

So the study had to be re-cut. The allocation below is the **superseded**
$15 cut, kept because it is what the six-arm design costs and therefore what
phase 2 would have to buy. The live plan is the phase-1/phase-2 split at the
top of this page.

| Line | Ceiling | Note |
|---|---|---|
| M1 calibration | $0.25 | judge only, 15 calls, actual estimate **$0.038** |
| Pilot | $1.00 | 20 generations |
| Stage D — main | $2.00 | 30 generations |
| Stage D — baseline: random search | $2.00 | matched |
| Stage D — baseline: hill climbing | $2.00 | matched |
| Stage D — ablation: parent selection | $2.00 | matched |
| Stage D — ablation: ensemble | $2.00 | matched |
| Stage D — ablation: novelty | $2.00 | matched |
| M4 judge-swap re-scoring | $0.50 | top-20 archive, 60 calls; needs an `ANTHROPIC_API_KEY` |
| Contingency | $1.25 | |
| **Total (superseded)** | **$15.00** | replaced by the $20 phase-1 plan above |

Matched budget across the six Stage D arms is preserved, because §4's
comparisons measure mechanism only if spend is held equal.

**At $2.00 per arm, the ensemble decides what that buys:**

| Ensemble | Evaluations per arm |
|---|---|
| opus-led *(the original config)* | **9** |
| `gpt-4.1` only | 29 |
| `gpt-4.1` + `gpt-4.1-nano`, 50/50 *(now configured)* | **51** |
| `gpt-4.1-nano` only | 189 |

> **Measured 2026-08-18** (preflight 32086108143, 3 attempts per model against
> the real validity gate). The table above assumed every mutation call yields a
> scoreable individual. It does not:
>
> | | mutation/call | gate pass | mutation/valid | + judge | evals per $2 |
> |---|---|---|---|---|---|
> | `gpt-4.1-nano` | $0.0017 | **33%** | $0.0051 | $0.0120 | **167** |
> | `gpt-4.1` | $0.0340 | **100%** | $0.0340 | $0.0409 | **49** |
>
> Nano keeps a **3.4×** advantage per valid individual despite failing two
> attempts in three, because a rejected candidate costs only the mutation call —
> the validity gate refuses it before any judge call is spent. The free exact
> check is what makes the cheap model affordable, which is the
> `ALPHAEVOLVE_COMPARISON.md` principle paying for itself in cash.

Nine evaluations per arm is not a search; it is nine samples. The re-picked
ensemble gives roughly 51, and more if the UCB1 bandit finds the nano tier
competitive — which is exactly the trade-off the bandit exists to discover.

## The open decision

Three ways to spend $15, in the order I would recommend them:

**A — Stage-gate it, and validate the judge first (recommended).**

```bash
python scripts/m1_calibration.py --real --compare-with gpt-4.1   # $0.23
```

This scores all five doctrines twice — once with the configured
`gpt-4.1-mini`, once with the 5×-dearer `gpt-4.1` — and reports the Spearman
rank correlation between the two orderings.

It is the single most valuable $0.23 in the project, because it removes the
one assumption that could waste the other $14.77. **The judge is the fitness
function.** If it is too weak to rank five deliberately-different doctrines,
every number downstream is noise and the whole budget buys nothing. If the two
judges agree, the cheap one is measuring what the dear one measures and the
75%-of-budget saving is demonstrated rather than hoped for. If they disagree,
that is the oracle problem arriving early and cheaply, while there is still
budget to respond to it.

Then run the pilot ($1.00) and let the ledger report the *actual* cost per
evaluation instead of my estimate. Commit the remaining ~$13 only after both.
Total spent before any irreversible commitment: **$1.23**, under a tenth of
the budget.

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

## The ensemble, re-picked 2026-08-17

Was:

```yaml
llm_models:
  - "claude-opus-5"          # $0.183/eval — unaffordable at this budget
  - "claude-sonnet-5"        # $0.113/eval — affordable for one arm, not six
  - "gpt-5.4"                # real, but rejects `temperature` (see below)
  - "gemini-3-flash-preview" # unverified, and no Google key provisioned
```

Now:

```yaml
llm_models:
  - "gpt-4.1"                # $0.068/eval — the strong tier
  - "gpt-4.1-nano"           # $0.0106/eval — the cheap tier, 20x apart
```

**The constraint that decided this: the entire OpenAI GPT-5 series rejects the
`temperature` parameter.** OpenAI removed it there to avoid injecting
randomness into reasoning chains — the same move Anthropic made on Claude 5,
and the same finding that shaped the original M0 note. It rules out GPT-5.4,
5.5 and 5.6 twice over: the judge needs `temperature: 0` per §2.2, and the
ensemble uses `temperatures: [0.0, 0.5, 1.0]` as its diversity mechanism.
`tests/test_configs.py` now fails if any model rejecting `temperature` appears
in any config.

That leaves the GPT-4.1 family as the only usable OpenAI models, and it has
exactly three members. One is the judge, so two remain for the ensemble.

**This is a deviation from RESEARCH_DESIGN §3**, which asks for four models
across mixed tiers. Two is what the constraints permit on OpenAI alone. The
tiers are genuinely mixed — `gpt-4.1` costs 20× `gpt-4.1-nano`, so the UCB1
bandit still has a real trade-off to explore. Getting back to four would need
a second provider key (Google or Anthropic); it does not block anything now,
and belongs in the methods section either way.

Two ids remain barred: `gpt-4.1-mini-2025-04-14` is the judge (hard rule 2),
and `claude-haiku-4-5-20251001` is the M4 judge-swap model — using it as a
mutator would weaken that check, since the swap judge would be re-scoring work
it partly wrote.

## Standing rules

- Ceilings may be **lowered** freely. Raising one is Roland's decision alone
  (KICKOFF hard rule 4).
- On reaching 90% of any ceiling, stop and report.
- Every real call is written to `runs/ledger/judge_calls.jsonl` with its token
  counts, its cost, and the price table used — so the ledger stays truthful
  even if list prices change, and a wrong estimate is recoverable after the
  fact rather than lost.
- Prices in `judge/client.py` were verified on 2026-08-17 against published
  pricing. `--estimate` reports the current figure and preflights the key.
