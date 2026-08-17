"""The offline pipeline: surrogate judge, mutation operators, analysis.

These cover the first code path that ever ran the loop end to end. Their value
is not the surrogate's numbers — those are meaningless by construction — but
the invariants the loop must hold under thousands of machine-generated
portfolios, which five hand-written seeds could never probe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "scripts", REPO_ROOT / "analysis"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import archive_analysis  # noqa: E402
import evaluate as evaluator  # noqa: E402
import offline_evolution as offline  # noqa: E402
from judge.client import MOCK, REAL, SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
from judge.surrogate import surrogate_deltas  # noqa: E402
from lowy import MEASURES  # noqa: E402


# -- the surrogate is offline, deterministic, and never mistakable for a result

def test_surrogate_makes_no_network_call(monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("the surrogate reached a network backend")

    monkeypatch.setattr(JudgeClient, "_call_anthropic", explode)
    monkeypatch.setattr(JudgeClient, "_call_openai", explode)
    monkeypatch.setattr(JudgeClient, "_assert_real_calls_authorized", explode)

    verdict = JudgeClient(JudgeConfig(mode=SURROGATE)).score(
        scenario_id="S1", scenario_text="x", prompt_text="y",
        portfolio={"dials": [{"dial": "resilience.resource_security",
                              "share": 1.0, "how": "z"}]},
    )
    assert verdict.surrogate is True
    assert verdict.cost_usd == 0.0


def test_surrogate_is_deterministic():
    portfolio = {"dials": [{"dial": "future_resources.broad_resources_2035",
                            "share": 1.0, "how": "x"}]}
    assert surrogate_deltas("S2", portfolio) == surrogate_deltas("S2", portfolio)


def test_surrogate_output_is_always_flagged_in_metrics():
    """A surrogate archive must never be readable as a scored one."""
    import initial

    result = evaluator.score_portfolio(
        initial.build_policy(), client=JudgeClient(JudgeConfig(mode=SURROGATE))
    )
    assert result["public"]["judge_surrogate"] is True


def test_mock_is_not_flagged_as_surrogate():
    import initial

    result = evaluator.score_portfolio(
        initial.build_policy(), client=JudgeClient(JudgeConfig(mode=MOCK))
    )
    assert result["public"]["judge_surrogate"] is False


def test_surrogate_mode_does_not_open_a_hole_in_the_stage_b_gate():
    """Adding a third mode must not create a way to make a real call."""
    client = JudgeClient(JudgeConfig(mode=REAL, stage_b_authorized=False))
    with pytest.raises(RuntimeError, match="stage_b_authorized"):
        client._assert_real_calls_authorized()


def test_surrogate_differentiates_scenarios():
    """The thing the real judge structurally could not do (M1 rule-5 failure)."""
    portfolio = {"dials": [{"dial": "military_capability.defence_spending",
                            "share": 1.0, "how": "x"}]}
    s1, s2 = surrogate_deltas("S1", portfolio), surrogate_deltas("S2", portfolio)
    assert s1 != s2
    assert s2["military_capability"] > s1["military_capability"], (
        "a Taiwan contingency should reward military capability more than a "
        "grinding status quo"
    )


def test_surrogate_encodes_backfire():
    heavy = {"dials": [{"dial": "military_capability.signature_capabilities",
                        "share": 1.0, "how": "x"}]}
    assert surrogate_deltas("S1", heavy)["economic_relationships"] < 0


def test_surrogate_encodes_diminishing_returns():
    """Equal effort must buy more where Japan has more headroom."""
    def one(dial):
        return {"dials": [{"dial": dial, "share": 1.0, "how": "x"}]}

    low = surrogate_deltas("S1", one("future_resources.broad_resources_2035"))
    high = surrogate_deltas("S1", one("diplomatic_influence.multilateral_power"))
    assert low["future_resources"] > high["diplomatic_influence"]


# -- the mutation operators

def test_mutation_operators_preserve_the_simplex():
    """Every operator except the deliberate saboteur must keep shares at 1.0."""
    import random

    import initial

    rng = random.Random(1)
    parent = initial.build_policy()
    for op, _weight in offline.OPERATORS:
        if op is offline.op_break_invariant:
            continue
        for _ in range(20):
            child = offline._clone(parent)
            op(child, rng)
            total = child.total_share()
            assert abs(total - 1.0) <= DEFAULT_TOL, (
                f"{op.__name__} left shares at {total!r}"
            )


DEFAULT_TOL = 1e-6


def test_the_saboteur_operator_is_always_caught_by_the_gate():
    """If the gate ever passes these, the gate has stopped working."""
    import random

    import initial

    rng = random.Random(3)
    for _ in range(25):
        child = offline._clone(initial.build_policy())
        offline.op_break_invariant(child, rng)
        valid, reasons = evaluator.validity_gate(child)
        assert not valid and reasons


def test_clone_does_not_alias_the_parent():
    import initial

    parent = initial.build_policy()
    before = parent.to_dict()
    child = offline._clone(parent)
    child.invest("cultural_influence.people_exchanges", share=0.9, how="mutated")
    assert parent.to_dict() == before, "mutating a child changed its parent"


# -- the loop and the analysis

@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("offline")
    summary = offline.run(generations=40, seed=7, out_dir=out)
    return summary, out


def test_the_loop_runs_and_writes_its_artifacts(small_run):
    summary, out = small_run
    assert summary["surrogate"] is True
    assert summary["evaluated"] == 41
    for name in ("archive.jsonl", "trajectory.json", "summary.json"):
        assert (out / name).is_file()


def test_the_loop_is_reproducible_from_its_seed(tmp_path):
    a = offline.run(generations=25, seed=11, out_dir=tmp_path / "a")
    b = offline.run(generations=25, seed=11, out_dir=tmp_path / "b")
    assert a["best_score"] == b["best_score"]
    assert (tmp_path / "a" / "archive.jsonl").read_text() == \
           (tmp_path / "b" / "archive.jsonl").read_text()


def test_invalid_individuals_score_zero_and_never_win(small_run):
    _summary, out = small_run
    records = [json.loads(l) for l in (out / "archive.jsonl").read_text().splitlines()]
    for record in records:
        if not record["valid"]:
            assert record["score"] == 0.0
    best = max(records, key=lambda r: r["score"])
    assert best["valid"], "an invalid portfolio became the champion"


def test_analysis_reads_the_archive_and_flags_it_surrogate(small_run, tmp_path):
    _summary, out = small_run
    records = archive_analysis.load_archive(out / "archive.jsonl")
    stats = archive_analysis.analyse(records)
    assert stats["surrogate"] is True
    assert stats["not_a_result"]
    assert set(stats["effort_best"]) == set(MEASURES)
    assert stats["best_lineage"][0] == 0, "lineage must trace back to the seed"


def test_analysis_report_carries_the_not_a_result_warning(small_run, tmp_path):
    _summary, out = small_run
    records = archive_analysis.load_archive(out / "archive.jsonl")
    report = archive_analysis.write_report(
        archive_analysis.analyse(records), records, tmp_path
    )
    assert "NOT A RESULT" in report.read_text()


def test_figures_are_valid_standalone_svg(small_run, tmp_path):
    _summary, out = small_run
    records = archive_analysis.load_archive(out / "archive.jsonl")
    seed = min(records, key=lambda r: r["generation"])
    best = max(records, key=lambda r: r["score"])
    archive_analysis.figure_trajectory(records, tmp_path / "t.svg")
    archive_analysis.figure_measure_shift(seed, best, tmp_path / "e.svg")
    for name in ("t.svg", "e.svg"):
        text = (tmp_path / name).read_text()
        assert text.startswith("<svg") and text.rstrip().endswith("</svg>")
