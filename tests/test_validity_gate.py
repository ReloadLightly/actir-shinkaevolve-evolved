"""Test 2: the Stage 1 validity gate rejects malformed portfolios.

RESEARCH_DESIGN section 2.2: invalid gets fitness 0 plus a reason string, and
no judge call is spent. This is the circle-overlap check of our task, so its
failure modes are worth testing individually — each reason string is what the
mutation LLM sees next.
"""

import pytest

from evaluate import validity_gate
from initial import build_policy
from schema import GateLimits, Initiative, Phase, PolicyPortfolio


def _valid_portfolio() -> PolicyPortfolio:
    return build_policy()


def _reasons_for(portfolio) -> str:
    valid, reasons = validity_gate(portfolio)
    assert not valid, "expected the gate to reject this portfolio"
    return " | ".join(reasons)


def test_the_2022_seed_passes():
    valid, reasons = validity_gate(_valid_portfolio())
    assert valid, f"the seed portfolio must pass the gate, got: {reasons}"


def test_seed_invests_in_all_thirty_dials_and_sums_to_one():
    portfolio = _valid_portfolio()
    assert len(portfolio.dials) == 30
    assert portfolio.total_share() == pytest.approx(1.0, abs=1e-9)


def test_rejects_shares_that_do_not_sum_to_one():
    portfolio = _valid_portfolio()
    portfolio.invest(
        "economic_capability.size", share=0.30, how="over-allocated on purpose"
    )
    assert "shares must sum to 1.0" in _reasons_for(portfolio)


def test_rejects_unknown_dial_names():
    portfolio = _valid_portfolio()
    portfolio.invest("soft_power.anime_diplomacy", share=0.0, how="not a Lowy dial")
    assert "unknown dial name" in _reasons_for(portfolio)


def test_rejects_negative_share():
    portfolio = _valid_portfolio()
    portfolio.invest("cultural_influence.information_flows", share=-0.05, how="negative")
    reasons = _reasons_for(portfolio)
    assert "must be within [0, 1]" in reasons


def test_rejects_non_finite_share():
    portfolio = _valid_portfolio()
    portfolio.invest("cultural_influence.information_flows", share=float("nan"), how="nan")
    assert "not finite" in _reasons_for(portfolio)


def test_rejects_how_string_over_the_cap():
    limits = GateLimits()
    portfolio = _valid_portfolio()
    portfolio.invest(
        "diplomatic_influence.foreign_policy",
        share=0.03,
        how="x" * (limits.how_char_cap + 1),
    )
    assert f"cap is {limits.how_char_cap}" in _reasons_for(portfolio)


def test_rejects_share_without_a_how_string():
    portfolio = _valid_portfolio()
    portfolio.invest("diplomatic_influence.foreign_policy", share=0.03, how="")
    assert "no 'how' string" in _reasons_for(portfolio)


def test_rejects_defence_spending_beyond_the_feasibility_bound():
    limits = GateLimits()
    portfolio = _valid_portfolio()
    portfolio.defence_spending_path({2026: 2.0, 2027: 3.0, 2028: 4.0, 2029: 5.0, 2030: 6.0})
    reasons = _reasons_for(portfolio)
    assert "feasibility bound" in reasons
    assert str(limits.defence_gdp_max) in reasons


def test_rejects_custom_initiative_without_targets():
    portfolio = _valid_portfolio()
    portfolio.custom_initiatives(
        [Initiative(name="Grand Strategy", rationale="unspecified", targets=())]
    )
    assert "names no target submeasures" in _reasons_for(portfolio)


def test_rejects_custom_initiative_targeting_an_unknown_dial():
    portfolio = _valid_portfolio()
    portfolio.custom_initiatives(
        [Initiative(name="X", rationale="y", targets=("not.a_dial",))]
    )
    assert "targets unknown dial" in _reasons_for(portfolio)


def test_rejects_phases_outside_the_horizon():
    portfolio = _valid_portfolio()
    portfolio.sequence([Phase(years=(2031, 2035), label="after the horizon")])
    assert "outside the horizon" in _reasons_for(portfolio)


def test_rejects_unordered_phases():
    portfolio = _valid_portfolio()
    portfolio.sequence(
        [
            Phase(years=(2029, 2030), label="later phase placed first"),
            Phase(years=(2026, 2027), label="earlier phase placed second"),
        ]
    )
    assert "phases must be ordered" in _reasons_for(portfolio)


def test_rejects_an_empty_sequence():
    portfolio = _valid_portfolio()
    portfolio.sequence([])
    assert "at least 1 phase" in _reasons_for(portfolio)


def test_rejects_a_wrong_horizon():
    portfolio = PolicyPortfolio(horizon=(2026, 2040))
    assert "horizon must be (2026, 2030)" in _reasons_for(portfolio)


def test_rejects_a_rhetoric_bomb():
    """The global free-text budget binds even when every item is within its own cap.

    30 dials x 240 chars is 7200, over the 6000 total, so per-item caps alone
    are not enough to bound what the judge reads.
    """
    limits = GateLimits()
    portfolio = _valid_portfolio()
    for dial_id in portfolio.dials:
        share = portfolio.dials[dial_id].share
        portfolio.invest(dial_id, share=share, how="y" * limits.how_char_cap)

    valid, reasons = validity_gate(portfolio)
    assert not valid
    joined = " | ".join(reasons)
    assert "total free text" in joined
    # every individual string is legal; only the budget is breached
    assert "cap is 240" not in joined


def test_per_item_caps_alone_do_not_breach_the_budget():
    """Maxed-out initiatives are still within budget; the seed leaves headroom."""
    limits = GateLimits()
    portfolio = _valid_portfolio()
    portfolio.custom_initiatives(
        [
            Initiative(
                name=f"Initiative {i}",
                rationale="y" * limits.initiative_rationale_char_cap,
                targets=("diplomatic_influence.foreign_policy",),
            )
            for i in range(limits.max_custom_initiatives)
        ]
    )
    valid, reasons = validity_gate(portfolio)
    assert valid, reasons
    assert portfolio.free_text_chars() < limits.total_free_text_cap


def test_rejects_something_that_is_not_a_portfolio_at_all():
    assert "must return a PolicyPortfolio" in _reasons_for({"shares": [1.0]})


def test_collects_every_violation_rather_than_the_first():
    """The mutation LLM gets all reasons at once; one per generation is too slow."""
    portfolio = PolicyPortfolio(horizon=(2026, 2040))
    portfolio.invest("not.a_dial", share=0.5, how="")
    portfolio.sequence([])
    valid, reasons = validity_gate(portfolio)
    assert not valid
    assert len(reasons) >= 4
