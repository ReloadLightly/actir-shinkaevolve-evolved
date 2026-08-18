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
    SURROGATE,
    JudgeClient,
    JudgeConfig,
)
from lowy import MEASURES, composite_with_deltas  # noqa: E402
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

    # The composite is what fitness actually uses, and it is NOT the same story
    # as the per-measure table: Lowy's weights are spread across eight measures,
    # so independent per-measure wobble partly cancels. Reporting only the
    # per-measure worst case overstates the damage to ranking; reporting only
    # the composite hides that the judge can flip the SIGN of a single measure,
    # which corrupts the mechanism-sentence corpus even when the score survives.
    # Both numbers are the finding.
    composites = [composite_with_deltas(r) for r in runs]
    composite_spread = max(composites) - min(composites) if composites else 0.0

    print()
    print(f"Determinism — {DETERMINISM_REPEATS} identical requests, cache bypassed")
    print(f"| {'measure':24} | " + " | ".join(f"run {i+1:>6}" for i in range(len(runs)))
          + " |   spread |")
    for m in MEASURES:
        cells = " | ".join(f"{r[m]:>+9.3f}" for r in runs)
        print(f"| {m:24} | {cells} | {spread[m]:>8.3f} |")
    print()
    print(f"Composite by run: " + "  ".join(f"{c:.4f}" for c in composites))
    print(f"Composite spread on identical input: {composite_spread:.4f}")
    print()
    if identical:
        print("  PASS — bit-identical across repeats. The cache is sound and "
              "'frozen judge' is a true description.")
    else:
        print(f"  NOT DETERMINISTIC — per-measure deltas vary by up to "
              f"{worst:.3f} on identical input, and at least one measure can "
              f"change SIGN between draws.")
        print("  The content-hash cache freezes whichever sample arrived first,")
        print("  so a 'reproduction' replays one draw rather than reproducing it.")
        print("  'Frozen judge' is therefore not a true description, and the")
        print("  claim must be dropped from the writeup.")
        print()
        print(f"  At the COMPOSITE level the self-noise is {composite_spread:.4f}, "
              f"because per-measure errors partly cancel under Lowy's weights.")
        print("  Compare: effect across five opposite doctrines 0.696 (M1),")
        print("  inter-judge disagreement 0.921 (M1).")
        if composite_spread > 0:
            print(f"  Doctrine-scale signal-to-self-noise: "
                  f"{0.696 / composite_spread:.1f}x.")
        print("  So the judge resolves DOCTRINES. Whether it resolves the small")
        print("  steps evolution actually compares is a separate question, and")
        print("  the answer is no wherever a mutation moves the composite by")
        print(f"  less than {composite_spread:.2f}.")
    return {"probe": "determinism", "repeats": len(runs), "identical": identical,
            "max_spread": worst, "per_measure_spread": spread, "runs": runs,
            "composites": [round(c, 6) for c in composites],
            "composite_spread": round(composite_spread, 6),
            # Consumed by probe_observability as its significance threshold.
            "noise_floor_per_measure": worst,
            "noise_floor_composite": round(composite_spread, 6)}


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


def _prior_noise_floor(config: JudgeConfig,
                       out_dir: Optional[Path] = None) -> Optional[Dict[str, float]]:
    """The significance threshold a shift must clear to count as sight.

    Two sources, in order:

    * **Exact.** The mock and surrogate backends are closed-form and have no
      sampling noise at all, so their floor is exactly zero and any nonzero
      shift is real. This is a fact about the code, not an estimate.
    * **Measured.** For a real LLM judge, the determinism probe's observed
      spread on identical input. The workflow runs determinism first, so in
      practice this is present.

    When neither is available the verdict is reported as UNCALIBRATED rather
    than guessed -- an uncalibrated "yes" is exactly what made the first run of
    this probe wrong.
    """
    if config.mode in (MOCK, SURROGATE):
        return {"per_measure": 0.0, "composite": 0.0}
    base = out_dir if out_dir is not None else REPO_ROOT / "runs" / "probes"
    path = base / "probes.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    entries = payload if isinstance(payload, list) else payload.get("results", [])
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if (isinstance(entry, dict) and entry.get("probe") == "determinism"
                and "noise_floor_per_measure" in entry):
            return {"per_measure": float(entry["noise_floor_per_measure"]),
                    "composite": float(entry.get("noise_floor_composite", 0.0))}
    return None


