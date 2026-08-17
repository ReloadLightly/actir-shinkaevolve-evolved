# Judge rubric — Japan's projected Lowy Asia Power Index measures, 2030

**STATUS: DRAFT, revision 2 — corrected after the M1 calibration run of
2026-08-17 (`docs/M1_FINDINGS.md`). Awaiting re-approval. Not frozen.**

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

### What your deltas are worth

Your per-measure deltas are aggregated with the weights above:

```
composite = sum over measures of  weight x clip(2025 score + your delta, 0, 100)
```

So the arithmetic you are feeding, at the weights above:

| Your delta | On military or economic capability (17.5%) | On a 10% measure |
|---|---|---|
| ±1 | ±0.175 composite | ±0.10 composite |
| ±3 | ±0.525 composite | ±0.30 composite |
| ±10 | ±1.75 composite | ±1.00 composite |

Japan's whole composite is 38.8. A portfolio you judge to be a large, real
national shift therefore moves the headline number by well under one point.
That is expected and correct — do not inflate deltas to make the total look
decisive. But it does mean small differences between your per-measure deltas
survive into the result, so **give two different portfolios two different
numbers when they differ, and the same number only when they genuinely do
not.** Reflexively assigning every plausible policy a similar positive delta
on a measure erases the only signal there is.

## This is one scenario of three

The same portfolio is scored separately under three fixed futures. You are
seeing exactly one of them, named below. You will not see your answers for the
other two.

| | |
|---|---|
| **S1 — Grinding status quo** | Competition without rupture. Incremental grey-zone pressure, no crisis that forces a decision. Time and compounding matter; nothing is tested suddenly. |
| **S2 — Taiwan contingency** | A cross-strait quarantine escalating between 2027 and 2029. Regional disruption is immediate; deterrence, resilience and alliance mechanics are tested under fire. |
| **S3 — US retrenchment** | Washington turns transactional. The treaty holds on paper, but host-nation costs rise, extended deterrence reads as conditional, and every dependency becomes a liability. |

Because you see only one, the burden is on you to ask explicitly: **what does
*this* scenario permit, foreclose, or make expensive that the other two would
not?** A portfolio that would score alike in all three has not been read
against any of them. Where the scenario is what decides the answer, say so in
the mechanism sentence.

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
5. **The scenario is the world.** You see one scenario of three, described
   above. Before answering, name to yourself what this scenario does to Japan
   *irrespective of policy*, then ask what the portfolio can still buy inside
   it. A policy that is sound in S1 may be irrelevant in S2 and actively
   costly in S3.
6. **Silence is a signal.** Submeasures receiving no effort are not neutral;
   in a competitive field, standing still can mean falling behind.
7. **Rhetoric is not evidence.** The `how` strings are capped and may be
   aspirational. Weigh what the allocation and sequencing make materially
   possible, not how the text describes itself.
8. **Score against December 2022, not against zero.** Japan's 2025 baseline
   already contains the counterstrike decision, the move to 2% of GDP, the
   43-trillion-yen procurement plan, economic security legislation, and FOIP
   diplomacy. The portfolio in front of you is Japan's *marginal* effort on
   top of that. So the question is never "is this sensible" — it is **what
   does this portfolio buy, or lose, relative to simply continuing the 2022
   programme?** A portfolio that reproduces 2022 with different labels earns
   deltas near zero, however reasonable it reads.
9. **Price what is given up.** Shares sum to 1, so every increase is funded by
   a cut somewhere. Before setting a delta, look at which submeasures this
   portfolio has starved relative to the 2022 programme, and let that show up
   as a negative where it bites. A portfolio whose every measure moves upward
   has not been read as a budget.

## Output

Return the structured object required by the response schema: exactly one
`delta` and one `mechanism` for each of the eight measures. No preamble, no
commentary, no recommendations.
