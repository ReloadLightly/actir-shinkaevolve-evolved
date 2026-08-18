"""Evaluator: Stage 1 validity gate, Stage 2 frozen judge, Lowy aggregation.

RESEARCH_DESIGN section 2.2. Two stages, mirroring the paper's structure
(constraint check, then score):

* **Stage 1 — programmatic validity gate (free, instant).** Schema
  completeness, budget arithmetic, feasibility bound, text caps. Invalid gets
  fitness 0 plus a reason string and no judge call is spent. This is our
  circle-overlap check.
* **Stage 2 — frozen judge (the world model).** Per scenario the judge returns
  a delta per Lowy measure; the composite is Lowy's own published formula.

    composite(s) = sum_m  w_m * clip(b_m + delta_m,s , 0, 100)
    fitness      = mean over the 3 scenarios

With all-zero deltas the fitness is Japan's 2025 composite, 38.8475, reported
by the index as 38.8. Fitness therefore reads directly as projected Lowy
points in 2030.

Run it directly:

    python evaluate.py --program_path initial.py --results_dir results
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional, Sequence, Tuple

TASK_DIR = Path(__file__).resolve().parent
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))
# initial.py resolves the schema through this variable when it is executed from
# a per-generation folder.
os.environ.setdefault("JAPAN_FP_TASK_DIR", str(TASK_DIR))

from _eval_harness import run_eval  # noqa: E402
from judge.client import JudgeClient, JudgeConfig  # noqa: E402
from lowy import (  # noqa: E402
    COMPOSITE_DECIMALS,
    DIALS,
    JAPAN_2025_COMPOSITE,
    MEASURES,
    composite_with_deltas,
    projected_scores,
)
from schema import DEFAULT_LIMITS, GateLimits, PolicyPortfolio  # noqa: E402

SCENARIO_IDS: Tuple[str, ...] = ("S1", "S2", "S3")
SCENARIO_FILES: Dict[str, str] = {
    "S1": "S1_grinding_status_quo.md",
    "S2": "S2_taiwan_contingency.md",
    "S3": "S3_us_retrenchment.md",
}
TEXT_FEEDBACK_CHAR_CAP = 1200


# --------------------------------------------------------------------------
# Frozen inputs
# --------------------------------------------------------------------------


def load_scenarios(task_dir: Path = TASK_DIR) -> Dict[str, str]:
    scenarios: Dict[str, str] = {}
    for scenario_id, filename in SCENARIO_FILES.items():
        path = task_dir / "scenarios" / filename
        scenarios[scenario_id] = path.read_text(encoding="utf-8")
    return scenarios


def load_judge_prompt(task_dir: Path = TASK_DIR) -> str:
    return (task_dir / "judge_prompt.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Stage 1: the validity gate
# --------------------------------------------------------------------------


def validity_gate(
    portfolio: Any, limits: GateLimits = DEFAULT_LIMITS
) -> Tuple[bool, List[str]]:
    """Check one portfolio against the schema and the feasibility bounds.

    Returns ``(is_valid, reasons)``. All violations are collected rather than
    short-circuiting: the reasons become the mutation LLM's feedback, and one
    reason at a time would waste generations.
    """
    reasons: List[str] = []

    if not isinstance(portfolio, PolicyPortfolio):
        return False, [
            "build_policy() must return a PolicyPortfolio, got "
            f"{type(portfolio).__name__}"
        ]

    reasons.extend(portfolio.construction_errors)

    # -- horizon ----------------------------------------------------------
    if tuple(portfolio.horizon) != tuple(limits.horizon):
        reasons.append(
            f"horizon must be {tuple(limits.horizon)}, got {tuple(portfolio.horizon)}"
        )

    # -- dials ------------------------------------------------------------
    unknown = portfolio.unknown_dials()
    for dial_id in unknown:
        reasons.append(
            f"unknown dial name: {dial_id!r} (dials are the 30 Lowy submeasures)"
        )

    dials = portfolio.dials
    if not dials:
        reasons.append("no dials were invested in; the portfolio is empty")

    # Repair before checking. Shares are a normalisation convention, so a
    # proposal summing to 0.67 has botched arithmetic, not botched policy --
    # see GateLimits.share_sum_repair_min. Out-of-band sums are NOT repaired
    # and still fail the check below.
    portfolio.normalise_shares(limits)
    dials = portfolio.dials

    for dial_id, dial in sorted(dials.items()):
        if dial_id in unknown:
            continue
        if not 0.0 <= dial.share <= 1.0:
            reasons.append(
                f"share for {dial_id} must be within [0, 1], got {dial.share}"
            )
        if dial.share > 0 and not dial.how:
            reasons.append(f"dial {dial_id} has a share but no 'how' string")
        if len(dial.how) > limits.how_char_cap:
            reasons.append(
                f"'how' for {dial_id} is {len(dial.how)} chars, cap is "
                f"{limits.how_char_cap}"
            )

    total = portfolio.total_share()
    if not math.isfinite(total):
        reasons.append("shares do not sum to a finite number")
    elif abs(total - limits.share_sum) > limits.share_sum_tolerance:
        reasons.append(
            f"shares must sum to {limits.share_sum} "
            f"(+/- {limits.share_sum_tolerance}), they sum to {total:.6f}; "
            f"auto-repair applies only to sums within "
            f"[{limits.share_sum_repair_min}, {limits.share_sum_repair_max}] "
            f"and to non-negative shares"
        )

    # -- sequence ---------------------------------------------------------
    phases = portfolio.phases
    if len(phases) < limits.min_phases:
        reasons.append(f"sequence needs at least {limits.min_phases} phase(s)")
    if len(phases) > limits.max_phases:
        reasons.append(
            f"sequence has {len(phases)} phases, cap is {limits.max_phases}"
        )
    start_year, end_year = limits.horizon
    previous_end: Optional[int] = None
    for index, phase in enumerate(phases):
        first, last = phase.years
        if not (start_year <= first <= last <= end_year):
            reasons.append(
                f"phase {index} years {phase.years} fall outside the horizon "
                f"{tuple(limits.horizon)} or are reversed"
            )
        if previous_end is not None and first < previous_end:
            reasons.append(
                f"phase {index} starts in {first}, before phase {index - 1} ends "
                f"in {previous_end}; phases must be ordered"
            )
        previous_end = last
        if len(phase.label) > limits.phase_label_char_cap:
            reasons.append(
                f"phase {index} label is {len(phase.label)} chars, cap is "
                f"{limits.phase_label_char_cap}"
            )
        for dial_id in phase.focus:
            if dial_id not in DIALS:
                reasons.append(f"phase {index} focuses on unknown dial {dial_id!r}")

    # -- custom initiatives -----------------------------------------------
    initiatives = portfolio.initiatives
    if len(initiatives) > limits.max_custom_initiatives:
        reasons.append(
            f"{len(initiatives)} custom initiatives, cap is "
            f"{limits.max_custom_initiatives}"
        )
    for index, initiative in enumerate(initiatives):
        if not initiative.name:
            reasons.append(f"custom initiative {index} has no name")
        if len(initiative.name) > limits.initiative_name_char_cap:
            reasons.append(
                f"custom initiative {index} name is {len(initiative.name)} chars, "
                f"cap is {limits.initiative_name_char_cap}"
            )
        if len(initiative.rationale) > limits.initiative_rationale_char_cap:
            reasons.append(
                f"custom initiative {index} rationale is "
                f"{len(initiative.rationale)} chars, cap is "
                f"{limits.initiative_rationale_char_cap}"
            )
        if not initiative.targets:
            reasons.append(
                f"custom initiative {index} names no target submeasures; every "
                "initiative must say which dials it moves"
            )
        for dial_id in initiative.targets:
            if dial_id not in DIALS:
                reasons.append(
                    f"custom initiative {index} targets unknown dial {dial_id!r}"
                )

    # -- free text budget --------------------------------------------------
    free_text = portfolio.free_text_chars()
    if free_text > limits.total_free_text_cap:
        reasons.append(
            f"total free text is {free_text} chars, cap is "
            f"{limits.total_free_text_cap}; rhetoric is capped so it cannot be scored"
        )

    # -- defence feasibility bound ----------------------------------------
    path = portfolio.defence_path
    if not path:
        reasons.append("defence spending path is empty")
    for year, value in sorted(path.items()):
        if not start_year <= year <= end_year:
            reasons.append(
                f"defence spending path year {year} falls outside the horizon "
                f"{tuple(limits.horizon)}"
            )
        if not limits.defence_gdp_min <= value <= limits.defence_gdp_max:
            reasons.append(
                f"defence spending in {year} is {value}% of GDP, outside the "
                f"feasibility bound [{limits.defence_gdp_min}, "
                f"{limits.defence_gdp_max}]"
            )

    return (not reasons), reasons


def _validate_for_harness(result: Any) -> Tuple[bool, Optional[str]]:
    valid, reasons = validity_gate(result)
    return valid, None if valid else "; ".join(reasons)


# --------------------------------------------------------------------------
# Stage 2: judge, then Lowy aggregation
# --------------------------------------------------------------------------


def _text_feedback(verdicts: Sequence[Any]) -> str:
    """The judge's mechanism sentences, ranked by |delta|, capped for the prompt."""
    lines: List[str] = []
    for verdict in verdicts:
        ranked = sorted(
            verdict.deltas.items(), key=lambda item: abs(item[1]), reverse=True
        )
        lines.append(f"[{verdict.scenario_id}]")
        for measure, delta in ranked:
            mechanism = verdict.mechanisms.get(measure, "")
            if not mechanism:
                continue
            lines.append(f"  {measure} {delta:+.1f}: {mechanism}")
    text = "\n".join(lines)
    if len(text) > TEXT_FEEDBACK_CHAR_CAP:
        text = text[: TEXT_FEEDBACK_CHAR_CAP - 3].rstrip() + "..."
    return text