def probe_observability(config: JudgeConfig, tmp: Path,
                        out_dir: Optional[Path] = None) -> Dict[str, Any]:
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
    base_composite = composite_with_deltas(base)

    # A shift is only evidence of the judge SEEING a field if it exceeds what
    # the same judge does to itself on identical input. The first version of
    # this probe used `shift > 1e-9` and concluded "all fields are visible"
    # from shifts of 1.0-1.3 -- while the determinism probe in the same run
    # measured up to 1.000 of pure self-noise on the same scale. That verdict
    # was unsupported by its own evidence. This is the fix.
    floor = _prior_noise_floor(config, out_dir)
    per_measure_floor = floor["per_measure"] if floor else None
    composite_floor = floor["composite"] if floor else None

    print()
    print("Genotype observability — dials held identical, one field changed")
    if floor:
        print(f"  significance threshold from the determinism probe: "
              f"per-measure {per_measure_floor:.3f}, "
              f"composite {composite_floor:.4f}")
    else:
        print("  UNCALIBRATED: no determinism result found, so no shift can be "
              "distinguished from the judge's own sampling noise. Run "
              "`--probe determinism` first.")
    print(f"| {'variant':36} | max |delta| | composite shift | verdict      |")
    print("|" + "-" * 38 + "|" + "-" * 13 + "|" + "-" * 17 + "|" + "-" * 14 + "|")

    verdicts = {}
    for name, deltas in results.items():
        if name == "baseline":
            continue
        shift = max(abs(deltas[m] - base[m]) for m in MEASURES)
        composite_shift = abs(composite_with_deltas(deltas) - base_composite)
        if floor is None:
            verdict, seen = "uncalibrated", None
        elif shift > per_measure_floor and composite_shift > composite_floor:
            verdict, seen = "SEEN", True
        elif shift > per_measure_floor or composite_shift > composite_floor:
            verdict, seen = "marginal", None
        else:
            verdict, seen = "within noise", False
        verdicts[name] = {"max_shift": round(shift, 6),
                          "composite_shift": round(composite_shift, 6),
                          "verdict": verdict, "noticed": seen}
        print(f"| {name:36} | {shift:>11.4f} | {composite_shift:>15.4f} "
              f"| {verdict:>12} |")

    blind = [n for n, v in verdicts.items() if v["noticed"] is False]
    unclear = [n for n, v in verdicts.items() if v["noticed"] is None]
    print()
    if floor is None:
        print("  No verdict. Re-run with the determinism probe to calibrate.")
    elif blind:
        print(f"  The judge is BLIND to: {', '.join(blind)}")
        print("  Mutation effort spent on those fields cannot change fitness, and")
        print("  each such variant still costs a separate judge call because the")
        print("  cache key includes fields the judge ignores.")
    elif unclear:
        print(f"  NOT ESTABLISHED for: {', '.join(unclear)}")
        print("  Their shifts are the same size as the judge's self-noise, so this")
        print("  probe cannot tell 'the judge read the field' from 'the judge")
        print("  resampled'. Separating them needs repeated draws per variant,")
        print("  which is the expensive version of this probe.")
    else:
        print("  All varied fields move the score by more than the judge's own")
        print("  self-noise. Every mutation operator can in principle move fitness.")
    return {"probe": "observability", "variants": verdicts, "blind_to": blind,
            "not_established": unclear, "deltas": results,
            "noise_floor": floor, "calibrated": floor is not None}


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
            results.append(probe_observability(config, tmp, out_dir))

    # Merge rather than overwrite. The preflight workflow runs each probe as a
    # SEPARATE process, so a plain write would erase the determinism record the
    # moment observability ran -- destroying both the audit trail and the very
    # noise floor the observability verdict depends on.
    written = out_dir / "probes.json"
    kept: List[Dict[str, Any]] = []
    if written.is_file():
        try:
            prior = json.loads(written.read_text(encoding="utf-8"))
            fresh = {r.get("probe") for r in results}
            kept = [r for r in prior.get("results", [])
                    if isinstance(r, dict) and r.get("probe") not in fresh]
        except (OSError, ValueError):
            kept = []
    payload = {
        "judge": config.identity(),
        "mode": config.mode,
        "meaningful": config.mode == REAL,
        "results": kept + results,
    }
    written.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {_display(written)}")

    # Exit non-zero when a probe FAILS. Until 2026-08-18 this returned 0
    # unconditionally: the scripts printed "FAIL" in the log while the workflow
    # step went green, and the run's overall status said success while three of
    # four probes had failed. A status that cannot go red is not a check.
    #
    # Under mock/surrogate the verdicts are artefacts of a closed-form backend
    # (determinism passes trivially, observability reports blindness to
    # everything), so they are reported and NOT treated as failures.
    failures = []
    if config.mode == REAL:
        for entry in results:
            if entry.get("probe") == "determinism" and not entry.get("identical"):
                failures.append(
                    f"determinism: deltas vary by up to "
                    f"{entry.get('max_spread', 0):.3f} on identical input "
                    f"(composite {entry.get('composite_spread', 0):.4f})")
            if entry.get("probe") == "observability":
                if not entry.get("calibrated"):
                    failures.append(
                        "observability: UNCALIBRATED — no determinism result, so "
                        "no shift can be told from the judge's own noise")
                elif entry.get("blind_to"):
                    failures.append(
                        f"observability: judge is blind to "
                        f"{', '.join(entry['blind_to'])}")
                elif entry.get("not_established"):
                    failures.append(
                        f"observability: NOT ESTABLISHED for "
                        f"{', '.join(entry['not_established'])} — shifts are the "
                        f"size of the judge's self-noise")
    if failures:
        print()
        print("PROBE FAILURES (this run is not green):")
        for line in failures:
            print(f"  - {line}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
