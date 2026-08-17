#!/usr/bin/env python3
"""Convert a real ShinkaEvolve run into the archive format the analysis reads.

    python analysis/shinka_adapter.py --results runs/pilot

The offline driver and the real engine keep their archives in different places:
`scripts/offline_evolution.py` writes `archive.jsonl` directly, while
ShinkaEvolve keeps a `ProgramDatabase` and hands out `Program` objects. Rather
than teach the analysis two formats, this normalises the engine's output into
the one `analysis/archive_analysis.py` and `analysis/novelty.py` already read.

The payoff is that every figure and every novelty statistic was built and
debugged against hundreds of offline archives before the first paid run, and
then applies unchanged to the real one.

**The portfolio survives the round trip because `evaluate.py` puts it there.**
`score_portfolio` writes the canonical portfolio dict into `private`, which
ShinkaEvolve stores as `private_metrics`. Without that the database would hold
only the program *text*, and the novelty analysis — which works on 30-dial
share vectors — would have nothing to read.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))


def _as_dict(value: Any) -> Dict[str, Any]:
    """private/public metrics arrive as dicts or as JSON strings."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def program_to_record(program: Any, index: int) -> Optional[Dict[str, Any]]:
    """One ShinkaEvolve Program as one archive record.

    Returns None for programs carrying no portfolio — a program that failed
    before `build_policy()` returned has nothing for the novelty analysis to
    measure, and silently emitting it with an empty dial list would drag every
    distance calculation toward a portfolio that does not exist.
    """
    private = _as_dict(getattr(program, "private_metrics", None))
    public = _as_dict(getattr(program, "public_metrics", None))
    portfolio = private.get("portfolio")
    if not isinstance(portfolio, dict) or not portfolio.get("dials"):
        return None

    correct = getattr(program, "correct", None)
    valid = bool(public.get("valid", correct if correct is not None else True))

    try:
        score = float(getattr(program, "combined_score", 0.0) or 0.0)
    except (TypeError, ValueError):
        score = 0.0

    ident = getattr(program, "id", None)
    parent = getattr(program, "parent_id", None)

    return {
        "id": ident if isinstance(ident, int) else index,
        "shinka_id": str(ident) if ident is not None else None,
        "parent": parent if isinstance(parent, int) else None,
        "shinka_parent_id": str(parent) if parent is not None else None,
        "generation": int(getattr(program, "generation", 0) or 0),
        "island": getattr(program, "island_idx", None),
        "operator": "llm_mutation",
        "valid": valid,
        "score": score,
        "surrogate": False,          # a real run; the analysis stamps accordingly
        "public": public,
        "portfolio": portfolio,
        "text_feedback": getattr(program, "text_feedback", "") or "",
    }


def _remap_lineage(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Make parent ids consistent with the integer ids we emit.

    ShinkaEvolve identifies programs by string uuid; the analysis walks lineage
    over the integer `id`/`parent` pair. Remapping keeps `best_lineage` honest
    rather than silently truncating every chain at its first hop.
    """
    by_shinka = {r["shinka_id"]: r["id"] for r in records if r.get("shinka_id")}
    for record in records:
        parent_uuid = record.get("shinka_parent_id")
        record["parent"] = by_shinka.get(parent_uuid) if parent_uuid else None
    return records


def load_from_results(results_dir: Path) -> List[Dict[str, Any]]:
    from shinka.database import DatabaseConfig, ProgramDatabase

    candidates = sorted(results_dir.rglob("*.db")) + sorted(results_dir.rglob("*.sqlite"))
    if not candidates:
        raise SystemExit(
            f"No ShinkaEvolve database found under {results_dir}. "
            "Looked for *.db and *.sqlite. Was the run started?"
        )
    db_path = candidates[0]
    database = ProgramDatabase(DatabaseConfig(db_path=str(db_path)), read_only=True)
    try:
        programs = database.get_all_programs()
    finally:
        try:
            database.close()
        except Exception:  # noqa: BLE001 - closing must not lose the export
            pass

    records = []
    for index, program in enumerate(programs):
        record = program_to_record(program, index)
        if record is not None:
            records.append(record)
    return _remap_lineage(records)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results", default="runs/pilot",
                        help="the run's results_dir, as set in the config")
    parser.add_argument("--out", default=None,
                        help="where to write archive.jsonl (default: alongside)")
    args = parser.parse_args(argv)

    results_dir = Path(args.results)
    if not results_dir.is_absolute():
        results_dir = REPO_ROOT / results_dir
    out_dir = Path(args.out) if args.out else results_dir
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_from_results(results_dir)
    if not records:
        raise SystemExit(
            f"{results_dir} holds no programs with a portfolio in private_metrics. "
            "Either no generation completed, or evaluate.py stopped writing "
            "'portfolio' into its private metrics."
        )

    target = out_dir / "archive.jsonl"
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    valid = sum(1 for r in records if r["valid"])
    best = max(records, key=lambda r: r["score"])
    print(f"Exported {len(records)} programs ({valid} valid) -> {target}")
    print(f"  generations {min(r['generation'] for r in records)}"
          f"-{max(r['generation'] for r in records)}")
    print(f"  best combined_score {best['score']:.4f} (id {best['id']})")
    print("Now run:")
    print(f"  python analysis/archive_analysis.py --archive {target}")
    print(f"  python analysis/novelty.py --archive {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
