# Decision log

Premises and prior decisions are in RESEARCH_DESIGN §8. This file records what
was decided after the repo existed, so that every run can be traced to the
decisions it was made under.

---

## M0 — approved 2026-08-17 by Roland

**Approved: all four M0 items** (RESEARCH_DESIGN §8 lists the open set as the
scenario texts, the judge model, and the feasibility bounds; the dial set was a
yes/no on Lowy's own list).

| Item | Decision |
|---|---|
| **Dial set** | The Index's own 30 submeasures under the 8 measures, verbatim. Not ours to invent. |
| **Scenario texts** | S1 grinding status quo, S2 Taiwan contingency, S3 US retrenchment — as drafted, ~250 words each. |
| **Judge rubric** | `judge_prompt.md` as drafted: 2025 baseline table, anchored delta rubric (+3 ≈ the December 2022 decision), seven rules against arithmetic. |
| **Judge model** | `claude-haiku-4-5-20251001`, temperature 0.0. A dated snapshot, so genuinely pinned. Rationale, including why temperature 0 rules out the frontier tier, in `JUDGE_MODEL_NOTE.md`. |
| **Feasibility bound** | Defence spending within **[0.5%, 3.5%] of GDP** across 2026–2030. The design's own example figure, adopted. |

**Exactly what was approved.** Approval attaches to these bytes, recorded as
`FROZEN.json` version `0.2.0-m0-approved`:

| File | sha256 (first 16) |
|---|---|
| `scenarios/S1_grinding_status_quo.md` | `cc7193676f410d84` |
| `scenarios/S2_taiwan_contingency.md` | `ef8d4cbecc60afa9` |
| `scenarios/S3_us_retrenchment.md` | `8e7bc666c1e9f2ff` |
| `judge_prompt.md` | `cb9c01891c5493a6` |

If any of these changes before M1, the approval is void for that file and needs
re-approval — that is what `tests/test_frozen_files.py` enforces.

### Freeze timing — deferred to after M1

RESEARCH_DESIGN §2.3 would freeze before any run; KICKOFF Stage B freezes only
after the M1 calibration table looks plausible. **Roland chose KICKOFF's
ordering.** So the files stay `status: DRAFT` and M0-approved until the smoke
test has been read.

The reasoning: M1 exists precisely to discover that the rubric is miscalibrated.
Freezing before it would mean any calibration fix costs a version bump and a new
experiment id, which spends the pre-registration on a draft. Freezing after M1
still satisfies §2.3's substantive requirement — frozen before the first
*scored search* run — because M1 is a 15-call plausibility check, not a search.

**This is a deviation from RESEARCH_DESIGN §2.3 as literally written, taken
knowingly, and it belongs in the methods section.** The pre-registration claim
the paper can make is: scenarios and rubric were frozen before any evolutionary
run, having been fixed in draft and hash-recorded before the calibration test.

### Not authorized at M0

**Stage B remains locked.** Roland was offered Stage B authorization alongside
M0 and declined it. `configs/judge.yaml` keeps `mode: mock` and
`stage_b_authorized: false`; no real judge call is possible. The next gate needs
an explicit go in chat *and* an API key in the environment.

---

## M1 inputs built — 2026-08-17, no approval needed

The four rival-school seeds and the calibration harness are written. This
needed no decision from Roland and spent nothing: it is all API-free.

| Item | What |
|---|---|
| `tasks/japan_fp/seeds/` | Four rival doctrines — autonomous rearmament, accommodation, status-quo-plus, middle-power internationalism — each a standalone program the evaluator loads exactly like an evolved individual. |
| `scripts/m1_calibration.py` | Scores all five portfolios across all three scenarios and writes the KICKOFF Stage B table to `runs/m1/`. Estimated cost of a real run: **$0.11** against the $1 ceiling. |
| `tests/test_seeds.py` | 45 tests, including that the four schools are materially distinct doctrines rather than variants of one position. |

Each seed is aimed at a specific rubric rule so that a miscalibrated rubric
fails visibly: accommodation tests scenario-sensitivity (rule 5),
status-quo-plus tests the ±0.5 marginal anchor as the deliberate near-twin of
December 2022, middle-power internationalism tests diminishing returns
(rule 3), and autonomous rearmament tests score backfire (rule 2). The
reasoning is in `tasks/japan_fp/seeds/README.md`.

**The judge remains locked.** `mode: mock`, `stage_b_authorized: false`. The
mock run produces 38.8475 for all five portfolios, which is correct and proves
only the harness — the doctrines cannot separate until a real judge has an
opinion.

---

## Pending

| # | Decision | Needed by |
|---|---|---|
| 1 | Stage B go + an **`ANTHROPIC_API_KEY`** (ceiling USD 1; M1 estimated at $0.11). The judge is Anthropic per the M0 decision, so an OpenAI key does not unblock this — see `API_KEYS.md`. | before M1 |
| 2 | Review of the mutation-ensemble model list in `configs/*.yaml` — four models across mixed tiers, but your API access to each is unverified and two ids (`gpt-5.4`, `gemini-3-flash-preview`) are placeholders | before the pilot |
| 3 | Second judge family for the judge-swap check (RESEARCH_DESIGN §4) | M4 |
