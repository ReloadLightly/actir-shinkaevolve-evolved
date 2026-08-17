#!/usr/bin/env python3
"""Read an archive and produce the RESEARCH_DESIGN section 4 readings.

    python analysis/archive_analysis.py --archive runs/offline/archive.jsonl

Works on any archive in the standard record shape, whether it came from the
offline surrogate driver or from a real ShinkaEvolve run, so the figures are
built and debugged before the first paid run rather than after it.

Outputs `report.md`, `analysis.json`, and standalone SVG figures. SVG is
hand-emitted rather than drawn with matplotlib on purpose: the repo's Stage A
dependency list is pyyaml and pytest, and an analysis layer that cannot run
without a scientific stack is one more thing to install at the worst moment.

Every output is stamped with whether the archive was surrogate-scored, because
a surrogate trajectory looks exactly like a real one and the two mean entirely
different things.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

from lowy import BASELINE_2025, JAPAN_2025_COMPOSITE, MEASURES, WEIGHTS  # noqa: E402

BASELINE_COMPOSITE = sum(WEIGHTS[m] * BASELINE_2025[m] for m in MEASURES)


# --------------------------------------------------------------------------
# Loading and derived quantities
# --------------------------------------------------------------------------


def load_archive(path: Path) -> List[Dict[str, Any]]:
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise SystemExit(f"{path} is empty")
    return records


def effort_by_measure(record: Dict[str, Any]) -> Dict[str, float]:
    totals = {m: 0.0 for m in MEASURES}
    for dial in record.get("portfolio", {}).get("dials", []):
        measure = str(dial.get("dial", "")).split(".", 1)[0]
        if measure in totals:
            try:
                totals[measure] += float(dial.get("share", 0.0))
            except (TypeError, ValueError):
                continue
    return totals


def lineage(records: List[Dict[str, Any]], ident: int) -> List[int]:
    by_id = {r["id"]: r for r in records}
    chain, current = [], by_id.get(ident)
    while current is not None:
        chain.append(current["id"])
        parent = current.get("parent")
        current = by_id.get(parent) if parent is not None else None
    return list(reversed(chain))


def best_so_far(records: List[Dict[str, Any]]) -> List[float]:
    """RQ1's trajectory: the improvement curve, in evaluation order."""
    trace, best = [], float("-inf")
    for record in sorted(records, key=lambda r: r["generation"]):
        best = max(best, record["score"])
        trace.append(best)
    return trace


# --------------------------------------------------------------------------
# SVG, hand-rolled so the analysis has no plotting dependency
# --------------------------------------------------------------------------


def _svg(width: int, height: int, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="system-ui,sans-serif">'
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>'
        f'<text x="{width/2}" y="26" text-anchor="middle" font-size="15" '
        f'font-weight="600" fill="#111">{title}</text>{body}</svg>'
    )


def figure_trajectory(records: List[Dict[str, Any]], out: Path) -> None:
    """Best-fitness trajectory against the 2025 baseline (their Fig. 5)."""
    trace = best_so_far(records)
    w, h, pad = 720, 320, 56
    lo = min(min(trace), BASELINE_COMPOSITE) - 0.1
    hi = max(max(trace), BASELINE_COMPOSITE) + 0.1
    span = max(hi - lo, 1e-9)

    def x(i: int) -> float:
        return pad + i * (w - 2 * pad) / max(len(trace) - 1, 1)

    def y(v: float) -> float:
        return h - pad - (v - lo) * (h - 2 * pad) / span

    pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(trace))
    body = [
        f'<line x1="{pad}" y1="{y(BASELINE_COMPOSITE):.1f}" x2="{w-pad}" '
        f'y2="{y(BASELINE_COMPOSITE):.1f}" stroke="#c0392b" stroke-width="1.5" '
        f'stroke-dasharray="6 4"/>',
        f'<text x="{w-pad}" y="{y(BASELINE_COMPOSITE)-7:.1f}" text-anchor="end" '
        f'font-size="11" fill="#c0392b">Japan 2025 = {BASELINE_COMPOSITE:.2f}</text>',
        f'<polyline points="{pts}" fill="none" stroke="#1f6feb" stroke-width="2"/>',
        f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#444"/>',
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#444"/>',
        f'<text x="{w/2}" y="{h-14}" text-anchor="middle" font-size="11" '
        f'fill="#444">evaluations</text>',
        f'<text x="{pad-8}" y="{y(hi-0.02):.1f}" text-anchor="end" font-size="10" '
        f'fill="#444">{hi:.2f}</text>',
        f'<text x="{pad-8}" y="{y(lo):.1f}" text-anchor="end" font-size="10" '
        f'fill="#444">{lo:.2f}</text>',
    ]
    out.write_text(_svg(w, h, "".join(body), "Best composite so far"), encoding="utf-8")


