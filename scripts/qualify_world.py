#!/usr/bin/env python3
"""Phase B0: does this world reward adaptivity? Free, and preregistered.

    python scripts/qualify_world.py --budget 3000

**No API key. No paid call. Nothing here can spend money.**

This is the gate that decides whether Project B's evolutionary search is worth
running at all, and it is deliberately built so that it can return NO.

## The circularity this is designed to avoid

The first draft of `docs/PROJECT_B_DESIGN.md` said:

> if adaptive is no better than constant, redesign the world, do not proceed

A review of 2026-08-19 identified that as circular, and it was: it tunes the
model until the desired answer appears. **It is deleted.** The world model and
the split seeds are hashed into `FROZEN.json` before this script runs, the
thresholds below are written down before the numbers are known, and whatever
comes out is the result. A coefficient may be revised only for a realism defect
that can be stated without reference to which arm it favours -- and then the
model version is bumped and everything reruns.

## The comparison that matters

Not adaptive versus constant. **Adaptive versus the best OPEN-LOOP SCHEDULE**,
which varies over time but reads nothing. A time-varying policy can beat a
constant one without using a single observation, so `open_loop` is the only
comparator that isolates the value of information. The two classes carry
identical parameter counts so capacity is not a confound.

## Preregistered decision rule

Proceed to the LLM search only if ALL of these hold on the **test** bank,
which is touched once:

  P1  linear_feedback beats open_loop, paired 95% CI excluding zero,
      by at least MIN_ADAPTIVE_MARGIN model points
  P2  that margin survives all structural forms, not just the pooled average
  P3  shuffling observations destroys the margin (it falls below half)
  P4  freezing observations destroys the margin (likewise)
  P5  linear_feedback does not already reach the oracle ceiling -- if a handful
      of linear rules saturate what is attainable, evolution has nothing to add

Any failure is reported as a falsification result, not tuned away.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
for extra in (str(TASK_DIR),):
    if extra not in sys.path:
        sys.path.insert(0, extra)

import baselines  # noqa: E402
import evaluate_adaptive as ea  # noqa: E402
import splits  # noqa: E402
import world as W  # noqa: E402

# --------------------------------------------------------------------------
# PREREGISTERED THRESHOLDS. Written before the numbers were known.
# --------------------------------------------------------------------------

#: Minimum paired advantage of an observation-using policy over the best
#: open-loop schedule, in ACTIR model points, for the search to be worth
#: running. Set by reference to what the whole December 2022 posture buys over
#: doing nothing (~7 points across five years): a tenth of that is the smallest
#: difference anyone would call strategically interesting.
MIN_ADAPTIVE_MARGIN: float = 0.70

#: A margin that survives an ablation at more than this fraction of its
#: original size was not coming from the observations.
ABLATION_KILL_FRACTION: float = 0.50

#: If feedback recovers more than this share of the oracle's advantage, simple
#: linear rules have effectively saturated the problem and a program search
#: cannot add much.
ORACLE_SATURATION_FRACTION: float = 0.90


# --------------------------------------------------------------------------
# A dependency-free optimiser. Same budget for every class, so no arm is
# advantaged by getting more search.
# --------------------------------------------------------------------------


def optimise(builder: Callable[[Sequence[float]], Any], dim: int,
             worlds: Sequence[W.WorldParams], budget: int, seed: int,
             init: Optional[Sequence[float]] = None,
             repeats: int = 1) -> Tuple[List[float], float]:
    """(1+lambda) evolution strategy with adaptive step size.

    Chosen over anything cleverer because it has no dependencies, is easy to
    audit, and -- most importantly -- is applied IDENTICALLY to every policy
    class. A comparison between arms optimised by different methods would
    measure the methods.
    """
    rng = random.Random(seed)
    theta = list(init) if init is not None else [rng.random() * 0.5 for _ in range(dim)]
    if len(theta) < dim:
        theta = theta + [0.0] * (dim - len(theta))
    theta = theta[:dim]

    def fitness(candidate: Sequence[float]) -> float:
        return ea.evaluate(builder(candidate), worlds, base_seed=seed,
                           repeats=repeats).mean

    best = fitness(theta)
    used = 1
    sigma = 0.25
    lam = 8
    stalls = 0

    while used < budget:
        children = []
        for _ in range(lam):
            child = [t + rng.gauss(0.0, sigma) for t in theta]
            children.append(child)
        scored = []
        for child in children:
            if used >= budget:
                break
            scored.append((fitness(child), child))
            used += 1
        if not scored:
            break
        scored.sort(key=lambda pair: -pair[0])
        if scored[0][0] > best:
            best, theta = scored[0][0], scored[0][1]
            sigma = min(0.5, sigma * 1.15)
            stalls = 0
        else:
            stalls += 1
            sigma = max(0.01, sigma * 0.85)
            if stalls > 25:
                break
    return theta, best


def optimise_oracle(worlds: Sequence[W.WorldParams], budget_per_world: int,
                    seed: int, repeats: int = 1,
                    init: Optional[Sequence[float]] = None) -> ea.Result:
    """Upper bound: an open-loop schedule optimised SEPARATELY for each world.

    It never reads an observation; it simply already knows which world it is in.
    So it bounds what any amount of inference could buy, and the gap between it
    and the single best open-loop schedule is the total value of knowing the
    world.
    """
    per_world: List[float] = []
    crises: List[float] = []
    for index, params in enumerate(worlds):
        # Warm-started from the best GENERAL schedule and then specialised to
        # this world. Started cold it is not an upper bound at all -- it is a
        # 105-dimensional problem solved from scratch on a tiny budget, and the
        # first smoke run duly had the "oracle" scoring BELOW the general
        # schedule it is supposed to bound.
        theta, _ = optimise(baselines.open_loop_policy,
                            baselines.DIMENSIONS["open_loop"], [params],
                            budget_per_world, seed + index, init=init,
                            repeats=repeats)
        result = ea.evaluate(baselines.open_loop_policy(theta), [params],
                             base_seed=seed + index, repeats=repeats)
        per_world.append(result.mean)
        crises.append(result.crises)
    ordered = sorted(per_world)
    tail = max(1, int(len(ordered) * ea.CVAR_FRACTION))
    return ea.Result(mean=statistics.fmean(per_world),
                     cvar=statistics.fmean(ordered[:tail]),
                     worst=ordered[0], per_world=per_world,
                     crises=statistics.fmean(crises))


# --------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--budget", type=int, default=3000,
                        help="fitness evaluations per policy class, matched")
    parser.add_argument("--oracle-budget", type=int, default=120,
                        help="evaluations per world for the oracle upper bound")
    parser.add_argument("--train-size", type=int, default=None)
    parser.add_argument("--test-size", type=int, default=None)
    parser.add_argument("--repeats", type=int, default=1,
                        help="episode repeats during OPTIMISATION (test always "
                             "uses the frozen splits.EPISODE_REPEATS)")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="runs/qualification")
    args = parser.parse_args(argv)

    train = splits.train_worlds()[:args.train_size] if args.train_size else splits.train_worlds()
    test = splits.test_worlds()[:args.test_size] if args.test_size else splits.test_worlds()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Qualification — model {W.MODEL_VERSION}")
    print(f"  train {len(train)} worlds, test {len(test)} worlds, "
          f"budget {args.budget} evaluations per class")
    print(f"  NO API CALL IS POSSIBLE FROM THIS SCRIPT\n")

    fitted: Dict[str, List[float]] = {}
    results: Dict[str, ea.Result] = {}

    # NESTED INITIALISATION. Each class is warm-started so that it CONTAINS the
    # simpler class's fitted solution:
    #
    #   constant        <- December 2022, the human posture
    #   open_loop       <- the best constant, repeated for all five years
    #   linear_feedback <- the best constant as its base, all gains zero
    #
    # Without this the comparison measures optimisation difficulty rather than
    # policy class. The first smoke run showed exactly that pathology: open_loop
    # has to fit five independent 21-vectors while linear_feedback's 21-vector
    # base does most of the work, so open_loop came out WORSE than a policy
    # whose observations had been frozen -- a nonsense that only looked like a
    # finding. Nested starts mean no class can lose to a simpler one because
    # its search was harder.
    def nested_init(name: str) -> Optional[List[float]]:
        if name == "constant":
            return baselines.december_2022_theta()
        best_constant = fitted.get("constant")
        if best_constant is None:
            return None
        if name == "open_loop":
            return list(best_constant) * len(W.YEARS)
        if name == "linear_feedback":
            return list(best_constant) + [0.0] * (
                baselines.DIMENSIONS["linear_feedback"] - len(best_constant))
        return None

    for name in ("constant", "open_loop", "linear_feedback"):
        builder = baselines.BUILDERS[name]
        dim = baselines.DIMENSIONS[name]
        init = nested_init(name)
        theta, train_score = optimise(builder, dim, train, args.budget,
                                      args.seed, init, args.repeats)
        fitted[name] = theta
        results[name] = ea.evaluate(builder(theta), test, base_seed=args.seed)
        print(f"  {name:18} train {train_score:7.3f}   "
              f"test mean {results[name].mean:7.3f}  cvar {results[name].cvar:7.3f}")

    results["december_2022"] = ea.evaluate(baselines.december_2022_policy(), test,
                                           base_seed=args.seed)
    print(f"  {'december_2022':18} {'(human baseline)':>13}   "
          f"test mean {results['december_2022'].mean:7.3f}  "
          f"cvar {results['december_2022'].cvar:7.3f}")

    print("\n  optimising the oracle upper bound, one schedule per world ...")
    results["oracle"] = optimise_oracle(test, args.oracle_budget, args.seed,
                                        init=fitted["open_loop"])
    print(f"  {'oracle':18} {'(upper bound)':>13}   "
          f"test mean {results['oracle'].mean:7.3f}  "
          f"cvar {results['oracle'].cvar:7.3f}")

    # -- the headline -------------------------------------------------------
    headline = ea.compare(results["linear_feedback"], results["open_loop"])
    print("\nHEADLINE — paired held-out difference, adaptive minus best open-loop")
    print(f"  {headline.mean_difference:+.4f} model points   "
          f"95% CI [{headline.ci_low:+.4f}, {headline.ci_high:+.4f}]   "
          f"win rate {headline.win_rate:.1%}")

    # -- ablations, review point 6 -----------------------------------------
    print("\nABLATIONS — does the advantage actually come from the observations?")
    ablations: Dict[str, Any] = {}
    feedback = baselines.linear_feedback_policy(fitted["linear_feedback"])
    for channel in ("shuffled", "frozen"):
        ablated = ea.evaluate(feedback, test, base_seed=args.seed,
                              channel_name=channel)
        versus = ea.compare(ablated, results["open_loop"])
        ablations[channel] = {"result": ablated.as_dict(),
                              "vs_open_loop": versus.as_dict()}
        print(f"  {channel:10} advantage {versus.mean_difference:+.4f} "
              f"(intact was {headline.mean_difference:+.4f})")

    # -- by structural form, review point 8 ---------------------------------
    print("\nBY STRUCTURAL FORM — a result that holds for only one is not a result")
    by_structure: Dict[str, Any] = {}
    for structure in W.STRUCTURES:
        idx = [i for i, w in enumerate(test) if w.structure == structure]
        if len(idx) < 10:
            continue
        a = ea.Result(0, 0, 0, [results["linear_feedback"].per_world[i] for i in idx])
        b = ea.Result(0, 0, 0, [results["open_loop"].per_world[i] for i in idx])
        cmp = ea.compare(a, b)
        by_structure[structure] = cmp.as_dict()
        print(f"  {structure:12} {cmp.mean_difference:+.4f}  "
              f"CI [{cmp.ci_low:+.4f}, {cmp.ci_high:+.4f}]  n={cmp.n}")

    # -- the preregistered decision ----------------------------------------
    oracle_gap = results["oracle"].mean - results["open_loop"].mean
    recovered = (headline.mean_difference / oracle_gap) if oracle_gap > 1e-9 else 0.0

    checks = {
        "P1_margin_and_significance": bool(
            headline.mean_difference >= MIN_ADAPTIVE_MARGIN and headline.ci_low > 0),
        "P2_holds_across_structures": bool(
            by_structure and all(v["mean_difference"] > 0 and v["ci95"][0] > 0
                                 for v in by_structure.values())),
        "P3_shuffling_destroys_it": bool(
            ablations["shuffled"]["vs_open_loop"]["mean_difference"]
            < ABLATION_KILL_FRACTION * headline.mean_difference),
        "P4_freezing_destroys_it": bool(
            ablations["frozen"]["vs_open_loop"]["mean_difference"]
            < ABLATION_KILL_FRACTION * headline.mean_difference),
        "P5_room_above_simple_rules": bool(recovered < ORACLE_SATURATION_FRACTION),
    }
    passed = all(checks.values())

    print("\nPREREGISTERED DECISION")
    for name, ok in checks.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n  oracle advantage over best open-loop: {oracle_gap:+.4f}")
    print(f"  recovered by linear feedback:        {recovered:.1%}")
    print(f"\n  => {'PROCEED to the LLM search' if passed else 'DO NOT PROCEED'}")
    if not passed:
        print("     Report the falsification. Do not tune the world until it passes.")

    payload = {
        "model_version": W.MODEL_VERSION,
        "splits": splits.describe(),
        "budget": args.budget, "seed": args.seed,
        "results": {k: v.as_dict() for k, v in results.items()},
        "headline_adaptive_vs_open_loop": headline.as_dict(),
        "ablations": ablations,
        "by_structure": by_structure,
        "oracle_gap": round(oracle_gap, 4),
        "fraction_of_oracle_recovered": round(recovered, 4),
        "thresholds": {
            "MIN_ADAPTIVE_MARGIN": MIN_ADAPTIVE_MARGIN,
            "ABLATION_KILL_FRACTION": ABLATION_KILL_FRACTION,
            "ORACLE_SATURATION_FRACTION": ORACLE_SATURATION_FRACTION,
        },
        "checks": checks,
        "decision": "proceed" if passed else "do_not_proceed",
        "fitted": {k: [round(x, 5) for x in v] for k, v in fitted.items()},
    }
    (out_dir / "qualification.json").write_text(json.dumps(payload, indent=2),
                                                encoding="utf-8")
    print(f"\n  wrote {out_dir / 'qualification.json'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
