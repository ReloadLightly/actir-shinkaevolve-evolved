"""The run configs, checked against KICKOFF's hard rules.

README claims "The judge is never in the mutation ensemble — check any config
in `configs/`". Until this file existed, nothing checked it. The configs are
hand-edited YAML and the judge id has already changed once, so the guarantee
needed to be executable rather than asserted in prose.

Rules enforced here:

* **Hard rule 2** — the judge model is never a member of the mutation ensemble.
* **Hard rule 4** — per-stage cost ceilings, and the total across the runs that
  will actually happen at Stage D. Ceilings may be lowered, never raised.
* **RESEARCH_DESIGN §4** — ablations run at matched budget against main, or the
  comparison measures budget rather than mechanism.
* Housekeeping that silently ruins a run: colliding `results_dir`, a missing
  seed program, a model id that does not exist.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"
ABLATION_DIR = CONFIG_DIR / "ablations"

# Cost ceilings, USD. Hard rule 4 says a ceiling may never be raised, so these
# are read-only from our side.
#
# **PROJECT_CEILING is the binding one.** Roland set the whole-project budget at
# USD 15 on 2026-08-17, superseding the per-stage figures written into KICKOFF
# (Stage B 1, Stage C 10, Stage D 250 — which total 261). Where KICKOFF and this
# number disagree, the smaller wins. See docs/BUDGET.md.
PROJECT_CEILING = 15.0

CEILING_M1 = 1.0            # KICKOFF Stage B; the real M1 estimate is ~0.19
CEILING_PILOT = 1.0         # re-cut from KICKOFF's 10 to fit PROJECT_CEILING
CEILING_STAGE_D_TOTAL = 12.0  # re-cut from KICKOFF's 250

#: Reserved outside the search runs: M1 calibration, the M4 judge-swap
#: re-scoring of the top-20 archive, and contingency.
RESERVE_M1 = 0.25
RESERVE_M4_JUDGE_SWAP = 0.50
RESERVE_CONTINGENCY = 1.25

#: The runs RESEARCH_DESIGN §4 actually calls for at Stage D: the main run, two
#: baselines (random search and hill climbing), and three ablations — one per
#: mechanism. Six runs. The ablation directory holds more configs than this,
#: because each mechanism has two variants; which variant runs is a decision,
#: and this list is where that decision is recorded.
STAGE_D_RUN_SET: List[str] = [
    "main.yaml",
    "ablations/parent_hill_climbing.yaml",     # baseline: hill climbing (§4)
    "ablations/random_search.yaml",            # baseline: random search (§4)
    "ablations/parent_best_of_n.yaml",         # ablation 1: parent selection
    "ablations/ensemble_single.yaml",          # ablation 2: ensemble composition
    "ablations/novelty_off.yaml",              # ablation 3: novelty handling
]

#: Configs that exist as alternatives but are not in the Stage D run set. Listed
#: explicitly so that a config cannot be silently forgotten *or* silently added.
STAGE_D_SPARES: List[str] = [
    "ablations/ensemble_fixed.yaml",           # variant of ablation 2
    "ablations/novelty_threshold_only.yaml",   # variant of ablation 3
]

#: The two §4 baselines. They strip evolutionary guidance rather than isolating
#: one mechanism, so the one-mechanism rule does not apply to them.
BASELINES: List[str] = [
    "ablations/random_search.yaml",
    "ablations/parent_hill_climbing.yaml",
]

#: Model ids not yet verified against Roland's accounts. Anything here will
#: fail a real run on its first call, so it must be resolved before Stage C.
#: Emptying this list is the fix; suppressing the test is not.
UNVERIFIED_MODEL_IDS = {
    "gpt-5.4",
    "gemini-3-flash-preview",
}


def _load(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _run_configs() -> Dict[str, Dict[str, Any]]:
    """Every config that drives an evolution run (i.e. not judge.yaml)."""
    found = {}
    for path in sorted(CONFIG_DIR.glob("*.yaml")) + sorted(ABLATION_DIR.glob("*.yaml")):
        if path.name == "judge.yaml":
            continue
        found[str(path.relative_to(CONFIG_DIR))] = _load(path)
    return found


@pytest.fixture(scope="module")
def configs() -> Dict[str, Dict[str, Any]]:
    return _run_configs()


@pytest.fixture(scope="module")
def judge_model() -> str:
    return _load(CONFIG_DIR / "judge.yaml")["model"]


def _evo(config: Dict[str, Any]) -> Dict[str, Any]:
    return config.get("evo_config", {})


def _ensemble(config: Dict[str, Any]) -> List[str]:
    return list(_evo(config).get("llm_models") or [])


# --------------------------------------------------------------------------
# Hard rule 2: the judge never mutates
# --------------------------------------------------------------------------


def test_the_judge_is_never_in_any_mutation_ensemble(configs, judge_model):
    """KICKOFF hard rule 2. Variation proposes, a separate environment
    disposes — if the judge also writes candidates, that separation is gone.
    """
    offenders = [
        name for name, config in configs.items() if judge_model in _ensemble(config)
    ]
    assert not offenders, (
        f"judge model {judge_model!r} appears in the mutation ensemble of: "
        f"{offenders}"
    )


def test_every_config_has_a_non_empty_ensemble(configs):
    for name, config in configs.items():
        assert _ensemble(config), f"{name} has no llm_models"


def test_meta_and_novelty_models_are_recorded_against_the_judge(configs, judge_model):
    """Not a violation, but a coupling that has to stay deliberate.

    RESEARCH_DESIGN §2.2 says the judge tier *is* the paper's meta/novelty
    tier, so overlap there is by design where hard rule 2's ban on the mutation
    ensemble is not. This test does not forbid the overlap; it fails if the
    judge silently becomes the novelty gatekeeper without that being noticed,
    because at M4 the swap judge and the novelty model are the same family.
    """
    coupled = []
    for name, config in configs.items():
        evo = _evo(config)
        for key in ("meta_llm_models", "novelty_llm_models"):
            models = evo.get(key) or []
            if judge_model in models:
                coupled.append(f"{name}:{key}")
    assert not coupled, (
        "the judge model is also doing meta/novelty duty in "
        f"{coupled}. That is defensible per RESEARCH_DESIGN 2.2, but it must "
        "be a recorded decision in docs/DECISIONS.md, not an accident of "
        "editing. If it is intended, update this test with the reasoning."
    )


# --------------------------------------------------------------------------
# Hard rule 4: cost ceilings
# --------------------------------------------------------------------------


def test_pilot_ceiling_matches_kickoff(configs):
    assert _evo(configs["pilot.yaml"])["max_api_costs"] <= CEILING_PILOT


def test_every_config_declares_a_ceiling(configs):
    for name, config in configs.items():
        ceiling = _evo(config).get("max_api_costs")
        assert ceiling is not None, f"{name} declares no max_api_costs"
        assert ceiling > 0, f"{name} has a non-positive ceiling"


def test_the_stage_d_run_set_fits_its_ceiling(configs):
    """The runs that will actually happen must fit inside the Stage D share."""
    total = 0.0
    for name in STAGE_D_RUN_SET:
        assert name in configs, f"STAGE_D_RUN_SET names a missing config: {name}"
        total += _evo(configs[name])["max_api_costs"]
    assert total <= CEILING_STAGE_D_TOTAL, (
        f"Stage D run set totals ${total:.2f}, over its ${CEILING_STAGE_D_TOTAL:.2f} "
        "share. Hard rule 4 forbids raising a ceiling, so the fix is fewer runs "
        "or lower per-run ceilings — Roland's call, not ours."
    )


def test_the_whole_project_fits_the_project_ceiling(configs):
    """The one that actually binds: everything Roland could spend, summed.

    Pilot + the Stage D run set + the reserves for M1 and the M4 judge-swap +
    contingency must fit inside USD 15. This is the check that would have
    caught the original configs, which authorised USD 290 against it.

    Spare configs are deliberately excluded: they are alternatives to members
    of the run set, not additional runs. Swapping one in for another keeps the
    total unchanged, which is why the spares carry a matched ceiling.
    """
    pilot = _evo(configs["pilot.yaml"])["max_api_costs"]
    stage_d = sum(_evo(configs[name])["max_api_costs"] for name in STAGE_D_RUN_SET)
    reserves = RESERVE_M1 + RESERVE_M4_JUDGE_SWAP + RESERVE_CONTINGENCY
    total = pilot + stage_d + reserves
    assert total <= PROJECT_CEILING, (
        f"the project authorises ${total:.2f} against a ${PROJECT_CEILING:.2f} "
        f"ceiling (pilot ${pilot:.2f} + Stage D ${stage_d:.2f} + reserves "
        f"${reserves:.2f}). Lower ceilings or drop runs; never raise the ceiling."
    )


def test_no_single_run_can_eat_the_whole_budget(configs):
    """A single ceiling above the Stage D share means one run could starve the
    rest even while passing the total check."""
    for name, config in configs.items():
        ceiling = _evo(config)["max_api_costs"]
        assert ceiling <= CEILING_STAGE_D_TOTAL / 2, (
            f"{name} alone authorises ${ceiling:.2f}, more than half the "
            f"${CEILING_STAGE_D_TOTAL:.2f} Stage D share"
        )


def test_spares_are_costed_like_the_arms_they_replace(configs):
    """A spare must be swappable without re-costing the study."""
    arm_ceilings = {
        _evo(configs[n])["max_api_costs"] for n in STAGE_D_RUN_SET if n != "main.yaml"
    }
    for name in STAGE_D_SPARES:
        ceiling = _evo(configs[name])["max_api_costs"]
        assert ceiling in arm_ceilings, (
            f"spare {name} is costed at ${ceiling:.2f}, which matches no arm "
            f"in the run set ({sorted(arm_ceilings)}); swapping it in would "
            "change the total"
        )


def test_every_run_config_is_either_scheduled_or_a_declared_spare(configs):
    """No config may be silently forgotten, and none may silently join the run.

    Both directions matter: an unlisted config is either dead weight nobody
    will run, or budget nobody counted.
    """
    accounted = set(STAGE_D_RUN_SET) | set(STAGE_D_SPARES) | {"pilot.yaml"}
    unaccounted = sorted(set(configs) - accounted)
    assert not unaccounted, (
        f"these configs are in neither the Stage D run set nor the spares "
        f"list: {unaccounted}. Add them to one or the other in "
        "tests/test_configs.py, so the Stage D budget stays countable."
    )


# --------------------------------------------------------------------------
# RESEARCH_DESIGN section 4: matched budget
# --------------------------------------------------------------------------


def test_ablations_run_at_matched_budget_against_main(configs):
    """§4 says "at matched budget". Differing generations or ceilings would
    make the comparison measure spend rather than mechanism."""
    main = _evo(configs["main.yaml"])
    mismatched = []
    for name in STAGE_D_RUN_SET:
        if name == "main.yaml":
            continue
        evo = _evo(configs[name])
        if evo["num_generations"] != main["num_generations"]:
            mismatched.append(
                f"{name}: {evo['num_generations']} generations vs "
                f"{main['num_generations']}"
            )
        if evo["max_api_costs"] != main["max_api_costs"]:
            mismatched.append(
                f"{name}: ${evo['max_api_costs']} ceiling vs ${main['max_api_costs']}"
            )
    assert not mismatched, "budget not matched to main:\n  " + "\n  ".join(mismatched)


def test_each_ablation_changes_exactly_one_mechanism(configs):
    """An ablation that moves two knobs cannot attribute its effect to either."""
    main = _evo(configs["main.yaml"])
    main_db = configs["main.yaml"].get("db_config", {})
    ignore = {"results_dir"}

    for name, config in configs.items():
        if name in {"main.yaml", "pilot.yaml"} or name in BASELINES:
            continue
        evo, db = _evo(config), config.get("db_config", {})
        changed = {
            k for k in set(main) | set(evo)
            if k not in ignore and main.get(k) != evo.get(k)
        }
        changed |= {
            f"db.{k}" for k in set(main_db) | set(db) if main_db.get(k) != db.get(k)
        }
        # Novelty and ensemble mechanisms are each carried by a pair of keys
        # that only make sense together, so collapse those to one mechanism.
        mechanisms = set()
        for key in changed:
            if key in {"novelty_llm_models", "code_embed_sim_threshold"}:
                mechanisms.add("novelty")
            elif key in {"llm_models", "llm_dynamic_selection"}:
                mechanisms.add("ensemble")
            elif key.startswith("db.parent_selection"):
                mechanisms.add("parent_selection")
            else:
                mechanisms.add(key)
        assert len(mechanisms) <= 1, (
            f"{name} changes {len(mechanisms)} mechanisms against main "
            f"({sorted(mechanisms)}); an ablation must change exactly one"
        )


# --------------------------------------------------------------------------
# Things that silently ruin a run
# --------------------------------------------------------------------------


def test_results_dirs_are_unique(configs):
    """Two runs writing to one directory destroys the first one's archive."""
    seen: Dict[str, str] = {}
    for name, config in configs.items():
        results_dir = _evo(config).get("results_dir")
        assert results_dir, f"{name} declares no results_dir"
        assert results_dir not in seen, (
            f"{name} and {seen[results_dir]} both write to {results_dir!r}"
        )
        seen[results_dir] = name


