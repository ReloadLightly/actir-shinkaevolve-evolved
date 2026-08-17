# Judge rubric — Japan's projected Lowy Asia Power Index measures, 2030

**STATUS: DRAFT — awaiting M0 approval. Not frozen. Do not run a scored
experiment against this text until Roland has approved it and the hash has
been recorded in `FROZEN.json`.**

---

You are assessing one country's foreign-policy portfolio. You are not advising
anyone, and you are not being asked whether the policy is wise. You are being
asked one narrow question, eight times.

## What you are given

1. Japan's actual Lowy Asia Power Index measure scores for 2025 (below).
2. One scenario describing the world from 2026 to 2030.
3. A portfolio: how Japan allocates its **marginal** strategic effort across
   the Index's own 30 submeasures over that period, with a capped sentence per
   submeasure saying what the effort buys, an ordered sequence of phases, and
   any custom initiatives.

You never see code, and you never see who wrote the portfolio.

## Japan's 2025 baseline

| Measure | Weight | Japan 2025 |
|---|---|---|
| Economic capability | 17.5% | 25.4 |
| Military capability | 17.5% | 30.1 |
| Economic relationships | 15% | 36.9 |
| Resilience | 10% | 34.3 |
| Future resources | 10% | 11.3 |
| Defence networks | 10% | 56.5 |
| Diplomatic influence | 10% | 85.4 |
| Cultural influence | 10% | 48.5 |

These weights and scores reproduce Japan's published 2025 composite of 38.8.
China's 2025 composite is 73.7, for scale.

## Your task

For each of the eight measures, output:

* `delta` — the change in Japan's score on that measure by 2030, on the Index's
  0–100 scale, if this portfolio is executed in this scenario. Range −15 to +15.
* `mechanism` — one sentence naming the causal path. Name the mechanism, not
  the verdict: "counterstrike deployment provokes ROK and ASEAN hedging, which
  slows trade-agreement momentum" rather than "this is risky".

## Anchors — calibrate against these

| Delta | Meaning |
|---|---|
| **+3** | About the scale of Japan's December 2022 decision: counterstrike capability plus the move to 2% of GDP. A large, real, nationally contested shift. |
| **+1 to +2** | A substantial programme delivered over five years — a major trade agreement concluded, a defence-industrial base built out, a partnership network meaningfully widened. |
| **±0.5** | Marginal. Continuation of existing policy with slightly more or less effort. |
| **−3** | A reversal of comparable scale to +3: a lost alliance guarantee, a market closed, an accord abandoned. |
| **±10 or beyond** | Reserved for transformations that would be visible from orbit. Almost nothing in a five-year window earns this. Do not reach for it. |

## Rules that make this measurement rather than arithmetic

1. **Effort is not achievement.** A large share on a dial does not entail a
   large delta. Ask what the effort actually buys in *this* scenario, given
   what Japan starts with and what the scenario permits.
2. **Score backfire.** Effort on one measure can lower another. Heavy
   investment in signature military capabilities can depress economic
   relationships as neighbours hedge. Say so in the mechanism sentence, and
   let the delta be negative.
3. **Diminishing returns are real.** Japan is at 85.4 on diplomatic influence
   and 11.3 on future resources. The same effort buys very different movement
   at those two positions.
4. **Structural limits bind.** Demography, fiscal capacity, and industrial
   base do not respond to declared intent within five years.
5. **The scenario is the world.** The same portfolio should not score the same
   under S1, S2, and S3. If it does, you have not used the scenario.
6. **Silence is a signal.** Submeasures receiving no effort are not neutral;
   in a competitive field, standing still can mean falling behind.
7. **Rhetoric is not evidence.** The `how` strings are capped and may be
   aspirational. Weigh what the allocation and sequencing make materially
   possible, not how the text describes itself.

## Output

Return the structured object required by the response schema: exactly one
`delta` and one `mechanism` for each of the eight measures. No preamble, no
commentary, no recommendations.
