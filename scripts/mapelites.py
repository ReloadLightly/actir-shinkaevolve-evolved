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
import math
import random
import sys
from dataclasses import dataclass, field, replace
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
from judge.client import (  # noqa: E402
    MOCK,
    REAL,
    SURROGATE,
    JudgeClient,
    JudgeConfig,
)
from schema import PolicyPortfolio  # noqa: E402


#: The real judge's composite self-noise on byte-identical input, measured in
#: preflight 32084865677: three draws at temperature 0 gave composites 40.1575,
#: 39.9900 and 40.0775. Used as the default significance margin for displacing
#: a cell's incumbent, so resampling alone cannot churn the archive.
JUDGE_SELF_NOISE_COMPOSITE: float = 0.17


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
    #: Standard error of the mean over `samples` judge draws. 0.0 when the
    #: backend is closed-form (surrogate/mock) or when samples == 1, in which
    #: case the score is one draw and its uncertainty is unmeasured, NOT zero.
    sem: float = 0.0
    samples: int = 1


# --------------------------------------------------------------------------
# The archive
# --------------------------------------------------------------------------


class Grid:
    """A MAP-Elites archive: one elite per behaviour cell."""

    def __init__(self, axes: Sequence[str] = DEFAULT_AXES, bins: int = 8,
                 min_improvement: float = 0.0) -> None:
        self.axes = tuple(axes)
        self.bins = bins
        self.cells: Dict[Tuple[int, ...], Elite] = {}
        self.improvements = 0
        self.discoveries = 0
        #: Score gain a challenger must clear to displace an incumbent. 0.0 for
        #: a closed-form backend, where any gain is real. For a real judge, set
        #: from its measured self-noise so the cells are not churned by
        #: resampling. See consider().
        self.min_improvement = float(min_improvement)
        #: Challengers that scored higher but not by enough. Reported, because
        #: "how often was an apparent improvement inside the noise" is a finding
        #: about the evaluator, not bookkeeping to hide.
        self.within_noise = 0

    def consider(self, elite: Elite, coords: Tuple[int, ...]) -> str:
        """Offer a candidate to its cell.

        Returns 'discovery' if the cell was empty, 'improvement' if it beat the
        incumbent by more than the noise, 'rejected' otherwise. The comparison
        is ALWAYS against one specific incumbent — never against the population
        — which is what keeps the judge's unreliable global RANKING out of the
        decision.

        That defence is only half of it, and a review was right to press on the
        other half. Per-cell comparison pits a portfolio against one that is
        already behaviourally similar, which is precisely the regime where the
        judge is weakest: preflight 32084865677 measured 0.17 composite points
        of self-noise on byte-identical input, and most single-dial moves are
        smaller than that. So a bare `>` would let noise churn the occupants.

        `min_improvement` is the significance margin. When scores carry a
        measured SEM the margin is the pooled standard error of the difference;
        otherwise the caller's floor is used. Coverage — the headline number —
        is untouched by any of this, because filling a cell needs no comparison
        at all.
        """
        incumbent = self.cells.get(coords)
        if incumbent is None:
            self.cells[coords] = elite
            self.discoveries += 1
            return "discovery"
        margin = self.min_improvement
        if elite.sem > 0.0 or incumbent.sem > 0.0:
            margin = max(margin, math.sqrt(elite.sem ** 2 + incumbent.sem ** 2))
        if elite.score > incumbent.score + margin:
            self.cells[coords] = elite
            self.improvements += 1
            return "improvement"
        if elite.score > incumbent.score:
            self.within_noise += 1
            return "within_noise"
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


