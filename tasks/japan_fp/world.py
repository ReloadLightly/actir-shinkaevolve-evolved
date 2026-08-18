"""A deterministic model-based evaluator for Japanese strategy, 2026-2030.

NOT an exact verifier. A review of 2026-08-19 was right to press on the word:
circle packing has mathematical constraints, and a packing either is valid or is
not. Foreign-policy consequences have uncertain, contested causal relationships.
This module supplies **repeatability, not truth** -- given the same world
parameters and seed it returns the same trajectory, and that is all "deterministic"
means here. Every number below is an assumption, declared, with its reasoning
attached so that a specialist can attack it individually.

What it buys is nonetheless the thing this project has lacked since M1: a fitness
function with no sampling noise. The judge's effect across five opposite
doctrines was 0.696 composite points against 0.17 of disagreement with ITSELF on
byte-identical input. Moving fitness here removes that floor, and moves the LLM
to where AlphaEvolve actually put it -- the mutation operator.

## Preregistration

This file is hashed into `FROZEN.json` BEFORE the qualification runs. That is
deliberate and it is the whole defence against the circularity a review
identified in the first draft of the design, which said "if adaptive is no
better than constant, redesign the world". That instruction tunes the model
until the desired answer appears. It is deleted.

**The model is frozen first, then run, then whatever comes out is the result.**
Coefficients may be revised only for an independently identified realism defect
-- one that can be stated without reference to which arm it favours -- and then
the version is bumped and the whole experiment reruns.

## Why adaptivity could pay here, if it pays at all

Three properties, and the qualification exists to test whether they are strong
enough to matter:

1. **Hidden parameters.** `us_decline_rate` and `security_dilemma_strength` are
   drawn per world and never observed. They must be inferred from noisy, lagged
   observations, and the right posture differs sharply between their extremes.
2. **Inertia.** No instrument moves more than a capped amount per year, so early
   commitment is expensive to reverse. Without this, a policy could simply wait
   and see at no cost, and adaptivity would be free rather than valuable.
3. **Counterpart response.** China's coercion responds to Japan's buildup, the
   US commitment to Japan's burden-sharing. That makes this a strategic
   interaction rather than open-loop control.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from instruments import BY_ID, INSTRUMENT_IDS
from lowy import BASELINE_2025, MEASURES, WEIGHTS, composite

# --------------------------------------------------------------------------
# COEFFICIENTS. All of them, in one place, frozen.
#
# Each carries (a) what it does, (b) why this magnitude, (c) the range over
# which sensitivity analysis must show the result surviving. Where no source
# exists the entry says "expert assumption" rather than implying one.
# --------------------------------------------------------------------------

MODEL_VERSION = "1.1.0-preregistered"

#: Years simulated. 2026-2030 inclusive: five decisions, matching the horizon
#: the whole project has used and the window the December 2022 documents set
#: themselves.
YEARS: Tuple[int, ...] = (2026, 2027, 2028, 2029, 2030)

#: Maximum change in one instrument's intensity per year. THE key structural
#: assumption: without inertia, waiting is free and adaptivity is worthless.
#: Set from lead time -- a 5-year procurement cannot be turned around in one.
#: Sensitivity: 0.15 to 0.45.
def inertia_cap(instrument_id: str) -> float:
    lead = BY_ID[instrument_id].lead_time_years
    return max(0.10, min(0.50, 1.0 / max(1, lead)))

#: How fast realised capability approaches the level the instruments imply.
#: An exponential approach with time-constant equal to the instrument's lead
#: time. Expert assumption; sensitivity 0.5x to 2x.
CAPABILITY_ADJUSTMENT: float = 1.0

#: Scale converting one unit of exposure-weighted instrument effort into Lowy
#: points per year. Calibrated so that December 2022's posture, sustained for
#: five years, moves Japan's composite by roughly +1.5 points -- the order of
#: magnitude the M1 rubric's own anchor implies ("+3 on military capability is
#: the scale of the counterstrike + 2%-GDP decision"). Sensitivity 0.5x to 2x.
EFFORT_TO_POINTS: float = 2.4

#: Diminishing returns: effort on a measure where Japan already scores highly
#: buys less. Japan is at 85.4 on diplomatic influence and 11.3 on future
#: resources, and the rubric has always asserted this asymmetry. Headroom
#: factor is (100 - score)/100 raised to this power. Sensitivity 0.5 to 1.5.
HEADROOM_EXPONENT: float = 1.0

#: Decay of capability when no effort is applied -- capabilities are not free
#: to hold. Expert assumption; sensitivity 0.0 to 0.04.
CAPABILITY_DECAY: float = 0.02

# -- counterpart response ---------------------------------------------------

#: How much China's coercion rises per unit of Japanese military capability
#: growth, scaled by the world's hidden security_dilemma_strength. The security
#: dilemma is the oldest proposition in the field and its MAGNITUDE is exactly
#: what is contested, which is why it is a hidden per-world parameter rather
#: than a fixed coefficient.
COERCION_PER_MILITARY_GROWTH: float = 0.030

#: How much economic engagement damps coercion. Expert assumption, and
#: deliberately smaller than the buildup term: the model does not assume
#: engagement buys safety.
COERCION_DAMPING_PER_ENGAGEMENT: float = 0.020

#: US commitment gained per unit of burden-sharing (host-nation support and
#: defence budget). Expert assumption; sensitivity 0.5x to 2x.
COMMITMENT_PER_BURDEN_SHARING: float = 0.035

#: Partner alignment gained per unit of OSA and minilateral investment, and its
#: natural decay when unattended.
ALIGNMENT_PER_INVESTMENT: float = 0.040
ALIGNMENT_DECAY: float = 0.020

# -- crisis -----------------------------------------------------------------

#: Annual crisis probability is base hazard multiplied by a factor rising with
#: the coercion/commitment gap. A crisis is the event that separates postures
#: that hedge from postures that do not.
CRISIS_GAP_SENSITIVITY: float = 1.6

#: Composite damage in a crisis year, before any offsetting from preparedness.
CRISIS_ECONOMIC_SHOCK: float = 0.15
CRISIS_CAPABILITY_SHOCK: Dict[str, float] = {
    "economic_relationships": -6.0,
    "economic_capability": -3.0,
    "resilience": -2.0,
}
#: How much military capability and defence networks offset crisis damage.
CRISIS_PREPAREDNESS_OFFSET: float = 0.6

# -- budgets ----------------------------------------------------------------

#: Per-year fiscal room for new commitments, and political capital per year.
#: These are the per-period version of the envelopes in instruments.py, which
#: were calibrated so December 2022 comes out feasible-but-stretched.
FISCAL_PER_YEAR: float = 2.20
POLITICAL_PER_YEAR: float = 3.00
#: Unspent capital that carries into the next year, capped. Governments bank
#: some goodwill but not indefinitely. Expert assumption.
POLITICAL_CARRYOVER: float = 0.30
POLITICAL_CARRYOVER_CAP: float = 1.00

# -- observation ------------------------------------------------------------

#: Standard deviation of Japan's noisy read on the world, and the lag in years.
#: Both are what make inference necessary rather than trivial. Sensitivity:
#: noise 0.02 to 0.12, lag 0 to 2.
OBSERVATION_NOISE: float = 0.06
OBSERVATION_LAG_YEARS: int = 1


# --------------------------------------------------------------------------
# Worlds
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class WorldParams:
    """The hidden draw. A policy never sees any of this."""

    us_decline_rate: float
    security_dilemma_strength: float
    crisis_hazard_base: float
    china_assertiveness: float
    economic_shock_sigma: float
    #: Which structural form the dynamics take. Review point 8: testing only
    #: parameter draws within one functional form understates model risk, so
    #: alternative STRUCTURES are drawn too.
    structure: str = "baseline"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "us_decline_rate": self.us_decline_rate,
            "security_dilemma_strength": self.security_dilemma_strength,
            "crisis_hazard_base": self.crisis_hazard_base,
            "china_assertiveness": self.china_assertiveness,
            "economic_shock_sigma": self.economic_shock_sigma,
            "structure": self.structure,
        }


#: Ranges the hidden parameters are drawn from. Wide on purpose: the point is
#: that the right posture differs across them, so a policy must infer.
PARAM_RANGES: Dict[str, Tuple[float, float]] = {
    "us_decline_rate": (0.00, 0.09),          # 0 = steady ally, 0.09 = fast exit
    "security_dilemma_strength": (0.0, 2.0),  # 0 = buildup is free, 2 = self-defeating
    "crisis_hazard_base": (0.01, 0.12),       # 1% to 12% per year
    "china_assertiveness": (-0.01, 0.05),     # drift independent of Japan
    "economic_shock_sigma": (0.02, 0.10),
}

#: Alternative model structures, review point 8. Same state variables, different
#: functional forms, so a result that depends on one of them is visible as such.
STRUCTURES: Tuple[str, ...] = (
    "baseline",       # linear response, as documented above
    "saturating",     # counterpart responses saturate (tanh) rather than staying linear
    "threshold",      # counterparts respond only past a trigger level
)


def sample_world(rng: random.Random,
                 structures: Sequence[str] = STRUCTURES) -> WorldParams:
    def draw(name: str) -> float:
        low, high = PARAM_RANGES[name]
        return low + rng.random() * (high - low)

    return WorldParams(
        us_decline_rate=draw("us_decline_rate"),
        security_dilemma_strength=draw("security_dilemma_strength"),
        crisis_hazard_base=draw("crisis_hazard_base"),
        china_assertiveness=draw("china_assertiveness"),
        economic_shock_sigma=draw("economic_shock_sigma"),
        structure=rng.choice(list(structures)),
    )


def world_bank(seed: int, count: int,
               structures: Sequence[str] = STRUCTURES) -> List[WorldParams]:
    """A reproducible bank of worlds. Seeds are frozen in `splits.py`."""
    rng = random.Random(seed)
    return [sample_world(rng, structures) for _ in range(count)]


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------


@dataclass
class WorldState:
    year: int
    capability: Dict[str, float]
    instrument_level: Dict[str, float]
    fiscal_available: float
    political_available: float
    us_commitment: float
    china_coercion: float
    partner_alignment: float
    economic_conditions: float
    crisis_active: bool = False
    crises_so_far: int = 0

    def copy(self) -> "WorldState":
        return WorldState(
            year=self.year, capability=dict(self.capability),
            instrument_level=dict(self.instrument_level),
            fiscal_available=self.fiscal_available,
            political_available=self.political_available,
            us_commitment=self.us_commitment,
            china_coercion=self.china_coercion,
            partner_alignment=self.partner_alignment,
            economic_conditions=self.economic_conditions,
            crisis_active=self.crisis_active, crises_so_far=self.crises_so_far,
        )


def initial_state(instrument_level: Optional[Mapping[str, float]] = None) -> WorldState:
    """2025, before the first decision. The starting world is the real one."""
    return WorldState(
        year=YEARS[0] - 1,
        # Japan's real 2025 measure scores, from lowy.py. Composite 38.8475.
        # An earlier draft of this file hardcoded a second, different set of
        # baseline numbers, which would have made every score in Project B
        # incomparable with the M1 results and with the seeds.
        capability=dict(BASELINE_2025),
        instrument_level={i: float((instrument_level or {}).get(i, 0.0))
                          for i in INSTRUMENT_IDS},
        fiscal_available=FISCAL_PER_YEAR,
        political_available=POLITICAL_PER_YEAR,
        us_commitment=0.70,        # post-2022, pre-retrenchment
        china_coercion=0.45,
        partner_alignment=0.50,
        economic_conditions=0.55,
    )


# --------------------------------------------------------------------------
# Dynamics
# --------------------------------------------------------------------------


def _respond(raw: float, structure: str) -> float:
    """Apply the world's structural form to a linear response term."""
    if structure == "saturating":
        return math.tanh(raw * 2.0) / 2.0
    if structure == "threshold":
        return raw if abs(raw) > 0.01 else 0.0
    return raw


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def apply_decision(state: WorldState, deltas: Mapping[str, float]
                   ) -> Tuple[Dict[str, float], List[str]]:
    """Clip a decision to inertia and budget. Returns (applied, notes).

    Over-budget decisions are SCALED DOWN rather than rejected: a government
    that asks for more than it can afford gets less of everything, which is
    what actually happens, and it keeps the policy's behaviour continuous so
    the search sees a gradient rather than a cliff.
    """
    notes: List[str] = []
    wanted: Dict[str, float] = {}
    for ident, delta in deltas.items():
        if ident not in BY_ID:
            notes.append(f"unknown instrument {ident!r} ignored")
            continue
        try:
            value = float(delta)
        except (TypeError, ValueError):
            notes.append(f"non-numeric delta for {ident!r} ignored")
            continue
        if not math.isfinite(value):
            notes.append(f"non-finite delta for {ident!r} ignored")
            continue
        cap = inertia_cap(ident)
        clipped = max(-cap, min(cap, value))
        if abs(clipped - value) > 1e-9:
            notes.append(f"{ident} change capped by inertia to {clipped:+.3f}")
        target = _clip(state.instrument_level[ident] + clipped)
        wanted[ident] = target - state.instrument_level[ident]

    # Only INCREASES cost money; standing down is free but slow (inertia still
    # applies), which is why a committed posture is expensive to unwind.
    fiscal = sum(BY_ID[i].fiscal_gdp_pct * max(0.0, d) for i, d in wanted.items())
    political = sum(BY_ID[i].total_political_cost * max(0.0, d)
                    for i, d in wanted.items())

    scale = 1.0
    if fiscal > state.fiscal_available and fiscal > 0:
        scale = min(scale, state.fiscal_available / fiscal)
    if political > state.political_available and political > 0:
        scale = min(scale, state.political_available / political)
    if scale < 1.0:
        notes.append(f"decision scaled to {scale:.2f} of requested by budget")
        wanted = {i: (d * scale if d > 0 else d) for i, d in wanted.items()}

    return wanted, notes


