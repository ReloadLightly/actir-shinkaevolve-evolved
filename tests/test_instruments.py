"""Policy instruments: the layer the search should have been running over.

A review of 2026-08-18 named this one of two foundational errors — Lowy's
outcome categories were being used as the action space, when "economic size"
and "demographic resources 2050" are not things Japan can choose.

The precise version is that the instruments were never absent, they were in the
wrong LAYER: the December 2022 seed says "Rapidus, TSMC Kumamoto", "43 trillion
yen procurement", "2% of GDP by 2027" — real instruments, living in free-text
`how` strings the gate only length-checks, while the structured searched object
was an allocation over outcomes.

These tests pin three properties that only become available once instruments
are the searched layer:

  * feasibility is checkable at all (an allocation over outcomes has no price);
  * the historical December 2022 decision comes out feasible, because it
    happened, and stretched, because it nearly broke the government that did it;
  * prose cannot drift from allocation, because it is derived from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

import evaluate as evaluator  # noqa: E402
import instruments as ins  # noqa: E402
from descriptors import effort_by_measure  # noqa: E402
from lowy import MEASURES, SUBMEASURES  # noqa: E402


#: The December 2022 documents encoded as instrument intensities: the
#: counterstrike reversal, the 2%-of-GDP path, the economic security act, the
#: export-rule relaxation. Immigration is conspicuously small and
#: constitutional revision and nuclear latency are zero, because that is what
#: actually happened.
DEC_2022 = {
    "defence_budget": 0.70, "counterstrike": 0.80, "host_nation_support": 0.50,
    "minilateral_formats": 0.60, "defence_exports": 0.35,
    "economic_security_regime": 0.55, "semiconductor_policy": 0.60,
    "energy_diversification": 0.40, "oda_infrastructure": 0.40,
    "official_security_assistance": 0.30, "trade_architecture": 0.45,
    "critical_minerals": 0.30, "cultural_diplomacy": 0.25, "space_isr": 0.25,
    "female_labour_participation": 0.25, "immigration_liberalisation": 0.15,
    "china_engagement": 0.30, "cyber_active_defence": 0.20, "unsc_reform": 0.10,
    "collective_self_defence": 0.0, "nuclear_latency_posture": 0.0,
}


# -- the catalogue is well formed --------------------------------------------


def test_every_instrument_points_at_real_lowy_measures():
    for instrument in ins.CATALOGUE:
        unknown = set(instrument.exposure) - set(MEASURES)
        assert not unknown, f"{instrument.ident} exposes unknown {unknown}"
        assert instrument.exposure, f"{instrument.ident} points at nothing"


def test_instrument_ids_are_unique():
    idents = [i.ident for i in ins.CATALOGUE]
    assert len(idents) == len(set(idents))


def test_costs_and_lead_times_are_sane():
    for i in ins.CATALOGUE:
        assert i.fiscal_gdp_pct >= 0.0
        assert 0.0 <= i.political_cost <= 1.0
        assert i.legal in ins.LEGAL_DIFFICULTY
        assert 1 <= i.lead_time_years <= 10


def test_tensions_name_real_instruments():
    for i in ins.CATALOGUE:
        for other in i.tension_with:
            assert other in ins.BY_ID, f"{i.ident} is in tension with unknown {other}"


def test_the_catalogue_covers_every_lowy_measure():
    """A measure no instrument can move would be unreachable by any policy,
    which would make its weight in the composite unusable."""
    covered = {m for i in ins.CATALOGUE for m, w in i.exposure.items() if w > 0}
    assert covered == set(MEASURES), f"unreachable measures: {set(MEASURES) - covered}"


def test_the_nuclear_option_a_model_reached_for_is_expressible():
    """In preflight 32086108143 gpt-4.1-nano invented
    `military_capability.nuclear_deterrence` and had its portfolio discarded.
    It was reaching for something real that Lowy has no dial for."""
    assert "nuclear_latency_posture" in ins.BY_ID
    nuclear = ins.BY_ID["nuclear_latency_posture"]
    # and it must cost something, in both directions
    assert nuclear.exposure["military_capability"] > 0
    assert nuclear.exposure["diplomatic_influence"] < 0
    assert nuclear.total_political_cost > 0.9


# -- the envelopes bind, and are calibrated against history --------------------


def test_the_envelopes_actually_constrain():
    """If everything at full intensity were affordable there would be no
    trade-off, and therefore no search problem."""
    everything = {i: 1.0 for i in ins.INSTRUMENT_IDS}
    assert ins.fiscal_cost(everything) > ins.FISCAL_ENVELOPE_GDP_PCT
    assert ins.political_cost(everything) > ins.POLITICAL_ENVELOPE
    assert not ins.coherence_report({"instruments": everything}).feasible


def test_the_real_december_2022_decision_is_feasible():
    """An envelope that rules the actual historical decision infeasible is not
    a strict model, it is a wrong one. The first draft of POLITICAL_ENVELOPE
    said 1.60 and did exactly that."""
    report = ins.coherence_report({"instruments": DEC_2022})
    assert report.feasible, report.violations


def test_the_real_december_2022_decision_is_stretched():
    """It nearly broke the government that did it, so it should sit near the
    top of both envelopes rather than comfortably inside them."""
    report = ins.coherence_report({"instruments": DEC_2022})
    assert report.fiscal_gdp_pct > 0.85 * ins.FISCAL_ENVELOPE_GDP_PCT
    assert report.political > 0.80 * ins.POLITICAL_ENVELOPE
    assert report.warnings, "the historical maximum should read as stretched"


def test_an_unaffordable_portfolio_is_rejected_not_warned():
    report = ins.coherence_report({"instruments": {
        "defence_budget": 1.0, "semiconductor_policy": 1.0,
        "energy_diversification": 1.0, "oda_infrastructure": 1.0,
        "female_labour_participation": 1.0, "space_isr": 1.0,
    }})
    assert not report.feasible
    assert any("fiscally infeasible" in v for v in report.violations)


def test_an_unknown_instrument_is_a_violation():
    report = ins.coherence_report({"instruments": {"invade_taiwan": 1.0}})
    assert not report.feasible
    assert any("unknown instrument" in v for v in report.violations)


def test_an_out_of_range_intensity_is_a_violation():
    report = ins.coherence_report({"instruments": {"defence_budget": 4.0}})
    assert not report.feasible


def test_contradictory_pairs_are_warned_not_forbidden():
    """Pulling in two directions is a real strategic posture, and the archive
    should be able to hold it. It is the judge's job to price it."""
    report = ins.coherence_report({"instruments": {
        "china_engagement": 0.8, "economic_security_regime": 0.8,
    }})
    assert report.feasible
    assert any("works against" in w for w in report.warnings)


