#!/usr/bin/env python3
"""Run the evolution loop end to end with no API calls and no cost.

    python scripts/offline_evolution.py --generations 120 --seed 0

**The archive this produces is not a research result.** It uses the surrogate
judge (`tasks/japan_fp/judge/surrogate.py`), a closed-form stand-in with no
claim to represent anything about Japan, and a programmatic mutation operator
instead of an LLM. Every record it writes carries ``surrogate: true``.

## What it is for

Before this existed, no part of the search loop had ever run. Two things
blocked it: mutation needs an LLM, and the mock judge returns all-zero deltas
so every candidate ties and there is nothing to select on. That left the
archive, lineage, selection pressure and the whole analysis layer untested —
and the only way to test them was to spend money on the very run whose
correctness was in question.

This closes that gap. What it exercises for real:

* the validity gate, under thousands of adversarial machine-generated
  portfolios rather than five hand-written ones
* `to_dict()` round-tripping and canonical ordering
* Lowy aggregation, worst-case metrics, `text_feedback` assembly
* archive maintenance, parent selection, lineage recording
* everything in `analysis/`, which now has real-shaped data to read

What it cannot tell you is whether the rubric is any good, or whether an LLM
would propose interesting policies. Only the real judge and a real ensemble do
that. This is the scaffolding test, not the experiment.

## The mutation operator

Deliberately dumb, and deliberately *not* an LLM: reallocate effort between
dials, shift the defence path, retarget a phase, add or drop an initiative.
Every operator preserves the share-sums-to-one invariant by construction, so
the gate mostly passes and the run exercises scoring rather than rejection —
with a small rate of deliberate invariant violations so the gate's rejection
path gets exercised too.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

import evaluate as evaluator  # noqa: E402
from judge.client import SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
from lowy import DIALS  # noqa: E402
from schema import DEFAULT_LIMITS, Initiative, Phase, PolicyPortfolio  # noqa: E402

BASELINE_COMPOSITE = 38.8475


# --------------------------------------------------------------------------
# Individuals
# --------------------------------------------------------------------------


@dataclass
class Individual:
    ident: int
    parent: Optional[int]
    generation: int
    portfolio: PolicyPortfolio
    score: float = 0.0
    valid: bool = True
    reasons: List[str] = field(default_factory=list)
    public: Dict[str, Any] = field(default_factory=dict)
    operator: str = "seed"

    def record(self) -> Dict[str, Any]:
        return {
            "id": self.ident,
            "parent": self.parent,
            "generation": self.generation,
            "operator": self.operator,
            "valid": self.valid,
            "score": round(self.score, 6),
            "n_gate_violations": len(self.reasons),
            "surrogate": True,
            "public": self.public,
            "portfolio": self.portfolio.to_dict(),
        }


def _clone(portfolio: PolicyPortfolio) -> PolicyPortfolio:
    """Deep-ish copy through the construction API, so a mutant never aliases
    its parent's state."""
    fresh = PolicyPortfolio(horizon=tuple(portfolio.horizon))
    for dial_id, dial in portfolio.dials.items():
        fresh.invest(dial_id, share=dial.share, how=dial.how)
    fresh.sequence([Phase(years=p.years, label=p.label, focus=p.focus)
                    for p in portfolio.phases])
    fresh.custom_initiatives([
        Initiative(name=i.name, rationale=i.rationale, targets=i.targets)
        for i in portfolio.initiatives
    ])
    fresh.defence_spending_path(dict(portfolio.defence_path))
    return fresh


# --------------------------------------------------------------------------
# Mutation operators. None of these calls an LLM.
# --------------------------------------------------------------------------


def _renormalise(portfolio: PolicyPortfolio) -> None:
    """Force the shares back onto the simplex, exactly."""
    dials = portfolio.dials
    total = sum(d.share for d in dials.values())
    if total <= 0:
        return
    for dial_id, dial in dials.items():
        portfolio.invest(dial_id, share=dial.share / total, how=dial.how)
    # Absorb float residue into the largest dial so the sum is exact.
    dials = portfolio.dials
    drift = 1.0 - sum(d.share for d in dials.values())
    biggest = max(dials, key=lambda k: dials[k].share)
    portfolio.invest(biggest, share=dials[biggest].share + drift,
                     how=dials[biggest].how)


