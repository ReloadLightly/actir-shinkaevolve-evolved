"""The two probes that test premises rather than calibration.

M1 asked whether the rubric is calibrated. These ask something prior: is the
judge the kind of object the design assumes? Determinism underwrites the
content-hash cache and the phrase "frozen judge"; observability decides whether
40% of the mutation budget is spent on fields the fitness function can see.

Both probes are exercised here against the surrogate, where the right answer is
known by construction, so the harness is trustworthy before it is ever pointed
at a paid judge.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

import preflight_probes as probes  # noqa: E402
from judge.client import MOCK, SURROGATE, JudgeClient, JudgeConfig  # noqa: E402
from lowy import MEASURES  # noqa: E402


@pytest.fixture
def tmp(tmp_path):
    return tmp_path


# -- the cache must really be bypassed, or determinism passes falsely ---------


def test_each_probe_client_gets_its_own_empty_cache(tmp):
    """If the second call were served from the first call's cache, the
    determinism probe would pass trivially and prove nothing."""
    config = JudgeConfig(mode=SURROGATE)
    a = probes._fresh_client(config, tmp, "a")
    b = probes._fresh_client(config, tmp, "b")
    assert a.cache_dir != b.cache_dir
    assert a.cache_dir.is_dir() and not list(a.cache_dir.iterdir())


def test_fresh_client_preserves_the_judge_identity(tmp):
    """Only the cache location may differ — model, provider and temperature
    must survive, or the probe would test a different judge."""
    config = JudgeConfig(mode=SURROGATE, provider="openai", model="gpt-4.1-mini")
    client = probes._fresh_client(config, tmp, "x")
    assert client.config.identity() == config.identity()
    assert client.config.mode == config.mode


# -- determinism -------------------------------------------------------------


def test_determinism_probe_passes_on_a_deterministic_judge(tmp):
    result = probes.probe_determinism(JudgeConfig(mode=SURROGATE), tmp)
    assert result["identical"] is True
    assert result["max_spread"] == 0.0
    assert result["repeats"] == probes.DETERMINISM_REPEATS


def test_determinism_probe_detects_a_nondeterministic_judge(tmp, monkeypatch):
    """The probe is only worth running if it can actually fail."""
    counter = {"n": 0}
    real_score = JudgeClient.score

    def drifting(self, **kwargs):
        verdict = real_score(self, **kwargs)
        counter["n"] += 1
        verdict.deltas = {m: v + 0.01 * counter["n"] for m, v in verdict.deltas.items()}
        return verdict

    monkeypatch.setattr(JudgeClient, "score", drifting)
    result = probes.probe_determinism(JudgeConfig(mode=SURROGATE), tmp)
    assert result["identical"] is False
    assert result["max_spread"] > 0


# -- observability -----------------------------------------------------------


def test_variants_differ_only_outside_the_dials():
    """The probe is confounded the moment a variant touches a dial."""
    variants = probes._variants()
    base = variants["baseline"].to_dict()
    assert len(variants) >= 4
    for name, portfolio in variants.items():
        as_dict = portfolio.to_dict()
        assert as_dict["dials"] == base["dials"], f"{name} moved a dial"
        if name != "baseline":
            assert as_dict != base, f"{name} is identical to the baseline"


def test_every_variant_still_passes_the_validity_gate():
    """A variant rejected by the gate would never reach a judge, so the probe
    would silently measure nothing."""
    import evaluate as evaluator

    for name, portfolio in probes._variants().items():
        valid, reasons = evaluator.validity_gate(portfolio)
        assert valid, f"{name} fails the gate: {reasons}"


def test_observability_probe_reports_the_surrogate_as_blind(tmp):
    """Ground truth: surrogate.py reads only dial shares, so it must be blind
    to all three non-dial fields. If the probe said otherwise it would be
    broken."""
    result = probes.probe_observability(JudgeConfig(mode=SURROGATE), tmp)
    assert set(result["blind_to"]) == {
        "phases_flattened",
        "initiatives_removed",
        "defence_1.6to2.0_becomes_3.4to3.5",
    }


def test_observability_probe_can_report_sight(tmp, monkeypatch):
    """It must be able to return the opposite answer, or it proves nothing."""
    real_score = JudgeClient.score

    def field_sensitive(self, **kwargs):
        verdict = real_score(self, **kwargs)
        n_phases = len(kwargs["portfolio"].get("sequence", []))
        verdict.deltas = {m: v + n_phases for m, v in verdict.deltas.items()}
        return verdict

    monkeypatch.setattr(JudgeClient, "score", field_sensitive)
    result = probes.probe_observability(JudgeConfig(mode=SURROGATE), tmp)
    assert "phases_flattened" not in result["blind_to"]


# -- cost and safety ---------------------------------------------------------


def test_probe_costs_are_declared_for_every_probe():
    assert set(probes.PROBE_CALLS) == {"determinism", "observability"}
    assert sum(probes.PROBE_CALLS.values()) == probes.DETERMINISM_REPEATS + 4


def test_estimate_stays_in_the_cents(capsys):
    probes.estimate(JudgeConfig(model="gpt-4.1-mini-2025-04-14"),
                    ["determinism", "observability"])
    out = capsys.readouterr().out
    dollars = [float(t.lstrip("$")) for t in out.split()
               if t.startswith("$") and t[1:].replace(".", "", 1).isdigit()]
    assert dollars and max(dollars) < 0.10


def test_probes_make_no_network_call_under_mock_or_surrogate(tmp, monkeypatch):
    def explode(*_a, **_k):
        raise AssertionError("a probe reached a network backend")

    monkeypatch.setattr(JudgeClient, "_call_anthropic", explode)
    monkeypatch.setattr(JudgeClient, "_call_openai", explode)
    monkeypatch.setattr(JudgeClient, "_assert_real_calls_authorized", explode)

    for mode in (MOCK, SURROGATE):
        probes.probe_determinism(JudgeConfig(mode=mode), tmp)
        probes.probe_observability(JudgeConfig(mode=mode), tmp)


def test_mock_mode_warns_that_the_result_is_meaningless(capsys, tmp_path):
    """Under mock every delta is zero, so determinism passes trivially and
    observability reports blindness to everything. Both are artefacts."""
    probes.main(["--probe", "determinism", "--out", str(tmp_path)])
    assert "MOCK mode" in capsys.readouterr().out


def test_output_path_outside_the_repo_does_not_crash(tmp_path, capsys):
    """--out to anywhere must work. Naively relativising against the repo root
    raises ValueError for any path outside it."""
    code = probes.main(["--probe", "determinism", "--out", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "probes.json").is_file()
    assert "Wrote" in capsys.readouterr().out
