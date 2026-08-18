#!/usr/bin/env python3
"""Record the hashes of the frozen task files.

KICKOFF hard rule 3: ``scenarios/`` and ``judge_prompt.md`` are frozen after
Stage B approval. Any later change is a version bump and a new experiment id,
never an edit in place. ``tests/test_frozen_files.py`` fails whenever a file's
hash no longer matches what is recorded here, so the only way to change one is
to change it deliberately and re-run this script with a new version.

    python scripts/freeze.py --version 0.2.0-draft
    python scripts/freeze.py --version 1.0.0 --status FROZEN
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "tasks" / "japan_fp" / "FROZEN.json"

FROZEN_FILES: List[str] = [
    # Stage A: the judge's inputs.
    "tasks/japan_fp/scenarios/S1_grinding_status_quo.md",
    "tasks/japan_fp/scenarios/S2_taiwan_contingency.md",
    "tasks/japan_fp/scenarios/S3_us_retrenchment.md",
    "tasks/japan_fp/judge_prompt.md",
    # Project B: the preregistration. These three ARE the experiment's
    # hypothesis -- the dynamics, the action space and the held-out split. They
    # are hashed before scripts/qualify_world.py runs, which is the mechanical
    # defence against tuning the model until it returns the desired answer.
    # A change without a version bump fails tests/test_frozen_files.py.
    "tasks/japan_fp/world.py",
    "tasks/japan_fp/instruments.py",
    "tasks/japan_fp/splits.py",
]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current_hashes(repo_root: Path = REPO_ROOT) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for relative in FROZEN_FILES:
        path = repo_root / relative
        if not path.is_file():
            raise FileNotFoundError(f"frozen file is missing: {relative}")
        hashes[relative] = sha256_of(path)
    return hashes


def load_manifest(path: Path = MANIFEST_PATH) -> Dict:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Record frozen-file hashes.")
    parser.add_argument(
        "--version",
        required=True,
        help="New version id. Must differ from the recorded version.",
    )
    parser.add_argument(
        "--status",
        default="DRAFT",
        choices=["DRAFT", "FROZEN"],
        help="DRAFT before M0/M1 approval; FROZEN after.",
    )
    parser.add_argument("--note", default="", help="Why this version exists.")
    args = parser.parse_args()

    existing = load_manifest()
    if existing and existing.get("version") == args.version:
        raise SystemExit(
            f"version {args.version!r} is already recorded. Bump the version: a "
            "frozen file may never change in place under the same version."
        )

    history = list(existing.get("history", []))
    if existing:
        history.append(
            {
                "version": existing.get("version"),
                "status": existing.get("status"),
                "recorded_at": existing.get("recorded_at"),
                "note": existing.get("note", ""),
                "files": existing.get("files", {}),
            }
        )

    manifest = {
        "version": args.version,
        "status": args.status,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "note": args.note,
        "files": current_hashes(),
        "history": history,
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print(f"Recorded version {args.version} ({args.status}) in {MANIFEST_PATH}")
    for relative, digest in manifest["files"].items():
        print(f"  {digest[:16]}  {relative}")


if __name__ == "__main__":
    main()
