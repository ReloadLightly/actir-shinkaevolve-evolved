"""Rival school 2 of 4: accommodation (the East Asian Community lineage).

The Ozawa-Hatoyama strand, and the older Japanese realist argument that the
security dilemma is itself the threat. Interdependence and reassurance are
cheaper than deterrence; the American alliance is as much a war risk as a
shield, because it makes Japan a party to a conflict it has no interest in.
The December 2022 programme is treated as a mistake and partly reversed.

M1 calibration seed. This one is the sharpest test of rule 5 of the rubric
("the scenario is the world"): it should read very differently under S2, where
a Taiwan contingency arrives anyway, and under S3, where the ally leaves.

Run standalone for a quick look:  python seed_accommodation.py
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

SCHOOL = "accommodation"
SCHOOL_LABEL = "Accommodation"


# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """Interdependence over deterrence; the 2022 programme partly reversed.

    26% of marginal effort goes to economic relationships and only 9% to
    military capability. Defence spending falls back to 1.0% of GDP by 2029 —
    below the pre-2022 level — and the counterstrike programme is cancelled as
    an explicit reassurance signal. Nuclear deterrence receives nothing.
    """
    p = PolicyPortfolio(horizon=(2026, 2030))

    # --- economic capability (0.16): the economy is the instrument --------
    p.invest("economic_capability.size", share=0.05,
             how="domestic demand and wage growth funded by the defence rollback")
    p.invest("economic_capability.international_leverage", share=0.02,
             how="yen swap lines widened with Asian central banks under CMIM")
    p.invest("economic_capability.technology", share=0.05,
             how="civilian-led technology; no export-control escalation against China")
    p.invest("economic_capability.connectivity", share=0.04,
             how="rail, port, air and visa links with China and the ROK restored")

    # --- military capability (0.09): a managed rollback -------------------
    p.invest("military_capability.defence_spending", share=0.03,
             how="the 2% target abandoned; spending falls to 1.0% of GDP by 2029")
    p.invest("military_capability.armed_forces", share=0.02,
             how="personnel sustained at current strength; no expansion")
    p.invest("military_capability.weapons_and_platforms", share=0.02,
             how="like-for-like replacement only; the 43-trillion-yen plan is cut back")
    p.invest("military_capability.signature_capabilities", share=0.01,
             how="counterstrike programme cancelled and announced as a reassurance step")
    p.invest("military_capability.asian_military_posture", share=0.01,
             how="Nansei garrison buildup halted; no new missile deployments")

    # --- resilience (0.14): stability through reassurance -----------------
    p.invest("resilience.internal_stability", share=0.02,
             how="social spending restored from the defence budget; cohesion argument made publicly")
    p.invest("resilience.resource_security", share=0.04,
             how="energy diversified across Gulf, Russian and Australian LNG; reactors restarted")
    p.invest("resilience.geoeconomic_security", share=0.02,
             how="supply chains left integrated; screening and decoupling measures rolled back")
    p.invest("resilience.geopolitical_security", share=0.06,
             how="Senkaku crisis management, military hotlines, joint resource development talks")
    p.invest("resilience.nuclear_deterrence", share=0.00,
             how="no marginal effort: extended deterrence de-emphasised, TPNW observer status taken")

    # --- future resources (0.11) ------------------------------------------
    p.invest("future_resources.economic_resources_2035", share=0.03,
             how="peace dividend redirected to productivity and capital deepening")
    p.invest("future_resources.defence_resources_2035", share=0.01,
             how="defence-industrial expansion halted; export liberalisation reversed")
    p.invest("future_resources.broad_resources_2035", share=0.03,
             how="civilian R&D, joint research programmes with Chinese and Korean institutions")
    p.invest("future_resources.demographic_resources_2050", share=0.04,
             how="regional labour mobility agreement with China, the ROK and ASEAN")

    # --- economic relationships (0.26): the core of the doctrine ----------
    p.invest("economic_relationships.regional_trade_relations", share=0.10,
             how="China-Japan-Korea FTA concluded; RCEP deepened; CPTPP kept but not weaponised")
    p.invest("economic_relationships.regional_investment_ties", share=0.08,
             how="Chinese inbound investment reopened; co-financing with BRI institutions")
    p.invest("economic_relationships.economic_diplomacy", share=0.08,
             how="East Asian Community institution-building as the organising project")

    # --- defence networks (0.04): treaty minimum --------------------------
    p.invest("defence_networks.regional_alliance_network", share=0.02,
             how="treaty maintained at minimum; host-nation support and base footprint reduced")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.01,
             how="OSA wound down; confidence-building with the PLA replaces capacity-building")
    p.invest("defence_networks.global_defence_partnerships", share=0.01,
             how="NATO IP4 participation ended; GCAP reviewed as provocative")

    # --- diplomatic influence (0.11) --------------------------------------
    p.invest("diplomatic_influence.diplomatic_network", share=0.03,
             how="posts expanded across East and Southeast Asia; China desk enlarged")
    p.invest("diplomatic_influence.multilateral_power", share=0.04,
             how="ASEAN+3 and the China-Japan-Korea trilateral revived at leaders' level")
    p.invest("diplomatic_influence.foreign_policy", share=0.04,
             how="FOIP retired as the organising frame; East Asian Community replaces it")

    # --- cultural influence (0.09) ----------------------------------------
    p.invest("cultural_influence.cultural_projection", share=0.03,
             how="content export and co-production with Chinese and Korean studios")
    p.invest("cultural_influence.information_flows", share=0.02,
             how="history-dialogue and joint textbook projects with Beijing and Seoul")
    p.invest("cultural_influence.people_exchanges", share=0.04,
             how="student and tourist flows with China and the ROK restored above 2019 levels")

    # Defence spending as % of GDP; read only by the feasibility bound.
    p.defence_spending_path({2026: 1.4, 2027: 1.2, 2028: 1.1, 2029: 1.0, 2030: 1.0})

    p.sequence([
        Phase(years=(2026, 2027), label="Signal reversal: cancel counterstrike, "
              "cut the procurement plan, open leader-level talks with Beijing.",
              focus=("military_capability.signature_capabilities",
                     "resilience.geopolitical_security")),
        Phase(years=(2028, 2029), label="Bank the interdependence: conclude the "
              "CJK FTA, reopen investment, restore exchange volumes.",
              focus=("economic_relationships.regional_trade_relations",
                     "economic_relationships.regional_investment_ties")),
        Phase(years=(2030, 2030), label="Institutionalise: East Asian Community "
              "machinery and a standing crisis-management regime.",
              focus=("economic_relationships.economic_diplomacy",
                     "diplomatic_influence.multilateral_power")),
    ])

    p.custom_initiatives([
        Initiative(
            name="East China Sea Modus Vivendi",
            rationale="A standing crisis-management regime around the Senkakus: "
                      "military and coast guard hotlines, incident protocols, and "
                      "resumed talks on joint development, with sovereignty claims "
                      "explicitly shelved rather than settled.",
            targets=("resilience.geopolitical_security",
                     "diplomatic_influence.foreign_policy"),
        ),
        Initiative(
            name="Northeast Asian Labour Mobility Compact",
            rationale="A reciprocal skilled-worker and student mobility agreement "
                      "with China, the ROK and ASEAN, attacking the demographic "
                      "constraint through regional integration rather than through "
                      "domestic immigration reform alone.",
            targets=("future_resources.demographic_resources_2050",
                     "cultural_influence.people_exchanges",
                     "economic_capability.size"),
        ),
    ])

    return p
# EVOLVE-BLOCK-END


if __name__ == "__main__":
    import json

    portfolio = build_policy()
    print(json.dumps(portfolio.to_dict(), indent=2, ensure_ascii=False))
    print(f"\n{SCHOOL_LABEL}: total share = {portfolio.total_share():.6f}")
