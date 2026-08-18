#!/usr/bin/env python3
"""MAP-Elites over policy space: illumination as a selection rule.

    python scripts/mapelites.py --evaluations 600 --seed 0          # free
    python scripts/mapelites.py --evaluations 600 --compare         # vs fitness-driven

**Why this algorithm, specifically.** M1 measured the judge's resolution at an
effect of 0.696 composite points across five opposite doctrines against
inter-judge disagreement reaching 0.921. A fitness-proportional archive keeps
"the best", which under that noise means keeping whatever scored high by
accident and never revisiting it.

MAP-Elites never asks for a global ranking. It partitions policy space by
**behaviour** — computed exactly, for free, with no LLM — and asks only "is this
better than the current occupant of *this* cell?" That is a local comparison
between portfolios already similar in behaviour, where the judge is on its
firmest ground. And the primary output, **coverage**, does not depend on the
judge's ranking at all: a cell is filled or it is not.

So the thing the paper most wants to claim — that the machinery illuminates a
space rather than optimises a number — is measured by a statistic the measured
noise cannot corrupt.

This is `docs/ALPHAEVOLVE_COMPARISON.md`'s "put the exact thing in the loop
wherever one exists", applied to selection rather than to fitness. The objective
stays borrowed from Lowy and uninvented (RESEARCH_DESIGN §2.1); exactness enters
through *where a portfolio sits*, never through *what it is worth*.

ShinkaEvolve's own `archive_criteria` cannot express this — it resolves only
`combined_score` and five code-analysis metrics, never task metrics — so the
selection rule lives here, in a driver we own.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
for extra in (TASK_DIR, REPO_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import evaluate as evaluator  # noqa: E402
import offline_evolution as offline  # noqa: E402
from descriptors import (  # noqa: E402
    DEFAULT_AXES,
    cell,
    cell_bounds,
    describe,
    describe_axes,
    total_cells,
)
from judge.client import SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
from schema import PolicyPortfolio  # noqa: E402


@dataclass
class Elite:
    """The current occupant of one grid cell."""

    ident: int
    portfolio: PolicyPortfolio
    score: float
    descriptor: Tuple[float, ...]
    public: Dict[str, Any] = field(default_factory=dict)
    generation: int = 0
    parent: Optional[int] = None


# --------------------------------------------------------------------------
# The archive
# --------------------------------------------------------------------------


class Grid:
    """A MAP-Elites archive: one elite per behaviour cell."""

    def __init__(self, axes: Sequence[str] = DEFAULT_AXES, bins: int = 8) -> None:
        self.axes = tuple(axes)
        self.bins = bins
        self.cells: Dict[Tuple[int, ...], Elite] = {}
        self.improvements = 0
        self.discoveries = 0

    def consider(self, elite: Elite, coords: Tuple[int, ...]) -> str:
        """Offer a candidate to its cell.

        Returns 'discovery' if the cell was empty, 'improvement' if it beat the
        incumbent, 'rejected' otherwise. Note that the comparison is ALWAYS
        against one specific incumbent — never against the population — which is
        what keeps the judge's unreliable global ranking out of the decision.
        """
        incumbent = self.cells.get(coords)
        if incumbent is None:
            self.cells[coords] = elite
            self.discoveries += 1
            return "discovery"
        if elite.score > incumbent.score:
            self.cells[coords] = elite
            self.improvements += 1
            return "improvement"
        return "rejected"

    @property
    def coverage(self) -> float:
        return len(self.cells) / total_cells(self.axes, self.bins)

    @property
    def qd_score(self) -> float:
        """Quality-diversity score: the summed fitness of every elite.

        The standard MAP-Elites headline. It rewards filling cells AND filling
        them well, so it cannot be gamed by either alone.
        """
        return sum(e.score for e in self.cells.values())

    def elites(self) -> List[Elite]:
        return list(self.cells.values())


# --------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------


def _evaluate(portfolio: PolicyPortfolio, client: JudgeClient) -> Tuple[bool, float, Dict[str, Any]]:
    valid, _reasons = evaluator.validity_gate(portfolio)
    if not valid:
        return False, 0.0, {}
    result = evaluator.score_portfolio(portfolio, client=client)
    return True, result["combined_score"], result["public"]


def run_mapelites(evaluations: int, seed: int, axes: Sequence[str],
                  bins: int, client: JudgeClient) -> Tuple[Grid, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    grid = Grid(axes, bins)
    import initial

    history: List[Dict[str, Any]] = []
    next_id = 0

    root = initial.build_policy()
    ok, score, public = _evaluate(root, client)
    if ok:
        grid.consider(
            Elite(next_id, root, score, describe(root.to_dict(), axes), public),
            cell(root.to_dict(), axes, bins),
        )

    rejected = 0
    for step in range(1, evaluations + 1):
        # Parent is drawn UNIFORMLY from the elites, not by fitness. That is
        # the MAP-Elites contract: every occupied region of policy space gets
        # equal opportunity to be explored from, so the search spreads instead
        # of crowding around whatever the judge happened to score highest.
        pool = grid.elites()
        parent = rng.choice(pool) if pool else Elite(-1, root, 0.0, (), {})
        child_portfolio, _op = offline.mutate(parent.portfolio, rng)

        ok, score, public = _evaluate(child_portfolio, client)
        if not ok:
            rejected += 1
            continue

        next_id += 1
        as_dict = child_portfolio.to_dict()
        outcome = grid.consider(
            Elite(next_id, child_portfolio, score, describe(as_dict, axes),
                  public, generation=step, parent=parent.ident),
            cell(as_dict, axes, bins),
        )
        history.append({
            "evaluation": step, "outcome": outcome, "score": round(score, 6),
            "coverage": round(grid.coverage, 6), "qd_score": round(grid.qd_score, 4),
        })

    return grid, history


def run_fitness_driven(evaluations: int, seed: int, axes: Sequence[str],
                       bins: int, client: JudgeClient) -> Tuple[Grid, List[Dict[str, Any]]]:
    """The control: the same budget and the same operators, selecting on fitness.

    Its archive is still *recorded* on the grid so coverage is comparable, but
    the grid plays no part in its selection — parents are drawn by fitness, as
    `offline_evolution.select_parent` does. This isolates the selection rule as
    the only difference.
    """
    rng = random.Random(seed)
    grid = Grid(axes, bins)
    import initial

    archive: List[offline.Individual] = []
    root = offline.Individual(0, None, 0, initial.build_policy(), operator="seed")
    ok, score, public = _evaluate(root.portfolio, client)
    root.valid, root.score, root.public = ok, score, public
    archive.append(root)
    if ok:
        grid.consider(Elite(0, root.portfolio, score, describe(root.portfolio.to_dict(), axes), public),
                      cell(root.portfolio.to_dict(), axes, bins))

    history: List[Dict[str, Any]] = []
    for step in range(1, evaluations + 1):
        parent = offline.select_parent(archive, rng)
        child_portfolio, op = offline.mutate(parent.portfolio, rng)
        child = offline.Individual(len(archive), parent.ident, step, child_portfolio, operator=op)
        ok, score, public = _evaluate(child_portfolio, client)
        child.valid, child.score, child.public = ok, score, public
        archive.append(child)
        if ok:
            as_dict = child_portfolio.to_dict()
            grid.consider(Elite(child.ident, child_portfolio, score, describe(as_dict, axes), public),
                          cell(as_dict, axes, bins))
        history.append({
            "evaluation": step, "outcome": "fitness", "score": round(score, 6),
            "coverage": round(grid.coverage, 6), "qd_score": round(grid.qd_score, 4),
        })
    return grid, history


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def heatmap_svg(grid: Grid, out: Path) -> None:
    """The map itself: every cell, shaded by its elite's score."""
    if len(grid.axes) != 2:
        return
    n = grid.bins
    size, pad, top = 44, 130, 70
    w, h = pad + n * size + 40, top + n * size + 90
    scores = [e.score for e in grid.elites()]
    lo, hi = (min(scores), max(scores)) if scores else (0.0, 1.0)
    span = max(hi - lo, 1e-9)

    body = []
    for i in range(n):          # x: first axis
        for j in range(n):      # y: second axis, drawn bottom-up
            occupant = grid.cells.get((i, j))
            x, y = pad + i * size, top + (n - 1 - j) * size
            if occupant is None:
                fill, label = "#f2f2f2", ""
            else:
                t = (occupant.score - lo) / span
                fill = f"rgb({int(247 - 150 * t)},{int(251 - 80 * t)},{int(255 - 60 * t)})"
                label = f"{occupant.score:.2f}"
            body.append(
                f'<rect x="{x}" y="{y}" width="{size - 2}" height="{size - 2}" '
                f'fill="{fill}" stroke="#ccc"/>'
            )
            if label:
                body.append(
                    f'<text x="{x + size/2 - 1}" y="{y + size/2 + 3}" font-size="9" '
                    f'text-anchor="middle" fill="#123">{label}</text>'
                )
    for i in range(n):
        low, _high = cell_bounds(grid.axes[0], i, n)
        body.append(f'<text x="{pad + i*size + size/2}" y="{top + n*size + 16}" '
                    f'font-size="9" text-anchor="middle" fill="#555">{low:.2f}</text>')
        low, _high = cell_bounds(grid.axes[1], i, n)
        body.append(f'<text x="{pad - 8}" y="{top + (n-1-i)*size + size/2 + 3}" '
                    f'font-size="9" text-anchor="end" fill="#555">{low:.2f}</text>')
    body.append(f'<text x="{pad + n*size/2}" y="{top + n*size + 38}" font-size="11" '
                f'text-anchor="middle" fill="#222">{grid.axes[0].replace("_"," ")} →</text>')
    body.append(f'<text transform="translate(22,{top + n*size/2}) rotate(-90)" '
                f'font-size="11" text-anchor="middle" fill="#222">'
                f'{grid.axes[1].replace("_"," ")} →</text>')

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" '
        f'height="{h}" font-family="system-ui,sans-serif">'
        f'<rect width="{w}" height="{h}" fill="#fff"/>'
        f'<text x="{w/2}" y="26" text-anchor="middle" font-size="15" font-weight="600">'
        f'MAP-Elites: the policy space, illuminated</text>'
        f'<text x="{w/2}" y="46" text-anchor="middle" font-size="11" fill="#555">'
        f'{len(grid.cells)}/{total_cells(grid.axes, grid.bins)} cells filled '
        f'({grid.coverage:.0%}) · QD {grid.qd_score:.1f}</text>'
        + "".join(body) + "</svg>"
    )
    out.write_text(svg, encoding="utf-8")


