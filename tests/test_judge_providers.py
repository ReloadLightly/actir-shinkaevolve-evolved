"""Both judge backends, and the fail-closed gate in front of each.

RESEARCH_DESIGN section 4 requires the final archive to be re-scored by "a
second frozen judge from a different model family", so two backends are on the
critical path for M4 whatever is chosen for M1. Section 2.2 names the paper's
own judge tier as gpt-5-nano / gpt-4.1 / gpt-5-mini at temperature 0, so the
OpenAI tier is the design's own precedent rather than a substitute for it.

The rule these tests defend: **adding a provider must not add a way around the
Stage B gate.** Every fail-closed check is asserted against both backends.
"""

from __future__ import annotations

import json

import pytest

from judge.client import (
    MOCK,
    PRICING_USD_PER_MTOK,
    REAL,
    RESPONSE_SCHEMA,
    SUPPORTED_PROVIDERS,
    JudgeClient,
    JudgeConfig,
)
from lowy import MEASURES

ANTHROPIC = JudgeConfig(provider="anthropic", model="claude-haiku-4-5-20251001")
OPENAI = JudgeConfig(provider="openai", model="gpt-5-mini")


# --------------------------------------------------------------------------
# The gate holds for every provider
# --------------------------------------------------------------------------


@pytest.mark.parametrize("provider,model", [
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("openai", "gpt-5-mini"),
])
def test_real_mode_refuses_without_authorization(provider, model):
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider=provider, model=model, stage_b_authorized=False
    ))
    with pytest.raises(RuntimeError, match="stage_b_authorized"):
        client._assert_real_calls_authorized()


@pytest.mark.parametrize("provider,model", [
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("openai", "gpt-5-mini"),
])
def test_authorization_alone_is_not_enough_without_real_mode(provider, model):
    """mode: mock with stage_b_authorized: true must still make no call."""
    client = JudgeClient(JudgeConfig(
        mode=MOCK, provider=provider, model=model, stage_b_authorized=True
    ))
    with pytest.raises(RuntimeError, match="mock mode"):
        client._assert_real_calls_authorized()


@pytest.mark.parametrize("provider,model", [
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("openai", "gpt-5-mini"),
])
def test_mock_mode_never_calls_either_backend(provider, model, monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("mock mode reached a network backend")

    monkeypatch.setattr(JudgeClient, "_call_anthropic", explode)
    monkeypatch.setattr(JudgeClient, "_call_openai", explode)

    client = JudgeClient(JudgeConfig(mode=MOCK, provider=provider, model=model))
    verdict = client.score(
        scenario_id="S1", scenario_text="x", prompt_text="y", portfolio={"a": 1}
    )
    assert verdict.mocked is True
    assert all(verdict.deltas[m] == 0.0 for m in MEASURES)


def test_unsupported_provider_is_refused_before_the_network():
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="cohere", model="whatever", stage_b_authorized=True
    ))
    with pytest.raises(RuntimeError, match="no implemented backend"):
        client._assert_real_calls_authorized()


def test_an_authorized_config_with_no_model_is_still_refused():
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="openai", model="", stage_b_authorized=True
    ))
    with pytest.raises(RuntimeError, match="no model pinned"):
        client._assert_real_calls_authorized()


def test_supported_providers_are_exactly_the_implemented_ones():
    assert set(SUPPORTED_PROVIDERS) == {"anthropic", "openai"}


# --------------------------------------------------------------------------
# The two backends must ask the same question
# --------------------------------------------------------------------------


def test_both_providers_send_identical_prompt_text():
    """A judge swap must differ in the model only, never in the prompt.

    If the two backends phrased the question differently, the rank correlation
    reported in RESEARCH_DESIGN section 4 would measure prompt drift rather
    than judge agreement.
    """
    kwargs = dict(
        scenario_id="S2",
        scenario_text="a scenario",
        prompt_text="a rubric",
        portfolio={"dials": [{"dial": "x", "share": 1.0, "how": "y"}]},
    )
    assert (
        JudgeClient(ANTHROPIC)._user_content(**kwargs)
        == JudgeClient(OPENAI)._user_content(**kwargs)
    )


def test_provider_is_part_of_the_cache_key():
    """Swapping judges must invalidate the cache, not reuse the other's verdicts."""
    kwargs = dict(
        scenario_id="S1",
        scenario_text="a scenario",
        prompt_text="a rubric",
        portfolio={"dials": []},
    )
    assert (
        JudgeClient(ANTHROPIC).cache_key(**kwargs)
        != JudgeClient(OPENAI).cache_key(**kwargs)
    )


def test_judge_identity_records_the_provider():
    assert ANTHROPIC.identity()["provider"] == "anthropic"
    assert OPENAI.identity()["provider"] == "openai"


