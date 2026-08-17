"""The four rival-school seeds, and the M1 calibration harness that scores them.

These are the inputs to the M1 smoke test (KICKOFF Stage B). They are not
evolved individuals, but they must be indistinguishable from one as far as the
evaluator is concerned: same loader, same gate, same aggregation. If a seed
cannot pass the gate, M1 cannot run.

The substantive test here is ``test_the_four_schools_are_materially_distinct``.
Four "rival doctrines" that are actually small perturbations of each other
would make the calibration table meaningless — the judge would be asked to
distinguish things that are not different.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
SEED_DIR = TASK_DIR / "seeds"

import evaluate as evaluator  # noqa: E402
from judge.client import JudgeClient, JudgeConfig  # noqa: E402
from lowy import DIALS, MEASURES  # noqa: E402
from schema import DEFAULT_LIMITS, PolicyPortfolio  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import m1_calibration  # noqa: E402

SEED_FILES = {
    "autonomous_rearmament": SEED_DIR / "seed_autonomous_rearmament.py",
    "accommodation": SEED_DIR / "seed_accommodation.py",
    "status_quo_plus": SEED_DIR / "seed_status_quo_plus.py",
    "middle_power_internationalism": SEED_DIR / "seed_middle_power_internationalism.py",
}


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(f"seedtest_{path.stem}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def portfolios():
    """Every seed plus the December 2022 baseline, built once."""
    built = {name: _load(path).build_policy() for name, path in SEED_FILES.items()}
    built["dec_2022"] = _load(TASK_DIR / "initial.py").build_policy()
    return built


# --------------------------------------------------------------------------
# Each seed on its own
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_file_exists(name):
    assert SEED_FILES[name].is_file(), f"missing seed program for {name}"


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_builds_a_portfolio(portfolios, name):
    assert isinstance(portfolios[name], PolicyPortfolio)


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_passes_the_validity_gate(portfolios, name):
    valid, reasons = evaluator.validity_gate(portfolios[name])
    assert valid, f"{name} fails the gate:\n" + "\n".join(f"  - {r}" for r in reasons)


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_shares_sum_to_one(portfolios, name):
    total = portfolios[name].total_share()
    assert abs(total - 1.0) <= DEFAULT_LIMITS.share_sum_tolerance, (
        f"{name} shares sum to {total!r}"
    )


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_covers_every_dial(portfolios, name):
    """A rival school states its position on all 30 dials, including the zeros.

    Rubric rule 6 makes silence meaningful, so a deliberate zero with a `how`
    string saying why is a different claim from an omission. The seeds make the
    deliberate-zero claim, so the judge is never guessing which it was.
    """
    missing = [d for d in DIALS if d not in portfolios[name].dials]
    assert not missing, f"{name} says nothing about: {missing}"


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_explains_every_dial_it_touches(portfolios, name):
    """Including the zeros: a zero without a reason is indistinguishable from
    an oversight, which is exactly the ambiguity rule 6 turns into signal."""
    silent = [
        dial_id for dial_id, dial in portfolios[name].dials.items() if not dial.how
    ]
    assert not silent, f"{name} has dials with no 'how' string: {silent}"


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_defence_path_is_inside_the_feasibility_bound(portfolios, name):
    path = portfolios[name].defence_path
    assert path, f"{name} has an empty defence path"
    for year, value in path.items():
        assert DEFAULT_LIMITS.defence_gdp_min <= value <= DEFAULT_LIMITS.defence_gdp_max, (
            f"{name} defence spending in {year} is {value}% of GDP, outside "
            f"[{DEFAULT_LIMITS.defence_gdp_min}, {DEFAULT_LIMITS.defence_gdp_max}]"
        )


@pytest.mark.parametrize("name", sorted(SEED_FILES))
def test_seed_runs_as_a_script(name):
    """Each seed is a standalone program, exactly like an evolved individual."""
    result = subprocess.run(
        [sys.executable, str(SEED_FILES[name])],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
    assert "total share = 1.000000" in result.stdout


# --------------------------------------------------------------------------
# The four schools against each other: the point of having four
# --------------------------------------------------------------------------


def _share_vector(portfolio):
    dials = portfolio.dials
    return [dials[d].share if d in dials else 0.0 for d in DIALS]


def _l1(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


#: L1 distance between share vectors: 0.0 is identical, 2.0 is disjoint. A
#: distance of d means d/2 of Japan's marginal effort is allocated differently.
DISTINCT_L1 = 0.20   # a tenth of total effort moved: a rival school, not a variant
TWIN_MAX_L1 = 0.20   # status-quo-plus must stay inside this: it is the near-twin
TWIN_MIN_L1 = 0.05   # ...but must not be a copy, or the near-twin test is vacuous

#: The one pair that is deliberately close. Everything else must be distinct.
NEAR_TWIN_PAIR = ("dec_2022", "status_quo_plus")


def test_the_rival_schools_are_materially_distinct(portfolios):
    """No two doctrines may be near-duplicates, except the deliberate twin.

    Four "rival schools" that are small perturbations of each other would make
    the M1 table meaningless: the judge would be asked to distinguish things
    that are not different. The single exemption is status-quo-plus against
    December 2022, which is *designed* to be close — see the next test.
    """
    names = sorted(portfolios)
    vectors = {n: _share_vector(portfolios[n]) for n in names}
    too_close = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if tuple(sorted((a, b))) == tuple(sorted(NEAR_TWIN_PAIR)):
                continue
            distance = _l1(vectors[a], vectors[b])
            if distance < DISTINCT_L1:
                too_close.append(f"{a} vs {b}: L1 = {distance:.3f}")
    assert not too_close, (
        "these portfolios are not materially different doctrines:\n  "
        + "\n  ".join(too_close)
    )


def test_status_quo_plus_is_a_near_twin_of_dec_2022_but_not_a_copy(portfolios):
    """The near-twin check in M1 asks whether the judge can see a small
    difference as small. That only means something if the difference is
    genuinely small *and* genuinely there.
    """
    distance = _l1(
        _share_vector(portfolios["status_quo_plus"]),
        _share_vector(portfolios["dec_2022"]),
    )
    assert TWIN_MIN_L1 < distance < TWIN_MAX_L1, (
        f"status_quo_plus sits at L1 = {distance:.3f} from December 2022; the "
        f"near-twin test needs it inside ({TWIN_MIN_L1}, {TWIN_MAX_L1})"
    )


def test_status_quo_plus_is_the_closest_school_to_dec_2022(portfolios):
    """No other school may accidentally be nearer than the designated twin."""
    baseline = _share_vector(portfolios["dec_2022"])
    distances = {
        name: _l1(_share_vector(portfolios[name]), baseline)
        for name in SEED_FILES
    }
    nearest = min(distances, key=distances.get)
    assert nearest == "status_quo_plus", (
        f"expected status_quo_plus nearest to Dec 2022, got {nearest}: {distances}"
    )


def test_the_schools_disagree_about_military_effort(portfolios):
    """The doctrines must span a real range on the axis they actually contest.

    Autonomous rearmament and accommodation are the poles; if they sit within
    a few points of each other, the seed set has no spine.
    """
    military = {
        name: portfolios[name].share_by_measure()["military_capability"]
        for name in portfolios
    }
    assert military["autonomous_rearmament"] > military["dec_2022"]
    assert military["accommodation"] < military["dec_2022"]
    span = military["autonomous_rearmament"] - military["accommodation"]
    assert span >= 0.25, f"military effort spans only {span:.3f}: {military}"


def test_the_schools_disagree_about_the_defence_spending_path(portfolios):
    """The 2030 GDP figures should not cluster: each doctrine implies its own."""
    endpoints = sorted(p.defence_path[2030] for p in portfolios.values())
    assert endpoints[-1] - endpoints[0] >= 2.0, f"2030 paths cluster: {endpoints}"


def test_middle_power_bets_on_future_resources(portfolios):
    """Its distinguishing claim: attack the 11.3 measure, where the headroom is."""
    shares = portfolios["middle_power_internationalism"].share_by_measure()
    assert shares["future_resources"] > portfolios["dec_2022"].share_by_measure()[
        "future_resources"
    ] * 2


# --------------------------------------------------------------------------
# The M1 calibration harness
# --------------------------------------------------------------------------


def test_m1_covers_five_portfolios_and_three_scenarios():
    assert len(m1_calibration.PORTFOLIOS) == 5
    assert len(evaluator.SCENARIO_IDS) == 3
    for _key, _label, path in m1_calibration.PORTFOLIOS:
        assert path.is_file(), f"M1 references a missing program: {path}"


def test_m1_scores_every_portfolio_under_the_mock_judge(tmp_path):
    client = JudgeClient(JudgeConfig(mode="mock"))
    rows = m1_calibration.score_all(client)
    assert len(rows) == 5
    for row in rows:
        assert row["public"]["valid"] is True
        assert row["public"]["judge_mocked"] is True
        assert row["combined_score"] == pytest.approx(38.8475, abs=1e-6)
        for measure in MEASURES:
            assert row["public"][f"mean_delta_{measure}"] == 0.0


def test_m1_writes_both_reports(tmp_path):
    client = JudgeClient(JudgeConfig(mode="mock"))
    rows = m1_calibration.score_all(client)
    json_path, md_path = m1_calibration.write_report(
        rows, client, tmp_path, "test-version"
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["mocked"] is True
    assert payload["judge_calls"] == 15
    assert payload["frozen_files_version"] == "test-version"
    assert len(payload["rows"]) == 5

    markdown = md_path.read_text(encoding="utf-8")
    assert "MOCK RUN" in markdown, "a mock table must say so on its face"
    assert "Autonomous rearmament" in markdown


def test_m1_refuses_real_without_authorization(tmp_path, monkeypatch):
    """--real is not authorization; it only refuses to report mock zeros as
    judgements. Both config flags are still required (KICKOFF hard rule 1)."""
    config = tmp_path / "judge.yaml"
    config.write_text(
        "mode: real\nstage_b_authorized: false\nprovider: anthropic\n"
        "model: claude-haiku-4-5-20251001\n",
        encoding="utf-8",
    )
    code = m1_calibration.main(["--real", "--judge-config", str(config)])
    assert code == 2


def test_m1_refuses_real_when_config_is_mock(tmp_path):
    config = tmp_path / "judge.yaml"
    config.write_text(
        "mode: mock\nstage_b_authorized: true\nprovider: anthropic\n"
        "model: claude-haiku-4-5-20251001\n",
        encoding="utf-8",
    )
    code = m1_calibration.main(["--real", "--judge-config", str(config)])
    assert code == 2


def test_m1_estimate_stays_under_the_stage_b_ceiling(capsys):
    m1_calibration.estimate(JudgeConfig())
    out = capsys.readouterr().out
    assert "15 judge calls" in out
    dollars = [
        float(token.lstrip("$"))
        for token in out.split()
        if token.startswith("$") and token[1:].replace(".", "", 1).isdigit()
    ]
    assert dollars, f"no cost figure printed:\n{out}"
    assert max(dollars) < 1.00, "M1 estimate breaches the KICKOFF Stage B ceiling"


def test_m1_makes_no_network_call_under_mock(monkeypatch):
    """The mock path must not so much as import the SDK."""
    def explode(*_args, **_kwargs):
        raise AssertionError("the mock judge attempted a real API call")

    monkeypatch.setattr(JudgeClient, "_call_api", explode)
    monkeypatch.setattr(JudgeClient, "_assert_real_calls_authorized", explode)

    client = JudgeClient(JudgeConfig(mode="mock"))
    rows = m1_calibration.score_all(client)
    assert len(rows) == 5
