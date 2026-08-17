"""Test 1: the published weights and Japan's 2025 scores reproduce 38.8.

This is the anchor for the whole experiment. If it fails, the fitness function
is not the Lowy Asia Power Index and nothing downstream means what it claims to
mean (RESEARCH_DESIGN section 2.2).
"""

import pytest

import lowy


def test_weights_sum_to_one():
    assert sum(lowy.WEIGHTS.values()) == pytest.approx(1.0, abs=1e-12)


def test_there_are_eight_measures_with_weights_and_baselines():
    assert len(lowy.MEASURES) == 8
    assert set(lowy.WEIGHTS) == set(lowy.MEASURES)
    assert set(lowy.BASELINE_2025) == set(lowy.MEASURES)


def test_thirty_submeasure_dials():
    """The dial set is Lowy's own, and there are exactly 30 of them."""
    assert lowy.N_DIALS == 30
    assert len(set(lowy.DIALS)) == 30
    for dial_id in lowy.DIALS:
        measure, submeasure = dial_id.split(".", 1)
        assert measure in lowy.MEASURES
        assert submeasure in lowy.SUBMEASURES[measure]


def test_baseline_reproduces_japans_published_composite():
    """25.4, 30.1, 36.9, 34.3, 11.3, 56.5, 85.4, 48.5 under the published weights."""
    composite = lowy.composite(lowy.BASELINE_2025)
    assert composite == pytest.approx(38.8475, abs=1e-9)
    assert round(composite, lowy.COMPOSITE_DECIMALS) == lowy.JAPAN_2025_COMPOSITE


def test_zero_deltas_reproduce_the_baseline():
    """A judge that returns all-zero deltas must leave the composite untouched."""
    assert lowy.composite_with_deltas({}) == pytest.approx(38.8475, abs=1e-9)
    zeros = {m: 0.0 for m in lowy.MEASURES}
    assert lowy.composite_with_deltas(zeros) == pytest.approx(38.8475, abs=1e-9)


def test_deltas_are_clipped_to_the_index_scale():
    """clip(b_m + delta_m, 0, 100): scores cannot leave the 0-100 scale."""
    huge = {m: 999.0 for m in lowy.MEASURES}
    assert lowy.composite_with_deltas(huge) == pytest.approx(100.0, abs=1e-9)
    tiny = {m: -999.0 for m in lowy.MEASURES}
    assert lowy.composite_with_deltas(tiny) == pytest.approx(0.0, abs=1e-9)

    # future_resources starts at 11.3, so -15 clips at 0 rather than going negative.
    projected = lowy.projected_scores({"future_resources": -15.0})
    assert projected["future_resources"] == pytest.approx(0.0, abs=1e-9)


def test_a_plus_three_on_military_capability_moves_the_composite_by_its_weight():
    """The anchor in the rubric: +3 on military capability is 0.175 * 3 points."""
    moved = lowy.composite_with_deltas({"military_capability": 3.0})
    assert moved - lowy.composite(lowy.BASELINE_2025) == pytest.approx(0.525, abs=1e-9)
