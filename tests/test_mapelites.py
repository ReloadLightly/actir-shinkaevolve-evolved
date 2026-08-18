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
from judge.client import SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
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
