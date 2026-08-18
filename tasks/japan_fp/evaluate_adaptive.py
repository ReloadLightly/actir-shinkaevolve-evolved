"""Run a policy through worlds and score it. The fitness function for Project B.

Deterministic given (policy, world, seed), with no API call anywhere. That is
the architectural inversion: the objective is a model we wrote and can inspect,
and the LLM is confined to writing candidate policies.

The word "exact" is not used. A review of 2026-08-19 was right that circle
packing has mathematical constraints while foreign-policy consequences have
contested causal ones. This gives repeatability, not truth.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from instruments import BY_ID, INSTRUMENT_IDS
from observation import CHANNELS, Observation, ObservationChannel
from splits import EPISODE_REPEATS
from world import (
    YEARS,
    WorldParams,
    WorldState,
    actir_model_score,
    initial_state,
    step,
)

#: A policy is a callable (Observation, memory dict) -> {instrument: delta}.
Policy = Callable[[Observation, Dict[str, Any]], Mapping[str, float]]


@dataclass
class Episode:
    """One policy through one world."""

    score: float
    trajectory: List[Dict[str, Any]] = field(default_factory=list)
    crises: int = 0
    final_state: Optional[WorldState] = None


def run_episode(policy: Policy, params: WorldParams, seed: int,
                channel_name: str = "normal",
                start_levels: Optional[Mapping[str, float]] = None,
                keep_trajectory: bool = False) -> Episode:
    """Five years of decisions in one world.

    `seed` fixes the crisis draws, economic shocks and observation noise, so two
    arms evaluated on the same (world, seed) face the IDENTICAL world. That is
    what makes the comparisons paired.
    """
    rng = random.Random(seed)
    obs_rng = random.Random(seed + 1_000_003)

    if channel_name == "shuffled":
        # Build the swap pool from a dry run so the shuffled values come from
        # the right distribution, just the wrong year.
        pool = _observation_pool(params, seed)
        channel = CHANNELS["shuffled"](obs_rng, pool)
    else:
        channel = CHANNELS[channel_name](obs_rng)

    state = initial_state(start_levels)
    memory: Dict[str, Any] = {}
    trajectory: List[Dict[str, Any]] = []

    for _year in YEARS:
        obs = channel.observe(state)
        try:
            deltas = policy(obs, memory) or {}
        except Exception as exc:                       # noqa: BLE001
            # A policy that raises scores as if it did nothing that year, rather
            # than crashing the run. ShinkaEvolve will propose broken programs
            # and the search must survive them.
            deltas = {}
            trajectory.append({"year": state.year + 1, "policy_error": repr(exc)})
        state, record = step(state, params, deltas, rng)
        if keep_trajectory:
            trajectory.append(record)

    return Episode(score=actir_model_score(state),
                   trajectory=trajectory if keep_trajectory else [],
                   crises=state.crises_so_far, final_state=state)


def _observation_pool(params: WorldParams, seed: int) -> List[Dict[str, float]]:
    """World views a do-nothing policy would have seen, for the shuffle ablation."""
    rng = random.Random(seed)
    obs_rng = random.Random(seed + 1_000_003)
    channel = ObservationChannel(obs_rng)
    state = initial_state()
    pool = []
    for _year in YEARS:
        obs = channel.observe(state)
        pool.append({
            "us_commitment": obs.us_commitment,
            "china_coercion": obs.china_coercion,
            "partner_alignment": obs.partner_alignment,
            "economic_conditions": obs.economic_conditions,
        })
        state, _ = step(state, params, {}, rng)
    return pool


@dataclass
class Result:
    """A policy's performance over a bank of worlds."""

    mean: float
    #: Conditional value at risk: the mean of the worst `cvar_fraction` of
    #: worlds. Review point 8 asked for tail risk, and for a strategy paper it
    #: is arguably the number that matters more than the mean -- a posture that
    #: is excellent on average and catastrophic in 10% of futures is not a
    #: posture any government would adopt.
    cvar: float
    worst: float
    per_world: List[float] = field(default_factory=list)
    crises: float = 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {"mean": round(self.mean, 4), "cvar": round(self.cvar, 4),
                "worst": round(self.worst, 4), "crises": round(self.crises, 3),
                "n": len(self.per_world)}


CVAR_FRACTION = 0.20


def evaluate(policy: Policy, worlds: Sequence[WorldParams],
             base_seed: int = 0, channel_name: str = "normal",
             repeats: int = EPISODE_REPEATS,
             start_levels: Optional[Mapping[str, float]] = None) -> Result:
    """Score a policy across a bank. Per-world scores are averaged over repeats."""
    per_world: List[float] = []
    crises: List[float] = []
    for index, params in enumerate(worlds):
        runs = [run_episode(policy, params, base_seed + index * 97 + r,
                            channel_name, start_levels)
                for r in range(max(1, repeats))]
        per_world.append(statistics.fmean(e.score for e in runs))
        crises.append(statistics.fmean(e.crises for e in runs))

    ordered = sorted(per_world)
    tail = max(1, int(len(ordered) * CVAR_FRACTION))
    return Result(
        mean=statistics.fmean(per_world),
        cvar=statistics.fmean(ordered[:tail]),
        worst=ordered[0],
        per_world=per_world,
        crises=statistics.fmean(crises) if crises else 0.0,
    )


# --------------------------------------------------------------------------
# Paired comparison. Review point 8: paired differences, confidence intervals.
# --------------------------------------------------------------------------


@dataclass
class Comparison:
    """A vs B on identical worlds."""

    mean_difference: float
    ci_low: float
    ci_high: float
    win_rate: float
    n: int

    @property
    def significant(self) -> bool:
        """The interval excludes zero. Not 'A is better', but 'the difference
        is larger than the bank's own variation'."""
        return self.ci_low > 0.0 or self.ci_high < 0.0

    def as_dict(self) -> Dict[str, Any]:
        return {"mean_difference": round(self.mean_difference, 4),
                "ci95": [round(self.ci_low, 4), round(self.ci_high, 4)],
                "win_rate": round(self.win_rate, 4),
                "significant": self.significant, "n": self.n}


def compare(a: Result, b: Result, bootstrap: int = 2000,
            seed: int = 12345) -> Comparison:
    """Paired bootstrap of (a - b) over the same worlds.

    Paired, because both arms saw the identical world bank with identical
    crisis draws. The unpaired difference of two means would be swamped by
    variation between worlds, which is large and entirely irrelevant to which
    policy is better.
    """
    if len(a.per_world) != len(b.per_world) or not a.per_world:
        raise ValueError("paired comparison needs equal, non-empty banks")
    diffs = [x - y for x, y in zip(a.per_world, b.per_world)]
    n = len(diffs)
    rng = random.Random(seed)
    means = []
    for _ in range(bootstrap):
        means.append(statistics.fmean(diffs[rng.randrange(n)] for _ in range(n)))
    means.sort()
    return Comparison(
        mean_difference=statistics.fmean(diffs),
        ci_low=means[int(0.025 * bootstrap)],
        ci_high=means[int(0.975 * bootstrap) - 1],
        win_rate=sum(1 for d in diffs if d > 0) / n,
        n=n,
    )