def _evaluate(portfolio: PolicyPortfolio, client: JudgeClient,
              repeats: int = 1) -> Tuple[bool, float, Dict[str, Any], float, int]:
    """Score one portfolio. Returns (valid, mean, public, sem, samples).

    With repeats > 1 the judge is sampled that many times and the SCORE IS THE
    MEAN, with the standard error reported alongside. This is the direct answer
    to a review point: a single LLM judgment per candidate cannot separate a
    small real improvement from the judge disagreeing with itself, and the
    content-hash cache then freezes whichever draw arrived first rather than
    estimating the distribution.

    Repeats bypass the cache deliberately — each draw needs a fresh sample, and
    a cache hit would return the same number `repeats` times and manufacture an
    SEM of exactly zero, which is the most dangerous possible answer.
    """
    valid, _reasons = evaluator.validity_gate(portfolio)
    if not valid:
        return False, 0.0, {}, 0.0, 0

    if repeats <= 1:
        result = evaluator.score_portfolio(portfolio, client=client)
        # sem 0.0 here means UNMEASURED, not zero. consider() falls back to the
        # grid's floor in that case rather than treating the score as exact.
        return True, result["combined_score"], result["public"], 0.0, 1

    scores, last = [], None
    for _ in range(repeats):
        last = evaluator.score_portfolio(portfolio, client=_uncached(client))
        scores.append(last["combined_score"])
    mean = sum(scores) / len(scores)
    if len(scores) > 1:
        variance = sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)
        sem = math.sqrt(variance / len(scores))
    else:
        sem = 0.0
    public = dict(last["public"])
    public["score_sem"] = round(sem, 6)
    public["score_samples"] = len(scores)
    return True, mean, public, sem, len(scores)


_UNCACHED_COUNTER = {"n": 0}


def _uncached(client: JudgeClient) -> JudgeClient:
    """A client sharing the judge's identity but not its cache directory.

    Without this, repeat 2..n of the same portfolio are cache hits and return
    an identical number, producing sem == 0.0 and a false claim of certainty.
    """
    from dataclasses import replace as _replace
    import tempfile

    _UNCACHED_COUNTER["n"] += 1
    tmp = Path(tempfile.gettempdir()) / f"japanfp_resample_{_UNCACHED_COUNTER['n']}"
    tmp.mkdir(parents=True, exist_ok=True)
    return JudgeClient(_replace(client.config, cache_dir=str(tmp)))


def run_mapelites(evaluations: int, seed: int, axes: Sequence[str],
                  bins: int, client: JudgeClient, repeats: int = 1,
                  min_improvement: float = 0.0
                  ) -> Tuple[Grid, List[Dict[str, Any]]]:
    rng = random.Random(seed)
    grid = Grid(axes, bins, min_improvement=min_improvement)
    import initial

    history: List[Dict[str, Any]] = []
    next_id = 0

    root = initial.build_policy()
    ok, score, public, sem, _n = _evaluate(root, client, repeats)
    if ok:
        grid.consider(
            Elite(next_id, root, score, describe(root.to_dict(), axes), public,
                  sem=sem, samples=_n),
            cell(root.to_dict(), axes, bins),
        )

    # Matched on VALID evaluations, not attempts. A gate rejection costs a
    # mutation but produces no scored candidate, and arms differ in how often
    # they are rejected -- so counting attempts would hand extra real
    # evaluations to whichever arm proposes more valid portfolios. This is the
    # matching key named in every config as matched_valid_evaluations.
    rejected = 0
    step = 0
    valid_count = 0
    while valid_count < evaluations:
        step += 1
        if step > evaluations * 50:
            break
        # Parent is drawn UNIFORMLY from the elites, not by fitness. That is
        # the MAP-Elites contract: every occupied region of policy space gets
        # equal opportunity to be explored from, so the search spreads instead
        # of crowding around whatever the judge happened to score highest.
        pool = grid.elites()
        parent = rng.choice(pool) if pool else Elite(-1, root, 0.0, (), {})
        child_portfolio, _op = offline.mutate(parent.portfolio, rng)

        ok, score, public, sem, _n = _evaluate(child_portfolio, client, repeats)
        if not ok:
            rejected += 1
            continue

        valid_count += 1
        next_id += 1
        as_dict = child_portfolio.to_dict()
        outcome = grid.consider(
            Elite(next_id, child_portfolio, score, describe(as_dict, axes),
                  public, generation=step, parent=parent.ident,
                  sem=sem, samples=_n),
            cell(as_dict, axes, bins),
        )
        history.append({
            "evaluation": step, "outcome": outcome, "score": round(score, 6),
            "coverage": round(grid.coverage, 6), "qd_score": round(grid.qd_score, 4),
        })

    return grid, history


