#!/usr/bin/env python3
"""M1 calibration smoke test: 5 portfolios x 3 scenarios (KICKOFF Stage B).

Scores the December 2022 seed and the four rival-school seeds under all three
scenarios, and prints the table Roland reads to decide whether the rubric is
plausible enough to freeze.

    python scripts/m1_calibration.py                 # mock: 0 calls, USD 0
    python scripts/m1_calibration.py --estimate      # what a real run would cost
    python scripts/m1_calibration.py --real          # needs Stage B authorized

Fail-closed (KICKOFF hard rule 1): ``--real`` does not itself authorize
anything. It only stops the script from silently reporting mock zeros as if
they were judgements. The judge still refuses unless ``configs/judge.yaml``
carries both ``mode: real`` and ``stage_b_authorized: true``, and the refusal
happens before the network is touched.

The 15 calls are content-hash cached, so re-running after an interruption
re-reads the cache and costs nothing for the calls already made.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

import evaluate as evaluator  # noqa: E402
from judge.client import (  # noqa: E402
    MOCK,
    PRICING_USD_PER_MTOK,
    PROVIDER_KEY_ENV,
    REAL,
    JudgeClient,
    JudgeConfig,
)
from lowy import BASELINE_2025, JAPAN_2025_COMPOSITE, MEASURES, WEIGHTS  # noqa: E402

# The five portfolios, in the order the table reports them. The 2022 seed is
# first because every other row is read as a movement away from it.
PORTFOLIOS: Tuple[Tuple[str, str, Path], ...] = (
    ("dec_2022", "December 2022 (actual)", TASK_DIR / "initial.py"),
    ("status_quo_plus", "Status-quo-plus",
     TASK_DIR / "seeds" / "seed_status_quo_plus.py"),
    ("autonomous_rearmament", "Autonomous rearmament",
     TASK_DIR / "seeds" / "seed_autonomous_rearmament.py"),
    ("accommodation", "Accommodation",
     TASK_DIR / "seeds" / "seed_accommodation.py"),
    ("middle_power", "Middle-power internationalism",
     TASK_DIR / "seeds" / "seed_middle_power_internationalism.py"),
)

#: Rough per-call token figures, for --estimate only. The ledger records what
#: was actually spent; this is a pre-flight sanity check against the ceiling.
EST_INPUT_TOKENS = 3500
EST_OUTPUT_TOKENS = 700

MEASURE_ABBREV: Dict[str, str] = {
    "economic_capability": "EconCap",
    "military_capability": "MilCap",
    "economic_relationships": "EconRel",
    "resilience": "Resil",
    "future_resources": "FutRes",
    "defence_networks": "DefNet",
    "diplomatic_influence": "DipInf",
    "cultural_influence": "CultInf",
}


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_portfolio(program_path: Path):
    """Load one program by absolute path and call its build_policy()."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        f"m1_seed_{program_path.stem}", program_path
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {program_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_policy()


# --------------------------------------------------------------------------
# Cost estimate
# --------------------------------------------------------------------------


def preflight(config: JudgeConfig) -> bool:
    """Local-only readiness check. Reads no key value and makes no call.

    Every failure here is one that would otherwise surface as a stack trace
    partway through a run that has already spent money.
    """
    import os

    ok = True
    print("Preflight")

    env_var = PROVIDER_KEY_ENV.get(config.provider)
    if env_var is None:
        print(f"  [!] provider {config.provider!r} has no known key variable")
        ok = False
    elif os.environ.get(env_var):
        print(f"  [ok] {env_var} is set")
    else:
        print(f"  [!] {env_var} is NOT set — a real run would fail on the "
              f"first call")
        ok = False

    if config.model in PRICING_USD_PER_MTOK:
        print(f"  [ok] {config.model} has a price entry")
    else:
        print(f"  [!] {config.model} has no price entry; cost would be "
              f"recorded as 0.00 and flagged pricing_known=false")
        ok = False

    if config.sends_temperature:
        print(f"  [ok] temperature {config.temperature} will be sent "
              f"(deterministic, per RESEARCH_DESIGN 2.2)")
    else:
        print(f"  [!] {config.model} rejects sampling parameters, so "
              f"temperature will be OMITTED — the run would not be "
              f"deterministic in the way the design intends")

    print(f"  [--] mode={config.mode}, stage_b_authorized={config.stage_b_authorized}"
          + ("  (locked: no real call possible)"
             if config.mode == MOCK or not config.stage_b_authorized else
             "  (ARMED: real calls will be made)"))
    return ok


def estimate(config: JudgeConfig) -> None:
    calls = len(PORTFOLIOS) * len(evaluator.SCENARIO_IDS)
    rates = PRICING_USD_PER_MTOK.get(config.model)
    print(f"M1 would make {calls} judge calls "
          f"({len(PORTFOLIOS)} portfolios x {len(evaluator.SCENARIO_IDS)} scenarios).")
    print(f"Judge: {config.provider} / {config.model}")
    if rates is None:
        print(f"No price table for {config.model!r}; cannot estimate.")
        return
    cost = calls * (
        EST_INPUT_TOKENS * rates["input"] + EST_OUTPUT_TOKENS * rates["output"]
    ) / 1_000_000
    print(f"Assuming ~{EST_INPUT_TOKENS} in / ~{EST_OUTPUT_TOKENS} out per call "
          f"at ${rates['input']:.2f}/${rates['output']:.2f} per Mtok:")
    print(f"  estimated total: ${cost:.4f}   (KICKOFF Stage B ceiling: $1.00)")
    print("Cached calls cost nothing on a re-run.")
    if config.provider == "openai":
        print("NOTE: the OpenAI price rows are unverified (see client.py). "
              "Confirm against your account before relying on this figure.")


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def score_all(client: JudgeClient) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for key, label, path in PORTFOLIOS:
        if not path.is_file():
            raise FileNotFoundError(f"missing seed program: {path}")
        portfolio = load_portfolio(path)

        valid, reasons = evaluator.validity_gate(portfolio)
        if not valid:
            raise SystemExit(
                f"{label} ({path.name}) fails the validity gate and cannot be "
                "scored:\n" + "\n".join(f"  - {r}" for r in reasons)
            )

        print(f"  scoring {label} ...", flush=True)
        result = evaluator.score_portfolio(portfolio, client=client)
        rows.append({
            "key": key,
            "label": label,
            "program": str(path.relative_to(REPO_ROOT)),
            "combined_score": result["combined_score"],
            "public": result["public"],
            "private": result["private"],
            "text_feedback": result["text_feedback"],
            "effort_share_by_measure": result["private"]["effort_share_by_measure"],
        })
    return rows


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------


def _fmt_signed(value: float) -> str:
    return f"{value:+.2f}"


def composite_table(rows: List[Dict[str, Any]]) -> str:
    """The table KICKOFF Stage B asks for: 5 portfolios x 3 scenarios."""
    scenarios = list(evaluator.SCENARIO_IDS)
    header = (
        f"| {'Portfolio':<30} | "
        + " | ".join(f"{s:>7}" for s in scenarios)
        + f" | {'Mean':>7} | {'Worst':>7} | {'vs 2025':>8} |"
    )
    rule = (
        "|" + "-" * 32 + "|"
        + "|".join("-" * 9 for _ in scenarios)
        + "|" + "-" * 9 + "|" + "-" * 9 + "|" + "-" * 10 + "|"
    )
    lines = [header, rule]
    for row in rows:
        public = row["public"]
        cells = " | ".join(
            f"{public[f'composite_{s}']:>7.2f}" for s in scenarios
        )
        lines.append(
            f"| {row['label']:<30} | {cells} | "
            f"{row['combined_score']:>7.2f} | "
            f"{public['worst_case_composite']:>7.2f} | "
            f"{_fmt_signed(public['improvement_vs_2025']):>8} |"
        )
    return "\n".join(lines)


def delta_table(rows: List[Dict[str, Any]]) -> str:
    """Mean delta per measure, so score backfire is visible per portfolio."""
    header = (
        f"| {'Portfolio':<30} | "
        + " | ".join(f"{MEASURE_ABBREV[m]:>7}" for m in MEASURES)
        + " |"
    )
    rule = "|" + "-" * 32 + "|" + "|".join("-" * 9 for _ in MEASURES) + "|"
    lines = [header, rule]
    for row in rows:
        cells = " | ".join(
            f"{row['public'][f'mean_delta_{m}']:>+7.2f}" for m in MEASURES
        )
        lines.append(f"| {row['label']:<30} | {cells} |")
    return "\n".join(lines)


def scenario_sensitivity(rows: List[Dict[str, Any]]) -> str:
    """Rule 5 check: the same portfolio must not score the same everywhere."""
    lines = []
    for row in rows:
        spread = row["public"]["spread_composite"]
        flag = "FLAT" if spread < 0.05 else ""
        lines.append(f"  {row['label']:<32} spread across S1-S3: {spread:>6.2f}  {flag}")
    return "\n".join(lines)


CALIBRATION_QUESTIONS = """\
What to look for (this is the decision, not the numbers)

1. Ordering. Is the ranking one a Japan specialist would recognise as
   arguable? It does not have to match your own view -- it has to be
   defensible. A ranking nobody would defend means the rubric is wrong.

2. Scenario sensitivity. Accommodation should look very different under S2
   (Taiwan contingency) and S3 (US retrenchment). If its spread is near zero,
   the judge is ignoring the scenario and rubric rule 5 is not landing.

3. The near-twin test. December 2022 and Status-quo-plus are deliberately
   close. If the judge separates them by much more than a point, the +/-0.5
   "marginal" anchor is not being applied and every small mutation will read
   as noise-sized signal.

4. Diminishing returns. Middle-power internationalism spends heavily on
   diplomatic influence (Japan at 85.4, almost no headroom) and on future
   resources (11.3, enormous headroom). If both move by similar amounts,
   rubric rule 3 is not landing.

5. Score backfire. Autonomous rearmament should cost something somewhere --
   economic relationships or defence networks under at least one scenario.
   If every measure moves up, the judge is adding effort rather than
   measuring consequence, and rubric rule 2 is not landing.

6. Magnitudes. Deltas beyond about +/-4 in a five-year window should be rare
   and should have a mechanism sentence that earns them.

If 3, 4 or 5 fail, fix the rubric and re-run before freezing. That is exactly
what M1 is for, and it is why the freeze was deferred until after it.
"""


def write_report(
    rows: List[Dict[str, Any]],
    client: JudgeClient,
    out_dir: Path,
    frozen_version: str,
) -> Tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    calls = sum(len(evaluator.SCENARIO_IDS) for _ in rows)
    cached = sum(r["public"]["judge_calls_cached"] for r in rows)
    cost = sum(r["public"]["judge_cost_usd"] for r in rows)
    mocked = all(r["public"]["judge_mocked"] for r in rows)

    payload = {
        "generated_at": timestamp,
        "stage": "M1 calibration smoke test",
        "judge": client.config.identity(),
        "judge_mode": client.config.mode,
        "stage_b_authorized": client.config.stage_b_authorized,
        "frozen_files_version": frozen_version,
        "mocked": mocked,
        "judge_calls": calls,
        "judge_calls_cached": cached,
        "judge_cost_usd": round(cost, 6),
        "baseline_2025_composite": round(evaluator.composite_with_deltas({}), 4),
        "reported_2025_composite": JAPAN_2025_COMPOSITE,
        "rows": rows,
    }
    json_path = out_dir / "m1_calibration.json"
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    md = [
        "# M1 calibration smoke test",
        "",
        f"Generated {timestamp}",
        "",
        f"- Judge: `{client.config.model}` (temperature "
        f"{client.config.temperature if client.config.sends_temperature else 'n/a'}), "
        f"mode `{client.config.mode}`",
        f"- Frozen files version: `{frozen_version}`",
        f"- Judge calls: {calls} ({cached} served from cache), "
        f"cost ${cost:.4f}",
        f"- Japan's 2025 composite: {evaluator.composite_with_deltas({}):.4f} "
        f"(reported as {JAPAN_2025_COMPOSITE})",
        "",
    ]
    if mocked:
        md += [
            "> **MOCK RUN — these are not judgements.** Every delta is zero by "
            "construction, so every composite is the 2025 baseline. This run "
            "proves the harness, not the rubric.",
            "",
        ]
    md += [
        "## Composite by scenario",
        "",
        "```",
        composite_table(rows),
        "```",
        "",
        "## Mean delta per measure",
        "",
        "```",
        delta_table(rows),
        "```",
        "",
        "## Scenario sensitivity",
        "",
        "```",
        scenario_sensitivity(rows),
        "```",
        "",
        "## Judge mechanism sentences",
        "",
    ]
    for row in rows:
        md += [f"### {row['label']}", "", "```", row["text_feedback"] or "(none)", "```", ""]
    md += ["## What to look for", "", "```", CALIBRATION_QUESTIONS, "```", ""]

    md_path = out_dir / "m1_calibration.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    return json_path, md_path


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="M1 calibration smoke test: 5 portfolios x 3 scenarios"
    )
    parser.add_argument("--out", default="runs/m1",
                        help="output directory (default: runs/m1)")
    parser.add_argument("--judge-config", default=None,
                        help="path to judge.yaml (default: configs/judge.yaml)")
    parser.add_argument("--estimate", action="store_true",
                        help="print the cost estimate and exit; makes no call")
    parser.add_argument("--real", action="store_true",
                        help="require a real judge; refuses if the config is mock "
                             "or Stage B is not authorized")
    args = parser.parse_args(argv)

    config = JudgeConfig.load(args.judge_config)

    if args.estimate:
        estimate(config)
        print()
        preflight(config)
        return 0

    if args.real and config.mode != REAL:
        print(
            "Refusing: --real was passed but the judge config has "
            f"mode: {config.mode}.\n"
            "Set both `mode: real` and `stage_b_authorized: true` in "
            "configs/judge.yaml first.\n"
            "That is Stage B, and it needs Roland's explicit go "
            "(KICKOFF hard rule 1).",
            file=sys.stderr,
        )
        return 2
    if args.real and not config.stage_b_authorized:
        print(
            "Refusing: --real was passed but stage_b_authorized is false.\n"
            "Both flags are required; neither alone is enough "
            "(KICKOFF hard rule 1).",
            file=sys.stderr,
        )
        return 2

    if config.mode == REAL and config.stage_b_authorized:
        # About to spend money. Catch a missing key or an unpriced model now,
        # rather than partway through a run that has already made calls.
        if not preflight(config):
            print("\nRefusing to start: preflight failed. Fix the above first.",
                  file=sys.stderr)
            return 3
        print()

    frozen = json.loads((TASK_DIR / "FROZEN.json").read_text(encoding="utf-8"))
    frozen_version = frozen.get("version", "unknown")

    print("M1 calibration smoke test")
    print(f"  judge:   {config.model}  mode={config.mode}  "
          f"stage_b_authorized={config.stage_b_authorized}")
    print(f"  frozen:  {frozen_version} (status {frozen.get('status')})")
    print(f"  scoring: {len(PORTFOLIOS)} portfolios x "
          f"{len(evaluator.SCENARIO_IDS)} scenarios")
    if config.mode == MOCK:
        print("  NOTE: mock judge — all deltas are zero and no call is made.")
    print()

    client = JudgeClient(config)
    rows = score_all(client)

    print()
    print("Composite by scenario")
    print(composite_table(rows))
    print()
    print("Mean delta per measure")
    print(delta_table(rows))
    print()
    print("Scenario sensitivity")
    print(scenario_sensitivity(rows))
    print()

    cost = sum(r["public"]["judge_cost_usd"] for r in rows)
    cached = sum(r["public"]["judge_calls_cached"] for r in rows)
    calls = len(rows) * len(evaluator.SCENARIO_IDS)
    print(f"Judge calls: {calls} ({cached} from cache).  Cost: ${cost:.4f}")

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    json_path, md_path = write_report(rows, client, out_dir, frozen_version)
    print(f"Wrote {json_path.relative_to(REPO_ROOT)}")
    print(f"Wrote {md_path.relative_to(REPO_ROOT)}")

    if config.mode == MOCK:
        print()
        print("This was a MOCK run: the table above proves the harness, not the "
              "rubric. Every composite is the 2025 baseline because every delta "
              "is zero.")
    else:
        print()
        print(CALIBRATION_QUESTIONS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