def score_portfolio(
    portfolio: PolicyPortfolio,
    client: Optional[JudgeClient] = None,
    task_dir: Path = TASK_DIR,
) -> Dict[str, Any]:
    """Run the 3-scenario battery and aggregate with Lowy's published weights."""
    client = client or JudgeClient(JudgeConfig.load())
    scenarios = load_scenarios(task_dir)
    prompt_text = load_judge_prompt(task_dir)
    portfolio_json = portfolio.to_dict()

    verdicts = [
        client.score(
            scenario_id=scenario_id,
            scenario_text=scenarios[scenario_id],
            prompt_text=prompt_text,
            portfolio=portfolio_json,
        )
        for scenario_id in SCENARIO_IDS
    ]

    composites = {v.scenario_id: composite_with_deltas(v.deltas) for v in verdicts}
    fitness = mean(composites.values())
    mean_deltas = {
        measure: mean(v.deltas[measure] for v in verdicts) for measure in MEASURES
    }

    baseline_composite = composite_with_deltas({})
    public: Dict[str, Any] = {
        "valid": True,
        "baseline_2025_composite": round(baseline_composite, 4),
        "reported_2025_composite": JAPAN_2025_COMPOSITE,
        "worst_case_composite": round(min(composites.values()), 4),
        "best_case_composite": round(max(composites.values()), 4),
        "spread_composite": round(max(composites.values()) - min(composites.values()), 4),
        "improvement_vs_2025": round(fitness - baseline_composite, 4),
        "judge_calls_cached": sum(1 for v in verdicts if v.cached),
        "judge_mocked": all(v.mocked for v in verdicts),
        "judge_surrogate": any(v.surrogate for v in verdicts),
        "judge_cost_usd": round(sum(v.cost_usd for v in verdicts), 6),
        "dials_used": sum(1 for d in portfolio.dials.values() if d.share > 0),
        # --- behaviour descriptors --------------------------------------
        # Public on purpose. ShinkaEvolve's `archive_criteria` is a weighted,
        # rank-normalised dict over PUBLIC metrics, and its database "supports
        # MAP-Elites style feature-based organization" — but only over metrics
        # it can see. Leaving the effort shape in `private` meant the archive
        # could select on nothing but the judge's score, which is precisely the
        # quantity M1 showed to be unreliable (effect 0.696 < noise 0.921).
        # Exposed here, the archive can be told to spread across the shape of a
        # portfolio rather than to converge on a ranking we do not trust.
        "effort_concentration": round(
            sum(d.share ** 2 for d in portfolio.dials.values()), 6
        ),  # Herfindahl over the 30 dials: 1/30 = perfectly even, 1.0 = all-in
        "custom_initiatives": len(portfolio.initiatives),
        "defence_gdp_2030": portfolio.defence_path.get(2030),
        # Repair telemetry. The preflight found gpt-4.1-nano summing 30 shares
        # to 0.67 -- a 100% gate-rejection rate. The gate now rescales instead,
        # and publishes what it had to do, so the repair rate is a reported
        # statistic about the mutation models rather than a hidden convenience.
        "shares_repaired": 1 if portfolio.shares_repaired else 0,
        "share_sum_raw": round(portfolio.raw_share_sum, 6)
        if portfolio.raw_share_sum is not None else None,
    }
    for scenario_id, value in composites.items():
        public[f"composite_{scenario_id}"] = round(value, 4)
    for measure, value in mean_deltas.items():
        public[f"mean_delta_{measure}"] = round(value, 4)
    for measure, value in portfolio.share_by_measure().items():
        public[f"effort_{measure}"] = round(value, 6)

    private: Dict[str, Any] = {
        "per_scenario_deltas": {v.scenario_id: v.deltas for v in verdicts},
        "per_scenario_mechanisms": {v.scenario_id: v.mechanisms for v in verdicts},
        "per_scenario_projected_scores": {
            v.scenario_id: projected_scores(v.deltas) for v in verdicts
        },
        "effort_share_by_measure": portfolio.share_by_measure(),
        "judge_cache_keys": [v.cache_key for v in verdicts],
        "portfolio": portfolio_json,
    }

    return {
        "combined_score": float(fitness),
        "public": public,
        "private": private,
        "text_feedback": _text_feedback(verdicts),
    }


