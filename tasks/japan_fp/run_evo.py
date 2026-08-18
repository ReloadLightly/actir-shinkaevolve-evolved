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
from typing import Any, Dict, List, Tuple

import yaml

TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parents[1]
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from judge.client import JudgeConfig  # noqa: E402

TASK_SYS_MSG = """You are evolving a Python program that outputs a Japanese foreign-policy portfolio for 2026-2030.

The program's EVOLVE-BLOCK builds a PolicyPortfolio: an allocation of Japan's marginal strategic effort across the 30 submeasures of the Lowy Institute's Asia Power Index, with one capped sentence per submeasure saying what the effort buys, an ordered sequence of phases, and free-slot custom initiatives.

Fitness is Japan's projected Lowy composite in 2030, averaged over three fixed scenarios: a grinding status quo, a Taiwan contingency, and US retrenchment. The 2025 baseline composite is 38.8, so that is the number to beat.

Hard limits, checked for free before any scoring happens. A portfolio breaking one of these is thrown away and its generation is wasted, so read them once:

* **The 30 dial names are fixed.** They are the Lowy Index's own submeasures and no others exist. Anywhere a dial is named - including a phase's focus list - it must be one of the 30 already in the program. The 2026-08-18 preflight had a model invent `military_capability.nuclear_deterrence`, which is a real policy idea and not a Lowy submeasure; that portfolio was discarded whole. If you want to propose something the 30 dials cannot express, that is exactly what `custom_initiatives` is for.
* **defence_spending_path must stay within 0.5 and 3.5 per cent of GDP**, every year. The same preflight had a model propose 7.0%, which is not a Japanese defence budget under any government. 3.5 is already far beyond the 2022 decision.
* Phases must be ordered and lie inside 2026-2030; every dial carrying effort needs a non-empty `how` under 240 characters; every custom initiative must name the submeasures it targets.

What actually moves the score:

1. Shares are proportions of one finite budget of effort, and are normalised for you - so do not spend effort on arithmetic, spend it on the allocation. What matters is the trade-off: raising one dial must lower others, because there is no more effort to be had.
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
        "shinka_commit": SHINKA_COMMIT,
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


# --------------------------------------------------------------------------
# Pre-launch gates. Every one of these was added on 2026-08-18 in response to a
# review of the state at 20ca8b4, and every one closes a path by which a real
# scored run could have started when it should not have.
# --------------------------------------------------------------------------

#: The parent-selection strategies ShinkaEvolve actually dispatches on. Read
#: from shinka/database/parents.py::sample_parent at commit 6ec47cd; anything
#: else raises ValueError *at sampling time*, i.e. after the run has started and
#: after money has been spent. Three of our nine configs carried invalid names
#: (`random`, `best`, `hill_climbing`) and would have died mid-run.
#: The ShinkaEvolve commit these configs were validated against, and the
#: one the workflows install. Recorded in every run manifest.
SHINKA_COMMIT: str = "6ec47cdddf2f7aea64848d872b8d9a1f7ce17bcd"

VALID_PARENT_STRATEGIES: Tuple[str, ...] = (
    "power_law", "weighted", "beam_search", "best_of_n", "sequential",
)

#: Island sampling, from dbase.py's documented set.
VALID_ISLAND_STRATEGIES: Tuple[str, ...] = (
    "uniform", "equal", "proportional", "weighted",
)


def check_engine_enums(config: Dict[str, Any]) -> List[str]:
    """Config values the engine will reject, found before it starts.

    --dry-run previously reported these configs as valid because the strategy
    name is only resolved when a parent is first sampled, deep inside a run.
    """
    problems = []
    db = config.get("db_config", {}) or {}
    parent = db.get("parent_selection_strategy")
    if parent is not None and parent not in VALID_PARENT_STRATEGIES:
        problems.append(
            f"db_config.parent_selection_strategy={parent!r} is not dispatched "
            f"by ShinkaEvolve; valid: {', '.join(VALID_PARENT_STRATEGIES)}"
        )
    island = db.get("island_selection_strategy")
    if island is not None and island not in VALID_ISLAND_STRATEGIES:
        problems.append(
            f"db_config.island_selection_strategy={island!r} is not valid; "
            f"valid: {', '.join(VALID_ISLAND_STRATEGIES)}"
        )
    return problems


def _frozen_manifest() -> Dict[str, Any]:
    path = TASK_DIR / "FROZEN.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def check_evaluator_is_frozen() -> List[str]:
    """A scored run may not start against a DRAFT rubric.

    FROZEN.json has said "NEEDS ROLAND'S RE-APPROVAL before any scored run"
    since revision 2, and nothing enforced it. Set status to FROZEN in
    tasks/japan_fp/FROZEN.json to authorise.
    """
    frozen = _frozen_manifest()
    status = frozen.get("status")
    if status != "FROZEN":
        return [
            f"the evaluator is {status!r}, not FROZEN. {frozen.get('note', '')}"
        ]
    return []


def check_budget_ceilings(config: Dict[str, Any]) -> List[str]:
    """Both ceilings must be declared, and the all-in one must bound the run.

    ShinkaEvolve's max_api_costs meters only ITS OWN calls -- mutation,
    embedding, novelty, meta. The judge is an external client it never sees, at
    three calls per scored candidate, so a run configured to "$2.00" could
    spend $2.00 of mutation plus an unbounded amount of judge on top. These two
    keys make the judge ceiling explicit and enforced.
    """
    evo = config.get("evo_config", {}) or {}
    problems = []
    if evo.get("max_api_costs") is None:
        problems.append("evo_config.max_api_costs is unset: mutation is unbounded")
    judge_ceiling = config.get("judge_max_cost_usd")
    if judge_ceiling is None:
        problems.append(
            "judge_max_cost_usd is unset. ShinkaEvolve does not meter the "
            "judge, so without this the run has no ceiling on judge spend."
        )
    total = config.get("run_max_cost_usd")
    if total is None:
        problems.append("run_max_cost_usd (all-in ceiling) is unset")
    elif evo.get("max_api_costs") is not None and judge_ceiling is not None:
        declared = float(evo["max_api_costs"]) + float(judge_ceiling)
        if declared > float(total) + 1e-9:
            problems.append(
                f"run_max_cost_usd={total} is below max_api_costs "
                f"({evo['max_api_costs']}) + judge_max_cost_usd "
                f"({judge_ceiling}) = {declared:.2f}"
            )
    return problems


def main(config_path: str, seed: int, dry_run: bool = False) -> None:
    path, config, results_dir = prepare_run(config_path, seed)

    # Gate every launch on the things a review found could silently pass.
    # Reported in dry-run, ENFORCED for a real one.
    blockers: List[str] = []
    blockers += check_engine_enums(config)
    blockers += check_budget_ceilings(config)
    judge_cfg = JudgeConfig.load()
    scored = judge_cfg.mode != "mock" and judge_cfg.stage_b_authorized
    if scored:
        blockers += check_evaluator_is_frozen()

    if dry_run:
        evo = config["evo_config"]
        print("DRY RUN — the engine is not started and nothing is spent.")
        if blockers:
            print("  BLOCKERS (a real run would refuse to start):")
            for line in blockers:
                print(f"    - {line}")
        else:
            print("  pre-launch gates: all pass")
        print(f"  config:      {path.relative_to(REPO_ROOT)}")
        print(f"  generations: {evo['num_generations']}")
        print(f"  ceiling:     ${evo['max_api_costs']:.2f}")
        print(f"  ensemble:    {evo.get('llm_models')}")
        print(f"  seed program:{evo['init_program_path']}")
        print(f"  results:     {results_dir}")
        return

    # Hand the judge ceiling to every evaluate.py subprocess. Without this the
    # declared judge_max_cost_usd would be documentation rather than a control.
    judge_ceiling = config.get("judge_max_cost_usd")
    if judge_ceiling is not None:
        os.environ["JAPAN_FP_JUDGE_MAX_COST_USD"] = str(float(judge_ceiling))

    if blockers:
        raise SystemExit(
            "Refusing to start. Pre-launch gates failed:\n"
            + "\n".join(f"  - {line}" for line in blockers)
            + "\n\nThese are fail-closed on purpose: each one is a way a real "
              "scored run could otherwise have started when it should not."
        )

    from _eval_harness import shinka_is_real

    if not shinka_is_real():
        raise SystemExit(
            "ShinkaEvolve is not installed, or the installed 'shinka' is the "
            "unrelated PyPI image-upscaling package of the same name.\n"
            "  pip uninstall -y shinka\n"
            "  pip install git+https://github.com/SakanaAI/ShinkaEvolve.git\n"
            "Use --dry-run to validate a config without the engine."
        )

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