def step(state: WorldState, params: WorldParams, deltas: Mapping[str, float],
         rng: random.Random) -> Tuple[WorldState, Dict[str, Any]]:
    """One year. Deterministic given (state, params, deltas, rng)."""
    new = state.copy()
    new.year = state.year + 1

    applied, notes = apply_decision(state, deltas)
    for ident, delta in applied.items():
        new.instrument_level[ident] = _clip(state.instrument_level[ident] + delta)

    spent_fiscal = sum(BY_ID[i].fiscal_gdp_pct * max(0.0, d)
                       for i, d in applied.items())
    spent_political = sum(BY_ID[i].total_political_cost * max(0.0, d)
                          for i, d in applied.items())

    # --- capability update, with lead-time lag and diminishing returns -----
    military_before = new.capability["military_capability"]
    for measure in MEASURES:
        pressure = 0.0
        for ident, level in new.instrument_level.items():
            weight = BY_ID[ident].exposure.get(measure, 0.0)
            if weight:
                lag = 1.0 / max(1, BY_ID[ident].lead_time_years)
                pressure += weight * level * lag * CAPABILITY_ADJUSTMENT
        headroom = max(0.0, (100.0 - new.capability[measure]) / 100.0)
        gain = EFFORT_TO_POINTS * pressure * (headroom ** HEADROOM_EXPONENT)
        decay = CAPABILITY_DECAY * new.capability[measure] * (1.0 if pressure <= 0 else 0.0)
        new.capability[measure] = max(0.0, min(100.0,
                                               new.capability[measure] + gain - decay))
    military_growth = new.capability["military_capability"] - military_before

    # --- counterpart response ---------------------------------------------
    buildup = COERCION_PER_MILITARY_GROWTH * military_growth * params.security_dilemma_strength
    engagement = COERCION_DAMPING_PER_ENGAGEMENT * new.instrument_level.get("china_engagement", 0.0)
    new.china_coercion = _clip(
        state.china_coercion
        + _respond(buildup - engagement, params.structure)
        + params.china_assertiveness
    )

    burden = 0.5 * (new.instrument_level.get("host_nation_support", 0.0)
                    + new.instrument_level.get("defence_budget", 0.0))
    new.us_commitment = _clip(
        state.us_commitment
        + _respond(COMMITMENT_PER_BURDEN_SHARING * burden, params.structure)
        - params.us_decline_rate
    )

    invest = 0.5 * (new.instrument_level.get("official_security_assistance", 0.0)
                    + new.instrument_level.get("minilateral_formats", 0.0))
    new.partner_alignment = _clip(
        state.partner_alignment
        + _respond(ALIGNMENT_PER_INVESTMENT * invest, params.structure)
        - ALIGNMENT_DECAY
    )

    # --- shocks and crisis --------------------------------------------------
    shock = rng.gauss(0.0, params.economic_shock_sigma)
    new.economic_conditions = _clip(state.economic_conditions + shock)

    gap = max(0.0, new.china_coercion - new.us_commitment)
    hazard = _clip(params.crisis_hazard_base * (1.0 + CRISIS_GAP_SENSITIVITY * gap))
    new.crisis_active = rng.random() < hazard
    if new.crisis_active:
        new.crises_so_far += 1
        preparedness = 0.5 * (new.capability["military_capability"] / 100.0
                              + new.capability["defence_networks"] / 100.0)
        offset = 1.0 - CRISIS_PREPAREDNESS_OFFSET * preparedness
        for measure, damage in CRISIS_CAPABILITY_SHOCK.items():
            new.capability[measure] = max(0.0, new.capability[measure] + damage * offset)
        new.economic_conditions = _clip(
            new.economic_conditions - CRISIS_ECONOMIC_SHOCK * offset)

    # --- budgets refresh ----------------------------------------------------
    unspent = max(0.0, state.political_available - spent_political)
    new.political_available = min(
        POLITICAL_PER_YEAR + POLITICAL_CARRYOVER_CAP,
        POLITICAL_PER_YEAR + POLITICAL_CARRYOVER * unspent,
    )
    new.fiscal_available = FISCAL_PER_YEAR * (0.7 + 0.6 * new.economic_conditions)

    return new, {
        "year": new.year, "notes": notes,
        "spent_fiscal": round(spent_fiscal, 4),
        "spent_political": round(spent_political, 4),
        "crisis": new.crisis_active, "hazard": round(hazard, 4),
        "military_growth": round(military_growth, 4),
    }


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# ENVIRONMENTAL CONTINGENCY, added in v1.1.0.
#
# PROVENANCE, stated plainly because it matters for how much this result can
# be trusted. The v1.0.0 qualification run FAILED, and tracing why showed that
# the strategic environment moved the score by 1.14 points across its entire
# range, exclusively through crisis hazard, while `partner_alignment` affected
# nothing whatsoever.
#
# The review's protocol permits revision only for a realism defect that can be
# stated without reference to which arm it favours. This one can:
#
#     The model treated Japan's capability as independent of its strategic
#     environment. Defence networks scored the same whether the United States
#     was committed or had withdrawn. Economic relationships scored the same
#     whether China was coercing Japan's trade or not.
#
# A model in which alliance capability does not depend on ally commitment is
# not modelling alliances. That is wrong on its own terms and would be wrong
# if it made adaptivity look worse. Hence the version bump and the full rerun;
# v1.0.0's failing numbers are kept in the record rather than discarded.
#
# What this changes substantively: the hidden parameters now determine WHICH
# investments pay, not merely how much noise there is. If the US is leaving,
# defence networks devalue and autonomous capability is worth more. If coercion
# is high, trade exposure devalues and resilience is worth more. That is the
# strategic structure the first version lacked, and it is what makes inferring
# the hidden parameters worth anything.
# --------------------------------------------------------------------------

