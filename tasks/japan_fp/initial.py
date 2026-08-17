"""Seed program: Japan's actual December 2022 posture (the anpo sanbunsho).

RESEARCH_DESIGN section 2.1 and rule 4 of section 1: seed with the real status
quo, not with randomness. This program's EVOLVE-BLOCK is what ShinkaEvolve
mutates. Everything outside the block is immutable harness.

Run standalone for a quick look:  python initial.py
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


_schema = _load_schema_module()
PolicyPortfolio = _schema.PolicyPortfolio
Initiative = _schema.Initiative
Phase = _schema.Phase
# --- end immutable harness -----------------------------------------------


# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """Japan's marginal strategic effort, 2026-2030, as decided in Dec 2022.

    The dials are the Lowy Asia Power Index's own 30 submeasures. `share` is
    the fraction of Japan's marginal strategic effort (shares sum to 1.0);
    `how` is capped free text saying what the effort actually buys.

    This seed encodes the three security documents of 16 December 2022:
    counterstrike capability, 2% of GDP by 2027, the 43-trillion-yen
    procurement plan, economic security legislation, energy security after
    Ukraine, FOIP diplomacy, and alliance/partnership deepening.
    """
    p = PolicyPortfolio(horizon=(2026, 2030))

    # --- economic capability (0.13) -------------------------------------
    p.invest("economic_capability.size", share=0.03,
             how="new capitalism growth package; wage-investment cycle")
    p.invest("economic_capability.international_leverage", share=0.02,
             how="yen internationalisation is not pursued; leverage held flat")
    p.invest("economic_capability.technology", share=0.06,
             how="semiconductor rebuild: Rapidus, TSMC Kumamoto, chip subsidies")
    p.invest("economic_capability.connectivity", share=0.02,
             how="maintain port/air hubs and undersea cable landings")

    # --- military capability (0.29) --------------------------------------
    p.invest("military_capability.defence_spending", share=0.09,
             how="2% of GDP by 2027 per the 2022 National Security Strategy")
    p.invest("military_capability.armed_forces", share=0.04,
             how="permanent joint headquarters; recruitment and retention fixes")
    p.invest("military_capability.weapons_and_platforms", share=0.05,
             how="43 trillion yen procurement: munitions stocks, sustainment")
    p.invest("military_capability.signature_capabilities", share=0.08,
             how="stand-off/counterstrike buildout per the 2022 NDS")
    p.invest("military_capability.asian_military_posture", share=0.03,
             how="southwest islands hardening; Nansei garrisons and dispersal")

    # --- resilience (0.14) ------------------------------------------------
    p.invest("resilience.internal_stability", share=0.01,
             how="status quo; no dedicated marginal effort")
    p.invest("resilience.resource_security", share=0.04,
             how="post-Ukraine energy security: LNG contracts, reactor restarts")
    p.invest("resilience.geoeconomic_security", share=0.05,
             how="Economic Security Promotion Act: supply chains, export controls")
    p.invest("resilience.geopolitical_security", share=0.02,
             how="territorial administration of the Senkakus; coast guard budget")
    p.invest("resilience.nuclear_deterrence", share=0.02,
             how="extended deterrence dialogue with Washington; no indigenous path")

    # --- future resources (0.06) ------------------------------------------
    p.invest("future_resources.economic_resources_2035", share=0.02,
             how="GX transition bonds; productivity agenda")
    p.invest("future_resources.defence_resources_2035", share=0.02,
             how="defence-industrial base law; export rule loosening")
    p.invest("future_resources.broad_resources_2035", share=0.01,
             how="incremental R&D budget growth")
    p.invest("future_resources.demographic_resources_2050", share=0.01,
             how="modest childcare expansion; migration policy untouched")

    # --- economic relationships (0.13) ------------------------------------
    p.invest("economic_relationships.regional_trade_relations", share=0.05,
             how="hold CPTPP/RCEP centrality; join IPEF pillars")
    p.invest("economic_relationships.regional_investment_ties", share=0.02,
             how="continue ASEAN and India infrastructure finance via JBIC/JICA")
    p.invest("economic_relationships.economic_diplomacy", share=0.06,
             how="CPTPP expansion diplomacy")

    # --- defence networks (0.15) -------------------------------------------
    p.invest("defence_networks.regional_alliance_network", share=0.05,
             how="US alliance modernisation: command and control, co-production")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.07,
             how="expand OSA beyond PH/VN; deepen Japan-ROK-US trilateral")
    p.invest("defence_networks.global_defence_partnerships", share=0.03,
             how="GCAP with UK and Italy; NATO IP4 participation")

    # --- diplomatic influence (0.06) ----------------------------------------
    p.invest("diplomatic_influence.diplomatic_network", share=0.01,
             how="hold the existing embassy and consulate footprint")
    p.invest("diplomatic_influence.multilateral_power", share=0.02,
             how="G7 presidency agenda; UNSC reform advocacy")
    p.invest("diplomatic_influence.foreign_policy", share=0.03,
             how="Free and Open Indo-Pacific as the organising frame")

    # --- cultural influence (0.04) -------------------------------------------
    p.invest("cultural_influence.cultural_projection", share=0.02,
             how="Cool Japan content export; inbound tourism recovery")
    p.invest("cultural_influence.information_flows", share=0.01,
             how="modest strategic communications budget")
    p.invest("cultural_influence.people_exchanges", share=0.01,
             how="restore pre-pandemic student and JET exchange volumes")

    # Defence spending as % of GDP; read only by the feasibility bound.
    p.defence_spending_path({2026: 1.6, 2027: 2.0, 2028: 2.0, 2029: 2.0, 2030: 2.0})

    p.sequence([
        Phase(years=(2026, 2027), label="Complete the 2022 build-out: reach 2% of "
              "GDP, field first counterstrike batteries, stand up joint command.",
              focus=("military_capability.defence_spending",
                     "military_capability.signature_capabilities")),
        Phase(years=(2028, 2029), label="Consolidate: sustainment stocks, "
              "co-production with the US, OSA recipients beyond PH/VN.",
              focus=("military_capability.weapons_and_platforms",
                     "defence_networks.regional_defence_diplomacy")),
        Phase(years=(2030, 2030), label="Hold the line: sustain spending, keep "
              "CPTPP and FOIP diplomacy running.",
              focus=("economic_relationships.economic_diplomacy",
                     "diplomatic_influence.foreign_policy")),
    ])

    p.custom_initiatives([
        Initiative(
            name="Official Security Assistance",
            rationale="Grant-based security assistance to like-minded regional "
                      "states, created 2023 as the civilian-aid mirror of ODA.",
            targets=("defence_networks.regional_defence_diplomacy",
                     "diplomatic_influence.foreign_policy"),
        ),
    ])

    return p
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    import json

    portfolio = build_policy()
    print(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False))
    print(f"\ntotal share = {portfolio.total_share():.6f}")
