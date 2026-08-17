"""Rival school 4 of 4: middle-power internationalism.

The Ohira-Fukuda-Takeshita liberal-internationalist lineage, and the maximally
civilian reading of "proactive contribution to peace". Japan's power is
rule-making, convening and capital, not force. Where the United States has
vacated the rule-making seat, Japan takes it. The defence programme is held at
the 2022 settlement rather than extended, and the marginal effort goes instead
at Japan's worst measure: future resources, at 11.3 the largest headroom on
the board, where demography is the binding constraint.

M1 calibration seed. This one tests rule 3 of the rubric (diminishing returns):
it spends heavily on diplomatic influence, where Japan already sits at 85.4 and
almost nothing can be bought, and on future resources, where almost everything
can. A judge that rewards both equally has not applied the rule.

Run standalone for a quick look:  python seed_middle_power_internationalism.py
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

SCHOOL = "middle_power_internationalism"
SCHOOL_LABEL = "Middle-power internationalism"


# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """Rule-making over force; the demographic constraint attacked directly.

    20% of marginal effort goes to future resources — Japan's weakest measure
    at 11.3 — with nearly half of that on the one lever that actually moves
    it, immigration. A further 19% goes to economic relationships and rule-
    making. Defence is held at the 2022 settlement, 1.8% of GDP flat, neither
    extended nor reversed.
    """
    p = PolicyPortfolio(horizon=(2026, 2030))

    # --- economic capability (0.16) ---------------------------------------
    p.invest("economic_capability.size", share=0.04,
             how="productivity agenda: services reform, corporate governance, capital deepening")
    p.invest("economic_capability.international_leverage", share=0.03,
             how="yen swap network, ADB co-financing, development-finance agenda-setting")
    p.invest("economic_capability.technology", share=0.06,
             how="AI, quantum and green technology developed under open international standards")
    p.invest("economic_capability.connectivity", share=0.03,
             how="digital and physical connectivity supplied to the region as a public good")

    # --- military capability (0.10): held, not extended -------------------
    p.invest("military_capability.defence_spending", share=0.03,
             how="held flat at 1.8% of GDP; the 2022 settlement neither extended nor reversed")
    p.invest("military_capability.armed_forces", share=0.02,
             how="personnel quality and retention within the existing establishment")
    p.invest("military_capability.weapons_and_platforms", share=0.02,
             how="replacement and sustainment; no expansion of the procurement plan")
    p.invest("military_capability.signature_capabilities", share=0.01,
             how="counterstrike capped at the 2022 programme; no follow-on buy")
    p.invest("military_capability.asian_military_posture", share=0.02,
             how="Nansei posture completed as planned; HADR and maritime domain roles emphasised")

    # --- resilience (0.11) ------------------------------------------------
    p.invest("resilience.internal_stability", share=0.02,
             how="social cohesion investment paired with the immigration programme")
    p.invest("resilience.resource_security", share=0.03,
             how="renewables build-out and grid interconnection reduce import dependence")
    p.invest("resilience.geoeconomic_security", share=0.02,
             how="supply-chain resilience pursued plurilaterally rather than through unilateral controls")
    p.invest("resilience.geopolitical_security", share=0.02,
             how="territorial administration maintained; disputes routed to legal and diplomatic channels")
    p.invest("resilience.nuclear_deterrence", share=0.02,
             how="extended deterrence retained while leading the disarmament and NPT agenda")

    # --- future resources (0.20): the central bet -------------------------
    p.invest("future_resources.economic_resources_2035", share=0.05,
             how="GX investment, capital deepening and labour-market reform compounding to 2035")
    p.invest("future_resources.defence_resources_2035", share=0.01,
             how="defence-industrial base maintained at current scale; no expansion")
    p.invest("future_resources.broad_resources_2035", share=0.05,
             how="R&D intensity raised, universities internationalised, basic science funded")
    p.invest("future_resources.demographic_resources_2050", share=0.09,
             how="immigration reform: skilled pathway, family reunification, naturalisation route")

    # --- economic relationships (0.19) ------------------------------------
    p.invest("economic_relationships.regional_trade_relations", share=0.07,
             how="CPTPP enlargement driven from the chair; digital economy agreements concluded")
    p.invest("economic_relationships.regional_investment_ties", share=0.05,
             how="quality infrastructure and climate finance for ASEAN and the Pacific Islands")
    p.invest("economic_relationships.economic_diplomacy", share=0.07,
             how="WTO reform and standard-setting leadership as US participation becomes intermittent")

    # --- defence networks (0.07) ------------------------------------------
    p.invest("defence_networks.regional_alliance_network", share=0.03,
             how="alliance maintained and modernised without deepening operational integration")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.03,
             how="OSA reframed as capacity-building: HADR, maritime domain awareness, coast guards")
    p.invest("defence_networks.global_defence_partnerships", share=0.01,
             how="GCAP honoured as an industrial commitment; no wider coalition role sought")

    # --- diplomatic influence (0.09) --------------------------------------
    p.invest("diplomatic_influence.diplomatic_network", share=0.02,
             how="posts opened across the Pacific Islands and the Global South")
    p.invest("diplomatic_influence.multilateral_power", share=0.04,
             how="UNSC reform, G7 and G20 agenda-setting, AI and climate governance leadership")
    p.invest("diplomatic_influence.foreign_policy", share=0.03,
             how="human security and rules-based order replace FOIP's competitive framing")

    # --- cultural influence (0.08) ----------------------------------------
    p.invest("cultural_influence.cultural_projection", share=0.03,
             how="content export scaled with public co-financing and festival diplomacy")
    p.invest("cultural_influence.information_flows", share=0.02,
             how="Japanese-language media and open-data platforms extended across the region")
    p.invest("cultural_influence.people_exchanges", share=0.03,
             how="student, researcher and JET exchange volumes doubled against 2019")

    # Defence spending as % of GDP; read only by the feasibility bound.
    p.defence_spending_path({2026: 1.6, 2027: 1.8, 2028: 1.8, 2029: 1.8, 2030: 1.8})

    p.sequence([
        Phase(years=(2026, 2027), label="Legislate the demographic turn: skilled "
              "immigration pathway, family reunification, naturalisation reform.",
              focus=("future_resources.demographic_resources_2050",
                     "resilience.internal_stability")),
        Phase(years=(2028, 2029), label="Take the vacated rule-making seat: CPTPP "
              "enlargement, digital and AI governance, WTO reform.",
              focus=("economic_relationships.regional_trade_relations",
                     "economic_relationships.economic_diplomacy")),
        Phase(years=(2030, 2030), label="Compound it: R&D intensity, university "
              "internationalisation, climate finance for the region.",
              focus=("future_resources.broad_resources_2035",
                     "economic_relationships.regional_investment_ties")),
    ])

    p.custom_initiatives([
        Initiative(
            name="Immigration and Settlement Act",
            rationale="Convert the technical-intern and specified-skilled schemes "
                      "into a genuine settlement pathway with family reunification "
                      "and a naturalisation route, targeting a net inflow large "
                      "enough to change the 2050 working-age projection rather "
                      "than merely soften it.",
            targets=("future_resources.demographic_resources_2050",
                     "economic_capability.size",
                     "resilience.internal_stability"),
        ),
        Initiative(
            name="Indo-Pacific Rule-Making Facility",
            rationale="A standing secretariat and fund for regional standard-"
                      "setting in digital trade, AI governance and green finance, "
                      "designed to occupy the convening role the United States "
                      "vacates and to bind partners through rules rather than arms.",
            targets=("economic_relationships.economic_diplomacy",
                     "diplomatic_influence.multilateral_power",
                     "economic_capability.technology"),
        ),
    ])

    return p
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    import json

    portfolio = build_policy()
    print(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False))
    print(f"\n{SCHOOL_LABEL}: total share = {portfolio.total_share():.6f}")
