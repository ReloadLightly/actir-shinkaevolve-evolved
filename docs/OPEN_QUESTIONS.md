# Open questions from Stage A

Where RESEARCH_DESIGN was ambiguous, I decided rather than blocked, and every
decision is recorded here with what it would take to reverse it. None of these
changes the architecture; all are one-line edits unless noted.

**Update, 2026-08-17: M0 approval resolved rows 7 and 8 and the bound in row 4.
See `DECISIONS.md`.** The rest still stand as my calls, reversible on request.

## Decisions I made (reversible; tell me and I change them)

| # | Question | What I did | Reverse by |
|---|---|---|---|
| 1 | The design says shares sum to 1 (§2.1) and to "100 ± ε" (§2.2). | Fractions summing to **1.0 ± 1e-6**. | `GateLimits.share_sum` |
| 2 | The `how` string is "capped" but no number is given. | **240 characters**. The seed's longest is 62, so there is ample room. | `GateLimits.how_char_cap` |
| 3 | No global bound on free text. Per-item caps alone cannot bound what the judge reads (30 × 240 = 7,200 chars). | Added a **6,000-character total budget** across all `how` strings, phase labels, and initiatives. The seed uses ~2,100. | `GateLimits.total_free_text_cap` |
| 4 | The gate must check "defence path within a feasibility bound, e.g. ≤ 3.5% GDP by 2030" — but the schema in §2.1 has no field carrying a GDP path. | Added `PolicyPortfolio.defence_spending_path()`, defaulting to Japan's actual December 2022 path (2% from 2027). It is **not a dial** and carries no share. Bound enforced at **[0.5%, 3.5%]** — **approved at M0**. | `GateLimits.defence_gdp_min/max`; removing the field would mean dropping the check |
| 5 | Nothing said how many phases or initiatives are allowed. | **1–6 phases, ≤6 initiatives**, ordered and inside the horizon. | `GateLimits` |
| 6 | Investing twice in the same dial is undefined. | **Last write wins**, silently. Rejecting it would make diff-edits brittle. | `PolicyPortfolio.invest` |
| 7 | Judge model unspecified (explicitly an M0 decision, §8). | **Decided at M0**: `claude-haiku-4-5-20251001`, temperature 0. See `JUDGE_MODEL_NOTE.md`. | new experiment, not an edit |
| 8 | The three scenario texts and the rubric are yours to write (§8). | **Approved at M0** as drafted. Still `status: DRAFT` — freeze deferred until the M1 table has been read. | Rewrite, then `python scripts/freeze.py --version <new>`; re-approval needed |

## Things worth your explicit attention

**The exact fitness is 38.8475, not 38.8.** The published index reports one
decimal. `combined_score` carries the unrounded value because rounding to 0.1
would erase most of the search signal — a policy worth +0.3 composite points
would be invisible. So the tests assert `round(score, 1) == 38.8` and the
console prints both. If you would rather the reported fitness be rounded, that
is a one-line change, but I would argue against it.

**Two spec deviations, both cosmetic.** KICKOFF names `EvolutionRunner`; the
class in the current ShinkaEvolve release is `ShinkaEvolveRunner`, so that is
what `run_evo.py` uses. And I added three modules KICKOFF does not list:
`lowy.py` (the index constants, so the weights are testable in isolation),
`_eval_harness.py` (lets `evaluate.py` run identically with or without
ShinkaEvolve installed), and `scripts/freeze.py`.

**The mutation-ensemble model list in the configs is a placeholder.** Four
models across mixed tiers per §3, with the judge model deliberately absent
(hard rule 2). But I have not verified your API access to each provider, and
the list should be reviewed before the pilot.

## Not decided — genuinely needs you

1. **Stage B authorization and an API key.** `configs/judge.yaml` ships with
   `mode: mock` and `stage_b_authorized: false`; both must flip before any real
   call. Offered at M0 and declined, so it stays locked. I will not change
   either without you saying so in chat.
2. **The four rival-school seeds for M1** (autonomous rearmament;
   accommodation; status-quo-plus; middle-power internationalism). Writing them
   needs no API access, but it is Stage B work and Stage B is not authorized,
   so I have not started. Say the word and they take one pass.
3. **The mutation-ensemble model list** in `configs/*.yaml`. Four models across
   mixed tiers per §3, judge deliberately absent — but your API access to each
   provider is unverified. Review before the pilot.
