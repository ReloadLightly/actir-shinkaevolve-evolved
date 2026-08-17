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

## M0 amendment — judge switched to the OpenAI tier, 2026-08-17

**Roland chose the OpenAI judge**, amending the M0 decision recorded above.
The M0 row for "Judge model" is superseded by this one; nothing else in the M0
approval changes.

| | Was (M0) | Now (M0 amended) |
|---|---|---|
| Provider | `anthropic` | `openai` |
| Model | `claude-haiku-4-5-20251001` | `gpt-4.1-2025-04-14` |
| Temperature | 0.0 | 0.0 |

**Why this is not a retreat from the M0 reasoning.** RESEARCH_DESIGN §2.2
names the paper's own judge tier explicitly: "they used gpt-5-nano / gpt-4.1 /
gpt-5-mini at temperature 0". The OpenAI tier is therefore the design's own
precedent, and `gpt-4.1` is named in it. The M0 choice of Haiku was made under
a constraint — that temperature 0 rules out the frontier Claude tier — and
that constraint is satisfied identically here.

**Why `gpt-4.1-2025-04-14` specifically**, among the three §2.2 names:

1. **It is a dated snapshot.** `JUDGE_MODEL_NOTE.md` argued that genuine
   pinning matters more than the model choice itself, because a floating alias
   can be repointed mid-experiment and silently break the pre-registration.
   That argument survives the provider change and selects the snapshot form
   over `gpt-5-mini`.
2. **It certainly accepts `temperature: 0`.** It is not a reasoning tier, so
   the design's determinism requirement is met literally rather than
   approximated. The reasoning tiers of both families reject the parameter.
3. **It certainly supports strict structured outputs**, so the 8 deltas and 8
   mechanism sentences stay schema-enforced rather than parsed out of prose.

**Cost.** ~$0.19 for M1 at 15 calls, against the $1 ceiling. Higher than the
Haiku figure ($0.11) because gpt-4.1 is a mid tier rather than a cheap one;
still far inside every ceiling in KICKOFF, and the content-hash cache means
re-scoring an unchanged portfolio is free.

**Two things to verify before spending**, both flagged in code and by
`--estimate`:

- The OpenAI price rows in `PRICING_USD_PER_MTOK` are from memory, not
  checked against the account. The Anthropic rows were checked.
- The exact snapshot id should be confirmed to resolve on your account. A bad
  id fails loudly on the first call rather than producing anything wrong, so
  this is a convenience check, not a safety one.

**The M4 judge-swap check is now cleanly set up.** `claude-haiku-4-5-20251001`
becomes the second judge from a different model family (RESEARCH_DESIGN §4).
Both backends send byte-identical prompts, so the rank correlation measures
judge agreement rather than prompt drift. Pending decision 3 is therefore
resolved in passing.

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

## Budget cut to USD 15 for the whole project — 2026-08-17

Roland set the total project budget at **USD 15**, superseding KICKOFF's
per-stage figures (Stage B 1 + Stage C 10 + Stage D 250 = 261). KICKOFF is
left unedited as the original spec; where the two disagree, 15 wins.

**This caught a latent breach.** The configs as written authorised **USD 290**
— seven Stage D runs at USD 40 plus a USD 10 pilot. Nothing had been spent, and
the judge was locked the whole time, but nothing in the repo would have stopped
it. There is now a `PROJECT_CEILING` test that fails if the authorised total
exceeds the budget.

Every ceiling was re-cut to fit; the full allocation and the reasoning are in
`BUDGET.md`. Ceilings were only ever lowered, per hard rule 4.

**The finding that matters more than the arithmetic:** at $2.00 per Stage D
arm, the mutation ensemble decides whether that buys **9 evaluations or 40**.
The current opus-led ensemble gives 9, which is not a search. Re-picking the
ensemble is now the highest-value open decision, and it subsumes pending
decision 2.

---

## Pending

| # | Decision | Needed by |
|---|---|---|
| 1 | Stage B go + an **`OPENAI_API_KEY` visible to the session** (M1 estimated at $0.19). Confirm with `python scripts/m1_calibration.py --estimate`, which preflights the key. | before M1 |
| 2 | **Re-pick the mutation ensemble.** Two of the four ids are placeholders that do not resolve (`gpt-5.4`, `gemini-3-flash-preview`); the other two are too expensive for a USD 15 budget. Constraints: `gpt-4.1-2025-04-14` is barred by hard rule 2, and `claude-haiku-4-5-20251001` is the M4 swap judge so using it as a mutator weakens that check. See `BUDGET.md`. | before the pilot |
| 3 | **How to spend the USD 15**: stage-gate it (recommended), six thin arms, or two deep arms. `BUDGET.md` costs all three. Choosing A costs nothing now and defers the rest until the pilot's ledger reports real per-evaluation cost. | before Stage D |
| ~~4~~ | ~~Second judge family for the judge-swap check~~ — **resolved 2026-08-17** by the M0 amendment: the judge is OpenAI, so `claude-haiku-4-5-20251001` is the M4 swap judge. Both backends are implemented and send identical prompts. | ~~M4~~ |