def op_reallocate(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Move effort from one dial to another. The bread-and-butter move."""
    dials = portfolio.dials
    donors = [d for d, v in dials.items() if v.share > 0.005]
    if not donors:
        return "reallocate:noop"
    source = rng.choice(donors)
    target = rng.choice([d for d in DIALS if d != source])
    amount = min(dials[source].share, rng.uniform(0.01, 0.06))
    portfolio.invest(source, share=dials[source].share - amount,
                     how=dials[source].how)
    existing = portfolio.dials.get(target)
    portfolio.invest(
        target,
        share=(existing.share if existing else 0.0) + amount,
        how=(existing.how if existing and existing.how
             else f"reallocated effort toward {target.split('.', 1)[1]}"),
    )
    _renormalise(portfolio)
    return "reallocate"


def op_concentrate(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Push effort into one measure. Tests saturation and backfire."""
    measure = rng.choice(sorted({d.split(".", 1)[0] for d in DIALS}))
    for dial_id, dial in portfolio.dials.items():
        factor = 1.6 if dial_id.startswith(measure + ".") else 0.85
        portfolio.invest(dial_id, share=dial.share * factor,
                         how=dial.how or f"effort on {dial_id}")
    _renormalise(portfolio)
    return "concentrate"


def op_defence_path(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Shift the GDP path. Occasionally out of bounds, to exercise the gate."""
    base = rng.uniform(0.4, 3.7)          # deliberately overshoots the bound
    step = rng.uniform(-0.15, 0.35)
    portfolio.defence_spending_path(
        {year: round(base + step * i, 3)
         for i, year in enumerate(range(2026, 2031))}
    )
    return "defence_path"


def op_phases(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Re-focus a phase on different dials."""
    phases = portfolio.phases
    if not phases:
        return "phases:noop"
    index = rng.randrange(len(phases))
    phase = phases[index]
    phases[index] = Phase(
        years=phase.years,
        label=phase.label,
        focus=tuple(rng.sample(list(DIALS), k=rng.randint(1, 3))),
    )
    portfolio.sequence(phases)
    return "phases"


def op_initiative(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Add or drop a free-slot initiative."""
    items = portfolio.initiatives
    if items and rng.random() < 0.4:
        items.pop(rng.randrange(len(items)))
        portfolio.custom_initiatives(items)
        return "initiative:drop"
    items.append(Initiative(
        name=f"Offline initiative {rng.randrange(1000)}",
        rationale="Generated by the offline operator to exercise the free slot.",
        targets=tuple(rng.sample(list(DIALS), k=rng.randint(1, 3))),
    ))
    portfolio.custom_initiatives(items)
    return "initiative:add"


def op_break_invariant(portfolio: PolicyPortfolio, rng: random.Random) -> str:
    """Deliberately invalid, so the gate's rejection path is exercised too.

    Every mode here has to survive share *repair*. The gate rescales an
    off-sum allocation rather than rejecting it (shares are a normalisation
    convention -- see GateLimits.share_sum_repair_min), so this operator's
    original trick of adding 0.3 to one dial is no longer a violation at all.
    What remains genuinely invalid is a claim the portfolio should not be able
    to make: a dial that does not exist, a negative allocation, a sum too far
    off to be arithmetic, or text past the cap.
    """
    dials = portfolio.dials
    victim = rng.choice(list(dials))
    mode = rng.choice(("unknown_dial", "negative_share", "absurd_sum", "long_how"))
    if mode == "unknown_dial":
        portfolio.invest("soft_power.not_a_lowy_dial", share=0.0, how="not a dial")
    elif mode == "negative_share":
        portfolio.invest(victim, share=-rng.uniform(0.05, 0.4), how=dials[victim].how)
    elif mode == "absurd_sum":
        portfolio.invest(victim, share=dials[victim].share + rng.uniform(4.0, 9.0),
                         how=dials[victim].how)
    else:
        portfolio.invest(victim, share=dials[victim].share, how="x" * 400)
    return "break_invariant"


OPERATORS: Tuple[Tuple[Any, float], ...] = (
    (op_reallocate, 0.44),
    (op_concentrate, 0.18),
    (op_defence_path, 0.12),
    (op_phases, 0.10),
    (op_initiative, 0.11),
    (op_break_invariant, 0.05),
)


def mutate(parent: PolicyPortfolio, rng: random.Random) -> Tuple[PolicyPortfolio, str]:
    child = _clone(parent)
    ops, weights = zip(*OPERATORS)
    op = rng.choices(ops, weights=weights, k=1)[0]
    return child, op(child, rng)


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def select_parent(archive: List[Individual], rng: random.Random) -> Individual:
    """Fitness-weighted with a novelty bonus for the less-used parents.

    Mirrors ShinkaEvolve's stated policy — weighted by fitness *and* by how few
    offspring a parent already has — closely enough to exercise the same
    dynamics, without pretending to be the same implementation.
    """
    live = [i for i in archive if i.valid] or archive
    counts = {}
    for ind in archive:
        counts[ind.parent] = counts.get(ind.parent, 0) + 1
    best = max(i.score for i in live)
    worst = min(i.score for i in live)
    span = max(best - worst, 1e-9)
    weights = [
        (0.15 + (i.score - worst) / span) / (1.0 + counts.get(i.ident, 0))
        for i in live
    ]
    return rng.choices(live, weights=weights, k=1)[0]


def run(generations: int, seed: int, out_dir: Path) -> Dict[str, Any]:
    rng = random.Random(seed)
    client = JudgeClient(JudgeConfig(mode=SURROGATE))

    import initial

    root = Individual(ident=0, parent=None, generation=0,
                      portfolio=initial.build_policy(), operator="seed")
    archive: List[Individual] = []
    next_id = 0

    def evaluate(ind: Individual) -> None:
        valid, reasons = evaluator.validity_gate(ind.portfolio)
        ind.valid, ind.reasons = valid, reasons
        if not valid:
            ind.score, ind.public = 0.0, {"valid": False}
            return
        result = evaluator.score_portfolio(ind.portfolio, client=client)
        ind.score = result["combined_score"]
        ind.public = result["public"]

    evaluate(root)
    archive.append(root)

    best_trace: List[Dict[str, Any]] = []
    for gen in range(1, generations + 1):
        parent = select_parent(archive, rng)
        child_portfolio, operator = mutate(parent.portfolio, rng)
        next_id += 1
        child = Individual(ident=next_id, parent=parent.ident, generation=gen,
                           portfolio=child_portfolio, operator=operator)
        evaluate(child)
        archive.append(child)

        best = max(archive, key=lambda i: i.score)
        best_trace.append({
            "generation": gen,
            "best_score": round(best.score, 6),
            "this_score": round(child.score, 6),
            "valid": child.valid,
            "operator": operator,
        })

    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "archive.jsonl").open("w", encoding="utf-8") as handle:
        for ind in archive:
            handle.write(json.dumps(ind.record(), ensure_ascii=False) + "\n")
    (out_dir / "trajectory.json").write_text(
        json.dumps(best_trace, indent=2), encoding="utf-8"
    )

    valid = [i for i in archive if i.valid]
    best = max(archive, key=lambda i: i.score)
    summary = {
        "surrogate": True,
        "not_a_result": "Surrogate judge and programmatic mutation. Pipeline "
                        "validation only; never report these numbers.",
        "seed": seed,
        "generations": generations,
        "evaluated": len(archive),
        "valid": len(valid),
        "rejected_by_gate": len(archive) - len(valid),
        "baseline_composite": BASELINE_COMPOSITE,
        "seed_score": round(archive[0].score, 6),
        "best_score": round(best.score, 6),
        "best_id": best.ident,
        "improvement_over_seed": round(best.score - archive[0].score, 6),
        "operators": {},
    }
    for ind in archive[1:]:
        entry = summary["operators"].setdefault(
            ind.operator, {"tried": 0, "valid": 0}
        )
        entry["tried"] += 1
        entry["valid"] += int(ind.valid)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--generations", type=int, default=120)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default="runs/offline")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    print("Offline evolution — surrogate judge, programmatic mutation, $0.00")
    summary = run(args.generations, args.seed, out_dir)

    print(f"  evaluated:     {summary['evaluated']}")
    print(f"  gate rejected: {summary['rejected_by_gate']} "
          f"({summary['rejected_by_gate'] / summary['evaluated']:.0%})")
    print(f"  seed score:    {summary['seed_score']:.4f}")
    print(f"  best score:    {summary['best_score']:.4f} "
          f"(+{summary['improvement_over_seed']:.4f})")
    print("  operators (valid/tried):")
    for name, counts in sorted(summary["operators"].items()):
        print(f"    {name:22} {counts['valid']:>4}/{counts['tried']:<4}")
    print(f"  wrote {out_dir}/archive.jsonl, trajectory.json, summary.json")
    print("\nNOT A RESULT: surrogate judge, no LLM. Pipeline validation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