def to_archive_records(grid: Grid) -> List[Dict[str, Any]]:
    """Elites in the standard archive shape, so analysis/novelty.py can read them."""
    return [
        {
            "id": e.ident, "parent": e.parent, "generation": e.generation,
            "operator": "mapelites", "valid": True, "score": e.score,
            "surrogate": True, "public": e.public, "portfolio": e.portfolio.to_dict(),
        }
        for e in grid.elites()
    ]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--evaluations", type=int, default=600)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--axes", nargs="+", default=list(DEFAULT_AXES))
    parser.add_argument("--compare", action="store_true",
                        help="also run fitness-driven selection at matched budget")
    parser.add_argument("--out", default="runs/mapelites")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    client = JudgeClient(JudgeConfig(mode=SURROGATE))
    print(f"MAP-Elites — axes {args.axes}, {args.bins}^{len(args.axes)} = "
          f"{total_cells(args.axes, args.bins)} cells, {args.evaluations} evaluations")
    print("SURROGATE judge: structure only, not a result.\n")

    grid, history = run_mapelites(args.evaluations, args.seed, args.axes, args.bins, client)
    print(f"  coverage  {len(grid.cells):>4}/{total_cells(args.axes, args.bins)} "
          f"({grid.coverage:.1%})")
    print(f"  QD score  {grid.qd_score:.2f}")
    print(f"  {grid.discoveries} discoveries, {grid.improvements} improvements")

    payload: Dict[str, Any] = {
        "surrogate": True,
        "not_a_result": "Surrogate-scored. Structure only; never report these numbers.",
        "axes": describe_axes(args.axes), "bins": args.bins,
        "evaluations": args.evaluations, "seed": args.seed,
        "mapelites": {"coverage": grid.coverage, "qd_score": grid.qd_score,
                      "cells_filled": len(grid.cells),
                      "cells_total": total_cells(args.axes, args.bins)},
    }

    if args.compare:
        control, _ = run_fitness_driven(args.evaluations, args.seed, args.axes, args.bins, client)
        print(f"\n  fitness-driven control, same budget and operators:")
        print(f"  coverage  {len(control.cells):>4}/{total_cells(args.axes, args.bins)} "
              f"({control.coverage:.1%})")
        print(f"  QD score  {control.qd_score:.2f}")
        payload["fitness_driven"] = {
            "coverage": control.coverage, "qd_score": control.qd_score,
            "cells_filled": len(control.cells),
        }
        ratio = grid.coverage / control.coverage if control.coverage else float("inf")
        payload["coverage_ratio"] = ratio
        print(f"\n  MAP-Elites covers {ratio:.2f}x the policy space at equal cost.")
        heatmap_svg(control, out_dir / "grid_fitness_driven.svg")

    heatmap_svg(grid, out_dir / "grid_mapelites.svg")
    (out_dir / "mapelites.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (out_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    with (out_dir / "archive.jsonl").open("w", encoding="utf-8") as handle:
        for record in to_archive_records(grid):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  wrote {out_dir.name}/grid_mapelites.svg, archive.jsonl, mapelites.json")
    print("\nNOT A RESULT: surrogate judge. Pipeline and algorithm validation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
