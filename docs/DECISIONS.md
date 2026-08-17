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

## Pending

| # | Decision | Needed by |
|---|---|---|
| 1 | Stage B go + API key (ceiling USD 1) | before M1 |
| 2 | Review of the mutation-ensemble model list in `configs/*.yaml` — four models across mixed tiers, but your API access to each is unverified | before the pilot |
| 3 | Second judge family for the judge-swap check (RESEARCH_DESIGN §4) | M4 |
