"""The gates that stop a real scored run from starting when it should not.

Every test here corresponds to a defect found in review of the state at
`20ca8b4`, where each of these paths was open:

* three of nine configs named a `parent_selection_strategy` ShinkaEvolve does
  not dispatch, and would have raised `ValueError` mid-run, after spending;
* `FROZEN.json` had said "NEEDS ROLAND'S RE-APPROVAL before any scored run"
  since revision 2, and nothing read it;
* the judge had no spend ceiling of any kind, because ShinkaEvolve's
  `max_api_costs` meters only its own mutation/embedding/novelty/meta calls and
  never sees the judge -- three calls per scored candidate, unbounded.

A gate with no test is a gate until someone edits it.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"

import run_evo  # noqa: E402
from judge.client import (  # noqa: E402
    JudgeBudgetExceeded,
    JudgeClient,
    JudgeConfig,
)

ALL_CONFIGS = sorted(
    [p for p in (REPO_ROOT / "configs").glob("*.yaml") if p.name != "judge.yaml"]
    + list((REPO_ROOT / "configs" / "ablations").glob("*.yaml"))
)


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# -- engine enums ------------------------------------------------------------


@pytest.mark.parametrize("config_path", ALL_CONFIGS, ids=lambda p: p.name)
def test_every_config_names_a_strategy_the_engine_dispatches(config_path):
    """Read from shinka/database/parents.py::sample_parent at the pinned commit.

    An unknown name raises ValueError at SAMPLING time -- deep inside a run,
    after money has been spent -- which is why --dry-run reported these configs
    as valid for weeks.
    """
    problems = run_evo.check_engine_enums(_load(config_path))
    assert not problems, "; ".join(problems)


def test_the_known_bad_strategy_names_are_actually_rejected():
    """The gate must be able to fail, or it proves nothing. These three are the
    exact values that shipped."""
    for bad in ("random", "best", "hill_climbing"):
        config = {"db_config": {"parent_selection_strategy": bad}}
        problems = run_evo.check_engine_enums(config)
        assert problems, f"{bad!r} must be rejected"
        assert bad in problems[0]


def test_the_valid_set_matches_the_pinned_engine():
    assert set(run_evo.VALID_PARENT_STRATEGIES) == {
        "power_law", "weighted", "beam_search", "best_of_n", "sequential",
    }
    assert run_evo.SHINKA_COMMIT == "6ec47cdddf2f7aea64848d872b8d9a1f7ce17bcd"


def test_the_workflow_installs_the_pinned_commit():
    """An unpinned engine means two runs of one config are not the same
    experiment, which silently voids the matched-budget comparison."""
    text = (REPO_ROOT / ".github" / "workflows" / "pilot.yml").read_text(encoding="utf-8")
    assert f"ShinkaEvolve.git@{run_evo.SHINKA_COMMIT}" in text
    assert "ShinkaEvolve.git\"" not in text, "an unpinned install remains"


# -- the FROZEN gate ---------------------------------------------------------


def test_a_draft_evaluator_blocks_a_scored_run():
    """FROZEN.json currently says DRAFT, so this must report a blocker. When
    the rubric is re-approved this test's expectation flips -- deliberately, so
    that approving it is a visible edit rather than a silent one."""
    frozen = json.loads((TASK_DIR / "FROZEN.json").read_text(encoding="utf-8"))
    problems = run_evo.check_evaluator_is_frozen()
    if frozen.get("status") == "FROZEN":
        assert not problems
    else:
        assert problems and "not FROZEN" in problems[0]


# -- budget ceilings ---------------------------------------------------------


@pytest.mark.parametrize("config_path", ALL_CONFIGS, ids=lambda p: p.name)
def test_every_config_declares_both_ceilings(config_path):
    problems = run_evo.check_budget_ceilings(_load(config_path))
    assert not problems, "; ".join(problems)


@pytest.mark.parametrize("config_path", ALL_CONFIGS, ids=lambda p: p.name)
def test_the_all_in_ceiling_covers_mutation_plus_judge(config_path):
    config = _load(config_path)
    declared = (float(config["evo_config"]["max_api_costs"])
                + float(config["judge_max_cost_usd"]))
    assert float(config["run_max_cost_usd"]) >= declared - 1e-9


def test_a_missing_judge_ceiling_is_a_blocker():
    config = {"evo_config": {"max_api_costs": 2.0}, "run_max_cost_usd": 2.0}
    problems = run_evo.check_budget_ceilings(config)
    assert any("judge_max_cost_usd" in p for p in problems)


def test_an_all_in_ceiling_that_does_not_cover_its_parts_is_a_blocker():
    config = {"evo_config": {"max_api_costs": 4.0},
              "judge_max_cost_usd": 4.0, "run_max_cost_usd": 5.0}
    problems = run_evo.check_budget_ceilings(config)
    assert any("run_max_cost_usd" in p for p in problems)


# -- the ceiling is ENFORCED, not merely declared -----------------------------


def test_the_judge_refuses_a_call_once_the_ledger_passes_the_ceiling(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"cost_usd": 2.5}) + "\n", encoding="utf-8")
    client = JudgeClient(JudgeConfig(
        mode="real", stage_b_authorized=True, provider="openai",
        model="gpt-4.1-mini", ledger_path=str(ledger), max_cost_usd=1.0,
    ))
    assert client.spent_usd() == pytest.approx(2.5)
    with pytest.raises(JudgeBudgetExceeded):
        client._assert_within_budget()


def test_spend_is_read_from_the_ledger_not_from_memory(tmp_path):
    """ShinkaEvolve runs evaluate.py as a subprocess per candidate, so an
    in-process counter would reset to zero on every evaluation and enforce
    nothing. The ledger is the only thing that survives."""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        "\n".join(json.dumps({"cost_usd": c}) for c in (0.4, 0.4, 0.4)) + "\n",
        encoding="utf-8",
    )
    config = JudgeConfig(mode="real", stage_b_authorized=True, provider="openai",
                         model="gpt-4.1-mini", ledger_path=str(ledger),
                         max_cost_usd=1.0)
    fresh_process = JudgeClient(config)          # no shared state with any other
    assert fresh_process.spent_usd() == pytest.approx(1.2)
    with pytest.raises(JudgeBudgetExceeded):
        fresh_process._assert_within_budget()


def test_no_ceiling_means_unbounded_and_that_is_explicit(tmp_path):
    """Absence of a ceiling must not silently become a ceiling of zero."""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"cost_usd": 99.0}) + "\n", encoding="utf-8")
    client = JudgeClient(JudgeConfig(
        mode="real", stage_b_authorized=True, provider="openai",
        model="gpt-4.1-mini", ledger_path=str(ledger), max_cost_usd=None,
    ))
    client._assert_within_budget()      # must not raise


def test_the_ceiling_reaches_a_subprocess_through_the_environment(monkeypatch, tmp_path):
    """run_evo.py exports it; evaluate.py's JudgeConfig.load must pick it up,
    because there is no other channel between those two processes."""
    judge_yaml = tmp_path / "judge.yaml"
    judge_yaml.write_text("mode: mock\nstage_b_authorized: false\n", encoding="utf-8")
    monkeypatch.setenv("JAPAN_FP_JUDGE_MAX_COST_USD", "3.25")
    config = JudgeConfig.load(str(judge_yaml))
    assert config.max_cost_usd == pytest.approx(3.25)
