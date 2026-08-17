"""Thin adapter over ShinkaEvolve's evaluation contract.

``shinka.core.run_shinka_eval`` is used when ShinkaEvolve is installed. When it
is not — Stage A runs with zero dependencies and zero network — an equivalent
local implementation produces the same two artifacts the runner reads:

* ``metrics.json``  — ``combined_score`` + ``public`` + ``private`` + ``text_feedback``
* ``correct.json``  — ``{"correct": bool, "error": str | None}``

Keeping both paths behind one function means ``evaluate.py`` is identical in
CI and under the real runner.
"""

from __future__ import annotations

import importlib.util
import json
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple


#: `shinka` on PyPI is an unrelated image-upscaling package by a different
#: author. Installing it gets you something that imports cleanly, provides
#: `shinka.core`, and has nothing whatever to do with SakanaAI's ShinkaEvolve.
#: The real engine must come from the git URL in requirements.txt.
_IMPOSTOR_HINT = (
    "A package named 'shinka' is installed but does not provide "
    "shinka.core.run_shinka_eval.\n"
    "  PyPI 'shinka' is an unrelated IMAGE-UPSCALING package, not ShinkaEvolve.\n"
    "  Falling back to the local harness, which is equivalent for evaluation.\n"
    "  For the real engine:  pip uninstall -y shinka && "
    "pip install git+https://github.com/SakanaAI/ShinkaEvolve.git"
)


def shinka_is_real() -> bool:
    """True only when the installed `shinka` is actually ShinkaEvolve.

    Distinguishes the real engine from the identically-named PyPI package, so
    a silent fallback can never be mistaken for a real run.
    """
    try:
        import shinka.core as core  # noqa: WPS433
    except Exception:  # noqa: BLE001
        return False
    return callable(getattr(core, "run_shinka_eval", None))


def _warn_if_impostor_shinka() -> None:
    """Say so loudly when a wrong-but-importable `shinka` is present.

    Without this the fallback is silent, and silence here is the dangerous
    kind: the run completes, the numbers look normal, and you believe the real
    engine produced them.
    """
    import importlib.util as _util

    if _util.find_spec("shinka") is not None and not shinka_is_real():
        print(_IMPOSTOR_HINT)


def load_program(program_path: str) -> Any:
    """Load an evolved program by file path (same semantics as ShinkaEvolve)."""
    spec = importlib.util.spec_from_file_location("program", program_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load program at {program_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _save(results_dir: str, metrics: Dict[str, Any], correct: bool, error: Optional[str]) -> None:
    os.makedirs(results_dir, exist_ok=True)
    with open(os.path.join(results_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    with open(os.path.join(results_dir, "correct.json"), "w", encoding="utf-8") as f:
        json.dump({"correct": correct, "error": error}, f, indent=2)


def _run_local(
    program_path: str,
    results_dir: str,
    experiment_fn_name: str,
    validate_fn: Callable[[Any], Tuple[bool, Optional[str]]],
    aggregate_metrics_fn: Callable[[List[Any]], Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool, Optional[str]]:
    correct = True
    error: Optional[str] = None
    metrics: Dict[str, Any]

    try:
        module = load_program(program_path)
        if not hasattr(module, experiment_fn_name):
            raise AttributeError(
                f"function {experiment_fn_name!r} not found in {program_path}"
            )
        start = time.perf_counter()
        result = getattr(module, experiment_fn_name)()
        elapsed = time.perf_counter() - start

        valid, message = validate_fn(result)
        if not valid:
            correct = False
            error = f"Validation failed: {message}"

        metrics = aggregate_metrics_fn([result])
        metrics["execution_time_mean"] = elapsed
        metrics["execution_time_std"] = 0.0
        metrics["num_valid_runs"] = 1 if valid else 0
        metrics["num_invalid_runs"] = 0 if valid else 1
        metrics["all_validation_errors"] = [] if valid else [message or "invalid"]
    except Exception as exc:  # noqa: BLE001 - the harness must never raise
        correct = False
        error = str(exc)
        metrics = {
            "combined_score": 0.0,
            "public": {"valid": False},
            "private": {},
            "text_feedback": f"The program raised an exception: {exc}",
            "execution_time_mean": 0.0,
            "execution_time_std": 0.0,
            "num_valid_runs": 0,
            "num_invalid_runs": 1,
            "all_validation_errors": [str(exc)],
        }

    _save(results_dir, metrics, correct, error)
    return metrics, correct, error


def run_eval(
    program_path: str,
    results_dir: str,
    experiment_fn_name: str,
    validate_fn: Callable[[Any], Tuple[bool, Optional[str]]],
    aggregate_metrics_fn: Callable[[List[Any]], Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool, Optional[str]]:
    """Evaluate one program, preferring ShinkaEvolve's own harness."""
    try:
        from shinka.core import run_shinka_eval
    except Exception:  # noqa: BLE001 - ShinkaEvolve absent is a supported mode
        _warn_if_impostor_shinka()
        return _run_local(
            program_path=program_path,
            results_dir=results_dir,
            experiment_fn_name=experiment_fn_name,
            validate_fn=validate_fn,
            aggregate_metrics_fn=aggregate_metrics_fn,
        )

    return run_shinka_eval(
        program_path=program_path,
        results_dir=results_dir,
        experiment_fn_name=experiment_fn_name,
        num_runs=1,
        get_experiment_kwargs=lambda _index: {},
        validate_fn=validate_fn,
        aggregate_metrics_fn=aggregate_metrics_fn,
    )
