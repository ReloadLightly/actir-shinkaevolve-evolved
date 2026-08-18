"""MAP-Elites over policy space, and the descriptors it runs on.

The algorithm is the direct answer to what M1 measured. A fitness-proportional
archive needs a trustworthy global ranking; M1 showed the judge does not supply
one (effect 0.696 against inter-judge noise 0.921). MAP-Elites never asks for
one — it compares a candidate only against the current occupant of its own
behaviour cell, and its headline output, coverage, is a count of filled cells
that no amount of ranking noise can corrupt.

These tests defend the properties that make that claim true, above all that the
cell comparison really is local and that the descriptors really are exact.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "scripts", REPO_ROOT / "analysis",
              REPO_ROOT / "tasks" / "japan_fp"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import descriptors as desc  # noqa: E402
import mapelites as me  # noqa: E402
from descriptors import DEFAULT_AXES, cell, describe  # noqa: E402
from judge.client import SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
from mapelites import to_archive_records  # noqa: E402
from lowy import DIALS, MEASURES  # noqa: E402


def _portfolio(shares):
    return {"dials": [{"dial": d, "share": s, "how": "x"} for d, s in zip(DIALS, shares)]}


def _even():
    return _portfolio([1.0 / len(DIALS)] * len(DIALS))


# -- descriptors must be exact, free and deterministic -----------------------


def test_descriptors_are_deterministic():
    p = _even()
    assert desc.describe(p) == desc.describe(p)


def test_effort_by_measure_sums_to_the_total_share():
    p = _even()
    assert sum(desc.effort_by_measure(p).values()) == pytest.approx(1.0)


def test_concentration_is_a_herfindahl_index():
    assert desc.concentration(_even()) == pytest.approx(1.0 / len(DIALS))
    allin = [0.0] * len(DIALS)
    allin[0] = 1.0
    assert desc.concentration(_portfolio(allin)) == pytest.approx(1.0)


def test_every_registered_axis_has_sane_bounds_and_a_meaning():
    for name, (_extract, low, high, meaning) in desc.DESCRIPTORS.items():
        assert high > low, f"{name} has empty bounds"
        assert meaning.strip(), f"{name} has no documented meaning"


def test_descriptors_ignore_unknown_dials():
    """A malformed portfolio must not silently shift the map."""
    p = _even()
    p["dials"].append({"dial": "not.a.real.dial", "share": 5.0, "how": "x"})
    assert sum(desc.effort_by_measure(p).values()) == pytest.approx(1.0)


def test_cells_clamp_rather_than_drop_extremes():
    """A portfolio spending 90% on one measure is still real and still belongs
    on the map, at the edge — not discarded."""
    extreme = [0.0] * len(DIALS)
    for i, dial in enumerate(DIALS):
        if dial.startswith("military_capability."):
            extreme[i] = 0.9 / 5
    coords = desc.cell(_portfolio(extreme), bins=8)
    assert coords[0] == 7, "an off-scale value must land in the top bin"


def test_the_default_axes_separate_the_human_doctrines():
    """If the two default axes put autonomous rearmament and accommodation in
    the same cell, the map cannot show the debate it exists to show."""
    import importlib.util

    task = REPO_ROOT / "tasks" / "japan_fp"
    cells = {}
    for name, path in (("rearm", task / "seeds" / "seed_autonomous_rearmament.py"),
                       ("accom", task / "seeds" / "seed_accommodation.py"),
                       ("dec22", task / "initial.py")):
        spec = importlib.util.spec_from_file_location(f"m_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        cells[name] = desc.cell(mod.build_policy().to_dict(), bins=8)
    assert len({tuple(c) for c in cells.values()}) == 3, (
        f"the default axes collapse distinct doctrines onto one cell: {cells}"
    )


# -- the grid: the comparison must be LOCAL ----------------------------------


def _elite(ident, score):
    return me.Elite(ident, None, score, (), {})


def test_an_empty_cell_accepts_anything():
    grid = me.Grid()
    assert grid.consider(_elite(1, 0.0), (0, 0)) == "discovery"
    assert grid.coverage > 0


def test_a_candidate_only_competes_with_its_own_cell():
    """The property the whole argument rests on. A weak candidate in an empty
    cell must survive a strong incumbent elsewhere — a global ranking would
    have discarded it."""
    grid = me.Grid()
    grid.consider(_elite(1, 100.0), (0, 0))
    assert grid.consider(_elite(2, 0.001), (7, 7)) == "discovery"
    assert grid.cells[(7, 7)].ident == 2
    assert grid.cells[(0, 0)].ident == 1


def test_a_worse_candidate_is_rejected_within_its_cell():
    grid = me.Grid()
    grid.consider(_elite(1, 10.0), (3, 3))
    assert grid.consider(_elite(2, 9.0), (3, 3)) == "rejected"
    assert grid.cells[(3, 3)].ident == 1


def test_a_better_candidate_displaces_only_its_own_incumbent():
    grid = me.Grid()
    grid.consider(_elite(1, 10.0), (3, 3))
    grid.consider(_elite(2, 50.0), (4, 4))
    assert grid.consider(_elite(3, 11.0), (3, 3)) == "improvement"
    assert grid.cells[(3, 3)].ident == 3
    assert grid.cells[(4, 4)].ident == 2


def test_coverage_never_decreases():
    grid = me.Grid()
    seen = 0.0
    for i in range(8):
        grid.consider(_elite(i, float(i)), (i, i))
        assert grid.coverage >= seen
        seen = grid.coverage


def test_qd_score_rewards_filling_and_filling_well():
    grid = me.Grid()
    grid.consider(_elite(1, 5.0), (0, 0))
    after_one = grid.qd_score
    grid.consider(_elite(2, 5.0), (1, 1))          # a new cell raises it
    assert grid.qd_score > after_one
    before = grid.qd_score
    grid.consider(_elite(3, 9.0), (1, 1))          # so does a better elite
    assert grid.qd_score > before


# -- end to end, on the surrogate --------------------------------------------


@pytest.fixture(scope="module")
def surrogate_client():
    return JudgeClient(JudgeConfig(mode=SURROGATE))


def test_mapelites_fills_cells_and_stays_reproducible(surrogate_client):
    a, _ = me.run_mapelites(120, 3, desc.DEFAULT_AXES, 8, surrogate_client)
    b, _ = me.run_mapelites(120, 3, desc.DEFAULT_AXES, 8, surrogate_client)
    assert len(a.cells) > 1
    assert a.coverage == b.coverage and a.qd_score == pytest.approx(b.qd_score)


def test_mapelites_outcovers_fitness_selection_at_matched_budget(surrogate_client):
    """The demonstration, run small. Same operators, same budget, same seed —
    the selection rule is the only difference."""
    grid, _ = me.run_mapelites(250, 0, desc.DEFAULT_AXES, 8, surrogate_client)
    control, _ = me.run_fitness_driven(250, 0, desc.DEFAULT_AXES, 8, surrogate_client)
    assert grid.coverage > control.coverage, (
        f"MAP-Elites {grid.coverage:.1%} did not beat fitness selection "
        f"{control.coverage:.1%}"
    )


def test_elites_export_into_the_standard_archive_format(surrogate_client, tmp_path):
    """So analysis/novelty.py reads a MAP-Elites archive unchanged."""
    import novelty

    grid, _ = me.run_mapelites(100, 1, desc.DEFAULT_AXES, 8, surrogate_client)
    records = me.to_archive_records(grid)
    assert records and all(r["valid"] for r in records)
    stats = novelty.analyse(records, min_novelty=0.20)
    assert stats["valid"] == len(records)
    assert stats["surrogate"] is True


def test_the_heatmap_is_valid_standalone_svg(surrogate_client, tmp_path):
    grid, _ = me.run_mapelites(80, 2, desc.DEFAULT_AXES, 8, surrogate_client)
    me.heatmap_svg(grid, tmp_path / "grid.svg")
    text = (tmp_path / "grid.svg").read_text()
    assert text.startswith("<svg") and text.rstrip().endswith("</svg>")


def test_every_elite_passed_the_validity_gate(surrogate_client):
    """An invalid portfolio must never occupy a cell; the map would be a map of
    things that cannot be done."""
    import evaluate as evaluator

    grid, _ = me.run_mapelites(120, 4, desc.DEFAULT_AXES, 8, surrogate_client)
    for elite in grid.elites():
        valid, reasons = evaluator.validity_gate(elite.portfolio)
        assert valid, f"cell holds an invalid portfolio: {reasons[:2]}"


# --------------------------------------------------------------------------
# Review response, 2026-08-18.
#
# Two defects this file did not previously cover:
#
#  * the driver HARDCODED the surrogate, so the illumination result the
#    writeup discusses had never been produced by the real judge -- while
#    `to_archive_records` stamped `surrogate: True` unconditionally, which
#    would have mislabelled real records the moment that changed;
#  * `consider` used a bare `>`, but per-cell comparison pits a portfolio
#    against a behaviourally SIMILAR one, which is exactly where a judge with
#    0.17 composite points of self-noise is least able to tell them apart.
# --------------------------------------------------------------------------


def test_a_real_judge_needs_explicit_spend_confirmation(tmp_path):
    code = me.main(["--evaluations", "2", "--judge", "real",
                           "--out", str(tmp_path)])
    assert code == 2, "a real judge must not run without --confirm-spend"


def test_a_real_judge_needs_an_armed_judge_config(tmp_path):
    """Even with --confirm-spend, the shipped judge config is mock, so this
    must still refuse."""
    code = me.main(["--evaluations", "2", "--judge", "real",
                           "--confirm-spend", "--out", str(tmp_path)])
    assert code == 2


def test_provenance_records_the_backend_that_actually_scored(tmp_path):
    code = me.main(["--evaluations", "20", "--seed", "0",
                           "--out", str(tmp_path)])
    assert code == 0
    payload = json.loads((tmp_path / "mapelites.json").read_text(encoding="utf-8"))
    assert payload["surrogate"] is True
    assert payload["judge"] == "surrogate"
    assert "not_a_result" in payload
    records = [json.loads(l) for l in
               (tmp_path / "archive.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    assert records and all(r["surrogate"] is True for r in records)


def test_to_archive_records_can_say_not_surrogate():
    """The flag must be able to be False, or it is decoration."""
    grid = me.Grid(DEFAULT_AXES, 4)
    import initial
    p = initial.build_policy()
    grid.consider(me.Elite(0, p, 1.0, describe(p.to_dict(), DEFAULT_AXES)),
                  cell(p.to_dict(), DEFAULT_AXES, 4))
    assert to_archive_records(grid, surrogate=False)[0]["surrogate"] is False


# -- the significance margin -------------------------------------------------


def _elite(ident, score, sem=0.0):
    import initial
    return me.Elite(ident, initial.build_policy(), score,
                           (0.0, 0.0), {}, sem=sem)


def test_an_improvement_inside_the_noise_does_not_displace_the_incumbent():
    grid = me.Grid(DEFAULT_AXES, 4, min_improvement=0.17)
    coords = (0, 0)
    assert grid.consider(_elite(1, 40.00), coords) == "discovery"
    # +0.10 is smaller than the judge's measured self-noise
    assert grid.consider(_elite(2, 40.10), coords) == "within_noise"
    assert grid.cells[coords].ident == 1
    assert grid.within_noise == 1


def test_an_improvement_beyond_the_noise_does_displace_it():
    grid = me.Grid(DEFAULT_AXES, 4, min_improvement=0.17)
    coords = (0, 0)
    grid.consider(_elite(1, 40.00), coords)
    assert grid.consider(_elite(2, 40.50), coords) == "improvement"
    assert grid.cells[coords].ident == 2


def test_a_measured_sem_widens_the_margin_beyond_the_floor():
    """When both scores carry a standard error the margin is the pooled
    standard error of their difference, not the static floor."""
    grid = me.Grid(DEFAULT_AXES, 4, min_improvement=0.01)
    coords = (0, 0)
    grid.consider(_elite(1, 40.00, sem=0.30), coords)
    # pooled sem = sqrt(0.30^2 + 0.30^2) = 0.424, so +0.40 is not significant
    assert grid.consider(_elite(2, 40.40, sem=0.30), coords) == "within_noise"
    assert grid.consider(_elite(3, 40.90, sem=0.30), coords) == "improvement"


def test_a_closed_form_backend_keeps_a_zero_margin():
    """The surrogate has no sampling noise, so any gain is real and the old
    behaviour must be preserved exactly."""
    grid = me.Grid(DEFAULT_AXES, 4, min_improvement=0.0)
    coords = (0, 0)
    grid.consider(_elite(1, 40.0), coords)
    assert grid.consider(_elite(2, 40.000001), coords) == "improvement"


def test_coverage_is_untouched_by_the_margin():
    """Coverage is the headline claim precisely because filling a cell needs no
    comparison. A stricter margin must not reduce it."""
    import initial
    loose = me.Grid(DEFAULT_AXES, 4, min_improvement=0.0)
    strict = me.Grid(DEFAULT_AXES, 4, min_improvement=99.0)
    p = initial.build_policy()
    d = describe(p.to_dict(), DEFAULT_AXES)
    for i, coords in enumerate([(0, 0), (1, 1), (2, 2)]):
        loose.consider(me.Elite(i, p, 40.0 + i, d), coords)
        strict.consider(me.Elite(i, p, 40.0 + i, d), coords)
    assert loose.coverage == strict.coverage


def test_the_null_model_exists_and_is_the_required_comparator():
    """A coverage claim without a null model is not a result.

    The 1.43x advantage in docs/ILLUMINATION.md was measured against the
    fitness-driven control alone, because the config that should have supplied
    a random baseline named a strategy ShinkaEvolve does not dispatch and had
    never run. Against a real null the result inverts: random draw reaches
    50.5% coverage against MAP-Elites' 28.9% at matched valid evaluations.

    This test exists so the null cannot quietly disappear again.
    """
    import random_baseline

    assert hasattr(random_baseline, "run")
    assert hasattr(random_baseline, "sample_portfolio")

    text = (REPO_ROOT / "docs" / "ILLUMINATION.md").read_text(encoding="utf-8")
    assert "RETRACTED" in text, (
        "docs/ILLUMINATION.md states a coverage advantage; if that claim is "
        "reinstated it must be against the random baseline, not only against "
        "the fitness-driven control."
    )


def test_random_draws_are_independent_of_each_other():
    """The null must have no memory. Two draws from different RNG states must
    not resemble each other more than chance."""
    import random as _random

    import random_baseline

    a = random_baseline.sample_portfolio(_random.Random(1)).to_dict()
    b = random_baseline.sample_portfolio(_random.Random(2)).to_dict()
    shares_a = {d["dial"]: d["share"] for d in a["dials"]}
    shares_b = {d["dial"]: d["share"] for d in b["dials"]}
    l1 = sum(abs(shares_a[k] - shares_b[k]) for k in shares_a)
    assert l1 > 0.3, f"two independent draws are suspiciously close (L1={l1:.3f})"


def test_every_random_draw_passes_the_validity_gate():
    """The null must spend its budget on scored candidates, not rejections, or
    the matched comparison is not matched."""
    import random as _random

    import evaluate as evaluator
    import random_baseline

    rng = _random.Random(0)
    for _ in range(25):
        portfolio = random_baseline.sample_portfolio(rng)
        valid, reasons = evaluator.validity_gate(portfolio)
        assert valid, f"random draw failed the gate: {reasons}"