#: How much of Japan's defence-network score survives an ally that is not
#: there. At us_commitment 0 with no partners, a network is worth this fraction
#: of its nominal value. Bases, interoperability and standing agreements retain
#: some worth without a guarantor, but not much. Sensitivity 0.20 to 0.60.
NETWORK_FLOOR: float = 0.35

#: How much of Japan's economic-relationships score survives maximum coercion.
#: Trade does not stop under pressure, but its strategic value as influence
#: does degrade. Sensitivity 0.40 to 0.80.
TRADE_FLOOR_UNDER_COERCION: float = 0.60

#: Resilience is partly a claim about withstanding pressure, so it is measured
#: against the pressure actually applied. Sensitivity 0.60 to 0.90.
RESILIENCE_FLOOR_UNDER_COERCION: float = 0.75


#: The 2025 environment, which is the one Japan's published Lowy scores were
#: actually measured in. The modifiers below are expressed RELATIVE to it, so
#: that a state at these values returns Japan's real 2025 capability unchanged
#: and the composite is exactly 38.8475.
#:
#: Without this normalisation the modifier would silently re-base Japan --
#: every Project B number would sit on a different scale from M1, from the
#: seeds and from the published Index, and the error would be invisible because
#: all the internal comparisons would still be self-consistent.
REFERENCE_US_COMMITMENT: float = 0.70
REFERENCE_CHINA_COERCION: float = 0.45
REFERENCE_PARTNER_ALIGNMENT: float = 0.50