def test_constitutional_amendment_is_flagged():
    report = ins.coherence_report({"instruments": {"collective_self_defence": 0.6}})
    assert any("referendum" in w for w in report.warnings)


# -- exposure ----------------------------------------------------------------


def test_exposure_can_be_negative_and_shares_cannot():
    """china_engagement points AWAY from resilience. The signed view must keep
    that; the judge's share view must not go negative."""
    signed = ins.lowy_exposure({"china_engagement": 1.0})
    assert signed["resilience"] < 0
    shares = ins.effort_shares({"china_engagement": 1.0})
    assert all(v >= 0 for v in shares.values())
    assert sum(shares.values()) == pytest.approx(1.0)


def test_an_empty_portfolio_gets_a_uniform_share_rather_than_a_crash():
    shares = ins.effort_shares({})
    assert sum(shares.values()) == pytest.approx(1.0)
    assert len(set(round(v, 9) for v in shares.values())) == 1


# -- the bridge into the existing apparatus -----------------------------------


def test_an_instrument_choice_becomes_a_gate_valid_portfolio():
    """This is what makes the change a rewrite of the engine and not of the
    whole car: judge, gate, descriptors, MAP-Elites and analysis keep working."""
    portfolio = ins.to_portfolio(DEC_2022)
    valid, reasons = evaluator.validity_gate(portfolio)
    assert valid, reasons
    assert len(portfolio.dials) == sum(len(SUBMEASURES[m]) for m in MEASURES)
    assert portfolio.total_share() == pytest.approx(1.0, abs=1e-9)


def test_the_derived_allocation_matches_the_derived_exposure():
    """Dial shares must be a CONSEQUENCE of the instruments, not a free
    choice. Moving an instrument must move the outcome exposure."""
    portfolio = ins.to_portfolio(DEC_2022)
    by_measure = effort_by_measure(portfolio.to_dict())
    expected = ins.effort_shares(DEC_2022)
    for measure in MEASURES:
        # 1e-5, not 1e-9: to_dict() rounds each share to 6 decimals so the
        # cache key is canonical, and a measure sums up to 5 of them. The
        # residual is serialisation, not a modelling error.
        assert by_measure[measure] == pytest.approx(expected[measure], abs=1e-5)


def test_moving_an_instrument_moves_the_outcome_exposure():
    base = ins.effort_shares(DEC_2022)
    pushed = dict(DEC_2022, immigration_liberalisation=0.9)
    after = ins.effort_shares(pushed)
    assert after["future_resources"] > base["future_resources"], (
        "immigration is the only real lever on Japan's 11.3 future-resources "
        "score; raising it must show up in the exposure"
    )


def test_prose_is_derived_so_it_cannot_drift_from_the_allocation():
    """In the old representation the `how` string and the share were
    independent and nothing checked one against the other."""
    portfolio = ins.to_portfolio({"immigration_liberalisation": 0.9})
    hows = {d.dial_id: d.how for d in portfolio.dials.values()}
    future = [h for k, h in hows.items() if k.startswith("future_resources")]
    assert future and all("immigration" in h.lower() for h in future)


def test_the_defence_path_is_derived_from_the_defence_instrument():
    """The headline number and the allocation cannot disagree, because there
    is only one of them now."""
    low = ins.to_portfolio({"defence_budget": 0.0}).defence_path
    high = ins.to_portfolio({"defence_budget": 1.0}).defence_path
    assert max(high.values()) > max(low.values())
    assert all(0.5 <= v <= 3.5 for v in list(low.values()) + list(high.values()))