def run_fitness_driven(evaluations: int, seed: int, axes: Sequence[str],
                       bins: int, client: JudgeClient, repeats: int = 1,
                       min_improvement: float = 0.0
                       ) -> Tuple[Grid, List[Dict[str, Any]]]:
    """The control: the same budget and the same operators, selecting on fitness.

    Its archive is still *recorded* on the grid so coverage is comparable, but
    the grid plays no part in its selection — parents are drawn by fitness, as
    `offline_evolution.select_parent` does. This isolates the selection rule as
    the only difference.
    """
    rng = random.Random(seed)
    grid = Grid(axes, bins, min_improvement=min_improvement)
    import initial

    archive: List[offline.Individual] = []
    root = offline.Individual(0, None, 0, initial.build_policy(), operator="seed")
    ok, score, public, sem, _n = _evaluate(root.portfolio, client, repeats)
    root.valid, root.score, root.public = ok, score, public
    archive.append(root)
    if ok:
        grid.consider(Elite(0, root.portfolio, score, describe(root.portfolio.to_dict(), axes),
                            public, sem=sem, samples=_n),
                      cell(root.portfolio.to_dict(), axes, bins))

    history: List[Dict[str, Any]] = []
    step = 0
    valid_count = 0
    while valid_count < evaluations:
        step += 1
        if step > evaluations * 50:
            break
        parent = offline.select_parent(archive, rng)
        child_portfolio, op = offline.mutate(parent.portfolio, rng)
        child = offline.Individual(len(archive), parent.ident, step, child_portfolio, operator=op)
        ok, score, public, sem, _n = _evaluate(child_portfolio, client, repeats)
        child.valid, child.score, child.public = ok, score, public
        archive.append(child)
        if ok:
            valid_count += 1
            as_dict = child_portfolio.to_dict()
            grid.consider(Elite(child.ident, child_portfolio, score, describe(as_dict, axes),
                            public, sem=sem, samples=_n),
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


def to_archive_records(grid: Grid, surrogate: bool = True) -> List[Dict[str, Any]]:
    """Elites in the standard archive shape, so analysis/novelty.py can read them.

    `surrogate` must reflect the backend that actually produced the scores. It
    was hardcoded True until 2026-08-18, which was correct only because the
    driver hardcoded the surrogate too -- and would have silently mislabelled
    every real record the moment that changed.
    """
    return [
        {
            "id": e.ident, "parent": e.parent, "generation": e.generation,
            "operator": "mapelites", "valid": True, "score": e.score,
            "surrogate": surrogate, "public": e.public,
            "portfolio": e.portfolio.to_dict(),
            "score_sem": e.sem, "score_samples": e.samples,
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
    parser.add_argument(
        "--judge", choices=["surrogate", "mock", "real"], default="surrogate",
        help="Which evaluator. DEFAULT SURROGATE, deliberately: until "
             "2026-08-18 this script hardcoded the surrogate, so the "
             "illumination result the writeup discusses had never been "
             "produced by the real judge at all. 'real' additionally requires "
             "--confirm-spend.")
    parser.add_argument(
        "--confirm-spend", action="store_true",
        help="Required alongside --judge real. Fail-closed, like every other "
             "spending path in this repository.")
    parser.add_argument(
        "--repeats", type=int, default=1,
        help="Judge draws per candidate. >1 makes the score a MEAN with a "
             "reported standard error instead of one cached draw, which is "
             "what lets consider() tell a real gain from resampling.")
    parser.add_argument(
        "--min-improvement", type=float, default=None,
        help="Score gain needed to displace a cell's incumbent. Defaults to "
             "0.0 for a closed-form backend and to the judge's measured "
             "composite self-noise (0.17) for a real one.")
    parser.add_argument(
        "--max-cost", type=float, default=None,
        help="Hard ceiling on judge spend, enforced against the ledger before "
             "each call.")
    args = parser.parse_args(argv)

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.judge == "real":
        if not args.confirm_spend:
            print("Refusing: --judge real requires --confirm-spend.", file=sys.stderr)
            return 2
        config = JudgeConfig.load()
        if config.mode != REAL or not config.stage_b_authorized:
            print("Refusing: judge config is not armed (need mode=real and "
                  "stage_b_authorized=true).", file=sys.stderr)
            return 2
        if args.max_cost is not None:
            config = replace(config, max_cost_usd=float(args.max_cost))
        elif config.max_cost_usd is None:
            print("Refusing: --judge real needs a ceiling. Pass --max-cost.",
                  file=sys.stderr)
            return 2
    else:
        config = JudgeConfig(mode=SURROGATE if args.judge == "surrogate" else MOCK)

    client = JudgeClient(config)
    closed_form = args.judge in ("surrogate", "mock")
    # A real judge disagrees with itself by 0.17 composite points on identical
    # input (preflight 32084865677), so a bare `>` would churn cell occupants on
    # resampling alone. A closed-form backend has no such noise and needs no
    # margin.
    min_improvement = (args.min_improvement if args.min_improvement is not None
                       else (0.0 if closed_form else JUDGE_SELF_NOISE_COMPOSITE))

    print(f"MAP-Elites — axes {args.axes}, {args.bins}^{len(args.axes)} = "
          f"{total_cells(args.axes, args.bins)} cells, {args.evaluations} evaluations")
    print(f"judge: {args.judge}  repeats: {args.repeats}  "
          f"significance margin: {min_improvement:.4f}")
    if closed_form:
        print("SURROGATE/MOCK judge: structure only, not a result.\n")
    else:
        print(f"REAL judge {config.model}. Ceiling ${config.max_cost_usd:.2f}.\n")

    grid, history = run_mapelites(args.evaluations, args.seed, args.axes, args.bins,
                                  client, args.repeats, min_improvement)
    print(f"  coverage  {len(grid.cells):>4}/{total_cells(args.axes, args.bins)} "
          f"({grid.coverage:.1%})")
    print(f"  QD score  {grid.qd_score:.2f}")
    print(f"  {grid.discoveries} discoveries, {grid.improvements} improvements")

    payload: Dict[str, Any] = {
        "surrogate": closed_form,
        "judge": args.judge,
        "judge_identity": config.identity(),
        "repeats": args.repeats,
        "min_improvement": min_improvement,
        "within_noise_rejections": grid.within_noise,
        "axes": describe_axes(args.axes), "bins": args.bins,
        "evaluations": args.evaluations, "seed": args.seed,
        "mapelites": {"coverage": grid.coverage, "qd_score": grid.qd_score,
                      "cells_filled": len(grid.cells),
                      "cells_total": total_cells(args.axes, args.bins)},
    }

    if closed_form:
        payload["not_a_result"] = (
            "Surrogate/mock-scored. Structure and algorithm only; never report "
            "these numbers as a finding about Japanese policy."
        )

    if args.compare:
        control, _ = run_fitness_driven(args.evaluations, args.seed, args.axes,
                                        args.bins, client, args.repeats,
                                        min_improvement)
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
        for record in to_archive_records(grid, closed_form):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"\n  wrote {out_dir.name}/grid_mapelites.svg, archive.jsonl, mapelites.json")
    print("\nNOT A RESULT: surrogate judge. Pipeline and algorithm validation only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
