"""Behaviour descriptors: what a portfolio *is*, computed exactly and for free.

The lesson of `docs/ALPHAEVOLVE_COMPARISON.md` in one module. Every AlphaEvolve
success rested on a cheap exact evaluator; ours rests on an LLM's opinion, whose
resolution M1 measured at 0.696 effect against 0.921 noise. The response is not
to abandon the judge but to **put the exact thing in the loop wherever one
exists** — and where a portfolio *sits* in policy space is exactly computable,
deterministic, and costs nothing.

These descriptors are what make MAP-Elites possible here. MAP-Elites is the
algorithm for precisely our situation, because it never needs a global ranking:
it asks only "is this better than the current occupant of *this* cell", a local
comparison between portfolios that are already behaviourally similar. Coverage —
its primary output, and ours — does not depend on the judge's ranking at all.

## Choosing the axes

The two defaults are not arbitrary. They are the axes along which Japanese
strategic thought actually divides, so a filled grid is a readable map of the
debate rather than an arbitrary projection:

* **hard power** — share of marginal effort on military capability. The axis
  running from accommodation to autonomous rearmament.
* **alliance reliance** — share on defence networks. The autonomy axis: whether
  Japan's security is bought through Washington and its lattice of partners, or
  built at home.

Those two produce the recognisable quadrants. Low/low is accommodation.
High/high is the December 2022 mainstream. **High military with low alliance is
autonomous rearmament** — and low military with high alliance is the cheap-ride
posture Japan actually held until 2022.

A third axis, `civilian_power`, is available for 3-D grids: the combined share
on economic relationships, diplomatic influence and cultural influence.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

from lowy import DIALS, MEASURES


def effort_by_measure(portfolio: Mapping[str, Any]) -> Dict[str, float]:
    """Share of marginal effort per Lowy measure, from a canonical dict."""
    totals = {m: 0.0 for m in MEASURES}
    for entry in portfolio.get("dials", []) or []:
        dial = entry.get("dial")
        if dial in DIALS:
            try:
                totals[dial.split(".", 1)[0]] += float(entry.get("share", 0.0))
            except (TypeError, ValueError):
                continue
    return totals


def concentration(portfolio: Mapping[str, Any]) -> float:
    """Herfindahl index over the 30 dials. 1/30 is even, 1.0 is all-in."""
    total = 0.0
    for entry in portfolio.get("dials", []) or []:
        try:
            total += float(entry.get("share", 0.0)) ** 2
        except (TypeError, ValueError):
            continue
    return total


# --------------------------------------------------------------------------
# The descriptor registry
# --------------------------------------------------------------------------

#: name -> (extractor, lower bound, upper bound, one-line meaning)
#:
#: Bounds are what the GRID spans, not what the schema permits. A portfolio may
#: legally put 0.9 on military capability; it will land in the top bin. Bounds
#: are chosen so the interesting range is resolved rather than compressed into
#: one cell — no real doctrine spends 90% on one measure, and a grid sized for
#: that possibility would waste almost all of its cells on empty extremes.
DESCRIPTORS: Dict[str, Tuple[Callable[[Mapping[str, Any]], float], float, float, str]] = {
    "hard_power": (
        lambda p: effort_by_measure(p)["military_capability"],
        0.0, 0.50,
        "effort on military capability — accommodation at one end, "
        "autonomous rearmament at the other",
    ),
    "alliance_reliance": (
        lambda p: effort_by_measure(p)["defence_networks"],
        0.0, 0.30,
        "effort on defence networks — security bought through Washington and "
        "its partner lattice, versus built at home",
    ),
    "civilian_power": (
        lambda p: sum(effort_by_measure(p)[m] for m in (
            "economic_relationships", "diplomatic_influence", "cultural_influence")),
        0.0, 0.60,
        "effort on trade, diplomacy and culture — the non-military instruments",
    ),
    "long_game": (
        lambda p: effort_by_measure(p)["future_resources"],
        0.0, 0.35,
        "effort on future resources — Japan's weakest measure at 11.3, and the "
        "one with the most headroom",
    ),
    "concentration": (
        concentration,
        1.0 / len(DIALS), 0.25,
        "Herfindahl over the 30 dials — a focused bet versus a spread one",
    ),
}

#: The 2-D default. See the module docstring for why these two.
DEFAULT_AXES: Tuple[str, ...] = ("hard_power", "alliance_reliance")


def describe(portfolio: Mapping[str, Any],
             axes: Sequence[str] = DEFAULT_AXES) -> Tuple[float, ...]:
    """The raw descriptor values for one portfolio."""
    return tuple(DESCRIPTORS[name][0](portfolio) for name in axes)


def cell(portfolio: Mapping[str, Any],
         axes: Sequence[str] = DEFAULT_AXES,
         bins: int = 8) -> Tuple[int, ...]:
    """Which grid cell a portfolio occupies.

    Values outside the axis bounds clamp to the edge bins rather than being
    dropped: a portfolio that spends 90% on military capability is still a real
    portfolio and still belongs on the map, at the extreme.
    """
    coords = []
    for name, value in zip(axes, describe(portfolio, axes)):
        _extract, low, high, _doc = DESCRIPTORS[name]
        span = high - low
        index = int((value - low) / span * bins) if span > 0 else 0
        coords.append(max(0, min(bins - 1, index)))
    return tuple(coords)


def cell_bounds(axis: str, index: int, bins: int = 8) -> Tuple[float, float]:
    """The value range one bin covers, for labelling a figure."""
    _extract, low, high, _doc = DESCRIPTORS[axis]
    width = (high - low) / bins
    return (low + index * width, low + (index + 1) * width)


def total_cells(axes: Sequence[str] = DEFAULT_AXES, bins: int = 8) -> int:
    return bins ** len(axes)


def describe_axes(axes: Sequence[str] = DEFAULT_AXES) -> List[Dict[str, Any]]:
    """Axis metadata, for reports and manifests."""
    return [
        {"name": name, "low": DESCRIPTORS[name][1], "high": DESCRIPTORS[name][2],
         "meaning": DESCRIPTORS[name][3]}
        for name in axes
    ]
