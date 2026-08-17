"""Rival school 3 of 4: status-quo-plus (the mainstream consensus).

The Kishida-Ishiba line carried forward without new doctrine: December 2022
was correct, so execute it fully and extend at the margin. 2% is reached on
schedule and drifts to 2.2%; the alliance is deepened through command and
control and co-production; OSA widens; economic security legislation enters a
second phase. Nothing here is contested outside the usual budget fights.

M1 calibration seed, and the most diagnostic of the four: it is deliberately
close to the December 2022 seed. If the judge separates them by more than
about a point, the rubric's anchors are miscalibrated and the +/-0.5 "marginal"
anchor is not being applied.

Run standalone for a quick look:  python seed_status_quo_plus.py
"""

# --- immutable harness: locate and load the task schema ------------------
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
        candidates.append(walk)
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


_schema = _load_schema_module()
PolicyPortfolio = _schema.PolicyPortfolio
Initiative = _schema.Initiative
Phase = _schema.Phase
# --- end immutable harness -----------------------------------------------

SCHOOL = "status_quo_plus"
SCHOOL_LABEL = "Status-quo-plus"


# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """The 2022 programme executed fully, extended at the margin.

    The shape of the December 2022 seed, moved deliberately but only slightly.
    Military capability's share of *marginal* effort falls from 29% to 26% —
    not a retreat, but the consequence of having won the fiscal argument in
    2027: holding 2% and drifting to 2.2% costs less marginal effort than
    reaching it did. The three points released go to technology, future
    resources, diplomacy and culture, and defence networks are reweighted from
    breadth toward alliance C2 and a wider OSA.
    """
    p = PolicyPortfolio(horizon=(2026, 2030))

    # --- economic capability (0.14) ---------------------------------------
    p.invest("economic_capability.size", share=0.03,
             how="continuation of the wage-investment cycle; no new growth doctrine")
    p.invest("economic_capability.international_leverage", share=0.02,
             how="yen stability management; leverage neither pursued nor conceded")
    p.invest("economic_capability.technology", share=0.07,
             how="Rapidus to volume production; AI compute build; chip materials retained")
    p.invest("economic_capability.connectivity", share=0.02,
             how="port, air and cable infrastructure maintained and incrementally hardened")

    # --- military capability (0.26) ---------------------------------------
    p.invest("military_capability.defence_spending", share=0.07,
             how="2% of GDP in 2027 as legislated, drifting to 2.2% by 2030")
    p.invest("military_capability.armed_forces", share=0.04,
             how="permanent joint headquarters embedded; recruitment and retention reforms")
    p.invest("military_capability.weapons_and_platforms", share=0.05,
             how="43-trillion-yen plan delivered: munitions depth, sustainment, co-production")
    p.invest("military_capability.signature_capabilities", share=0.07,
             how="counterstrike fielded and sustained at the scale the 2022 NDS set out")
    p.invest("military_capability.asian_military_posture", share=0.03,
             how="Nansei garrisons completed; dispersal and resilience work continued")

    # --- resilience (0.13) ------------------------------------------------
    p.invest("resilience.internal_stability", share=0.01,
             how="status quo; no dedicated marginal effort")
    p.invest("resilience.resource_security", share=0.03,
             how="LNG contract portfolio maintained; reactor restarts continued")
    p.invest("resilience.geoeconomic_security", share=0.05,
             how="Economic Security Promotion Act phase two: screening, data, critical goods")
    p.invest("resilience.geopolitical_security", share=0.02,
             how="Senkaku administration and coast guard capacity on the existing trajectory")
    p.invest("resilience.nuclear_deterrence", share=0.02,
             how="extended deterrence dialogue institutionalised; no indigenous path")

    # --- future resources (0.08) ------------------------------------------
    p.invest("future_resources.economic_resources_2035", share=0.03,
             how="GX transition bonds and the productivity agenda as legislated")
    p.invest("future_resources.defence_resources_2035", share=0.02,
             how="defence-industrial base law implemented; export rules as loosened in 2023")
    p.invest("future_resources.broad_resources_2035", share=0.02,
             how="incremental R&D budget growth on the existing trend")
    p.invest("future_resources.demographic_resources_2050", share=0.01,
             how="childcare expansion continued; migration policy left substantially unchanged")

    # --- economic relationships (0.13) ------------------------------------
    p.invest("economic_relationships.regional_trade_relations", share=0.05,
             how="CPTPP and RCEP centrality held; IPEF pillars worked where they function")
    p.invest("economic_relationships.regional_investment_ties", share=0.03,
             how="ASEAN and India infrastructure finance through JBIC and JICA continued")
    p.invest("economic_relationships.economic_diplomacy", share=0.05,
             how="CPTPP accession management and digital trade rule-making")

    # --- defence networks (0.14): the main increment ----------------------
    p.invest("defence_networks.regional_alliance_network", share=0.05,
             how="alliance C2 modernisation, co-production lines, joint HQ interface with USFJ")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.06,
             how="OSA widened to eight to ten recipients; JP-ROK-US and JP-AUS-US institutionalised")
    p.invest("defence_networks.global_defence_partnerships", share=0.03,
             how="GCAP with the UK and Italy; NATO IP4; the RAA network extended")

    # --- diplomatic influence (0.07) --------------------------------------
    p.invest("diplomatic_influence.diplomatic_network", share=0.02,
             how="embassy and consulate footprint maintained with modest Pacific additions")
    p.invest("diplomatic_influence.multilateral_power", share=0.02,
             how="G7 agenda-setting continued; UNSC reform advocacy sustained")
    p.invest("diplomatic_influence.foreign_policy", share=0.03,
             how="Free and Open Indo-Pacific retained as the organising frame")

    # --- cultural influence (0.05) ----------------------------------------
    p.invest("cultural_influence.cultural_projection", share=0.02,
             how="content export and inbound tourism on the recovery trajectory")
    p.invest("cultural_influence.information_flows", share=0.01,
             how="strategic communications budget grown incrementally")
    p.invest("cultural_influence.people_exchanges", share=0.02,
             how="student and JET exchange volumes restored and modestly expanded")

    # Defence spending as % of GDP; read only by the feasibility bound.
    p.defence_spending_path({2026: 1.8, 2027: 2.0, 2028: 2.1, 2029: 2.15, 2030: 2.2})

    p.sequence([
        Phase(years=(2026, 2027), label="Deliver 2022 on schedule: 2% of GDP, "
              "counterstrike fielded, joint headquarters operating.",
              focus=("military_capability.defence_spending",
                     "military_capability.signature_capabilities")),
        Phase(years=(2028, 2029), label="Widen the lattice: OSA recipients, "
              "trilaterals, co-production, economic security phase two.",
              focus=("defence_networks.regional_defence_diplomacy",
                     "resilience.geoeconomic_security")),
        Phase(years=(2030, 2030), label="Consolidate at 2.2% and hold CPTPP and "
              "FOIP diplomacy on their existing trajectories.",
              focus=("economic_relationships.economic_diplomacy",
                     "defence_networks.regional_alliance_network")),
    ])

    p.custom_initiatives([
        Initiative(
            name="Official Security Assistance expansion",
            rationale="Grant-based security assistance widened from the initial "
                      "recipients to eight to ten regional states, with maritime "
                      "domain awareness packages as the standard offering.",
            targets=("defence_networks.regional_defence_diplomacy",
                     "diplomatic_influence.foreign_policy"),
        ),
        Initiative(
            name="Alliance co-production framework",
            rationale="Standing US-Japan lines for munitions and sustainment, "
                      "converting the alliance from a guarantee into shared "
                      "industrial capacity that survives a change of administration.",
            targets=("defence_networks.regional_alliance_network",
                     "military_capability.weapons_and_platforms",
                     "future_resources.defence_resources_2035"),
        ),
    ])

    return p
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    import json

    portfolio = build_policy()
    print(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False))
    print(f"\n{SCHOOL_LABEL}: total share = {portfolio.total_share():.6f}")