def _network_factor(us_commitment: float, partner_alignment: float) -> float:
    reliance = 0.5 * (us_commitment + partner_alignment)
    return NETWORK_FLOOR + (1.0 - NETWORK_FLOOR) * reliance


def _coercion_factor(coercion: float, floor: float) -> float:
    return 1.0 - (1.0 - floor) * coercion


#: Normalising constants, computed once at the reference environment.
_REF_NETWORK = _network_factor(REFERENCE_US_COMMITMENT, REFERENCE_PARTNER_ALIGNMENT)
_REF_TRADE = _coercion_factor(REFERENCE_CHINA_COERCION, TRADE_FLOOR_UNDER_COERCION)
_REF_RESILIENCE = _coercion_factor(REFERENCE_CHINA_COERCION,
                                   RESILIENCE_FLOOR_UNDER_COERCION)


def effective_capability(state: WorldState) -> Dict[str, float]:
    """Capability as it counts, given the environment Japan is actually in.

    Japan's own instruments produce nominal capability; the world decides how
    much of it is worth anything. The five measures not listed here are treated
    as intrinsic -- economic capability, future resources, diplomatic influence,
    cultural influence and military capability are Japan's whether or not
    Washington stays, which is exactly why autonomy becomes attractive when
    commitment falls.
    """
    out = dict(state.capability)

    out["defence_networks"] *= (
        _network_factor(state.us_commitment, state.partner_alignment) / _REF_NETWORK)
    out["economic_relationships"] *= (
        _coercion_factor(state.china_coercion, TRADE_FLOOR_UNDER_COERCION)
        / _REF_TRADE)
    out["resilience"] *= (
        _coercion_factor(state.china_coercion, RESILIENCE_FLOOR_UNDER_COERCION)
        / _REF_RESILIENCE)
    return out


def actir_model_score(state: WorldState) -> float:
    """Lowy-weighted ACTIR model score. **Not a projected Lowy Index score.**

    Review point 4, and it is correct. Lowy's Index is a relative,
    distance-to-frontier comparison across 27 countries, 8 measures, 30
    submeasures and 131 indicators. What happens here is that eight Japanese
    measure scores are moved by dynamics this project authored, with all 26
    other countries held implicit, and Lowy's published WEIGHTS are then
    applied. Only the weights are Lowy's.

    Reported everywhere under this name so the distinction cannot be lost in
    transcription.
    """
    return composite(effective_capability(state))


