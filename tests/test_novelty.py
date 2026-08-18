"""The novelty instrument — the one that measures the project's actual purpose.

RESEARCH_DESIGN §5 calls the archive "a map of alternatives, not an answer",
and RQ3 asks whether the machinery holds diversity. Neither is a ranking claim,
which matters: the resolution floor measured at M1 would sink a "the champion is
best" claim while barely touching "the archive is diverse and coherent".

So these tests defend the properties that make the diversity claim honest —
above all that novelty is measured against the NEAREST human seed rather than
their average, and that the frontier applies no score threshold.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "analysis") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "analysis"))

import novelty  # noqa: E402
from lowy import DIALS  # noqa: E402


@pytest.fixture(scope="module")
def humans():
    return novelty._load_human_vectors()


def _record(ident, shares, worst=40.0, mean=40.0, valid=True):
    return {
        "id": ident, "valid": valid, "score": mean, "surrogate": True,
        "public": {"worst_case_composite": worst},
        "portfolio": {"dials": [{"dial": d, "share": s} for d, s in zip(DIALS, shares)]},
    }


def _uniform():
    return [1.0 / len(DIALS)] * len(DIALS)


# -- the human reference set -------------------------------------------------


def test_all_five_human_seeds_load(humans):
    assert set(humans) == {n for n, _ in novelty.HUMAN_SEEDS}
    for name, vec in humans.items():
        assert abs(sum(vec) - 1.0) < 1e-6, f"{name} does not sum to 1"


def test_human_seeds_span_a_real_doctrinal_range(humans):
    """If the reference set were tightly clustered, everything would look novel
    and the metric would be flattering rather than informative."""
    span = max(novelty.l1(a, b) for a in humans.values() for b in humans.values())
    assert span > 1.0, f"human seeds span only {span:.3f}"


def test_a_human_seed_has_zero_novelty_against_itself(humans):
    for name, vec in humans.items():
        distance, nearest = novelty.novelty_against_humans(vec, humans)
        assert distance == pytest.approx(0.0, abs=1e-9)
        assert nearest == name


def test_novelty_uses_the_nearest_seed_not_the_average(humans):
    """The average of five opposed doctrines is a portfolio nobody holds.

    Measuring against it would score a bland centrist portfolio as maximally
    novel, which is exactly backwards.
    """
    centroid = [sum(v[i] for v in humans.values()) / len(humans)
                for i in range(len(DIALS))]
    nearest_distance, _ = novelty.novelty_against_humans(centroid, humans)
    mean_distance = sum(novelty.l1(centroid, v) for v in humans.values()) / len(humans)
    assert nearest_distance < mean_distance, (
        "a centroid must look LESS novel by nearest-seed than by mean-distance"
    )


# -- families ----------------------------------------------------------------


def test_identical_portfolios_form_one_family():
    vectors = [_uniform() for _ in range(5)]
    assert len(novelty.families(vectors)) == 1


def test_disjoint_portfolios_form_separate_families():
    n = len(DIALS)
    a = [1.0] + [0.0] * (n - 1)
    b = [0.0] * (n - 1) + [1.0]
    assert len(novelty.families([a, b])) == 2


def test_family_threshold_matches_the_projects_own_definition():
    """tests/test_seeds.py enforces L1 >= 0.20 between rival schools. The two
    thresholds must not drift apart, or 'different doctrine' means two things."""
    assert novelty.SAME_FAMILY == 0.20


# -- the frontier ------------------------------------------------------------


def test_frontier_excludes_portfolios_too_close_to_a_human_seed(humans):
    near = dict(zip(DIALS, humans["dec_2022"]))
    record = _record(1, [near[d] for d in DIALS])
    assert novelty.frontier([record], humans, min_novelty=0.20) == []


def test_frontier_keeps_the_non_dominated_and_drops_the_dominated(humans):
    """A portfolio beaten on BOTH novelty and robustness is not a find."""
    strong = _record(1, _uniform(), worst=41.0)
    weak = dict(strong)
    weak = _record(2, _uniform(), worst=39.0)      # same novelty, worse worst-case
    kept = novelty.frontier([strong, weak], humans, min_novelty=0.0)
    assert [c["id"] for c in kept] == [1]


def test_frontier_ranks_on_worst_case_not_mean(humans):
    """A portfolio that wins one future and collapses in another must not
    qualify as robust, however good its average."""
    lucky = _record(1, _uniform(), worst=35.0, mean=45.0)
    steady = _record(2, _uniform(), worst=41.0, mean=41.0)
    kept = novelty.frontier([lucky, steady], humans, min_novelty=0.0)
    assert [c["id"] for c in kept] == [2]


def test_frontier_ignores_invalid_portfolios(humans):
    record = _record(1, _uniform(), worst=99.0, valid=False)
    assert novelty.frontier([record], humans, min_novelty=0.0) == []


def test_frontier_applies_no_score_threshold(humans):
    """Thresholding on score would reintroduce the ranking claim the
    resolution floor cannot support."""
    poor_but_novel = _record(1, _uniform(), worst=1.0, mean=1.0)
    kept = novelty.frontier([poor_but_novel], humans, min_novelty=0.0)
    assert [c["id"] for c in kept] == [1]


# -- end to end --------------------------------------------------------------


def test_analyse_runs_on_a_real_offline_archive(tmp_path):
    import offline_evolution as offline  # noqa

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import offline_evolution as oe

    oe.run(generations=40, seed=5, out_dir=tmp_path)
    records = [json.loads(l) for l in
               (tmp_path / "archive.jsonl").read_text().splitlines() if l.strip()]
    stats = novelty.analyse(records, min_novelty=0.20)

    assert stats["surrogate"] is True
    assert stats["valid"] > 0
    assert stats["families"]["count"] >= 1
    assert stats["human_seed_span_l1"] > 1.0
    report = novelty.write_report(stats, tmp_path)
    assert "NOT A RESULT" in report.read_text()
