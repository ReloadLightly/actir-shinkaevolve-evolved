# KICKOFF — actir-shinkaevolve-evolved

**For Claude Code.** This repo implements the third experiment of the submission
*"After 2022: Japan's Search for a Novel Foreign Policy"*: ShinkaEvolve evolves
Japanese foreign-policy programs whose fitness is Japan's projected Lowy Asia
Power Index composite in 2030.

**Authoritative spec: `RESEARCH_DESIGN.md` in this repo. Read it fully before
writing any code.** Where this file and the spec disagree, the spec wins. Where
the spec is ambiguous, ask Roland in chat — never decide silently.

---

## Build stages — strictly in order, STOP at each stop line

### Stage A — API-free foundation (no LLM call anywhere, no API key needed)

Dependencies: Python 3.11+, ShinkaEvolve installed from
https://github.com/SakanaAI/ShinkaEvolve (Apache-2.0). Wire the task via
ShinkaEvolve's standard interface (EvolutionRunner / EvolutionConfig with
`init_program_path`, LocalJobConfig with `eval_program_path` — see the paper's
Appendix A and the repo's own docs).

Build:

- `tasks/japan_fp/schema.py` — `PolicyPortfolio`: exactly the 30 Lowy
  submeasure dials listed in RESEARCH_DESIGN §2.1 (share per dial, capped
  `how` string, sequence, `custom_initiatives`).
- `tasks/japan_fp/initial.py` — the December 2022 seed portfolio inside an
  EVOLVE-BLOCK (RESEARCH_DESIGN §2.1).
- `tasks/japan_fp/evaluate.py` — Stage 1 validity gate, Stage 2 judge call,
  Lowy aggregation with the published weights (RESEARCH_DESIGN §2.2);
  returns combined_score + public metrics + text_feedback.
- `tasks/japan_fp/judge/client.py` — judge client with **MOCK mode as
  default** (returns all-zero deltas), pinned model id read from config,
  temperature 0, content-hash cache of every real call.
- `tasks/japan_fp/scenarios/` — S1–S3 as placeholder files marked `DRAFT`.
- `tasks/japan_fp/judge_prompt.md` — rubric skeleton marked `DRAFT`
  (baseline table + anchored delta rubric per RESEARCH_DESIGN §2.2).
- `configs/` — pilot.yaml (30 generations), main.yaml (150), ablations/
  (values from RESEARCH_DESIGN §3).
- `tests/` — minimum four:
  1. Lowy weights × Japan's eight 2025 baseline scores reproduce 38.8
     (numbers in RESEARCH_DESIGN §2.2);
  2. validity gate rejects malformed portfolios (shares not summing to 1,
     caps exceeded, unknown dial names);
  3. end-to-end mock run: seed portfolio through evaluate.py with the mock
     judge → fitness exactly 38.8;
  4. frozen-file hash check for `scenarios/` and `judge_prompt.md`
     (records hashes; fails when a frozen file changes without a version bump).

**Done when:** pytest is green and the mock end-to-end run prints 38.8 with
zero network access. **STOP. Show Roland the full test output.**

### Stage B — M1 calibration smoke test (needs Roland's explicit go + API key; ceiling USD 1)

Write 4 rival-school seed portfolios (autonomous rearmament; accommodation;
status-quo-plus; middle-power internationalism). Judge scores them and the
2022 seed across the three scenarios. Output: one table (5 portfolios × 3
scenarios + composite). Roland judges plausibility of the ordering; if
approved, freeze `scenarios/` and `judge_prompt.md` (record hashes).
**STOP.**

### Stage C — Pilot (Roland's go; ceiling USD 10)

30 generations per configs/pilot.yaml. Output: fitness trajectory, evolution
tree, cost ledger. **STOP.**

### Stage D — Main run + baselines + ablations (Roland's go; total ceiling USD 250)

Per RESEARCH_DESIGN §4: main 150 evaluations; baselines random search and
hill climbing at matched budget; the three ablations; judge-swap re-scoring
of the top-20 archive.

---

## Hard rules (fail closed)

1. **No real LLM call before Stage B is authorized by Roland in chat.** The
   judge client defaults to MOCK; real mode requires an explicit config flag.
2. The judge is **one pinned model version, temperature 0, cached, and never
   a member of the mutation ensemble**.
3. `scenarios/` and `judge_prompt.md` are **frozen after Stage B approval**.
   Any later change = version bump + new experiment id, never an edit in place.
4. **Cost ceilings per stage as above.** On reaching 90% of a ceiling, stop
   and report. Never raise a ceiling yourself.
5. Every run writes: config snapshot, git hash, RNG seed, per-call token and
   cost ledger, and all judge inputs/outputs (the cache is the audit trail).
6. Prohibited claims (RESEARCH_DESIGN §6): never present results as Japan's
   optimal policy, as a forecast of actual Lowy Index values, or as a
   recommendation to act. The system explores and preserves possibilities.
7. Keep Roland oriented: at every STOP, report in at most ten plain sentences
   — what was built, what the tests show, what his single next decision is.

## What Roland provides at the gates

Stage B go + API key · approval of the scenario texts and judge rubric
(M0/M1) · pilot go · main-run go.
