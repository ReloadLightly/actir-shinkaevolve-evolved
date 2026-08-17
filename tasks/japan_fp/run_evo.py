#!/usr/bin/env python3
"""Launch a ShinkaEvolve run on the Japan foreign-policy task.

    python tasks/japan_fp/run_evo.py --config_path configs/pilot.yaml

Before the engine starts this writes a provenance manifest (KICKOFF hard rule
5): the config snapshot, the git hash, the RNG seed, and the judge's identity.
The judge's own per-call ledger and content-hash cache are written by the judge
client as the run proceeds.

Nothing here bypasses the judge gate: the run inherits configs/judge.yaml, so a
run started before Stage B is authorized scores every portfolio with the mock
judge and never touches the network.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple

import yaml

TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from judge.client import JudgeConfig  # noqa: E402

TASK_SYS_MSG = """You are evolving a Python program that outputs a Japanese foreign-policy portfolio for 2026-2030.

The program's EVOLVE-BLOCK builds a PolicyPortfolio: an allocation of Japan's marginal strategic effort across the 30 submeasures of the Lowy Institute's Asia Power Index, with one capped sentence per submeasure saying what the effort buys, an ordered sequence of phases, and free-slot custom initiatives.

Fitness is Japan's projected Lowy composite in 2030, averaged over three fixed scenarios: a grinding status quo, a Taiwan contingency, and US retrenchment. The 2025 baseline composite is 38.8, so that is the number to beat.

What actually moves the score:

1. Shares must sum to 1.0 exactly. Reallocating means taking effort from somewhere.
2. Effort is not achievement. An evaluator judges, per scenario, whether the effort plausibly moves the measure - including backfire, where effort on one measure lowers another. You cannot buy index points directly.
3. Japan starts at 85.4 on diplomatic influence and 11.3 on future resources. Returns diminish sharply where Japan is already strong.
4. The three scenarios reward different things. A portfolio tuned to one may collapse in another; the worst-case composite is reported alongside the mean.
5. custom_initiatives is the open slot for a genuinely novel policy - not a recombination of what is already there. Each must name the submeasures it targets.

Read the evaluator's feedback: it contains the causal mechanism sentences behind each measure's change. They tell you where the portfolio's logic failed, not just that it scored badly.

Explore boldly. Portfolios that merely re-weight the December 2022 seed will not find anything the seed did not already contain."""


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
    except Exception:  # noqa: BLE001 - provenance must never block a run
        return "unknown"


def _git_is_dirty() -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        )
        return bool(out.strip())
    except Exception:  # noqa: BLE001
        return False


def write_run_manifest(
    config_path: Path, config: Dict[str, Any], results_dir: Path, seed: int
) -> None:
    judge = JudgeConfig.load()
    frozen_path = TASK_DIR / "FROZEN.json"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8")) if frozen_path.is_file() else {}

    manifest = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config_path": str(config_path),
        "config_snapshot": config,
        "git_hash": _git_hash(),
        "git_dirty": _git_is_dirty(),
        "rng_seed": seed,
        "judge": {
            "mode": judge.mode,
            "stage_b_authorized": judge.stage_b_authorized,
            **judge.identity(),
        },
        "frozen_files": {
            "version": frozen.get("version"),
            "status": frozen.get("status"),
            "files": frozen.get("files", {}),
        },
    }
    results_dir.mkdir(parents=True, exist_ok=True)
    with (results_dir / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)

    print(f"Run manifest written to {results_dir / 'run_manifest.json'}")
    print(f"  git {manifest['git_hash'][:12]}{' (dirty)' if manifest['git_dirty'] else ''}")
    print(f"  judge mode: {judge.mode} | model: {judge.model}")
    print(f"  frozen files: {frozen.get('version')} ({frozen.get('status')})")
    if judge.mode == "mock":
        print("  NOTE: judge is in MOCK mode - every portfolio will score 38.8475.")


def prepare_run(
    config_path: str, seed: int, write_manifest: bool = True
) -> Tuple[Path, Dict[str, Any], Path]:
    """Load the config, resolve paths, seed the RNG, write the manifest.

    Deliberately free of any ShinkaEvolve import, for two reasons: the
    provenance guarantee (KICKOFF hard rule 5) is then testable without the
    engine installed, and ``--dry-run`` can validate a config on a machine that
    has never had ShinkaEvolve on it. Everything that can be checked before the
    engine starts is checked here.
    """
    path = Path(config_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.is_file():
        raise FileNotFoundError(f"no such config: {path}")
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)

    for section in ("evo_config", "db_config"):
        if section not in config:
            raise KeyError(f"{path.name} has no {section!r} section")

    random.seed(seed)
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    os.environ["JAPAN_FP_TASK_DIR"] = str(TASK_DIR)

    config["evo_config"]["task_sys_msg"] = TASK_SYS_MSG
    results_dir = REPO_ROOT / config["evo_config"].get("results_dir", "runs/unnamed")
    config["evo_config"]["results_dir"] = str(results_dir)

    init_program = REPO_ROOT / config["evo_config"]["init_program_path"]
    if not init_program.is_file():
        raise FileNotFoundError(f"seed program does not exist: {init_program}")
    config["evo_config"]["init_program_path"] = str(init_program)

    if write_manifest:
        write_run_manifest(path, config, results_dir, seed)
    return path, config, results_dir


def main(config_path: str, seed: int, dry_run: bool = False) -> None:
    path, config, results_dir = prepare_run(config_path, seed)

    if dry_run:
        evo = config["evo_config"]
        print("DRY RUN — the engine is not started and nothing is spent.")
        print(f"  config:      {path.relative_to(REPO_ROOT)}")
        print(f"  generations: {evo['num_generations']}")
        print(f"  ceiling:     ${evo['max_api_costs']:.2f}")
        print(f"  ensemble:    {evo.get('llm_models')}")
        print(f"  seed program:{evo['init_program_path']}")
        print(f"  results:     {results_dir}")
        return

    from shinka.core import EvolutionConfig, ShinkaEvolveRunner
    from shinka.database import DatabaseConfig
    from shinka.launch import LocalJobConfig

    runner = ShinkaEvolveRunner(
        evo_config=EvolutionConfig(**config["evo_config"]),
        job_config=LocalJobConfig(
            eval_program_path=str(TASK_DIR / "evaluate.py"),
            time="00:10:00",
        ),
        db_config=DatabaseConfig(**config["db_config"]),
        max_evaluation_jobs=config.get("max_evaluation_jobs"),
        max_proposal_jobs=config.get("max_proposal_jobs"),
        max_db_workers=config.get("max_db_workers"),
        verbose=True,
    )
    runner.run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evolve Japanese foreign policy.")
    parser.add_argument("--config_path", type=str, default="configs/pilot.yaml")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true",
                        help="load the config, write the manifest, print what "
                             "would run, and stop. Needs no ShinkaEvolve and "
                             "spends nothing.")
    args = parser.parse_args()
    main(args.config_path, args.seed, dry_run=args.dry_run)