def test_derived_portfolios_are_always_well_formed_even_when_infeasible():
    """Two different things, and the distinction is the whole point.

    WELL-FORMED is about shape: 30 dials, shares summing to 1.0, `how` strings
    inside the cap, phases ordered, defence path in bounds. `to_portfolio` must
    guarantee that for every corner of the instrument space, or the search
    would waste budget on malformed output rather than on real trade-offs.

    FEASIBLE is about whether Japan could do it. Most of the instrument space
    is not, and that is the finding, not a bug -- see the test below.
    """
    import random

    rng = random.Random(0)
    for _ in range(40):
        intensities = {i: rng.random() for i in ins.INSTRUMENT_IDS}
        portfolio = ins.to_portfolio(intensities)
        _valid, reasons = evaluator.validity_gate(portfolio)
        shape_errors = [r for r in reasons
                        if "infeasible" not in r and "unknown instrument" not in r]
        assert not shape_errors, shape_errors
        assert portfolio.total_share() == pytest.approx(1.0, abs=1e-9)
        assert len(portfolio.dials) == 30


def test_the_feasible_set_is_a_small_part_of_the_instrument_space():
    """The reason this layer contains a search problem and the old one did not.

    In the outcome representation EVERY point of the simplex was valid, so
    `scripts/random_baseline.py` had a 100% gate pass rate and beat MAP-Elites
    on coverage simply by sampling everywhere at once. Instruments have prices,
    so the feasible set is a thin region: about 1% of uniform draws over all 21
    instruments survive the fiscal and political envelopes.

    That is what "a genuinely contained search problem" means, and it is the
    property the outcome layer lacked.
    """
    import random

    rng = random.Random(0)
    feasible = sum(
        1 for _ in range(300)
        if evaluator.validity_gate(
            ins.to_portfolio({i: rng.random() for i in ins.INSTRUMENT_IDS}))[0]
    )
    assert feasible / 300 < 0.10, (
        "if most random instrument draws were feasible the envelopes would not "
        "be binding and there would be no trade-off to search over"
    )
    assert feasible >= 1, (
        "if NO random draw were feasible the envelopes would be too tight to "
        "admit any policy at all"
    )


def test_two_different_instrument_mixes_are_different_genotypes():
    """The point of the layer: portfolios that differ in HOW they buy military
    capability are now distinct, where before they differed only in prose."""
    via_budget = ins.to_portfolio({"defence_budget": 0.8}).to_dict()
    via_nuclear = ins.to_portfolio({"nuclear_latency_posture": 0.8}).to_dict()
    assert via_budget["dials"] != via_nuclear["dials"]


# -- the gate now prices policy, not just formatting --------------------------


def test_the_gate_rejects_a_fiscally_impossible_portfolio():
    """Review point 3: the gate proved formatting, not coherence. It could not
    have done otherwise while the searched layer was outcomes, which have no
    price. Now it does."""
    blowout = ins.to_portfolio({
        "defence_budget": 1.0, "semiconductor_policy": 1.0,
        "energy_diversification": 1.0, "oda_infrastructure": 1.0,
        "female_labour_participation": 1.0, "space_isr": 1.0,
    })
    valid, reasons = evaluator.validity_gate(blowout)
    assert not valid
    assert any("fiscally infeasible" in r for r in reasons)


def test_the_gate_accepts_the_real_december_2022_decision():
    valid, reasons = evaluator.validity_gate(ins.to_portfolio(DEC_2022))
    assert valid, reasons


def test_the_gate_still_only_length_checks_a_portfolio_without_instruments():
    """The older representation must keep working untouched. This is the
    preserve half of preserve-rewrite."""
    import initial

    portfolio = initial.build_policy()
    assert not getattr(portfolio, "instruments", {})
    valid, reasons = evaluator.validity_gate(portfolio)
    assert valid, reasons


def test_adding_instruments_does_not_change_an_old_portfolio_s_cache_key():
    """to_dict() omits the key entirely when empty. Adding it unconditionally
    would invalidate every cached judge call in the repository and silently
    re-spend the ledger."""
    import initial

    assert "instruments" not in initial.build_policy().to_dict()
    assert "instruments" in ins.to_portfolio(DEC_2022).to_dict()


def test_a_contradictory_but_affordable_portfolio_still_passes_the_gate():
    """Warnings must not become violations. Pricing a contradiction is the
    judge's job; forbidding it would delete a real strategic posture from the
    search space."""
    portfolio = ins.to_portfolio({"china_engagement": 0.8,
                                  "economic_security_regime": 0.8})
    valid, reasons = evaluator.validity_gate(portfolio)
    assert valid, reasons


def test_the_instrument_seed_program_runs_and_passes():
    import initial_instruments

    portfolio = initial_instruments.build_policy()
    valid, reasons = evaluator.validity_gate(portfolio)
    assert valid, reasons
    assert portfolio.instruments, "the seed must record its decisions"
    report = ins.coherence_report({"instruments": portfolio.instruments})
    assert report.feasible
    assert report.warnings, "December 2022 should read as stretched"