def _aggregate(results: List[Any]) -> Dict[str, Any]:
    """ShinkaEvolve aggregator: gate first, judge only if the gate passes."""
    if not results:
        return {
            "combined_score": 0.0,
            "public": {"valid": False},
            "private": {},
            "text_feedback": "build_policy() produced no result.",
        }

    portfolio = results[0]
    valid, reasons = validity_gate(portfolio)
    if not valid:
        listed = "\n".join(f"- {reason}" for reason in reasons)
        return {
            "combined_score": 0.0,
            "public": {"valid": False, "n_gate_violations": len(reasons)},
            "private": {"gate_violations": reasons},
            "text_feedback": (
                "The portfolio failed the validity gate and was not scored. "
                f"Fix these and resubmit:\n{listed}"
            ),
        }
    return score_portfolio(portfolio)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(program_path: str, results_dir: str) -> Dict[str, Any]:
    print(f"Evaluating program: {program_path}")
    print(f"Saving results to: {results_dir}")
    os.makedirs(results_dir, exist_ok=True)

    metrics, correct, error = run_eval(
        program_path=program_path,
        results_dir=results_dir,
        experiment_fn_name="build_policy",
        validate_fn=_validate_for_harness,
        aggregate_metrics_fn=_aggregate,
    )

    if correct:
        print("Validity gate passed.")
    else:
        print(f"Validity gate failed: {error}")

    score = metrics.get("combined_score", 0.0)
    print(f"combined_score = {score:.4f}  (Lowy composite, {score:.{COMPOSITE_DECIMALS}f} as reported)")
    public = metrics.get("public", {})
    for key in sorted(public):
        print(f"  {key}: {public[key]}")
    return metrics


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Japan foreign-policy evaluator (validity gate + frozen judge)"
    )
    parser.add_argument("--program_path", type=str, default=str(TASK_DIR / "initial.py"))
    parser.add_argument("--results_dir", type=str, default="results")
    args = parser.parse_args()
    main(args.program_path, args.results_dir)
