"""The adapter from ShinkaEvolve's database to the analysis archive format.

Its job is to make one format out of two, so every figure and novelty statistic
built against hundreds of free offline archives applies unchanged to the first
paid run. These tests use stand-in Program objects rather than a live database,
because the contract that matters is field-level and can be pinned exactly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (REPO_ROOT / "analysis", REPO_ROOT / "tasks" / "japan_fp"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import shinka_adapter as adapter  # noqa: E402
from lowy import DIALS  # noqa: E402


class FakeProgram:
    """Mirrors the fields of shinka.database.Program that the adapter reads."""

    def __init__(self, **kw):
        self.id = kw.get("id", "uuid-0")
        self.parent_id = kw.get("parent_id")
        self.generation = kw.get("generation", 0)
        self.island_idx = kw.get("island_idx", 0)
        self.combined_score = kw.get("combined_score", 40.0)
        self.correct = kw.get("correct", True)
        self.public_metrics = kw.get("public_metrics", {"valid": True})
        self.private_metrics = kw.get("private_metrics", _private())
        self.text_feedback = kw.get("text_feedback", "")


def _portfolio():
    return {"dials": [{"dial": d, "share": 1.0 / len(DIALS), "how": "x"} for d in DIALS]}


def _private():
    return {"portfolio": _portfolio()}


def test_a_program_becomes_an_archive_record():
    record = adapter.program_to_record(FakeProgram(), 0)
    assert record["valid"] is True
    assert record["surrogate"] is False, "a real run must never be stamped surrogate"
    assert record["portfolio"]["dials"]
    assert record["score"] == 40.0


def test_a_program_without_a_portfolio_is_dropped():
    """Emitting it with an empty dial list would drag every novelty distance
    toward a portfolio that does not exist."""
    assert adapter.program_to_record(FakeProgram(private_metrics={}), 0) is None
    assert adapter.program_to_record(
        FakeProgram(private_metrics={"portfolio": {"dials": []}}), 0) is None


def test_metrics_stored_as_json_strings_are_parsed():
    """ShinkaEvolve may persist metrics as serialised JSON rather than dicts."""
    record = adapter.program_to_record(
        FakeProgram(private_metrics=json.dumps(_private()),
                    public_metrics=json.dumps({"valid": True, "worst_case_composite": 39.5})),
        0,
    )
    assert record is not None
    assert record["public"]["worst_case_composite"] == 39.5


def test_invalid_programs_are_marked_invalid():
    record = adapter.program_to_record(
        FakeProgram(correct=False, public_metrics={"valid": False}), 0)
    assert record["valid"] is False


def test_lineage_is_remapped_from_uuids_to_integers():
    """The analysis walks lineage over integer ids. Without remapping, every
    ancestry chain would truncate at its first hop and lineage depth would be
    reported as 1 for everything."""
    programs = [
        FakeProgram(id="uuid-a", parent_id=None, generation=0),
        FakeProgram(id="uuid-b", parent_id="uuid-a", generation=1),
        FakeProgram(id="uuid-c", parent_id="uuid-b", generation=2),
    ]
    records = adapter._remap_lineage(
        [adapter.program_to_record(p, i) for i, p in enumerate(programs)]
    )
    by_id = {r["id"]: r for r in records}
    child = records[2]
    assert child["parent"] == records[1]["id"]
    assert by_id[child["parent"]]["parent"] == records[0]["id"]
    assert records[0]["parent"] is None


def test_the_exported_records_satisfy_the_analysis_contract(tmp_path):
    """The whole point: the real archive must feed both analysis modules
    unchanged."""
    import archive_analysis
    import novelty

    records = adapter._remap_lineage([
        adapter.program_to_record(FakeProgram(id=f"u{i}", parent_id=None if i == 0 else "u0",
                                              generation=i), i)
        for i in range(6)
    ])
    stats = archive_analysis.analyse(records)
    assert stats["surrogate"] is False
    assert stats["evaluated"] == 6

    nov = novelty.analyse(records, min_novelty=0.20)
    assert nov["surrogate"] is False
    assert nov["valid"] == 6


def test_a_real_archive_is_not_labelled_not_a_result(tmp_path):
    """The NOT A RESULT banner belongs on surrogate archives only. Leaving it
    on a real one would discredit the actual finding."""
    import archive_analysis

    records = [adapter.program_to_record(FakeProgram(), 0)]
    stats = archive_analysis.analyse(records)
    report = archive_analysis.write_report(stats, records, tmp_path)
    assert "NOT A RESULT" not in report.read_text()
