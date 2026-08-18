#!/usr/bin/env python3
"""The null model: independent random portfolios, no evolution of any kind.

    python scripts/random_baseline.py --evaluations 400 --seed 0     # free
    python scripts/random_baseline.py --judge real --confirm-spend --max-cost 1.00

RESEARCH_DESIGN section 4 asks for "random search at matched budget" as the
baseline the search has to beat. `configs/ablations/random_search.yaml` was
supposed to be it, and a review of 2026-08-18 showed it was not, for two
independent reasons:

1. It set `parent_selection_strategy: random`, which ShinkaEvolve does not
   dispatch -- the arm would have raised ValueError mid-run, after spending.
   The nearest valid name, `sequential`, is deterministic ordering, which is a
   different thing again and still not random.
2. Even with the enum repaired it kept `use_text_feedback: true` and the meta
   recommender, so the judge's mechanism sentences and periodic meta-advice
   would still have been steering the "unguided" arm.

The deeper point is that a *blind* baseline cannot be expressed in ShinkaEvolve
at all: the engine is built to select parents and feed back critique, and every
knob that turns those off still leaves an evolutionary loop. So the null model
lives here instead, outside the engine, where it is exactly what it claims:

    sample a portfolio, score it, keep the record. No parents. No lineage. No
    feedback. No inspirations. Nothing carried between draws.

## What is randomised, and what is held

The 30 dial SHARES are drawn afresh each time, from a Dirichlet-style
normalisation of exponential draws, which samples the simplex without favouring
the middle the way normalising uniforms does. The defence path and the phase
boundaries are drawn within their feasible bounds. Custom initiatives are drawn
from the seed's pool.

The `how` strings are inherited from the December 2022 seed rather than
invented, because an LLM would be needed to invent them and this baseline must
not call one -- that is the whole point of it. This is stated rather than
hidden: the comparison it licenses is about ALLOCATION, which is what the
behaviour descriptors measure and what the MAP-Elites grid partitions, and it
is silent about prose quality. A baseline that is honest about its scope is
worth more than one that quietly smuggles in a mutation model.

## Matching

Arms are compared on their first `--evaluations` VALID evaluations, never on
dollars or generations, because a dollar buys a different number of scored
candidates depending on the model and a generation may produce nothing the gate
accepts.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
for extra in (str(TASK_DIR), str(REPO_ROOT / "scripts")):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import evaluate as evaluator  # noqa: E402
from descriptors import DEFAULT_AXES, cell, describe, total_cells  # noqa: E402
from judge.client import (  # noqa: E402
    MOCK,
    REAL,
    SURROGATE,
    JudgeClient,
    JudgeConfig,
)
from lowy import DIALS  # noqa: E402
from schema import DEFAULT_LIMITS, Phase, PolicyPortfolio  # noqa: E402


def sample_portfolio(rng: random.Random) -> PolicyPortfolio:
    """One portfolio drawn independently of every other."""
    import initial

    seed = initial.build_policy()
    hows = {d.dial_id: d.how for d in seed.dials.values()}

    # Dirichlet(1,...,1) via normalised exponentials: uniform over the simplex.
    # Normalising uniform draws instead would concentrate mass near the centre
    # and under-sample the concentrated allocations, which are exactly the
    # doctrines the grid's extreme cells represent.
    weights = [-math.log(max(rng.random(), 1e-12)) for _ in DIALS]
    total = sum(weights)
    shares = [w / total for w in weights]

    portfolio = PolicyPortfolio(horizon=(2026, 2030))
    for dial_id, share in zip(DIALS, shares):
        portfolio.invest(dial_id, share=share,
                         how=hows.get(dial_id) or "marginal effort on this submeasure")

    start, end = DEFAULT_LIMITS.horizon
    cut = rng.randint(start + 1, end - 1)
    portfolio.sequence([
        Phase(label="first phase", years=(start, cut), focus=()),
        Phase(label="second phase", years=(cut, end), focus=()),
    ])

    lo, hi = DEFAULT_LIMITS.defence_gdp_min, DEFAULT_LIMITS.defence_gdp_max
    base = rng.uniform(lo, hi)
    path, current = {}, base
    for year in range(start, end + 1):
        current = min(hi, max(lo, current + rng.uniform(-0.15, 0.35)))
        path[year] = round(current, 2)
    portfolio.defence_spending_path(path)
    return portfolio


def run(evaluations: int, seed: int, client: JudgeClient,
        axes: Sequence[str] = DEFAULT_AXES, bins: int = 8,
        repeats: int = 1) -> Dict[str, Any]:
    """Draw until `evaluations` candidates have PASSED the gate."""
    import mapelites as me

    rng = random.Random(seed)
    grid = me.Grid(axes, bins)          # used only to MEASURE coverage
    records: List[Dict[str, Any]] = []
    drawn = valid = 0

    while valid < evaluations:
        drawn += 1
        if drawn > evaluations * 50:
            print(f"  giving up after {drawn} draws for {valid} valid", file=sys.stderr)
            break
        portfolio = sample_portfolio(rng)
        ok, score, public, sem, samples = me._evaluate(portfolio, client, repeats)
        if not ok:
            continue
        valid += 1
        as_dict = portfolio.to_dict()
        # The grid records where the draw LANDED. It never selects: there is no
        # parent to select, which is what makes this the null model.
        grid.consider(
            me.Elite(valid, portfolio, score, describe(as_dict, axes), public,
                     generation=valid, parent=None, sem=sem, samples=samples),
            cell(as_dict, axes, bins),
        )
        records.append({
            "id": valid, "parent": None, "generation": valid,
            "operator": "random_draw", "valid": True, "score": score,
            "score_sem": sem, "score_samples": samples,
            "public": public, "portfolio": as_dict,
        })

    return {"grid": grid, "records": records, "drawn": drawn, "valid": valid}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evaluations", type=int, default=400,
                        help="VALID evaluations to collect. The matching key.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--axes", nargs="+", default=list(DEFAULT_AXES))
    parser.add_argument("--judge", choices=["surrogate", "mock", "real"],
                        default="surrogate")
    parser.add_argument("--confirm-spend", action="store_true")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--max-cost", type=float, default=None)
    parser.add_argument("--out", default="runs/random_baseline")
    args = parser.parse_args(argv)

    if args.judge == "real":
        if not args.confirm_spend:
            print("Refusing: --judge real requires --confirm-spend.", file=sys.stderr)
            return 2
        config = JudgeConfig.load()
        if config.mode != REAL or not config.stage_b_authorized:
            print("Refusing: judge config is not armed.", file=sys.stderr)
            return 2
        if args.max_cost is not None:
            config = replace(config, max_cost_usd=float(args.max_cost))
        elif config.max_cost_usd is None:
            print("Refusing: --judge real needs a ceiling. Pass --max-cost.",
                  file=sys.stderr)
            return 2
    else:
        config = JudgeConfig(mode=SURROGATE if args.judge == "surrogate" else MOCK)

    closed_form = args.judge in ("surrogate", "mock")
    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Random baseline — {args.evaluations} valid evaluations, judge "
          f"{args.judge}, repeats {args.repeats}")
    print("No parents, no lineage, no feedback. Each draw is independent.\n")

    result = run(args.evaluations, args.seed, JudgeClient(config),
                 args.axes, args.bins, args.repeats)
    grid = result["grid"]
    cells_total = total_cells(args.axes, args.bins)
    print(f"  drew {result['drawn']} to get {result['valid']} valid "
          f"({result['valid'] / max(result['drawn'], 1):.0%} gate pass rate)")
    print(f"  coverage  {len(grid.cells)}/{cells_total} ({grid.coverage:.1%})")
    print(f"  QD score  {grid.qd_score:.2f}")

    payload: Dict[str, Any] = {
        "arm": "random_baseline",
        "surrogate": closed_form,
        "judge": args.judge,
        "judge_identity": config.identity(),
        "repeats": args.repeats,
        "matched_valid_evaluations": result["valid"],
        "draws": result["drawn"],
        "seed": args.seed,
        "axes": args.axes, "bins": args.bins,
        "coverage": grid.coverage, "qd_score": grid.qd_score,
        "cells_filled": len(grid.cells), "cells_total": cells_total,
    }
    if closed_form:
        payload["not_a_result"] = (
            "Surrogate/mock-scored. Structure and algorithm only.")
    (out_dir / "random_baseline.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8")
    with (out_dir / "archive.jsonl").open("w", encoding="utf-8") as handle:
        for record in result["records"]:
            handle.write(json.dumps(record) + "\n")
    print(f"\n  wrote {out_dir / 'random_baseline.json'}, archive.jsonl")
    if closed_form:
        print("\nNOT A RESULT: closed-form judge. Algorithm validation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