def test_init_program_exists(configs):
    for name, config in configs.items():
        init = _evo(config).get("init_program_path")
        assert init, f"{name} declares no init_program_path"
        assert (REPO_ROOT / init).is_file(), f"{name} seeds from missing {init}"


def test_text_feedback_is_on_everywhere(configs):
    """The judge's mechanism sentences are what steer the next mutation
    (RESEARCH_DESIGN §2.2 and rule 3 of §1). A run with this off is a
    different experiment."""
    for name, config in configs.items():
        assert _evo(config).get("use_text_feedback") is True, (
            f"{name} has use_text_feedback off"
        )


def _models_in(config: Dict[str, Any]) -> List[str]:
    evo = _evo(config)
    models = list(evo.get("llm_models") or [])
    models += list(evo.get("meta_llm_models") or [])
    models += list(evo.get("novelty_llm_models") or [])
    return models


def test_every_model_id_is_either_known_good_or_declared_unverified(configs):
    """The registry must stay complete.

    This is the test that holds today: a *new* placeholder cannot be added to a
    config without either being verified or being declared. It does not require
    the placeholders to be gone — that is the next test, which is expected to
    fail until Roland supplies ids his accounts can reach.
    """
    known_good = {
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-haiku-4-5-20251001",
        "gpt-4.1-2025-04-14",
    }
    undeclared: Dict[str, List[str]] = {}
    for name, config in configs.items():
        loose = sorted({
            m for m in _models_in(config)
            if m not in known_good and m not in UNVERIFIED_MODEL_IDS
        })
        if loose:
            undeclared[name] = loose
    assert not undeclared, (
        f"model ids that are neither verified nor declared unverified: "
        f"{undeclared}. Add them to the known-good set if you have checked "
        "them, or to UNVERIFIED_MODEL_IDS if you have not."
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN BLOCKER, pending decision 2 in docs/DECISIONS.md: the mutation "
        "ensemble still names placeholder model ids that will fail on the "
        "first call of a real run. Needs ids Roland's accounts can reach. "
        "strict=True means this test flips the suite red the moment the ids "
        "are fixed, so the marker cannot be left behind."
    ),
)
def test_no_unverified_model_ids_remain(configs):
    """Placeholder ids fail on the first mutation call, after the run has
    started and the ceiling clock is running. Blocks Stage C, not M1."""
    found: Dict[str, List[str]] = {}
    for name, config in configs.items():
        bad = sorted({m for m in _models_in(config) if m in UNVERIFIED_MODEL_IDS})
        if bad:
            found[name] = bad
    assert not found, (
        "these model ids are unverified placeholders and will fail a real "
        f"run: {found}. Replace them with ids Roland's accounts can reach, "
        "then remove them from UNVERIFIED_MODEL_IDS."
    )
