# Note for M0: "temperature 0" constrains which judge models are available

**Status: DECIDED at M0, then AMENDED the same day. The judge is
`gpt-4.1-2025-04-14` at temperature 0.0 (provider `openai`); the M0 choice of
`claude-haiku-4-5-20251001` is now the M4 judge-swap model. See
`DECISIONS.md`. This note is retained as the rationale: it records the
constraint both choices were made under, and that constraint did not
change.**

**What the amendment did not change:** the requirement that the judge take
`temperature: 0`, that it be pinned to a dated snapshot rather than a floating
alias, that it support structured outputs, and that it be excluded from the
mutation ensemble. The OpenAI choice satisfies all four, and RESEARCH_DESIGN
§2.2 names `gpt-4.1` among the paper's own judge tier — so it is the design's
precedent rather than a substitute for it.

**What it did change:** the cost line below is now the Anthropic figure, i.e.
the M4 swap. M1 on `gpt-4.1-2025-04-14` estimates at ~$0.19 rather than
~$0.08, still far inside the $1 ceiling. Run `--estimate` for the current
figure; note the OpenAI price rows are unverified.

---

## The finding

RESEARCH_DESIGN §2.2 specifies the judge as "one LLM, pinned to an exact API
version, temperature 0". That is exactly right as a design intent — a frozen,
deterministic environment against which variation is proposed.

The complication: **the current frontier models no longer accept a
`temperature` parameter at all.** On Claude Opus 5, Sonnet 5, Fable 5, and the
Opus 4.7/4.8 generation, `temperature`, `top_p`, and `top_k` were removed from
the API; a request carrying any of them is rejected with HTTP 400. The same
applies to the newest OpenAI reasoning-tier models. Sampling is no longer a
knob the caller turns on those tiers.

So "temperature 0" and "frontier model" are, as of August 2026, mutually
exclusive. One has to give.

## Why this does not damage the design

The design does not actually need a *frontier* judge. RESEARCH_DESIGN §2.2 is
explicit: the judge tier is the paper's meta/novelty tier — "cheap, frozen,
boring". The judge's job is a bounded, rubric-anchored estimate, not open-ended
reasoning. The paper used gpt-5-nano / gpt-4.1 / gpt-5-mini at temperature 0
for precisely this role.

The cheap tier still takes `temperature`. So the constraint resolves cleanly in
favour of what the design already wanted.

## What is configured by default

`configs/judge.yaml` configures:

```yaml
provider: anthropic
model: claude-haiku-4-5-20251001
temperature: 0.0
```

Reasons:

1. **It accepts `temperature: 0.0`.** The design's determinism requirement is
   met literally rather than approximated.
2. **The id is a dated snapshot.** `claude-haiku-4-5-20251001` is a pinned
   version in the strict sense the design asks for — not a floating alias that
   can be repointed under us mid-experiment. This matters more than the model
   choice itself: a floating alias would silently break the pre-registration.
3. **It is the cheap tier.** $1.00 / $5.00 per million input / output tokens.
4. **It supports structured outputs**, so the 8 deltas plus 8 mechanism
   sentences are schema-enforced rather than parsed out of prose. One less
   failure mode between the judge and the arithmetic.

`JudgeConfig.sends_temperature` detects models that reject sampling parameters
and omits `temperature` rather than sending a request that would 400. So if you
choose a Claude 5-tier judge instead, the code will not break — but the run
would then be non-deterministic in a way the design does not intend, and that
should be a conscious choice.

## Cost, at this model

One evaluation is 3 judge calls. Estimating ~2,500 input and ~600 output tokens
per call (rubric + baseline table + scenario + portfolio JSON in; 8 deltas and
8 sentences out):

| Stage | Judge calls | Est. judge cost |
|---|---|---|
| M1 smoke test (5 portfolios x 3 scenarios) | 15 | **~$0.08** |
| Pilot, 30 generations | 90 | ~$0.50 |
| Main run, 150 evaluations | 450 | ~$2.50 |
| Full study (main + 2 baselines + 3 ablations) | ~2,700 | ~$15 |

Well inside every ceiling in KICKOFF. As RESEARCH_DESIGN §3 predicted, the
mutation side dominates cost, not the judge side. The content-hash cache pushes
the real figures below these, since re-evaluating an unchanged portfolio costs
nothing.

Every real call writes its token counts and its cost — with the price table it
used — to `runs/ledger/judge_calls.jsonl`, so the ledger stays truthful even if
list prices change later.

## What this left open (resolved at M0)

1. **Provider** — resolved: `anthropic`. Only that backend is implemented. If
   you later want the OpenAI tier the paper used, the client is written against
   a provider-neutral interface and I can add it.
2. **Model** — resolved: `claude-haiku-4-5-20251001`.
3. **Whether determinism matters enough to constrain the tier** — resolved in
   favour of determinism. The judge is pinned and temperature 0, at the cost of
   being a cheap-tier model. That trade is the design's own ("cheap, frozen,
   boring", §2.2) and needs no defence beyond it.

## The judge-swap check is unaffected

RESEARCH_DESIGN §4 calls for re-scoring the top-20 archive with a second frozen
judge from a different model family. That check needs a *different* judge, not
a *temperature-0* one, so it is unaffected by any of the above. Choosing a
second family is an M4 decision.
