"""Test 3: the seed portfolio through evaluate.py with the mock judge gives 38.8.

KICKOFF Stage A done-condition. With all-zero deltas the pipeline must return
Japan's published 2025 composite exactly — proof that every step downstream of
the judge is the published index and nothing else. Also asserts the fail-closed
rule: no network call is possible in mock mode.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import lowy
from evaluate import TASK_DIR, score_portfolio
from initial import build_policy
from judge.client import JudgeClient, JudgeConfig

REPO_ROOT = Path(__file__).resolve().parents[1]

EXACT_BASELINE = 38.8475
REPORTED_BASELINE = 38.8


@pytest.fixture()
def mock_client():
    return JudgeClient(JudgeConfig(mode="mock"))


def test_seed_scores_the_2025_baseline_under_the_mock_judge(mock_client):
    metrics = score_portfolio(build_policy(), client=mock_client)
    score = metrics["combined_score"]
    assert score == pytest.approx(EXACT_BASELINE, abs=1e-9)
    assert round(score, lowy.COMPOSITE_DECIMALS) == REPORTED_BASELINE


def test_all_three_scenarios_are_scored_and_reported(mock_client):
    metrics = score_portfolio(build_policy(), client=mock_client)
    public = metrics["public"]
    for scenario_id in ("S1", "S2", "S3"):
        assert public[f"composite_{scenario_id}"] == pytest.approx(
            EXACT_BASELINE, abs=1e-3
        )
    assert public["worst_case_composite"] == pytest.approx(EXACT_BASELINE, abs=1e-3)
    assert public["judge_mocked"] is True
    assert public["judge_cost_usd"] == 0.0


def test_metrics_carry_the_shinka_contract(mock_client):
    metrics = score_portfolio(build_policy(), client=mock_client)
    assert set(metrics) >= {"combined_score", "public", "private", "text_feedback"}
    assert isinstance(metrics["text_feedback"], str)
    assert len(metrics["text_feedback"]) <= 1200
    assert set(metrics["private"]["per_scenario_deltas"]) == {"S1", "S2", "S3"}
    # The judge sees the portfolio JSON, never the program.
    assert "def build_policy" not in json.dumps(metrics["private"])


def test_mock_judge_makes_no_network_call(monkeypatch, mock_client):
    """Fail closed: mock mode must not be able to reach the network at all."""

    def explode(*args, **kwargs):
        raise AssertionError("mock mode attempted a network call")

    monkeypatch.setattr("socket.socket.connect", explode)
    metrics = score_portfolio(build_policy(), client=mock_client)
    assert metrics["combined_score"] == pytest.approx(EXACT_BASELINE, abs=1e-9)


def test_real_mode_refuses_without_stage_b_authorization():
    """KICKOFF hard rule 1: mode=real is not enough on its own."""
    client = JudgeClient(JudgeConfig(mode="real", stage_b_authorized=False))
    with pytest.raises(RuntimeError, match="stage_b_authorized=false"):
        client._assert_real_calls_authorized()


def test_shipped_judge_config_is_mock_and_unauthorized():
    """The config in the repo must never be committed in an armed state."""
    config = JudgeConfig.load(str(REPO_ROOT / "configs" / "judge.yaml"))
    assert config.mode == "mock"
    assert config.stage_b_authorized is False
    assert config.temperature == 0.0
    assert config.model, "a judge model id must be pinned in config"


def test_cache_key_changes_when_the_rubric_changes(mock_client):
    portfolio = build_policy().to_dict()
    args = dict(scenario_id="S1", scenario_text="world", portfolio=portfolio)
    key_a = mock_client.cache_key(prompt_text="rubric A", **args)
    key_b = mock_client.cache_key(prompt_text="rubric B", **args)
    assert key_a != key_b, "editing the rubric must invalidate cached verdicts"


def test_cache_key_is_stable_across_dial_insertion_order(mock_client):
    """to_dict() is canonical, so re-ordering invest() calls must not re-score."""
    from schema import PolicyPortfolio

    def build(order):
        p = PolicyPortfolio(horizon=(2026, 2030))
        for dial_id, share in order:
            p.invest(dial_id, share=share, how="x")
        return p.to_dict()

    pairs = [
        ("economic_capability.size", 0.5),
        ("military_capability.armed_forces", 0.5),
    ]
    args = dict(scenario_id="S1", scenario_text="w", prompt_text="r")
    assert mock_client.cache_key(portfolio=build(pairs), **args) == mock_client.cache_key(
        portfolio=build(list(reversed(pairs))), **args
    )


def test_cli_end_to_end_prints_the_baseline(tmp_path):
    """The full CLI path ShinkaEvolve uses: python evaluate.py --program_path ..."""
    results_dir = tmp_path / "results"
    completed = subprocess.run(
        [
            sys.executable,
            str(TASK_DIR / "evaluate.py"),
            "--program_path",
            str(TASK_DIR / "initial.py"),
            "--results_dir",
            str(results_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr

    metrics = json.loads((results_dir / "metrics.json").read_text(encoding="utf-8"))
    correct = json.loads((results_dir / "correct.json").read_text(encoding="utf-8"))

    assert correct["correct"] is True
    assert metrics["combined_score"] == pytest.approx(EXACT_BASELINE, abs=1e-9)
    assert f"{REPORTED_BASELINE}" in completed.stdout


def test_invalid_program_scores_zero_with_a_reason(tmp_path):
    """A malformed portfolio gets fitness 0 and a readable reason, not a crash."""
    program = tmp_path / "broken.py"
    program.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {str(TASK_DIR)!r})\n"
        "from schema import PolicyPortfolio\n"
        "def build_policy():\n"
        "    p = PolicyPortfolio(horizon=(2026, 2030))\n"
        "    p.invest('economic_capability.size', share=0.42, how='does not sum to 1')\n"
        "    return p\n",
        encoding="utf-8",
    )
    results_dir = tmp_path / "results"
    subprocess.run(
        [
            sys.executable,
            str(TASK_DIR / "evaluate.py"),
            "--program_path",
            str(program),
            "--results_dir",
            str(results_dir),
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=120,
        check=True,
    )
    metrics = json.loads((results_dir / "metrics.json").read_text(encoding="utf-8"))
    correct = json.loads((results_dir / "correct.json").read_text(encoding="utf-8"))

    assert correct["correct"] is False
    assert metrics["combined_score"] == 0.0
    assert "shares must sum to 1.0" in metrics["text_feedback"]
