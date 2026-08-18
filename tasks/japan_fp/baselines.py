"""The comparators. Getting these right is most of what makes B an experiment.

A review of 2026-08-19 made the point that decides this file's shape:

> Best constant is too weak a comparator. Add a best **open-loop five-year
> schedule**. Otherwise an "adaptive" program can win merely because it changes
> actions by year without using observations.

Exactly right, and it would have invalidated the headline. So the ladder is:

| policy class | varies over time? | reads observations? | parameters |
|---|---|---|---|
| `constant` | no | no | 21 |
| `open_loop` | **yes** | no | 105 |
| `linear_feedback` | yes | **yes** | 105 |
| `oracle_open_loop` | yes | no, but knows the hidden world | 105 per world |

`open_loop` and `linear_feedback` carry the **same number of parameters** on
purpose. If the adaptive class won only because it had more capacity, that
would be a fact about model size and not about observation, and matching the
counts removes the confound before it arises.

**The headline statistic of the whole project is the paired held-out difference
between an observation-using policy and the best open-loop schedule.** Everything
else is context for that number.

`oracle_open_loop` is the upper bound: a schedule optimised separately for each
world, with the hidden parameters known. No observation-using policy can beat it
by inference alone, so the gap between it and `open_loop` is the total value of
knowing the world, and the gap between `linear_feedback` and `open_loop` is how
much of that a policy actually recovers from noisy, lagged evidence.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from instruments import BY_ID, INSTRUMENT_IDS
from observation import Observation
from world import YEARS, inertia_cap

N = len(INSTRUMENT_IDS)

#: The observation features a feedback policy may condition on. Deliberately
#: few and interpretable: an evolved program can invent richer ones, and the
#: point of this class is to be a STRONG SIMPLE baseline, not to be clever.
#: If a handful of linear rules already saturate the attainable performance,
#: the review's termination criterion applies and evolution has nothing to add.
FEATURES: Tuple[str, ...] = (
    "us_commitment",        # is the ally leaving?
    "china_coercion",       # is pressure rising?
    "partner_alignment",    # is the lattice holding?
    "economic_conditions",  # can we afford it?
)


def _features(obs: Observation) -> List[float]:
    return [
        obs.us_commitment - 0.70,        # centred on the 2025 starting values,
        obs.china_coercion - 0.45,       # so a zero-weight policy is the base
        obs.partner_alignment - 0.50,    # vector and nothing else
        obs.economic_conditions - 0.55,
    ]


def _approach(target: Sequence[float], obs: Observation) -> Dict[str, float]:
    """Move each instrument toward its target, letting inertia do the limiting.

    Policies express a DESTINATION, not a step. The world clips the step to the
    inertia cap, so a policy cannot accidentally out-run the physics and does
    not have to model it.
    """
    out: Dict[str, float] = {}
    for index, ident in enumerate(INSTRUMENT_IDS):
        want = max(0.0, min(1.0, target[index]))
        out[ident] = want - obs.instrument_level[ident]
    return out


# --------------------------------------------------------------------------
# The classes
# --------------------------------------------------------------------------


def constant_policy(theta: Sequence[float]):
    """One target vector, held for five years. 21 parameters."""
    target = list(theta[:N])

    def policy(obs: Observation, memory: Dict[str, Any]) -> Dict[str, float]:
        return _approach(target, obs)

    return policy


def open_loop_policy(theta: Sequence[float]):
    """A different target vector each year. Reads nothing. 5 x 21 parameters.

    THE comparator. Anything that beats a constant policy merely by having a
    trajectory beats this one too, so the difference between this and an
    observation-using policy isolates the value of information.
    """
    schedule = [list(theta[y * N:(y + 1) * N]) for y in range(len(YEARS))]

    def policy(obs: Observation, memory: Dict[str, Any]) -> Dict[str, float]:
        index = min(len(schedule) - 1, max(0, obs.year - YEARS[0]))
        return _approach(schedule[index], obs)

    return policy


def linear_feedback_policy(theta: Sequence[float]):
    """Base vector plus linear response to observed features. 21 + 21*4 = 105.

    Matched in parameter count to `open_loop_policy` so the comparison is about
    observation and not about capacity.
    """
    base = list(theta[:N])
    gains = [list(theta[N + k * N:N + (k + 1) * N]) for k in range(len(FEATURES))]

    def policy(obs: Observation, memory: Dict[str, Any]) -> Dict[str, float]:
        feats = _features(obs)
        target = []
        for i in range(N):
            value = base[i]
            for k, f in enumerate(feats):
                value += gains[k][i] * f
            target.append(value)
        return _approach(target, obs)

    return policy


#: Parameter counts, so an optimiser can size its search without knowing the
#: internals and a test can assert the matching.
DIMENSIONS: Dict[str, int] = {
    "constant": N,
    "open_loop": N * len(YEARS),
    "linear_feedback": N + N * len(FEATURES),
}

BUILDERS = {
    "constant": constant_policy,
    "open_loop": open_loop_policy,
    "linear_feedback": linear_feedback_policy,
}


def december_2022_policy():
    """The human baseline: Japan's actual posture, held constant.

    Read from the instrument seed so there is one definition of December 2022
    in the repository rather than two that can drift apart.
    """
    import initial_instruments

    levels = dict(initial_instruments.build_policy().instruments)
    target = [levels.get(ident, 0.0) for ident in INSTRUMENT_IDS]
    return constant_policy(target)


DECEMBER_2022_THETA: List[float] = []


def december_2022_theta() -> List[float]:
    global DECEMBER_2022_THETA
    if not DECEMBER_2022_THETA:
        import initial_instruments

        levels = dict(initial_instruments.build_policy().instruments)
        DECEMBER_2022_THETA = [levels.get(i, 0.0) for i in INSTRUMENT_IDS]
    return list(DECEMBER_2022_THETA)
