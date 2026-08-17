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

> **Superseded the same day** on the model, not the provider: the judge is
> now `gpt-4.1-mini-2025-04-14`, not `gpt-4.1-2025-04-14`. See "Models
> re-picked on verified prices" below. The reasoning in this section still
> holds — it is why the judge is an OpenAI GPT-4.1 model at all.

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
| `scripts/m1_calibration.py` | Scores all five portfolios across all three scenarios and writes the KICKOFF Stage B table to `runs/m1/`. Estimated cost of a real run: **$0.038** against the $1 ceiling. |
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
The opus-led ensemble gave 9, which is not a search. That made re-picking the
ensemble the highest-value open decision — resolved immediately below.

---

## Models re-picked on verified prices — 2026-08-17

Roland asked for models at a fair price. Prices were checked against published
pricing rather than recalled, and that turned up two errors in my own earlier
work, both now corrected in code and docs:

1. **`gpt-5.4` is a real model.** I had listed it as a non-existent
   placeholder. It exists and is priced at $2.50/$15.00.
2. **`gpt-5-mini`, `gpt-5-nano` and `gpt-5` do not exist** under those names.
   I had priced all three from memory. The 2026 lineup is the GPT-5.4/5.5/5.6
   series. A test now fails if those ids return to the price table, since a
   price entry would let an unusable model pass the preflight.

**The finding that decided the ensemble: the entire OpenAI GPT-5 series
rejects the `temperature` parameter** — the same move Anthropic made on
Claude 5, and the same constraint that shaped the original M0 note. It rules
the series out twice: the judge needs `temperature: 0` (§2.2), and the
ensemble varies temperature as its diversity mechanism. So the usable OpenAI
models are the three GPT-4.1 tiers.

| | Was | Now | Effect |
|---|---|---|---|
| Judge | `gpt-4.1-2025-04-14` | **`gpt-4.1-mini-2025-04-14`** | M1 $0.19 → **$0.038**; judge cost per evaluation $0.038 → $0.0076 |
| Ensemble | opus-5, sonnet-5, gpt-5.4, gemini-3-flash | **`gpt-4.1` + `gpt-4.1-nano`** | ~9 → **~51** evaluations per Stage D arm |

The judge stays in §2.2's "cheap, frozen, boring" tier, still a dated snapshot,
still temperature 0. The ensemble keeps genuinely mixed tiers — `gpt-4.1`
costs 20× `gpt-4.1-nano`, so the UCB1 bandit has a real trade-off — but has
**two models where §3 asks for four**. That is a recorded deviation: the
temperature constraint plus hard rule 2 leaves only two usable OpenAI models.
Restoring four needs a second provider key. See `BUDGET.md`.

**M4 now needs an `ANTHROPIC_API_KEY`** for the judge-swap check, since the
judge is OpenAI and §4 requires a different model family.

---

## M1 run #1 — rubric NOT frozen, 2026-08-17

Roland ran M1 in GitHub Actions: 30 real judge calls, **$0.1869**, 2m14s.
Run 32058962532. Full analysis in `M1_FINDINGS.md`.

**Result: do not freeze, do not search.** M1 did its job at 1.2% of budget.

| Check | Verdict |
|---|---|
| Judge agreement (`gpt-4.1-mini` vs `gpt-4.1`) | Spearman **−0.300** — no reliable agreement |
| Dynamic range | `gpt-4.1` separates five opposite doctrines by **0.696** composite; max inter-judge disagreement is **0.921**. Noise exceeds signal. |
| Scenario sensitivity (rule 5) | **Fails.** Accommodation has the *smallest* spread (0.19) and scores worse under S3 than S2 — backwards. |
| Near-twin anchor | Passes. Dec 2022 vs status-quo-plus 0.22 apart. |
| Score backfire (rule 2) | Passes. |
| Diminishing returns (rule 3) | Partially — right direction, weak magnitude. |

**Root cause found: rule 5 asked for something the architecture forbids.** Each
judge call carries the rubric, *one* scenario, and the portfolio. The judge
never sees the other two scenarios, so "the same portfolio should not score the
same under S1, S2 and S3" was an instruction it could not act on. We asked for
a comparison and supplied one side of it.

**Rubric revision 2** (`FROZEN.json` → `0.3.0-m1-corrected`, still DRAFT):
names all three scenarios so rule 5 becomes actionable; shows the judge what a
delta is worth in composite points (±3 ≈ ±0.5, which it was never told); adds
rule 8 — score against December 2022 rather than against zero — and rule 9,
price what the portfolio gives up. Scenario texts unchanged.

Deliberately **not** done: widening the delta anchors to manufacture range.
That would fabricate signal and the search would optimise an artefact.

**One disagreement is kept, not tuned away.** `mini` ranks autonomous
rearmament first and middle-power last; `gpt-4.1` reverses exactly that pair.
That is two defensible world models disagreeing about whether force or
rule-making buys more index points — the oracle problem made measurable. If it
survives the fix, it is a finding for the paper, not a bug.

**NEEDS RE-APPROVAL.** The M0 approval attached to the old `judge_prompt.md`
bytes and is void for that file. Re-approval required before any scored run.

---

## Pending

| # | Decision | Needed by |
|---|---|---|
| 1 | Stage B go + an **`OPENAI_API_KEY` visible to the session** (M1 estimated at $0.038). Confirm with `python scripts/m1_calibration.py --estimate`, which preflights the key. | before M1 |
| 2 | **How to spend the USD 15**: stage-gate it (recommended), six thin arms, or two deep arms. `BUDGET.md` costs all three. Choosing A costs nothing now and defers the rest until the pilot's ledger reports real per-evaluation cost. | before Stage D |
| 3 | Optional: a second provider key (Google or Anthropic) to restore §3's four-model ensemble. Does not block anything. | before Stage D |
| 4 | An **`ANTHROPIC_API_KEY`** for the M4 judge-swap check against `claude-haiku-4-5-20251001`. | M4 |
| ~~4~~ | ~~Second judge family for the judge-swap check~~ — **resolved 2026-08-17** by the M0 amendment: the judge is OpenAI, so `claude-haiku-4-5-20251001` is the M4 swap judge. Both backends are implemented and send identical prompts. | ~~M4~~ |