# --------------------------------------------------------------------------
# Structured output and sampling parameters
# --------------------------------------------------------------------------


def test_response_schema_is_openai_strict_compatible():
    """OpenAI strict mode requires additionalProperties false and every
    property listed in required, at every level."""
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert set(RESPONSE_SCHEMA["required"]) == set(MEASURES)
    for measure in MEASURES:
        entry = RESPONSE_SCHEMA["properties"][measure]
        assert entry["additionalProperties"] is False
        assert set(entry["required"]) == {"delta", "mechanism"}


@pytest.mark.parametrize("model,expected", [
    ("gpt-5-mini", True),
    ("gpt-4.1", True),
    ("gpt-5-nano", True),
    ("claude-haiku-4-5-20251001", True),
    ("o3", False),
    ("o4-mini", False),
    ("claude-opus-5", False),
    ("claude-sonnet-5", False),
])
def test_temperature_is_sent_only_to_models_that_accept_it(model, expected):
    """RESEARCH_DESIGN section 2.2 wants temperature 0. Models that reject the
    parameter get no temperature rather than a 400."""
    assert JudgeConfig(model=model).sends_temperature is expected


# --------------------------------------------------------------------------
# Cost accounting
# --------------------------------------------------------------------------


def test_the_paper_s_own_judge_tier_is_priced():
    """RESEARCH_DESIGN section 2.2 names these three; a cost ceiling cannot be
    checked against a model with no price."""
    for model in ("gpt-5-nano", "gpt-5-mini", "gpt-4.1"):
        assert model in PRICING_USD_PER_MTOK


def test_unknown_pricing_is_flagged_not_silently_free(monkeypatch):
    """A model with no price entry must not look like a free model."""
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="openai", model="gpt-unpriced-9",
        stage_b_authorized=True,
    ))
    monkeypatch.setattr(
        JudgeClient, "_call_openai",
        lambda self, _c: (
            json.dumps({m: {"delta": 0.0, "mechanism": "m"} for m in MEASURES}),
            {"input_tokens": 1000, "output_tokens": 500},
            "stop", "resp_1",
        ),
    )
    payload = client._call_api("S1", "scenario", "rubric", {})
    assert payload["cost_usd"] == 0.0
    assert payload["pricing_known"] is False, (
        "an unpriced model must be visible as a gap, not as a free call"
    )


def test_known_pricing_is_flagged_and_computed(monkeypatch):
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="openai", model="gpt-5-mini", stage_b_authorized=True,
    ))
    monkeypatch.setattr(
        JudgeClient, "_call_openai",
        lambda self, _c: (
            json.dumps({m: {"delta": 1.0, "mechanism": "m"} for m in MEASURES}),
            {"input_tokens": 1_000_000, "output_tokens": 1_000_000},
            "stop", "resp_1",
        ),
    )
    payload = client._call_api("S1", "scenario", "rubric", {})
    assert payload["pricing_known"] is True
    rates = PRICING_USD_PER_MTOK["gpt-5-mini"]
    assert payload["cost_usd"] == pytest.approx(rates["input"] + rates["output"])


# --------------------------------------------------------------------------
# Response handling, without touching the network
# --------------------------------------------------------------------------


def test_openai_payload_parses_into_a_verdict(monkeypatch):
    deltas = {m: {"delta": 1.5, "mechanism": f"{m} moves"} for m in MEASURES}
    monkeypatch.setattr(
        JudgeClient, "_call_openai",
        lambda self, _c: (
            json.dumps(deltas), {"input_tokens": 10, "output_tokens": 5},
            "stop", "resp_x",
        ),
    )
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="openai", model="gpt-5-mini", stage_b_authorized=True,
    ))
    payload = client._call_api("S3", "scenario", "rubric", {})
    verdict = client._verdict_from_payload("S3", "key", payload)
    assert all(verdict.deltas[m] == 1.5 for m in MEASURES)
    assert verdict.mechanisms["resilience"] == "resilience moves"


def test_unparseable_response_raises_rather_than_scoring_zero(monkeypatch):
    """Silent zeros would read as 'the judge saw no effect', which is a
    different claim from 'the judge did not answer'."""
    monkeypatch.setattr(
        JudgeClient, "_call_openai",
        lambda self, _c: ("not json at all", {"input_tokens": 1,
                                              "output_tokens": 1}, "stop", "r"),
    )
    client = JudgeClient(JudgeConfig(
        mode=REAL, provider="openai", model="gpt-5-mini", stage_b_authorized=True,
    ))
    with pytest.raises(RuntimeError, match="unparseable JSON"):
        client._call_api("S1", "scenario", "rubric", {})
