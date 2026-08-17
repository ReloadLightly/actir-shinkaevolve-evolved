# M1 calibration, run #1 — findings

Run [32058962532](https://github.com/ReloadLightly/actir-shinkaevolve-evolved/actions/runs/32058962532),
2026-08-17. 30 real judge calls, $0.1869, 2m14s. Evidence artifact
`m1-evidence-32058962532` (34 files: full request/response cache, ledger, tables).

**Verdict: do not freeze the rubric, do not start the search.** M1 did exactly
what it was built to do, at 1.2% of the project budget.

---

## The headline, and a correction to it

Spearman rank correlation between `gpt-4.1-mini` and `gpt-4.1`: **−0.300**.

It is tempting to read that as "the judges chose almost opposite rankings".
They did not, and the difference matters for the fix. Item by item:

| Portfolio | mini | gpt-4.1 | |
|---|---|---|---|
| December 2022 | #2 | #2 | **identical** |
| Status-quo-plus | #3 | #3 | **identical** |
| Accommodation | #4 | #5 | off by one |
| Autonomous rearmament | #1 | #4 | **disagree** |
| Middle-power internationalism | #5 | #1 | **disagree** |

The judges agree exactly on the middle of the field. The −0.300 comes entirely
from the two extremes swapping ends. With n = 5, two items trading places is
enough to drive Spearman negative — the statistic is coarse at this size, and
−0.300 here means "no reliable agreement", not "systematic inversion". If it
were a true inversion we would see ≈ −1.0 and should suspect a sign error
somewhere. We do not.

## The real finding: the signal is smaller than the noise

| | |
|---|---|
| `gpt-4.1` total spread across all five doctrines | **0.696** |
| `gpt-4.1-mini` total spread | 1.200 |
| Inter-judge disagreement, mean / max | 0.437 / **0.921** |
| `gpt-4.1` spread across the middle three | **0.067** |

**The maximum disagreement between judges (0.921) is larger than the entire
range the stronger judge assigns to five deliberately opposite doctrines
(0.696).** On the middle three portfolios, noise exceeds signal by 14×:
`gpt-4.1` separates December 2022, Status-quo-plus and Autonomous rearmament by
0.067 composite points in total — rank 3 and rank 4 are 0.008 apart.

Ranks that turn on the third decimal place are not measurements. This is why
the correlation is low, and it would stay low with any pair of judges. The
ordering is not unstable because one judge is weak; it is unstable because
**there is almost nothing to order.**

## Why the range collapses

Arithmetic the judge is never shown:

```
a +3.0 delta on military capability   moves the composite by +0.525
a +3.0 delta on economic capability   moves the composite by +0.525
a +3.0 delta on economic relationships moves the composite by +0.450
```

The rubric's own top anchor — "+3 ≈ the December 2022 decision: counterstrike
plus 2% of GDP, a large, real, nationally contested shift" — is worth about
**half a composite point**. The judge is calibrating in per-measure units while
fitness lives in composite units, and nothing in the prompt connects the two.
So it produces sober, defensible per-measure deltas that aggregate into a
0.7-point band, and five incompatible visions of Japanese grand strategy come
out looking like rounding error.

The compression is visible directly in the per-measure table. Economic
capability, across five portfolios that allocate between 11% and 16% of effort
to it with completely different content:

```
+1.67   +1.33   +1.50   +1.33   +1.50
```

Five near-identical numbers. The judge is scoring "is this a sensible policy"
rather than "what does *this* portfolio buy that the others do not".

## The structural bug: rule 5 asks for something impossible

Rubric rule 5 reads:

> **The scenario is the world.** The same portfolio should not score the same
> under S1, S2, and S3. If it does, you have not used the scenario.

**The judge cannot comply with this instruction.** Each call sends the rubric,
*one* scenario, and the portfolio (`JudgeClient._user_content`). The judge never
sees the other two scenarios, never sees what it scored under them, and has no
way to know what would count as "different". We asked for a comparison and
supplied one side of it.

The result is exactly what that predicts. Accommodation — the doctrine whose
entire logic turns on whether the United States stays — has the *smallest*
scenario spread of the five, 0.19. And it scores **worse** under S3 (US
retrenchment, 39.27) than under S2 (a Taiwan contingency, 39.44). That is
backwards on the substance: accommodation should be near-catastrophic when
China attacks anyway and comparatively rational when the ally leaves. The judge
is not using the scenarios because it structurally cannot.

## What did work

Worth recording, because these do not need fixing:

- **Score backfire (rule 2) lands.** Autonomous rearmament is charged
  −0.50 defence networks, −0.67 diplomatic influence, −0.83 economic
  relationships. Accommodation is charged −2.67 military capability. The judge
  is willing to make effort cost something.
- **The ±0.5 marginal anchor lands.** December 2022 and Status-quo-plus, the
  deliberate near-twins, come out 0.22 apart under mini. Correct behaviour.
- **Diminishing returns (rule 3) partially lands.** Middle-power gets +0.67 on
  diplomatic influence (Japan at 85.4, little headroom) and +1.17 on future
  resources (at 11.3, large headroom). Right direction, weak magnitude.

## The disagreement that is not a bug

Strip out the noise and one substantive disagreement remains: `mini` ranks
autonomous rearmament first and middle-power last; `gpt-4.1` reverses exactly
that pair. That is a real disagreement about whether military capability or
rule-making capacity buys more index points for Japan by 2030 — two defensible
world models, not a calibration error.

That one is **not** to be tuned away. If it survives the fixes below, it is a
finding for the paper: the oracle problem made concrete and measurable, which
is what RESEARCH_DESIGN §6.1 says the judge-swap check exists to expose. We
should report it, not suppress it.

## Proposed corrections

Targeted, in descending order of expected effect:

1. **Give the judge all three scenario names and one-line summaries**, and tell
   it which one it is scoring. Makes rule 5 actionable instead of impossible.
2. **Show the composite arithmetic in the rubric.** State that a ±3 per-measure
   delta is worth ≈ ±0.5 composite, so the judge can see the scale its answers
   land on.
3. **Require differentiation against the December 2022 programme**, which the
   judge already has in the baseline table. Ask what this portfolio buys *that
   the 2022 programme did not*, and what it gives up. Attacks the compression
   directly.
4. **Require a forgone-effort sentence.** The judge currently scores what is
   invested; the schema forces shares to sum to 1, so every gain is funded by a
   cut it is not being asked to price.

What is deliberately **not** proposed: widening the delta anchors to manufacture
range. Inflating deltas to make the numbers look decisive would fabricate
signal, and the resulting search would optimise an artefact. If after these
fixes the honest spread is still ~0.7, that is a real finding about the Lowy
composite as an objective — that it is insensitive to five-year policy variation
at this scale — and it belongs in the limitations section, not in a bigger
number.

## Re-test plan

The fixes touch `judge_prompt.md`, which is M0-approved and hash-recorded, so
this needs a version bump and your re-approval before any re-run.

The re-run should be the smallest thing that tests the fix, not another full
matrix:

| Test | Calls | Cost |
|---|---|---|
| Accommodation across S1–S3 on `gpt-4.1-mini` — does scenario spread appear? | 3 | ~$0.006 |
| If yes: all five on `gpt-4.1-mini` — did the range widen? | 15 | ~$0.030 |
| Only if that looks right: the `gpt-4.1` comparison again | 15 | ~$0.157 |

Total worst case ~$0.19, and the first step is under a cent. Spent so far:
$0.1869 of $15.
