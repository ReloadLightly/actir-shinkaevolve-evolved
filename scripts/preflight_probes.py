#!/usr/bin/env python3
"""Cheap probes for premises the whole design rests on and never tested.

    python scripts/preflight_probes.py --estimate            # free
    python scripts/preflight_probes.py --probe determinism   # ~$0.008
    python scripts/preflight_probes.py --probe observability # ~$0.015
    python scripts/preflight_probes.py --probe all           # ~$0.023

M1 asked "is the rubric calibrated". These ask something prior: **is the judge
the kind of object the design assumes it is?** Two assumptions have been load-
bearing since Stage A and neither was ever verified.

## Probe 1 — determinism

RESEARCH_DESIGN §2.2 specifies "one LLM, pinned to an exact API version,
temperature 0", and the content-hash cache is built on that: an identical
request is assumed to deserve an identical answer, so the cached one is reused
forever. If the judge is not actually deterministic, then

* the cache freezes whichever answer happened to arrive first, and a rerun of
  the "same" experiment silently reuses a sample rather than reproducing one;
* the M1 judge-disagreement finding is confounded, because part of the
  -0.300 could be one model disagreeing with *itself*;
* "frozen judge" is not true, and the paper cannot claim it.

The probe scores one portfolio under one scenario N times with the cache
bypassed, and reports whether the deltas are bit-identical.

## Probe 2 — genotype observability

The judge receives phases, custom initiatives and the defence-spending path in
the portfolio JSON. Whether it *uses* them is unknown. The offline run found
that the four mutation operators touching those fields have a 0% improvement
rate — provable for the surrogate, which reads only dial shares, and an open
question for the real judge.

It matters because roughly 40% of the mutation budget is spent editing those
fields. If the judge is blind to them, that fraction of every run is spent
proposing changes the fitness function cannot see, and the cache makes it worse:
two portfolios differing only in an invisible field hash differently, so they
cost two calls to receive one answer.

The probe holds the dials fixed and varies exactly one invisible field at a
time, then reports whether the judge's deltas move at all.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

import evaluate as evaluator  # noqa: E402
from judge.client import (  # noqa: E402
    MOCK,
    PRICING_USD_PER_MTOK,
    REAL,
    JudgeClient,
    JudgeConfig,
)
from lowy import MEASURES  # noqa: E402
from schema import Initiative, Phase  # noqa: E402

DETERMINISM_REPEATS = 3
SCENARIO = "S2"          # the scenario with the most to disagree about
EST_IN, EST_OUT = 3500, 700


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _seed_portfolio():
    import initial

    return initial.build_policy()


def _fresh_client(config: JudgeConfig, tmp: Path, tag: str) -> JudgeClient:
    """A client whose cache is empty, so an identical request is really re-sent.

    Without this the second call of a determinism probe would be served from
    the cache and the probe would trivially, and falsely, pass.
    """
    cache = tmp / f"cache_{tag}"
    cache.mkdir(parents=True, exist_ok=True)
    return JudgeClient(
        JudgeConfig(**{**config.__dict__, "cache_dir": str(cache)})
    )


def _score_once(client: JudgeClient, portfolio_dict: Dict[str, Any],
                scenario_id: str = SCENARIO) -> Dict[str, float]:
    scenarios = evaluator.load_scenarios()
    prompt = evaluator.load_judge_prompt()
    verdict = client.score(
        scenario_id=scenario_id,
        scenario_text=scenarios[scenario_id],
        prompt_text=prompt,
        portfolio=portfolio_dict,
    )
    return verdict.deltas


def _spread(runs: List[Dict[str, float]]) -> Dict[str, float]:
    return {
        m: round(max(r[m] for r in runs) - min(r[m] for r in runs), 6)
        for m in MEASURES
    }


# --------------------------------------------------------------------------
# Probe 1 — determinism
# --------------------------------------------------------------------------


def probe_determinism(config: JudgeConfig, tmp: Path) -> Dict[str, Any]:
    portfolio = _seed_portfolio().to_dict()
    runs = []
    for i in range(DETERMINISM_REPEATS):
        client = _fresh_client(config, tmp, f"det{i}")
        runs.append(_score_once(client, portfolio))
        print(f"  call {i + 1}/{DETERMINISM_REPEATS} done", flush=True)

    spread = _spread(runs)
    worst = max(spread.values()) if spread else 0.0
    identical = worst == 0.0

    print()
    print(f"Determinism — {DETERMINISM_REPEATS} identical requests, cache bypassed")
    print(f"| {'measure':24} | " + " | ".join(f"run {i+1:>6}" for i in range(len(runs)))
          + " |   spread |")
    for m in MEASURES:
        cells = " | ".join(f"{r[m]:>+9.3f}" for r in runs)
        print(f"| {m:24} | {cells} | {spread[m]:>8.3f} |")
    print()
    if identical:
        print("  PASS — bit-identical across repeats. The cache is sound and "
              "'frozen judge' is a true description.")
    else:
        print(f"  FAIL — deltas vary by up to {worst:.3f} on identical input.")
        print("  The content-hash cache freezes whichever sample arrived first,")
        print("  so a 'reproduction' replays one draw rather than reproducing it.")
        print("  It also means part of M1's -0.300 is a model disagreeing with")
        print("  itself, not with the other judge.")
    return {"probe": "determinism", "repeats": len(runs), "identical": identical,
            "max_spread": worst, "per_measure_spread": spread, "runs": runs}


# --------------------------------------------------------------------------
# Probe 2 — genotype observability
# --------------------------------------------------------------------------


def _variants() -> Dict[str, Any]:
    """Same dials throughout; exactly one non-dial field changed per variant."""
    base = _seed_portfolio()

    phases = _seed_portfolio()
    phases.sequence([
        Phase(years=(2026, 2030),
              label="Single undifferentiated phase: everything at once, no "
                    "sequencing, no priority order.",
              focus=()),
    ])

    initiatives = _seed_portfolio()
    initiatives.custom_initiatives([])

    defence = _seed_portfolio()
    defence.defence_spending_path(
        {2026: 3.4, 2027: 3.4, 2028: 3.5, 2029: 3.5, 2030: 3.5}
    )

    return {
        "baseline": base,
        "phases_flattened": phases,
        "initiatives_removed": initiatives,
        "defence_1.6to2.0_becomes_3.4to3.5": defence,
    }


def probe_observability(config: JudgeConfig, tmp: Path) -> Dict[str, Any]:
    variants = _variants()
    base_dials = variants["baseline"].to_dict()["dials"]
    results: Dict[str, Dict[str, float]] = {}

    for i, (name, portfolio) in enumerate(variants.items()):
        as_dict = portfolio.to_dict()
        assert as_dict["dials"] == base_dials, (
            f"variant {name} changed the dials; the probe would be confounded"
        )
        client = _fresh_client(config, tmp, f"obs{i}")
        results[name] = _score_once(client, as_dict)
        print(f"  scored {name}", flush=True)

    base = results["baseline"]
    print()
    print("Genotype observability — dials held identical, one field changed")
    print(f"| {'variant':36} | max |delta| shift | judge noticed? |")
    print("|" + "-" * 38 + "|" + "-" * 18 + "|" + "-" * 16 + "|")

    verdicts = {}
    for name, deltas in results.items():
        if name == "baseline":
            continue
        shift = max(abs(deltas[m] - base[m]) for m in MEASURES)
        noticed = shift > 1e-9
        verdicts[name] = {"max_shift": round(shift, 6), "noticed": noticed}
        print(f"| {name:36} | {shift:>16.4f} | {'yes' if noticed else 'NO':>14} |")

    blind = [n for n, v in verdicts.items() if not v["noticed"]]
    print()
    if not blind:
        print("  All fields are visible to the judge. Every mutation operator "
              "can in principle move the score.")
    else:
        print(f"  The judge is BLIND to: {', '.join(blind)}")
        print("  Mutation effort spent on those fields cannot change fitness, and")
        print("  each such variant still costs a separate judge call because the")
        print("  cache key includes fields the judge ignores.")
    return {"probe": "observability", "variants": verdicts, "blind_to": blind,
            "deltas": results}


# --------------------------------------------------------------------------
# Cost and entry point
# --------------------------------------------------------------------------


PROBE_CALLS = {"determinism": DETERMINISM_REPEATS, "observability": 4}


def estimate(config: JudgeConfig, probes: List[str]) -> None:
    calls = sum(PROBE_CALLS[p] for p in probes)
    rates = PRICING_USD_PER_MTOK.get(config.model)
    print(f"Probes: {', '.join(probes)}")
    print(f"Judge:  {config.provider} / {config.model}")
    print(f"Calls:  {calls}")
    if rates is None:
        print("No price entry for this model; cannot estimate.")
        return
    cost = calls * (EST_IN * rates["input"] + EST_OUT * rates["output"]) / 1e6
    print(f"Estimated cost: ${cost:.4f}")
    print("Cache is bypassed by design, so re-running costs the same again.")


def _display(path: Path) -> str:
    """Repo-relative when it helps, absolute when it must.

    `Path.relative_to` raises for anything outside the repository, so naively
    relativising crashes whenever --out points elsewhere — a tmp dir, for
    instance.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--probe", default="all",
                        choices=["all", "determinism", "observability"])
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--judge-config", default=None)
    parser.add_argument("--out", default="runs/probes")
    args = parser.parse_args(argv)

    config = JudgeConfig.load(args.judge_config)
    probes = (["determinism", "observability"] if args.probe == "all"
              else [args.probe])

    if args.estimate:
        estimate(config, probes)
        return 0

    if config.mode == MOCK:
        print("Judge is in MOCK mode: every delta is zero, so determinism "
              "passes trivially and observability reports blindness to "
              "everything. Neither result means anything. Use the surrogate to "
              "exercise the harness, or a real judge to learn something.")

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Preflight probes — judge {config.model}, mode={config.mode}")
    print()
    results = []
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        if "determinism" in probes:
            results.append(probe_determinism(config, tmp))
            print()
        if "observability" in probes:
            results.append(probe_observability(config, tmp))

    payload = {
        "judge": config.identity(),
        "mode": config.mode,
        "meaningful": config.mode == REAL,
        "results": results,
    }
    written = out_dir / "probes.json"
    written.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {_display(written)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
