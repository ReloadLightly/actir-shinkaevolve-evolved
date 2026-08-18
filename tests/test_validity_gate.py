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


# --------------------------------------------------------------------------
# Share normalisation: repaired inside the band, rejected outside it.
#
# The preflight run of 2026-08-18 measured gpt-4.1-nano summing its 30 shares
# to 0.670000 and being rejected for it -- 0/1 models produced a portfolio the
# gate accepted, which would have spent the pilot's entire ceiling on gate
# failures. Shares are a normalisation convention (only proportions carry
# policy meaning), so the gate now rescales rather than rejects. These tests
# pin both halves of that contract: what gets repaired, and what still does not.
# --------------------------------------------------------------------------


def test_repairs_shares_that_merely_fail_to_sum_to_one():
    portfolio = _valid_portfolio()
    portfolio.invest(
        "economic_capability.size", share=0.30, how="over-allocated on purpose"
    )
    raw = portfolio.total_share()
    assert raw != pytest.approx(1.0, abs=1e-6), "the fixture must be off-sum"

    valid, reasons = validity_gate(portfolio)
    assert valid, f"an in-band sum must be repaired, not rejected: {reasons}"
    assert portfolio.shares_repaired is True
    assert portfolio.raw_share_sum == pytest.approx(raw)
    assert portfolio.total_share() == pytest.approx(1.0, abs=1e-9)


def test_repair_preserves_the_proportions_it_rescales():
    """Repair must not change what the portfolio *says*, only its scale."""
    portfolio = _valid_portfolio()
    portfolio.invest("economic_capability.size", share=0.30, how="over-allocated")
    before = {k: d.share for k, d in portfolio.dials.items()}
    raw = portfolio.total_share()

    validity_gate(portfolio)

    after = {k: d.share for k, d in portfolio.dials.items()}
    assert set(before) == set(after)
    for dial_id, share in before.items():
        assert after[dial_id] == pytest.approx(share / raw, abs=1e-12)


def test_the_nano_failure_from_the_preflight_now_passes():
    """The exact observed failure: 30 shares summing to 0.670000."""
    portfolio = _valid_portfolio()
    factor = 0.67 / portfolio.total_share()
    scaled = [(d.dial_id, d.share * factor, d.how) for d in portfolio.dials.values()]
    rebuilt = PolicyPortfolio(horizon=(2026, 2030))
    for dial_id, share, how in scaled:
        rebuilt.invest(dial_id, share=share, how=how or "placeholder")
    rebuilt.sequence(portfolio.phases)
    rebuilt.custom_initiatives(portfolio.initiatives)
    rebuilt.defence_spending_path(portfolio.defence_path)
    assert rebuilt.total_share() == pytest.approx(0.67, abs=1e-9)

    valid, reasons = validity_gate(rebuilt)
    assert valid, f"the preflight's nano output must now pass: {reasons}"
    assert rebuilt.shares_repaired is True


def test_rejects_a_sum_too_far_off_to_be_arithmetic():
    """Outside the band it is an incoherent allocation, not a slipped sum."""
    portfolio = PolicyPortfolio(horizon=(2026, 2030))
    portfolio.invest("economic_capability.size", share=9.0, how="wildly out of band")
    portfolio.sequence([Phase(label="only", years=(2026, 2030), focus=())])
    reasons = _reasons_for(portfolio)
    assert "shares must sum to 1.0" in reasons
    assert portfolio.shares_repaired is False


def test_negative_shares_are_never_repaired_away():
    """A negative share is a real error; rescaling would hide it."""
    portfolio = _valid_portfolio()
    portfolio.invest("economic_capability.size", share=-0.20, how="negative")
    reasons = _reasons_for(portfolio)
    assert "must be within [0, 1]" in reasons
    assert portfolio.shares_repaired is False


def test_a_correct_sum_is_left_completely_alone():
    portfolio = _valid_portfolio()
    before = {k: d.share for k, d in portfolio.dials.items()}
    valid, _ = validity_gate(portfolio)
    assert valid
    assert portfolio.shares_repaired is False
    assert {k: d.share for k, d in portfolio.dials.items()} == before


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
    # A negative share is out of repair scope, so the sum violation survives
    # to be reported alongside the others rather than being rescaled away.
    portfolio.invest("economic_capability.size", share=-0.5, how="negative")
    portfolio.sequence([])
    valid, reasons = validity_gate(portfolio)
    assert not valid
    assert len(reasons) >= 4, reasons
