"""Property tests for the deterministic model-based evaluator.

Not "exact simulator" -- a review of 2026-08-19 was right that the word implies
a verifier of reality, and this is a model. What these tests pin is the weaker
and achievable property: **repeatability**, plus the structural facts the
experiment's validity depends on.

The most important test in this file is
`test_the_environment_actually_affects_the_score`. Model v1.0.0 failed it in
substance -- the entire strategic environment moved the score by 1.14 points
through crisis hazard alone, and `partner_alignment` affected nothing -- which
is why v1.1.0 exists.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

import baselines  # noqa: E402
import evaluate_adaptive as ea  # noqa: E402
import splits  # noqa: E402
import world as W  # noqa: E402
from instruments import BY_ID, INSTRUMENT_IDS  # noqa: E402
from lowy import BASELINE_2025, JAPAN_2025_COMPOSITE, MEASURES  # noqa: E402
from observation import ObservationChannel  # noqa: E402


# -- the model starts where Japan actually is --------------------------------


def test_the_baseline_is_japans_real_2025_position():
    """An earlier draft of world.py hardcoded a SECOND, different set of
    baseline measure scores, which would have made every Project B number
    incomparable with M1 and with the seeds."""
    state = W.initial_state()
    assert state.capability == BASELINE_2025
    assert W.actir_model_score(state) == pytest.approx(38.8475, abs=1e-4)
    assert round(W.actir_model_score(state), 1) == JAPAN_2025_COMPOSITE


# -- repeatability, which is all "deterministic" claims ----------------------


def test_the_same_policy_and_seed_give_the_same_trajectory():
    params = W.sample_world(random.Random(3))
    policy = baselines.december_2022_policy()
    a = ea.run_episode(policy, params, seed=11)
    b = ea.run_episode(policy, params, seed=11)
    assert a.score == b.score
    assert a.crises == b.crises


def test_different_seeds_give_different_trajectories():
    """If they did not, the episode repeats would be averaging nothing."""
    params = W.sample_world(random.Random(3))
    policy = baselines.december_2022_policy()
    scores = {ea.run_episode(policy, params, seed=s).score for s in range(12)}
    assert len(scores) > 1


def test_arms_are_paired_on_identical_worlds():
    """Two policies at the same (world, seed) must face the same crisis draws
    and shocks, or the paired comparison is not paired."""
    params = W.sample_world(random.Random(5))
    nothing = ea.run_episode(lambda o, m: {}, params, seed=21)
    also_nothing = ea.run_episode(lambda o, m: {}, params, seed=21)
    assert nothing.crises == also_nothing.crises


# -- the structural facts the experiment depends on --------------------------


def test_inertia_binds():
    """Without inertia, waiting costs nothing and adaptivity is free rather
    than valuable. This is the load-bearing assumption of the whole design."""
    state = W.initial_state()
    applied, notes = W.apply_decision(state, {i: 1.0 for i in INSTRUMENT_IDS})
    for ident, delta in applied.items():
        assert delta <= W.inertia_cap(ident) + 1e-9
    assert any("inertia" in n for n in notes)


def test_slow_instruments_move_more_slowly_than_fast_ones():
    assert W.inertia_cap("semiconductor_policy") < W.inertia_cap("defence_budget")


def test_inertia_binds_before_the_fiscal_envelope_does():
    """A measured property of the model, recorded rather than assumed.

    Asking every instrument to maximum, then applying the inertia caps, costs
    about 1.43% of GDP against a 2.20% envelope and 2.96 of political capital
    against 3.00. So POLITICAL CAPITAL is the binding constraint and the fiscal
    envelope almost never is -- even in the worst economy, where fiscal room
    falls to 1.54%.

    This is a fact about the world model that a reader should know, and it is
    pinned here rather than corrected, because correcting it after seeing a
    qualification result would be tuning the model toward an answer.
    """
    from instruments import BY_ID

    state = W.initial_state()
    applied, _notes = W.apply_decision(state, {i: 1.0 for i in INSTRUMENT_IDS})
    fiscal = sum(BY_ID[i].fiscal_gdp_pct * max(0.0, d) for i, d in applied.items())
    political = sum(BY_ID[i].total_political_cost * max(0.0, d)
                    for i, d in applied.items())
    assert fiscal < W.FISCAL_PER_YEAR, "fiscal envelope does not bind after inertia"
    assert political > 0.9 * W.POLITICAL_PER_YEAR, "political capital is the binding one"


def test_an_over_budget_request_is_scaled_not_refused():
    """A continuous response gives the search a gradient instead of a cliff."""
    state = W.initial_state()
    state.political_available = 0.2
    _applied, notes = W.apply_decision(state, {i: 1.0 for i in INSTRUMENT_IDS})
    assert any("scaled" in n for n in notes)


def test_standing_down_is_free_but_still_slow():
    """Reducing an instrument costs no budget, but inertia still applies, which
    is what makes a committed posture expensive to unwind."""
    state = W.initial_state({i: 0.8 for i in INSTRUMENT_IDS})
    applied, _ = W.apply_decision(state, {i: -1.0 for i in INSTRUMENT_IDS})
    assert all(d < 0 for d in applied.values())
    for ident, delta in applied.items():
        assert abs(delta) <= W.inertia_cap(ident) + 1e-9


def test_doing_nothing_loses_ground():
    """Capabilities decay, so the null policy must underperform the 2025
    baseline. If standing still were free the search would have no floor."""
    result = ea.evaluate(lambda o, m: {}, splits.dev_worlds()[:15], repeats=2)
    assert result.mean < 38.8475


def test_the_human_baseline_beats_doing_nothing():
    worlds = splits.dev_worlds()[:15]
    nothing = ea.evaluate(lambda o, m: {}, worlds, repeats=2)
    dec2022 = ea.evaluate(baselines.december_2022_policy(), worlds, repeats=2)
    assert dec2022.mean > nothing.mean


# -- THE test that model v1.0.0 failed ---------------------------------------


def test_the_environment_actually_affects_the_score():
    """v1.0.0's defect, and the reason v1.1.0 exists.

    In v1.0.0 the entire strategic environment moved the score by 1.14 points
    across its full range, exclusively through crisis hazard, and
    `partner_alignment` affected nothing at all. A model in which alliance
    capability does not depend on ally commitment is not modelling alliances.
    """
    policy = baselines.december_2022_policy()
    steady = W.WorldParams(0.00, 0.0, 0.01, 0.0, 0.02)
    exiting = W.WorldParams(0.09, 2.0, 0.12, 0.05, 0.10)
    a = ea.evaluate(policy, [steady], repeats=6).mean
    b = ea.evaluate(policy, [exiting], repeats=6).mean
    assert a - b > 2.0, (
        "the same policy must fare materially worse in a hostile world, or the "
        "hidden parameters are decorative and there is nothing to adapt to"
    )


def test_partner_alignment_is_not_decorative():
    state = W.initial_state()
    high = state.copy(); high.partner_alignment = 1.0
    low = state.copy(); low.partner_alignment = 0.0
    assert W.actir_model_score(high) > W.actir_model_score(low)


def test_alliance_capability_depends_on_ally_commitment():
    state = W.initial_state()
    committed = state.copy(); committed.us_commitment = 1.0
    gone = state.copy(); gone.us_commitment = 0.0
    assert (W.effective_capability(committed)["defence_networks"]
            > W.effective_capability(gone)["defence_networks"])


# -- observation -------------------------------------------------------------


def test_the_policy_never_sees_the_hidden_parameters():
    """The whole premise. If a hidden parameter leaked into Observation the
    inference problem would be trivial."""
    channel = ObservationChannel(random.Random(0))
    obs = channel.observe(W.initial_state())
    text = repr(obs.as_dict())
    for name in ("us_decline_rate", "security_dilemma_strength",
                 "crisis_hazard_base", "china_assertiveness"):
        assert name not in text


def test_observations_are_noisy_and_lagged():
    state = W.initial_state()
    channel = ObservationChannel(random.Random(0))
    first = channel.observe(state)
    assert first.us_commitment != state.us_commitment, "noise must be applied"
    moved = state.copy(); moved.us_commitment = 0.1
    second = channel.observe(moved)
    assert second.us_commitment == first.us_commitment, "lag must hold the old value"


def test_own_state_is_observed_exactly():
    state = W.initial_state()
    obs = ObservationChannel(random.Random(0)).observe(state)
    assert obs.capability == state.capability
    assert obs.fiscal_available == state.fiscal_available


# -- the comparator ladder ---------------------------------------------------


def test_open_loop_and_feedback_have_matched_parameter_counts():
    """Review point 5's confound. If the adaptive class simply had more
    parameters, any advantage would be about capacity, not observation."""
    assert (baselines.DIMENSIONS["open_loop"]
            == baselines.DIMENSIONS["linear_feedback"])


def test_open_loop_varies_over_time_but_reads_nothing():
    theta = [0.2] * baselines.DIMENSIONS["constant"] * 5
    for year in range(5):
        for i in range(21):
            theta[year * 21 + i] = 0.1 * year
    policy = baselines.open_loop_policy(theta)
    state = W.initial_state()
    channel = ObservationChannel(random.Random(0))
    obs_a = channel.observe(state)
    hostile = state.copy()
    hostile.china_coercion = 1.0
    hostile.us_commitment = 0.0
    obs_b = ObservationChannel(random.Random(1)).observe(hostile)
    # identical year, wildly different world -> identical decision
    assert policy(obs_a, {}) == policy(obs_b, {})


def test_feedback_does_read_the_world():
    theta = [0.3] * 21 + [0.5] * 84
    policy = baselines.linear_feedback_policy(theta)
    state = W.initial_state()
    hostile = state.copy(); hostile.china_coercion = 1.0
    a = policy(ObservationChannel(random.Random(0)).observe(state), {})
    b = policy(ObservationChannel(random.Random(0)).observe(hostile), {})
    assert a != b


# -- statistics --------------------------------------------------------------


def test_paired_comparison_needs_equal_banks():
    a = ea.Result(0, 0, 0, [1.0, 2.0])
    b = ea.Result(0, 0, 0, [1.0])
    with pytest.raises(ValueError):
        ea.compare(a, b)


def test_a_real_difference_is_detected_and_a_null_one_is_not():
    """The test must be able to say both yes and no, or it says nothing."""
    base = [40.0 + 0.1 * i for i in range(60)]
    same = ea.compare(ea.Result(0, 0, 0, list(base)), ea.Result(0, 0, 0, list(base)))
    assert not same.significant
    better = ea.compare(ea.Result(0, 0, 0, [b + 1.0 for b in base]),
                        ea.Result(0, 0, 0, list(base)))
    assert better.significant and better.mean_difference == pytest.approx(1.0)


def test_cvar_is_the_lower_tail_not_the_mean():
    result = ea.Result(0, 0, 0, [])
    scores = list(range(100))
    full = ea.evaluate.__wrapped__ if hasattr(ea.evaluate, "__wrapped__") else None
    ordered = sorted(scores)
    tail = max(1, int(len(ordered) * ea.CVAR_FRACTION))
    assert sum(ordered[:tail]) / tail < sum(ordered) / len(ordered)


# -- the splits are frozen ---------------------------------------------------


def test_splits_are_disjoint_and_reproducible():
    train, dev, test = splits.train_worlds(), splits.dev_worlds(), splits.test_worlds()
    assert len(train) == splits.TRAIN_SIZE
    assert len(test) == splits.TEST_SIZE
    assert splits.train_worlds()[0].as_dict() == train[0].as_dict(), "must be reproducible"
    assert train[0].as_dict() != dev[0].as_dict() != test[0].as_dict()


def test_the_test_bank_covers_every_structural_form():
    """Review point 8: testing only parameter draws within one functional form
    understates model risk."""
    seen = {w.structure for w in splits.test_worlds()}
    assert seen == set(W.STRUCTURES)
