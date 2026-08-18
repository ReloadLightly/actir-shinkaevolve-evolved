"""What Japan can see, and what it cannot.

The partial-observation half of Project B. Without it, "adaptive" would mean
only "time-varying", and a review of 2026-08-19 was right that a time-varying
open-loop schedule can beat a constant policy while reading nothing at all.
That is why the qualification's real comparator is the best OPEN-LOOP SCHEDULE,
and why this module exists: the gap between an observation-using policy and the
best schedule that ignores observations is the value of information, and it is
the only thing that makes the word "adaptive" mean anything.

Three rules, and each one is load-bearing:

* **Own state is exact.** A government knows its own budget and its own force
  structure.
* **The world is noisy and lagged.** Japan reads US commitment and Chinese
  coercion through diplomatic reporting and analysis, imperfectly and late.
* **The hidden parameters are never observed.** Whether American withdrawal is
  structural or cyclical, and whether Chinese coercion responds to Japanese
  rearmament, are exactly the questions no one can look up. They must be
  inferred from the trajectory, and inferring them is what memory is for.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from instruments import INSTRUMENT_IDS
from lowy import MEASURES
from world import OBSERVATION_LAG_YEARS, OBSERVATION_NOISE, WorldState


@dataclass(frozen=True)
class Observation:
    """One year's view. Everything a policy is allowed to condition on."""

    year: int
    #: Exact: Japan's own position.
    capability: Dict[str, float]
    instrument_level: Dict[str, float]
    fiscal_available: float
    political_available: float
    #: Noisy and lagged: the world.
    us_commitment: float
    china_coercion: float
    partner_alignment: float
    economic_conditions: float
    #: Observed without noise, because a crisis is not subtle.
    crisis_last_year: bool
    crises_so_far: int

    def as_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "capability": dict(self.capability),
            "instrument_level": dict(self.instrument_level),
            "fiscal_available": self.fiscal_available,
            "political_available": self.political_available,
            "us_commitment": self.us_commitment,
            "china_coercion": self.china_coercion,
            "partner_alignment": self.partner_alignment,
            "economic_conditions": self.economic_conditions,
            "crisis_last_year": self.crisis_last_year,
            "crises_so_far": self.crises_so_far,
        }


class ObservationChannel:
    """Produces observations from true states, with noise and lag.

    Holds the history so the lag is real rather than simulated by re-noising an
    old value: a policy that saw a value last year must see the SAME value this
    year, or the noise would average away and the lag would be free.
    """

    def __init__(self, rng: random.Random,
                 noise: float = OBSERVATION_NOISE,
                 lag: int = OBSERVATION_LAG_YEARS) -> None:
        self.rng = rng
        self.noise = noise
        self.lag = lag
        self._history: List[Dict[str, float]] = []

    def _noisy(self, value: float) -> float:
        if self.noise <= 0.0:
            return value
        return max(0.0, min(1.0, value + self.rng.gauss(0.0, self.noise)))

    def observe(self, state: WorldState) -> Observation:
        self._history.append({
            "us_commitment": self._noisy(state.us_commitment),
            "china_coercion": self._noisy(state.china_coercion),
            "partner_alignment": self._noisy(state.partner_alignment),
            "economic_conditions": self._noisy(state.economic_conditions),
        })
        index = max(0, len(self._history) - 1 - self.lag)
        seen = self._history[index]
        return Observation(
            year=state.year,
            capability=dict(state.capability),
            instrument_level=dict(state.instrument_level),
            fiscal_available=state.fiscal_available,
            political_available=state.political_available,
            us_commitment=seen["us_commitment"],
            china_coercion=seen["china_coercion"],
            partner_alignment=seen["partner_alignment"],
            economic_conditions=seen["economic_conditions"],
            crisis_last_year=state.crisis_active,
            crises_so_far=state.crises_so_far,
        )


# --------------------------------------------------------------------------
# Ablations. Review point 6: an evolved program's advantage must be shown to
# come from USING observations, not merely from being allowed to vary. These
# are the counterfactual channels that prove it.
# --------------------------------------------------------------------------


class ShuffledChannel(ObservationChannel):
    """Observations drawn from the right distribution but the wrong year.

    A policy genuinely conditioning on the world should lose its advantage
    here. One that is really an open-loop schedule in disguise will not notice.
    """

    def __init__(self, rng: random.Random, pool: List[Dict[str, float]],
                 **kwargs: Any) -> None:
        super().__init__(rng, **kwargs)
        self._pool = pool

    def observe(self, state: WorldState) -> Observation:
        base = super().observe(state)
        if not self._pool:
            return base
        swap = self._pool[self.rng.randrange(len(self._pool))]
        return Observation(
            year=base.year, capability=base.capability,
            instrument_level=base.instrument_level,
            fiscal_available=base.fiscal_available,
            political_available=base.political_available,
            us_commitment=swap["us_commitment"],
            china_coercion=swap["china_coercion"],
            partner_alignment=swap["partner_alignment"],
            economic_conditions=swap["economic_conditions"],
            crisis_last_year=base.crisis_last_year,
            crises_so_far=base.crises_so_far,
        )


class FrozenChannel(ObservationChannel):
    """Every year returns the first year's world view.

    Strictly weaker than shuffling: the policy is told the world never changes.
    An advantage that survives this was never about the world.
    """

    def __init__(self, rng: random.Random, **kwargs: Any) -> None:
        super().__init__(rng, **kwargs)
        self._first: Optional[Observation] = None

    def observe(self, state: WorldState) -> Observation:
        current = super().observe(state)
        if self._first is None:
            self._first = current
            return current
        return Observation(
            year=current.year, capability=current.capability,
            instrument_level=current.instrument_level,
            fiscal_available=current.fiscal_available,
            political_available=current.political_available,
            us_commitment=self._first.us_commitment,
            china_coercion=self._first.china_coercion,
            partner_alignment=self._first.partner_alignment,
            economic_conditions=self._first.economic_conditions,
            crisis_last_year=current.crisis_last_year,
            crises_so_far=current.crises_so_far,
        )


CHANNELS = {
    "normal": ObservationChannel,
    "frozen": FrozenChannel,
    "shuffled": ShuffledChannel,
}