def figure_measure_shift(seed: Dict[str, Any], best: Dict[str, Any], out: Path) -> None:
    """Where the champion put its effort, against the December 2022 seed."""
    s, b = effort_by_measure(seed), effort_by_measure(best)
    order = sorted(MEASURES, key=lambda m: -(b[m] - s[m]))
    w, h, pad, row = 720, 60 + 30 * len(order), 210, 30
    mid = pad + (w - pad - 40) / 2
    scale = (w - pad - 50) / 2 / 0.30      # +/-30 percentage points full scale
    body = [f'<line x1="{mid}" y1="44" x2="{mid}" y2="{h-14}" stroke="#999"/>']
    for i, m in enumerate(order):
        delta = b[m] - s[m]
        y0 = 52 + i * row
        length = max(min(delta, 0.30), -0.30) * scale
        x0 = min(mid, mid + length)
        colour = "#2e7d32" if delta >= 0 else "#c0392b"
        body.append(
            f'<text x="{pad-10}" y="{y0+14}" text-anchor="end" font-size="11" '
            f'fill="#111">{m.replace("_"," ")}</text>'
            f'<rect x="{x0:.1f}" y="{y0}" width="{abs(length):.1f}" height="17" '
            f'fill="{colour}" opacity="0.85"/>'
            f'<text x="{mid + length + (6 if delta>=0 else -6):.1f}" y="{y0+13}" '
            f'font-size="10" fill="#333" '
            f'text-anchor="{"start" if delta>=0 else "end"}">{delta*100:+.1f}pp</text>'
        )
    out.write_text(
        _svg(w, h, "".join(body), "Champion effort vs December 2022 seed"),
        encoding="utf-8",
    )


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


