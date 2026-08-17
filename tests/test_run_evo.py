"""The run launcher: provenance, config resolution, and the mutation prompt.

`run_evo.py` had no test coverage at all, while carrying KICKOFF hard rule 5 —
"every run writes provenance". A provenance guarantee nothing checks is a
guarantee only until the first time it quietly breaks, and it would break
invisibly: the run still completes, the manifest is just wrong or absent, and
nobody notices until they try to reproduce a result months later.

None of this needs ShinkaEvolve installed. `prepare_run` is deliberately free
of engine imports so the manifest path stays testable and `--dry-run` works on
a machine that has never had the engine on it.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"

import run_evo  # noqa: E402
from judge.client import JudgeConfig  # noqa: E402

ALL_CONFIGS = sorted(
    [p for p in (REPO_ROOT / "configs").glob("*.yaml") if p.name != "judge.yaml"]
    + list((REPO_ROOT / "configs" / "ablations").glob("*.yaml"))
)


# --------------------------------------------------------------------------
# Hard rule 5: every run writes provenance
# --------------------------------------------------------------------------


def test_manifest_records_everything_a_rerun_would_need(tmp_path):
    config_path = REPO_ROOT / "configs" / "pilot.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    run_evo.write_run_manifest(config_path, config, tmp_path, seed=7)

    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    # The five things KICKOFF hard rule 5 names.
    assert manifest["config_snapshot"] == config, "config must be snapshotted, not referenced"
    assert manifest["git_hash"]
    assert manifest["rng_seed"] == 7
    assert manifest["judge"]["model"]
    assert manifest["frozen_files"]["version"]

    # And the things that make the snapshot interpretable later.
    assert "started_at" in manifest
    assert isinstance(manifest["git_dirty"], bool)
    assert manifest["judge"]["mode"] in {"mock", "real"}
    assert "stage_b_authorized" in manifest["judge"]


def test_manifest_snapshot_is_a_copy_not_a_live_reference(tmp_path):
    """If the manifest held a reference, a later mutation of the config dict
    would silently rewrite the record of what was run."""
    config = yaml.safe_load(
        (REPO_ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    )
    run_evo.write_run_manifest(REPO_ROOT / "configs" / "pilot.yaml", config, tmp_path, 0)
    written = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    config["evo_config"]["num_generations"] = 99999
    assert written["config_snapshot"]["evo_config"]["num_generations"] != 99999


def test_manifest_records_the_frozen_file_hashes(tmp_path):
    """A result is only reproducible if you know which rubric produced it."""
    config = yaml.safe_load(
        (REPO_ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    )
    run_evo.write_run_manifest(REPO_ROOT / "configs" / "pilot.yaml", config, tmp_path, 0)
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    frozen = json.loads((TASK_DIR / "FROZEN.json").read_text(encoding="utf-8"))
    assert manifest["frozen_files"]["files"] == frozen["files"]
    assert manifest["frozen_files"]["status"] == frozen["status"]


def test_manifest_records_the_judge_lock_state(tmp_path):
    """A run made under the mock judge must be identifiable as such forever.

    Every mock run scores 38.8475. Without this field in the manifest, a mock
    run's output is indistinguishable from a real run where the judge saw no
    effect anywhere — the two mean completely different things.
    """
    config = yaml.safe_load(
        (REPO_ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    )
    run_evo.write_run_manifest(REPO_ROOT / "configs" / "pilot.yaml", config, tmp_path, 0)
    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))

    shipped = JudgeConfig.load()
    assert manifest["judge"]["mode"] == shipped.mode
    assert manifest["judge"]["stage_b_authorized"] == shipped.stage_b_authorized


def test_provenance_never_blocks_a_run(monkeypatch, tmp_path):
    """Git failing is not a reason to lose a run; it is a reason to record
    'unknown' and carry on."""
    def boom(*_a, **_k):
        raise OSError("git is not available")

    monkeypatch.setattr(subprocess, "check_output", boom)
    assert run_evo._git_hash() == "unknown"
    assert run_evo._git_is_dirty() is False


# --------------------------------------------------------------------------
# Config resolution
# --------------------------------------------------------------------------


@pytest.mark.parametrize("config_path", ALL_CONFIGS, ids=lambda p: p.name)
def test_every_shipped_config_loads_and_resolves(config_path, tmp_path):
    """Every config must survive path resolution before Stage C, not during it."""
    path, config, results_dir = run_evo.prepare_run(
        str(config_path), seed=0, write_manifest=False
    )
    assert path == config_path
    assert Path(config["evo_config"]["init_program_path"]).is_file()
    assert Path(config["evo_config"]["results_dir"]).is_absolute()
    assert results_dir.is_absolute()


def test_prepare_run_rejects_a_missing_config():
    with pytest.raises(FileNotFoundError, match="no such config"):
        run_evo.prepare_run("configs/does_not_exist.yaml", seed=0, write_manifest=False)


def test_prepare_run_rejects_a_config_missing_a_section(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("evo_config:\n  num_generations: 1\n", encoding="utf-8")
    with pytest.raises(KeyError, match="db_config"):
        run_evo.prepare_run(str(bad), seed=0, write_manifest=False)


def test_prepare_run_rejects_a_missing_seed_program(tmp_path):
    """Caught before the engine starts rather than on the first generation."""
    config = yaml.safe_load(
        (REPO_ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    )
    config["evo_config"]["init_program_path"] = "tasks/japan_fp/no_such_seed.py"
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump(config), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match="seed program does not exist"):
        run_evo.prepare_run(str(bad), seed=0, write_manifest=False)


def test_the_task_dir_env_var_is_set_for_the_evaluator(tmp_path):
    """initial.py resolves schema.py through JAPAN_FP_TASK_DIR when it runs
    from a per-generation folder. Unset, every generation fails to import."""
    import os

    monkey = os.environ.pop("JAPAN_FP_TASK_DIR", None)
    try:
        run_evo.prepare_run("configs/pilot.yaml", seed=0, write_manifest=False)
        assert os.environ["JAPAN_FP_TASK_DIR"] == str(TASK_DIR)
    finally:
        if monkey is not None:
            os.environ["JAPAN_FP_TASK_DIR"] = monkey


def test_dry_run_needs_no_engine_and_starts_nothing():
    """--dry-run must work where ShinkaEvolve is not installed, which is the
    case in this test environment."""
    result = subprocess.run(
        [sys.executable, str(TASK_DIR / "run_evo.py"),
         "--config_path", "configs/pilot.yaml", "--dry-run"],
        capture_output=True, text=True, timeout=120, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "DRY RUN" in result.stdout
    assert "MOCK mode" in result.stdout, "a mock-judge run must announce itself"


# --------------------------------------------------------------------------
# The mutation prompt: it is shipped text that steers every generation
# --------------------------------------------------------------------------


def test_the_mutation_prompt_never_names_the_judge():
    """The mutation LLM must not learn which model grades it.

    Naming the judge invites writing to that model's known habits rather than
    to the policy problem — the search would optimise the grader instead of
    the portfolio, and hard rule 2's separation would be defeated by prose
    rather than by configuration.
    """
    prompt = run_evo.TASK_SYS_MSG.lower()
    for token in ("gpt-4", "gpt-5", "claude", "openai", "anthropic", "haiku"):
        assert token not in prompt, f"the mutation prompt names the judge: {token!r}"


def test_the_mutation_prompt_states_the_binding_constraints():
    """These are the constraints the validity gate enforces for free. A prompt
    that omits them spends generations on portfolios the gate rejects."""
    prompt = run_evo.TASK_SYS_MSG
    assert "sum to 1.0" in prompt
    assert "38.8" in prompt, "the number to beat must be stated"
    assert "30 submeasures" in prompt


def test_the_mutation_prompt_warns_about_the_three_judge_rules_that_bite():
    """Effort-is-not-achievement, backfire, and diminishing returns are the
    three rubric rules that most often make a confident portfolio score badly."""
    prompt = run_evo.TASK_SYS_MSG
    assert "Effort is not achievement" in prompt
    assert "backfire" in prompt
    assert "85.4" in prompt and "11.3" in prompt, "diminishing returns need anchors"


def test_the_mutation_prompt_asks_for_novelty_not_reweighting():
    """RESEARCH_DESIGN §1 rule 4 inherits the paper's warning that evolution
    tends to stay near its initialization."""
    prompt = run_evo.TASK_SYS_MSG
    assert "custom_initiatives" in prompt
    assert "re-weight" in prompt


def test_the_mutation_prompt_is_carried_into_every_config(tmp_path):
    _path, config, _results = run_evo.prepare_run(
        "configs/pilot.yaml", seed=0, write_manifest=False
    )
    assert config["evo_config"]["task_sys_msg"] == run_evo.TASK_SYS_MSG
