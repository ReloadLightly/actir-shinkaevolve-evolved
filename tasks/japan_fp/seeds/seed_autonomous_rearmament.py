"""Rival school 1 of 4: autonomous rearmament (jishu boei).

The Nakasone lineage, revived after 2022 by the security right: the American
guarantee is a wasting asset, so Japan should buy sovereign capability while
the alliance still covers the transition. The alliance is maintained but
deliberately not deepened, because every deepening is another dependency.

M1 calibration seed. Not an evolved individual and not evolved from; it exists
so the judge's *ordering* of four rival doctrines can be inspected before the
rubric is frozen (KICKOFF Stage B).

Run standalone for a quick look:  python seed_autonomous_rearmament.py
"""

# --- immutable harness: locate and load the task schema ------------------
# Seed programs are loaded by absolute file path, exactly like an evolved
# individual, so the schema is resolved the same way initial.py resolves it.
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

SCHOOL = "autonomous_rearmament"
SCHOOL_LABEL = "Autonomous rearmament"


# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    """Sovereign capability first; the alliance is hedged, not deepened.

    44% of marginal effort goes to military capability and a further 13% to
    the 2035 defence-industrial base. Defence spending climbs to 3.5% of GDP
    by 2030 — the top of the feasibility bound. Defence networks get 4%: the
    treaty is kept, but co-production, OSA and minilateral latticework are
    read as dependencies rather than assets.
    """
    p = PolicyPortfolio(horizon=(2026, 2030))

    # --- economic capability (0.11): the economy serves the buildout ------
    p.invest("economic_capability.size", share=0.02,
             how="defence procurement as industrial demand; no separate growth agenda")
    p.invest("economic_capability.international_leverage", share=0.01,
             how="no yen internationalisation push; leverage is not the instrument")
    p.invest("economic_capability.technology", share=0.07,
             how="sovereign dual-use base: sensors, propulsion, space launch, ASW, EW")
    p.invest("economic_capability.connectivity", share=0.01,
             how="hardened cable landings and dispersal airfields, not commercial hubs")

    # --- military capability (0.44): the whole point ----------------------
    p.invest("military_capability.defence_spending", share=0.11,
             how="3.5% of GDP by 2030; the 2027 2% target treated as a floor, not a ceiling")
    p.invest("military_capability.armed_forces", share=0.07,
             how="pay and retention overhaul, reserve expansion, uncrewed systems to offset recruits")
    p.invest("military_capability.weapons_and_platforms", share=0.10,
             how="indigenous build: GCAP, submarines, Type-12 evolution, deep munitions stocks")
    p.invest("military_capability.signature_capabilities", share=0.11,
             how="long-range strike mass, hypersonics, sovereign ISR constellation, counter-A2AD")
    p.invest("military_capability.asian_military_posture", share=0.05,
             how="Nansei hardening: shelters, dispersal, prepositioned stocks, resilient logistics")

    # --- resilience (0.19): autarky logic ---------------------------------
    p.invest("resilience.internal_stability", share=0.01,
             how="constitutional revision debate carried; no dedicated social programme")
    p.invest("resilience.resource_security", share=0.05,
             how="wartime stockpiles, reactor restarts, strategic reserves sized for blockade")
    p.invest("resilience.geoeconomic_security", share=0.04,
             how="sovereign supply chains for defence inputs; export controls tightened")
    p.invest("resilience.geopolitical_security", share=0.03,
             how="Senkaku administration hardened; coast guard-JSDF command integration")
    p.invest("resilience.nuclear_deterrence", share=0.06,
             how="latency preserved: reprocessing, naval propulsion R&D, nuclear-sharing debate opened")

    # --- future resources (0.13): the industrial base ---------------------
    p.invest("future_resources.economic_resources_2035", share=0.02,
             how="defence-led R&D spillover; no broad growth strategy")
    p.invest("future_resources.defence_resources_2035", share=0.08,
             how="defence-industrial base law, prime consolidation, export rules fully liberalised")
    p.invest("future_resources.broad_resources_2035", share=0.02,
             how="applied research directed to defence-relevant fields")
    p.invest("future_resources.demographic_resources_2050", share=0.01,
             how="automation rather than migration; the demographic hole is accepted")

    # --- economic relationships (0.05): a cost, not an asset --------------
    p.invest("economic_relationships.regional_trade_relations", share=0.02,
             how="CPTPP maintained; trade is not used as a strategic instrument")
    p.invest("economic_relationships.regional_investment_ties", share=0.01,
             how="existing JBIC/JICA commitments honoured, not expanded")
    p.invest("economic_relationships.economic_diplomacy", share=0.02,
             how="economic diplomacy subordinated to procurement and technology access")

    # --- defence networks (0.04): deliberately shallow --------------------
    p.invest("defence_networks.regional_alliance_network", share=0.02,
             how="treaty kept, interoperability held flat; further integration read as dependency")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.01,
             how="OSA held at current recipients; capacity-building is not the priority")
    p.invest("defence_networks.global_defence_partnerships", share=0.01,
             how="GCAP continued strictly as technology sovereignty, not as coalition-building")

    # --- diplomatic influence (0.02) --------------------------------------
    p.invest("diplomatic_influence.diplomatic_network", share=0.01,
             how="existing footprint held; posts reweighted toward defence attaches")
    p.invest("diplomatic_influence.multilateral_power", share=0.00,
             how="no marginal effort: multilateral fora are judged to constrain rearmament")
    p.invest("diplomatic_influence.foreign_policy", share=0.01,
             how="FOIP retained rhetorically; the operative frame is self-reliant deterrence")

    # --- cultural influence (0.02) ----------------------------------------
    p.invest("cultural_influence.cultural_projection", share=0.01,
             how="existing content export sustained without new budget")
    p.invest("cultural_influence.information_flows", share=0.01,
             how="strategic communications retooled to explain rearmament domestically")
    p.invest("cultural_influence.people_exchanges", share=0.00,
             how="no marginal effort; exchange programmes run at current volumes")

    # Defence spending as % of GDP; read only by the feasibility bound.
    p.defence_spending_path({2026: 2.0, 2027: 2.4, 2028: 2.8, 2029: 3.2, 2030: 3.5})

    p.sequence([
        Phase(years=(2026, 2027), label="Break the 2% ceiling: fiscal settlement "
              "for 3%+, defence-industrial base law, export rules liberalised.",
              focus=("military_capability.defence_spending",
                     "future_resources.defence_resources_2035")),
        Phase(years=(2028, 2029), label="Field sovereign strike mass and the ISR "
              "constellation; harden the Nansei chain against blockade.",
              focus=("military_capability.signature_capabilities",
                     "military_capability.asian_military_posture")),
        Phase(years=(2030, 2030), label="Reach 3.5% of GDP with stocks and "
              "sustainment sized to fight without resupply.",
              focus=("military_capability.weapons_and_platforms",
                     "resilience.resource_security")),
    ])

    p.custom_initiatives([
        Initiative(
            name="Strategic Latency Programme",
            rationale="Preserve and shorten the technical path to an independent "
                      "deterrent without crossing the NPT threshold: reprocessing "
                      "capacity, naval propulsion research, and an opened domestic "
                      "debate on nuclear sharing.",
            targets=("resilience.nuclear_deterrence",
                     "military_capability.signature_capabilities"),
        ),
        Initiative(
            name="Defence Industrial Sovereignty Act",
            rationale="Consolidate the primes, guarantee order books across the "
                      "horizon, and remove the remaining export restrictions so the "
                      "base can amortise capacity abroad.",
            targets=("future_resources.defence_resources_2035",
                     "military_capability.weapons_and_platforms",
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
