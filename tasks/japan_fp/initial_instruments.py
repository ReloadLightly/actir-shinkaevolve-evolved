"""Seed program (instrument layer): Japan's December 2022 decisions.

The same anpo sanbunsho posture as `initial.py`, expressed as the DECISIONS
that produced it rather than as the outcome allocation they produced.

A review of 2026-08-18 identified the outcome-as-action-space error as one of
two foundational problems:

    "economic size", "demographic resources 2050" and "cultural influence"
    are not actions Japan can select.

The precise version is that the instruments were never absent from `initial.py`
-- it says "Rapidus, TSMC Kumamoto", "43 trillion yen procurement", "2% of GDP
by 2027". They were in the wrong LAYER: unstructured `how` strings the gate only
length-checked, while the searched object was an allocation over outcomes.

So here the EVOLVE-BLOCK chooses **instrument intensities**, and the Lowy
allocation, the `how` prose and the defence-spending path are all DERIVED from
them by `instruments.to_portfolio`. Three consequences:

* the search moves things Japan can actually decide;
* feasibility is checkable -- an allocation over outcomes has no price, but
  instruments have a fiscal and a political one, and `coherence_report` tests
  a portfolio against envelopes calibrated so that the real December 2022
  decision comes out feasible-but-stretched;
* prose cannot drift from allocation, because it is generated from it.

Everything outside the EVOLVE-BLOCK is immutable harness.

Run standalone for a quick look:  python initial_instruments.py
"""

# --- immutable harness: locate and load the task schema ------------------
# initial.py is copied into per-generation folders, so the schema is resolved
# by absolute file path rather than by a relative import.
import importlib.util as _importlib_util
import os as _os
import sys as _sys


def _load_schema_module():
    candidates = []
    env_dir = _os.environ.get("JAPAN_FP_TASK_DIR")
    if env_dir:
        candidates.append(_os.path.abspath(env_dir))
    here = _os.path.dirname(_os.path.abspath(__file__))
    candidates.append(here)
    walk = here
    for _ in range(6):
        walk = _os.path.dirname(walk)
        if not walk:
            break
        candidates.append(_os.path.join(walk, "tasks", "japan_fp"))
    for path in _sys.path:
        if path:
            candidates.append(_os.path.join(path, "tasks", "japan_fp"))

    for candidate in candidates:
        schema_path = _os.path.join(candidate, "schema.py")
        if _os.path.isfile(schema_path):
            if candidate not in _sys.path:
                _sys.path.insert(0, candidate)
            if "schema" in _sys.modules:
                return _sys.modules["schema"]
            spec = _importlib_util.spec_from_file_location("schema", schema_path)
            if spec is None or spec.loader is None:
                continue
            module = _importlib_util.module_from_spec(spec)
            _sys.modules["schema"] = module
            spec.loader.exec_module(module)
            return module
    raise ImportError(
        "could not locate tasks/japan_fp/schema.py; set JAPAN_FP_TASK_DIR"
    )


def _load_instruments_module():
    """Same search as the schema loader, for the instrument catalogue."""
    for path in _sys.path:
        candidate = _os.path.join(path, "instruments.py")
        if _os.path.isfile(candidate):
            if "instruments" in _sys.modules:
                return _sys.modules["instruments"]
            spec = _importlib_util.spec_from_file_location("instruments", candidate)
            if spec is not None and spec.loader is not None:
                module = _importlib_util.module_from_spec(spec)
                _sys.modules["instruments"] = module
                spec.loader.exec_module(module)
                return module
    raise ImportError("could not locate tasks/japan_fp/instruments.py")


_schema = _load_schema_module()
PolicyPortfolio = _schema.PolicyPortfolio
Initiative = _schema.Initiative
Phase = _schema.Phase
_instruments = _load_instruments_module()
# --- end immutable harness -----------------------------------------------

# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """Japan's December 2022 posture, as the decisions that produced it.

    Each number is an INTENSITY in [0, 1]: how hard Japan pushes that
    instrument over 2026-2030, where 1.0 is the most any government could
    plausibly push it. These are the things a cabinet decides.

    Two scarce budgets bind, and both are checked before scoring:
      * fiscal, in % of GDP per year of NEW commitments (envelope 2.20);
      * political capital, with legal difficulty added (envelope 3.00).
    December 2022 spends 1.98 and 2.60 of those. It is near the limit of what
    a Japanese government has ever carried, which is why raising anything here
    means lowering something else.

    Run `python -c "import instruments, json;
    print(json.dumps(instruments.describe_catalogue(), indent=2))"` for what
    each instrument is, what it costs, what law it needs, how long it takes,
    and which Lowy measures it is pointed at.
    """
    intensities = {
        # --- the 2022 security reversal ---------------------------------
        "defence_budget": 0.70,          # 2% of GDP by FY2027 per the NSS
        "counterstrike": 0.80,           # the headline decision
        "host_nation_support": 0.50,     # basing, dispersal, munitions
        "minilateral_formats": 0.60,     # Quad, JAROKUS, RAAs
        "defence_exports": 0.35,         # begun, not completed
        "space_isr": 0.25,
        "cyber_active_defence": 0.20,    # legislated later and slowly

        # --- economic security ------------------------------------------
        "economic_security_regime": 0.55,
        "semiconductor_policy": 0.60,    # Rapidus, TSMC Kumamoto
        "critical_minerals": 0.30,
        "energy_diversification": 0.40,  # GX plan, nuclear restart

        # --- the non-military instruments -------------------------------
        "oda_infrastructure": 0.40,
        "official_security_assistance": 0.30,
        "trade_architecture": 0.45,      # CPTPP stewardship
        "cultural_diplomacy": 0.25,
        "unsc_reform": 0.10,
        "china_engagement": 0.30,        # de-risking, not decoupling

        # --- the demographic question, conspicuously unanswered ----------
        "female_labour_participation": 0.25,
        "immigration_liberalisation": 0.15,   # Japan's weakest measure is 11.3

        # --- what December 2022 declined to do ---------------------------
        "collective_self_defence": 0.0,  # no Article 9 amendment attempted
        "nuclear_latency_posture": 0.0,  # the hedge left implicit
    }

    return _instruments.to_portfolio(intensities, horizon=(2026, 2030))
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    import json

    portfolio = build_policy()
    print(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False)[:1200])
