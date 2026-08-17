"""Test 4: the frozen files match their recorded hashes.

KICKOFF hard rule 3: `scenarios/` and `judge_prompt.md` are frozen after Stage B
approval; any later change is a version bump and a new experiment id, never an
edit in place. This test is the enforcement: editing a frozen file without
running `scripts/freeze.py --version <new>` turns the suite red.
"""

import json
from pathlib import Path

import pytest

from scripts.freeze import FROZEN_FILES, MANIFEST_PATH, current_hashes, sha256_of

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.is_file(), (
        "tasks/japan_fp/FROZEN.json is missing. Run: "
        "python scripts/freeze.py --version 0.1.0-draft"
    )
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_every_frozen_file_exists():
    for relative in FROZEN_FILES:
        assert (REPO_ROOT / relative).is_file(), f"missing frozen file: {relative}"


def test_manifest_covers_exactly_the_frozen_file_set(manifest):
    assert set(manifest["files"]) == set(FROZEN_FILES)


def test_hashes_match_the_recorded_manifest(manifest):
    """The load-bearing assertion: a frozen file changed without a version bump."""
    actual = current_hashes()
    drifted = [
        relative
        for relative, digest in manifest["files"].items()
        if actual.get(relative) != digest
    ]
    assert not drifted, (
        "These frozen files changed without a version bump:\n"
        + "\n".join(f"  - {relative}" for relative in drifted)
        + "\n\nA frozen file may never be edited in place. Bump the version:\n"
        "  python scripts/freeze.py --version <new-version> --note '<why>'"
    )


def test_manifest_records_a_version_and_a_status(manifest):
    assert manifest.get("version"), "FROZEN.json must record a version"
    assert manifest.get("status") in {"DRAFT", "FROZEN"}


def test_history_versions_are_unique(manifest):
    """A version identifies one set of hashes; reusing one would break provenance."""
    versions = [entry.get("version") for entry in manifest.get("history", [])]
    versions.append(manifest["version"])
    assert len(versions) == len(set(versions)), f"duplicate version ids: {versions}"


def test_draft_files_are_labelled_draft_in_their_own_text(manifest):
    """While status is DRAFT, the texts must say so, so no run is mistaken for M0."""
    if manifest["status"] != "DRAFT":
        pytest.skip("files are frozen; the DRAFT banner is expected to be gone")
    for relative in FROZEN_FILES:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert "DRAFT" in text, f"{relative} is not labelled DRAFT"


def test_hashing_is_deterministic():
    path = REPO_ROOT / FROZEN_FILES[0]
    assert sha256_of(path) == sha256_of(path)
