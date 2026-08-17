"""Put the task folder on sys.path so tests import it the way evaluate.py does."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"

for path in (str(TASK_DIR), str(REPO_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
