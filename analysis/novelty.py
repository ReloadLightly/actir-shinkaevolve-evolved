#!/usr/bin/env python3
"""Does the archive contain options a human would not have written?

    python analysis/novelty.py --archive runs/offline/archive.jsonl

This is the instrument for the project's actual purpose. RESEARCH_DESIGN §5
calls the archive "a map of alternatives, not an answer", and §4's RQ3 asks
whether the machinery "holds diversity — an option map, not one answer". Neither
is a question about ranking, and that matters: the resolution floor measured at
M1 (effect 0.696 against inter-judge noise 0.921) would sink a claim that the
champion is *best*, while barely touching a claim that the archive is *diverse
and coherent*.

So this module deliberately does not care who won. It asks four things:

1. **Novelty** — how far is each portfolio from the nearest human-written seed?
   The five seeds span the recognised doctrinal space (December 2022 plus four
   rival schools). A portfolio far from all five occupies ground no author in
   this project chose to occupy.
2. **Robustness** — worst-case composite across the three scenarios, not the
   mean. A portfolio that survives its worst scenario is a different kind of
   object from one that averages well by winning a single future.
3. **The frontier** — portfolios that are simultaneously novel and robust.
   Those are the reportable finds: coherent, gate-valid, unlike anything the
   humans wrote, and not fragile.
4. **Coverage** — how much of the allocation space the search actually visited,
   and whether it collapsed onto one family.

Distances are L1 over the 30-dial share vector, where 0 is identical and 2.0 is
disjoint. A distance of d means d/2 of Japan's marginal effort is allocated
differently, which is interpretable in a way cosine similarity over embeddings
is not — and interpretability is the point when the output is meant to be read
by a human analyst.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
for extra in (TASK_DIR, TASK_DIR / "seeds"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from lowy import DIALS, MEASURES  # noqa: E402

#: The human-written reference set: the actual December 2022 programme plus the
#: four rival schools. Novelty is measured against all of them at once.
HUMAN_SEEDS: Tuple[Tuple[str, Path], ...] = (
    ("dec_2022", TASK_DIR / "initial.py"),
    ("status_quo_plus", TASK_DIR / "seeds" / "seed_status_quo_plus.py"),
    ("autonomous_rearmament", TASK_DIR / "seeds" / "seed_autonomous_rearmament.py"),
    ("accommodation", TASK_DIR / "seeds" / "seed_accommodation.py"),
    ("middle_power", TASK_DIR / "seeds" / "seed_middle_power_internationalism.py"),
)

#: L1 below this and two portfolios are the same doctrine with different labels.
#: 0.20 is the floor tests/test_seeds.py already enforces between rival schools,
#: so it is the project's existing definition of "materially different".
SAME_FAMILY = 0.20


def _load_human_vectors() -> Dict[str, List[float]]:
    import importlib.util

    vectors = {}
    for name, path in HUMAN_SEEDS:
        spec = importlib.util.spec_from_file_location(f"human_{name}", path)
        module = importlib.util.module_from_spec(spec)   # type: ignore[arg-type]
        spec.loader.exec_module(module)                  # type: ignore[union-attr]
        dials = module.build_policy().dials
        vectors[name] = [dials[d].share if d in dials else 0.0 for d in DIALS]
    return vectors


def share_vector(record: Dict[str, Any]) -> List[float]:
    shares = {d.get("dial"): d.get("share", 0.0)
              for d in record.get("portfolio", {}).get("dials", [])}
    out = []
    for dial in DIALS:
        try:
            out.append(float(shares.get(dial, 0.0)))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def l1(a: List[float], b: List[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


# --------------------------------------------------------------------------
# The four questions
# --------------------------------------------------------------------------


def novelty_against_humans(
    vector: List[float], humans: Dict[str, List[float]]
) -> Tuple[float, str]:
    """Distance to the NEAREST human seed, and which one it is.

    Nearest rather than mean: a portfolio is only novel if it is unlike *every*
    doctrine a human wrote, not merely unlike their average — the average of
    five opposed doctrines is itself a portfolio nobody holds.
    """
    distances = {name: l1(vector, vec) for name, vec in humans.items()}
    nearest = min(distances, key=distances.get)
    return distances[nearest], nearest


def families(vectors: List[List[float]], threshold: float = SAME_FAMILY) -> List[List[int]]:
    """Greedy single-link clustering: how many distinct doctrines are held?

    Deliberately simple and deterministic. The number wanted is "roughly how
    many genuinely different things are in here", and a greedy pass answers that
    without importing a clustering library or introducing a random seed.
    """
    clusters: List[List[int]] = []
    for index, vector in enumerate(vectors):
        for cluster in clusters:
            if any(l1(vector, vectors[member]) < threshold for member in cluster):
                cluster.append(index)
                break
        else:
            clusters.append([index])
    return clusters


def frontier(records: List[Dict[str, Any]], humans: Dict[str, List[float]],
             min_novelty: float) -> List[Dict[str, Any]]:
    """Novel AND robust: unlike every human seed, and strong in its worst scenario.

    Pareto-style rather than thresholded on score, because a score threshold
    would smuggle the ranking claim back in through the side door. A portfolio
    is on the frontier if nothing else is both more novel and more robust.
    """
    candidates = []
    for record in records:
        if not record.get("valid"):
            continue
        worst = record.get("public", {}).get("worst_case_composite")
        if worst is None:
            continue
        distance, nearest = novelty_against_humans(share_vector(record), humans)
        if distance >= min_novelty:
            candidates.append({"id": record["id"], "novelty": round(distance, 4),
                               "nearest_human": nearest,
                               "worst_case": round(float(worst), 4),
                               "mean": round(record.get("score", 0.0), 4)})
    keep = []
    for c in candidates:
        dominated = any(
            o["novelty"] >= c["novelty"] and o["worst_case"] >= c["worst_case"]
            and (o["novelty"] > c["novelty"] or o["worst_case"] > c["worst_case"])
            for o in candidates
        )
        if not dominated:
            keep.append(c)
    return sorted(keep, key=lambda c: -c["novelty"])


def measure_coverage(vectors: List[List[float]]) -> Dict[str, Any]:
    """Which measures the search actually explored, versus left alone."""
    by_measure: Dict[str, List[float]] = {m: [] for m in MEASURES}
    for vector in vectors:
        totals = {m: 0.0 for m in MEASURES}
        for dial, share in zip(DIALS, vector):
            totals[dial.split(".", 1)[0]] += share
        for m, v in totals.items():
            by_measure[m].append(v)
    return {
        m: {"min": round(min(v), 4), "max": round(max(v), 4),
            "range": round(max(v) - min(v), 4)}
        for m, v in by_measure.items()
    }


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def analyse(records: List[Dict[str, Any]], min_novelty: float) -> Dict[str, Any]:
    humans = _load_human_vectors()
    valid = [r for r in records if r.get("valid")]
    vectors = [share_vector(r) for r in valid]

    novelties = [novelty_against_humans(v, humans)[0] for v in vectors]
    clusters = families(vectors)
    human_span = max(
        l1(a, b) for a in humans.values() for b in humans.values()
    )

    return {
        "surrogate": any(r.get("surrogate") for r in records),
        "evaluated": len(records),
        "valid": len(valid),
        "human_seed_span_l1": round(human_span, 4),
        "novelty": {
            "max": round(max(novelties), 4) if novelties else 0.0,
            "mean": round(sum(novelties) / len(novelties), 4) if novelties else 0.0,
            "beyond_human_span": sum(1 for n in novelties if n > human_span),
            "materially_novel": sum(1 for n in novelties if n >= min_novelty),
            "threshold": min_novelty,
        },
        "families": {
            "count": len(clusters),
            "largest": max((len(c) for c in clusters), default=0),
            "singletons": sum(1 for c in clusters if len(c) == 1),
        },
        "coverage": measure_coverage(vectors),
        "frontier": frontier(valid, humans, min_novelty),
    }


def write_report(stats: Dict[str, Any], out_dir: Path) -> Path:
    lines = ["# Novelty and diversity", ""]
    if stats["surrogate"]:
        lines += ["> **SURROGATE ARCHIVE — NOT A RESULT.** Scored by the offline "
                  "closed-form stand-in. Structure only; the policies mean nothing.", ""]
    n = stats["novelty"]
    lines += [
        f"- Valid portfolios: **{stats['valid']}** of {stats['evaluated']}",
        f"- The five human seeds span **{stats['human_seed_span_l1']}** L1 between "
        "their two extremes — that is the width of the recognised doctrinal space",
        f"- Most novel evolved portfolio sits **{n['max']}** from its nearest human seed",
        f"- **{n['materially_novel']}** portfolios are at least {n['threshold']} from "
        "every human seed (the project's own threshold for 'a different doctrine')",
        f"- **{n['beyond_human_span']}** are further from their nearest seed than the "
        "human seeds are from each other",
        f"- Distinct families found: **{stats['families']['count']}** "
        f"(largest holds {stats['families']['largest']}, "
        f"{stats['families']['singletons']} singletons)",
        "",
        "## The frontier — novel *and* robust",
        "",
        "Pareto-optimal on (distance from every human seed, worst-case composite). "
        "Worst-case rather than mean, so a portfolio that wins one future and "
        "collapses in another does not qualify. No score threshold is applied — "
        "that would smuggle a ranking claim back in.",
        "",
    ]
    if not stats["frontier"]:
        lines.append("*Nothing cleared the novelty threshold. The search stayed "
                     "inside the doctrinal space the humans had already mapped.*")
    else:
        lines += ["| id | novelty | nearest human seed | worst case | mean |",
                  "|---|---|---|---|---|"]
        for f in stats["frontier"][:20]:
            lines.append(f"| {f['id']} | {f['novelty']:.3f} | {f['nearest_human']} | "
                         f"{f['worst_case']:.3f} | {f['mean']:.3f} |")
    lines += ["", "## Where the search went", "",
              "| measure | min share | max share | range explored |", "|---|---|---|---|"]
    for m, c in sorted(stats["coverage"].items(), key=lambda kv: -kv[1]["range"]):
        lines.append(f"| {m.replace('_',' ')} | {c['min']:.3f} | {c['max']:.3f} "
                     f"| {c['range']:.3f} |")
    report = out_dir / "novelty.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--archive", default="runs/offline/archive.jsonl")
    parser.add_argument("--min-novelty", type=float, default=SAME_FAMILY)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    path = Path(args.archive)
    if not path.is_absolute():
        path = REPO_ROOT / path
    out_dir = Path(args.out) if args.out else path.parent
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    stats = analyse(records, args.min_novelty)
    (out_dir / "novelty.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    report = write_report(stats, out_dir)

    n = stats["novelty"]
    if stats["surrogate"]:
        print("SURROGATE ARCHIVE — structure only, not a result.")
    print(f"valid {stats['valid']}/{stats['evaluated']}  "
          f"families {stats['families']['count']}")
    print(f"human doctrinal span: {stats['human_seed_span_l1']:.3f} L1")
    print(f"max novelty {n['max']:.3f}, materially novel {n['materially_novel']}, "
          f"beyond the human span {n['beyond_human_span']}")
    print(f"frontier (novel AND robust): {len(stats['frontier'])} portfolios")
    print(f"wrote {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
