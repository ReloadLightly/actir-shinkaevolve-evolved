# Note for M0: "temperature 0" constrains which judge models are available

**Status: a finding, not a decision. The judge model is yours to choose
(RESEARCH_DESIGN §8). This note exists so the choice is made with the
constraint visible.**

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

`configs/judge.yaml` proposes:

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

## Decisions this leaves you

1. **Provider.** Only `anthropic` has an implemented backend. If you would
   rather use the OpenAI tier the paper used, say so and I will add that
   backend — the client is written against a provider-neutral interface.
2. **Model.** The default above is a proposal.
3. **Whether determinism matters enough** to constrain the tier at all. If you
   would rather have a stronger judge and accept sampling you cannot pin, that
   is a defensible trade — but it belongs in the limitations section, next to
   the oracle problem.

## The judge-swap check is unaffected

RESEARCH_DESIGN §4 calls for re-scoring the top-20 archive with a second frozen
judge from a different model family. That check needs a *different* judge, not
a *temperature-0* one, so it is unaffected by any of the above. Choosing a
second family is an M4 decision.