def analyse(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    valid = [r for r in records if r.get("valid")]
    seed = min(records, key=lambda r: r["generation"])
    best = max(records, key=lambda r: r["score"])
    surrogate = any(r.get("surrogate") for r in records)

    operators: Dict[str, Dict[str, int]] = defaultdict(lambda: {"tried": 0, "valid": 0, "improved": 0})
    by_id = {r["id"]: r for r in records}
    for record in records:
        if record.get("parent") is None:
            continue
        stats = operators[record.get("operator", "?")]
        stats["tried"] += 1
        stats["valid"] += int(bool(record.get("valid")))
        parent = by_id.get(record["parent"])
        if parent is not None and record["score"] > parent["score"]:
            stats["improved"] += 1

    return {
        "surrogate": surrogate,
        "not_a_result": (
            "Surrogate-scored archive: pipeline validation only, never report."
            if surrogate else None
        ),
        "evaluated": len(records),
        "valid": len(valid),
        "rejected_by_gate": len(records) - len(valid),
        "baseline_2025_composite": round(BASELINE_COMPOSITE, 4),
        "reported_2025_composite": JAPAN_2025_COMPOSITE,
        "seed_score": round(seed["score"], 6),
        "best_score": round(best["score"], 6),
        "best_id": best["id"],
        "improvement_over_seed": round(best["score"] - seed["score"], 6),
        "improvement_over_2025": round(best["score"] - BASELINE_COMPOSITE, 6),
        "best_lineage": lineage(records, best["id"]),
        "best_lineage_depth": len(lineage(records, best["id"])) - 1,
        "effort_seed": {m: round(v, 4) for m, v in effort_by_measure(seed).items()},
        "effort_best": {m: round(v, 4) for m, v in effort_by_measure(best).items()},
        "operators": {k: dict(v) for k, v in sorted(operators.items())},
    }


def write_report(stats: Dict[str, Any], records: List[Dict[str, Any]], out_dir: Path) -> Path:
    lines = ["# Archive analysis", ""]
    if stats["surrogate"]:
        lines += [
            "> **SURROGATE ARCHIVE — NOT A RESULT.** Scored by the closed-form "
            "stand-in in `tasks/japan_fp/judge/surrogate.py`, with programmatic "
            "mutation rather than an LLM. This validates the pipeline, not the "
            "policy. Never report these numbers.",
            "",
        ]
    lines += [
        f"- Evaluated **{stats['evaluated']}**, valid {stats['valid']}, "
        f"rejected by the gate {stats['rejected_by_gate']} "
        f"({stats['rejected_by_gate']/stats['evaluated']:.0%})",
        f"- Seed **{stats['seed_score']:.4f}** → best **{stats['best_score']:.4f}** "
        f"({stats['improvement_over_seed']:+.4f})",
        f"- Japan 2025 baseline {stats['baseline_2025_composite']:.4f}; champion is "
        f"{stats['improvement_over_2025']:+.4f} against it",
        f"- Champion lineage depth **{stats['best_lineage_depth']}** — "
        + ("cumulative improvement, not a single lucky jump"
           if stats["best_lineage_depth"] > 3 else
           "shallow; the champion was found early and not built on"),
        "",
        "## RQ1 — does the search beat the seed?",
        "",
        "![trajectory](trajectory.svg)",
        "",
        "## Where the champion moved effort",
        "",
        "![effort](effort_shift.svg)",
        "",
        "| Measure | 2025 score | headroom | seed | champion | shift |",
        "|---|---|---|---|---|---|",
    ]
    for m in sorted(MEASURES, key=lambda m: -(stats["effort_best"][m] - stats["effort_seed"][m])):
        lines.append(
            f"| {m.replace('_', ' ')} | {BASELINE_2025[m]:.1f} | "
            f"{100 - BASELINE_2025[m]:.1f} | {stats['effort_seed'][m]*100:.1f}% | "
            f"{stats['effort_best'][m]*100:.1f}% | "
            f"{(stats['effort_best'][m] - stats['effort_seed'][m])*100:+.1f}pp |"
        )
    lines += [
        "",
        "## Operator effectiveness",
        "",
        "`improved` counts children that scored above their own parent — the "
        "only fair measure of an operator, since parents differ in quality.",
        "",
        "| Operator | tried | valid | improved | improve rate |",
        "|---|---|---|---|---|",
    ]
    for name, counts in stats["operators"].items():
        rate = counts["improved"] / counts["tried"] if counts["tried"] else 0.0
        lines.append(
            f"| `{name}` | {counts['tried']} | {counts['valid']} | "
            f"{counts['improved']} | {rate:.0%} |"
        )
    report = out_dir / "report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse an evolution archive.")
    parser.add_argument("--archive", default="runs/offline/archive.jsonl")
    parser.add_argument("--out", default=None,
                        help="output directory (default: alongside the archive)")
    args = parser.parse_args(argv)

    archive_path = Path(args.archive)
    if not archive_path.is_absolute():
        archive_path = REPO_ROOT / archive_path
    out_dir = Path(args.out) if args.out else archive_path.parent
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_archive(archive_path)
    stats = analyse(records)
    seed = min(records, key=lambda r: r["generation"])
    best = max(records, key=lambda r: r["score"])

    figure_trajectory(records, out_dir / "trajectory.svg")
    figure_measure_shift(seed, best, out_dir / "effort_shift.svg")
    (out_dir / "analysis.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    report = write_report(stats, records, out_dir)

    if stats["surrogate"]:
        print("SURROGATE ARCHIVE — pipeline validation only, not a result.")
    print(f"evaluated {stats['evaluated']}, gate rejected {stats['rejected_by_gate']}")
    print(f"seed {stats['seed_score']:.4f} -> best {stats['best_score']:.4f} "
          f"({stats['improvement_over_seed']:+.4f}), lineage depth "
          f"{stats['best_lineage_depth']}")
    print(f"wrote {report.relative_to(REPO_ROOT)}, analysis.json, "
          "trajectory.svg, effort_shift.svg")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
