"""A deterministic, offline stand-in for the frozen judge.

**THIS IS NOT A WORLD MODEL AND ITS OUTPUT IS NOT A RESULT.** It is a test
double: a closed-form function from portfolio to deltas, with no LLM, no
network, and no claim to represent anything about Japan. Every verdict it
produces is stamped ``surrogate=True`` and every metric dict it reaches carries
``judge_surrogate: true``, so a surrogate run can never be mistaken for a
scored one.

## Why it exists

Until now nothing had ever run the evolution loop end to end. Two things
blocked it: mutations need an LLM (costs money), and the mock judge returns
all-zero deltas, so the search has no gradient to climb and every candidate
ties at 38.8475. A pipeline that has never run is a pipeline whose bugs are all
still in front of you, and finding them with real judge calls is the expensive
way round.

So the surrogate gives the loop a *shaped* landscape — one with genuine
trade-offs to discover — at zero cost and full reproducibility. What it
validates is the machinery: that mutation, the validity gate, aggregation, the
archive, lineage, and the analysis all work on data of the right shape. What it
cannot validate is whether the rubric is any good. Only the real judge does
that.

## The landscape it encodes

Four properties, chosen because each mirrors a rule the real rubric asks for,
so a search that exploits the surrogate is exercising the same shape of
trade-off the real judge is meant to impose:

1. **Diminishing returns.** Gain scales with remaining headroom, so effort on
   future resources (Japan at 11.3) buys far more than the same effort on
   diplomatic influence (85.4). Rubric rule 3.
2. **Backfire.** Concentrated military effort subtracts from economic
   relationships and defence networks as neighbours hedge. Rubric rule 2.
3. **Saturation.** Delta grows with the square root of effort share, so
   dumping everything on one dial pays much less than it costs elsewhere.
   Rubric rule 1, effort is not achievement.
4. **Scenario dependence.** Each scenario multiplies the measures differently,
   so the same portfolio genuinely scores differently under S1, S2 and S3.
   Rubric rule 5 — the one the real judge structurally could not follow.

The numbers below are invented. They are not calibrated against anything and
must never be reported as findings.
"""

from __future__ import annotations

import math
from typing import Dict, Mapping

from lowy import BASELINE_2025, DIALS, MEASURES, SCORE_MAX

#: How much each scenario rewards effort on each measure. Deliberately spread,
#: so scenario sensitivity is real rather than cosmetic.
SCENARIO_WEIGHTS: Dict[str, Dict[str, float]] = {
    # Competition without rupture: compounding favours the slow measures.
    "S1": {
        "economic_capability": 1.10, "military_capability": 0.85,
        "economic_relationships": 1.15, "resilience": 0.90,
        "future_resources": 1.30, "defence_networks": 1.00,
        "diplomatic_influence": 1.05, "cultural_influence": 1.10,
    },
    # Taiwan contingency: hard power and resilience are tested; soft power stalls.
    "S2": {
        "economic_capability": 0.80, "military_capability": 1.45,
        "economic_relationships": 0.55, "resilience": 1.40,
        "future_resources": 0.70, "defence_networks": 1.35,
        "diplomatic_influence": 0.85, "cultural_influence": 0.60,
    },
    # US retrenchment: autonomy and coalitions outside Washington gain value.
    "S3": {
        "economic_capability": 1.05, "military_capability": 1.15,
        "economic_relationships": 1.25, "resilience": 1.20,
        "future_resources": 1.10, "defence_networks": 0.60,
        "diplomatic_influence": 1.20, "cultural_influence": 1.05,
    },
}

#: Effort on the source measure subtracts from the targets. Neighbours hedge.
BACKFIRE: Dict[str, Dict[str, float]] = {
    "military_capability": {
        "economic_relationships": 0.55, "defence_networks": 0.25,
        "cultural_influence": 0.20,
    },
    "resilience": {"economic_relationships": 0.20},
}

#: Overall scale, chosen so a doctrine-sized reallocation moves a measure by a
#: few points — the same order the real rubric's +3 anchor describes.
GAIN = 11.0
BACKFIRE_GAIN = 9.0
DELTA_CLIP = 12.0


def _effort_by_measure(portfolio: Mapping[str, object]) -> Dict[str, float]:
    """Share of marginal effort per measure, from the canonical dict."""
    totals = {m: 0.0 for m in MEASURES}
    for entry in portfolio.get("dials", []) or []:  # type: ignore[union-attr]
        dial = entry.get("dial")  # type: ignore[union-attr]
        if dial in DIALS:
            try:
                totals[dial.split(".", 1)[0]] += float(entry.get("share", 0.0))  # type: ignore[union-attr]
            except (TypeError, ValueError):
                continue
    return totals


def surrogate_deltas(
    scenario_id: str, portfolio: Mapping[str, object]
) -> Dict[str, float]:
    """Deterministic per-measure deltas. Same input always gives same output."""
    effort = _effort_by_measure(portfolio)
    weights = SCENARIO_WEIGHTS.get(scenario_id, SCENARIO_WEIGHTS["S1"])

    deltas: Dict[str, float] = {}
    for measure in MEASURES:
        share = max(0.0, effort.get(measure, 0.0))
        # Saturating in effort, and proportional to remaining headroom.
        headroom = (SCORE_MAX - BASELINE_2025[measure]) / SCORE_MAX
        deltas[measure] = GAIN * math.sqrt(share) * headroom * weights[measure]

    for source, targets in BACKFIRE.items():
        share = max(0.0, effort.get(source, 0.0))
        for target, strength in targets.items():
            deltas[target] -= BACKFIRE_GAIN * strength * (share ** 1.5)

    return {m: max(-DELTA_CLIP, min(DELTA_CLIP, round(v, 4))) for m, v in deltas.items()}


def surrogate_mechanisms(
    scenario_id: str, deltas: Mapping[str, float]
) -> Dict[str, str]:
    return {
        m: (
            f"SURROGATE (not a judgement): closed-form score for {scenario_id}, "
            f"headroom- and saturation-weighted, delta {deltas[m]:+.2f}."
        )
        for m in MEASURES
    }
