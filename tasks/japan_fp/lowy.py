"""Lowy Asia Power Index constants: measures, submeasure dials, weights, baseline.

Nothing in this module is invented by this project. The 8 measures, the 30
submeasures, the published weights and Japan's 2025 measure scores are taken
from the Lowy Institute Asia Power Index (2025 edition, methodology page and
Japan country page), as recorded in RESEARCH_DESIGN.md sections 2.1 and 2.2.

The design rule (RESEARCH_DESIGN section 2.1): the same authority that defines
the objective also defines the coordinate system.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------
# The 8 measures and their published weights (RESEARCH_DESIGN section 2.2).
# --------------------------------------------------------------------------

MEASURES: Tuple[str, ...] = (
    "economic_capability",
    "military_capability",
    "economic_relationships",
    "resilience",
    "future_resources",
    "defence_networks",
    "diplomatic_influence",
    "cultural_influence",
)

WEIGHTS: Dict[str, float] = {
    "economic_capability": 0.175,
    "military_capability": 0.175,
    "economic_relationships": 0.150,
    "resilience": 0.100,
    "future_resources": 0.100,
    "defence_networks": 0.100,
    "diplomatic_influence": 0.100,
    "cultural_influence": 0.100,
}

# Japan, Asia Power Index 2025 edition, per-measure scores on the 0-100 scale.
# Listed in RESEARCH_DESIGN section 2.2 in the same order as the weights above.
BASELINE_2025: Dict[str, float] = {
    "economic_capability": 25.4,
    "military_capability": 30.1,
    "economic_relationships": 36.9,
    "resilience": 34.3,
    "future_resources": 11.3,
    "defence_networks": 56.5,
    "diplomatic_influence": 85.4,
    "cultural_influence": 48.5,
}

# Japan's published 2025 composite. The weighted sum above is 38.8475, which is
# 38.8 at the index's one-decimal reporting precision.
JAPAN_2025_COMPOSITE: float = 38.8
COMPOSITE_DECIMALS: int = 1

# China 2025, kept only as the scale reference quoted in RESEARCH_DESIGN.
CHINA_2025_COMPOSITE: float = 73.7

# --------------------------------------------------------------------------
# The 30 submeasure dials (RESEARCH_DESIGN section 2.1, verbatim from the
# Lowy methodology). A dial id is "<measure>.<submeasure>".
# --------------------------------------------------------------------------

SUBMEASURES: Dict[str, Tuple[str, ...]] = {
    "economic_capability": (
        "size",
        "international_leverage",
        "technology",
        "connectivity",
    ),
    "military_capability": (
        "defence_spending",
        "armed_forces",
        "weapons_and_platforms",
        "signature_capabilities",
        "asian_military_posture",
    ),
    "resilience": (
        "internal_stability",
        "resource_security",
        "geoeconomic_security",
        "geopolitical_security",
        "nuclear_deterrence",
    ),
    "future_resources": (
        "economic_resources_2035",
        "defence_resources_2035",
        "broad_resources_2035",
        "demographic_resources_2050",
    ),
    "economic_relationships": (
        "regional_trade_relations",
        "regional_investment_ties",
        "economic_diplomacy",
    ),
    "defence_networks": (
        "regional_alliance_network",
        "regional_defence_diplomacy",
        "global_defence_partnerships",
    ),
    "diplomatic_influence": (
        "diplomatic_network",
        "multilateral_power",
        "foreign_policy",
    ),
    "cultural_influence": (
        "cultural_projection",
        "information_flows",
        "people_exchanges",
    ),
}


def _build_dial_ids() -> Tuple[str, ...]:
    dial_ids: List[str] = []
    for measure in MEASURES:
        for submeasure in SUBMEASURES[measure]:
            dial_ids.append(f"{measure}.{submeasure}")
    return tuple(dial_ids)


# Canonical order: measures in weight-table order, submeasures in Lowy order.
DIALS: Tuple[str, ...] = _build_dial_ids()
N_DIALS: int = len(DIALS)

# Delta range the judge may return per measure (RESEARCH_DESIGN section 2.2).
DELTA_MIN: float = -15.0
DELTA_MAX: float = 15.0

# Index score bounds.
SCORE_MIN: float = 0.0
SCORE_MAX: float = 100.0


def measure_of(dial_id: str) -> str:
    """Return the measure a dial belongs to. Raises KeyError for unknown dials."""
    measure = dial_id.split(".", 1)[0]
    if dial_id not in DIALS:
        raise KeyError(f"unknown dial id: {dial_id!r}")
    return measure


def composite(scores: Dict[str, float]) -> float:
    """Lowy's own weighted sum over the 8 measures. No rounding applied."""
    missing = [m for m in MEASURES if m not in scores]
    if missing:
        raise KeyError(f"missing measure scores: {missing}")
    return sum(WEIGHTS[m] * float(scores[m]) for m in MEASURES)


# --------------------------------------------------------------------------
# MODELLING ASSUMPTION, stated 2026-08-18 after review.
#
# Lowy's Asia Power Index is a RELATIVE, distance-to-frontier comparison across
# 27 countries and 131 indicators: a country's score depends on where every
# other country sits. https://power.lowyinstitute.org/methodology/
#
# What we do below is NOT that procedure. We add an LLM-estimated delta to
# Japan's fixed 2025 measure scores and re-apply Lowy's published weights, with
# all 26 other countries held implicit and unchanged. Only the WEIGHTS are
# genuinely Lowy's; the projection is ours.
#
# So a number out of composite_with_deltas is "Japan's 2030 composite under our
# model of how this portfolio moves Japan's own measures", and must never be
# reported as "Japan's projected Lowy score". In particular it cannot capture
# the relative effects that dominate a real Index movement -- China slowing,
# India rising, a partner's capability shifting the frontier.
# --------------------------------------------------------------------------


def composite_with_deltas(deltas: Dict[str, float]) -> float:
    """composite(s) = sum_m w_m * clip(b_m + delta_m, 0, 100).

    This is the aggregation formula of RESEARCH_DESIGN section 2.2. Deltas for
    measures the judge did not mention are treated as 0.
    """
    projected = {
        m: min(SCORE_MAX, max(SCORE_MIN, BASELINE_2025[m] + float(deltas.get(m, 0.0))))
        for m in MEASURES
    }
    return composite(projected)


def projected_scores(deltas: Dict[str, float]) -> Dict[str, float]:
    """Per-measure projected 2030 scores after clipping, for reporting."""
    return {
        m: min(SCORE_MAX, max(SCORE_MIN, BASELINE_2025[m] + float(deltas.get(m, 0.0))))
        for m in MEASURES
    }
