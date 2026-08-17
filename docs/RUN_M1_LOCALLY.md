# Running M1 from your own machine

The recommended way to spend the first real money on this project. Your API
key never leaves your laptop, no cloud environment variable is involved, and
the shipped repo stays locked.

M1 is a single script. It needs **no ShinkaEvolve**, no GPU, and about
**$0.04**.

## Why this is the better path, not a fallback

The judge is the only thing that makes API calls at M1 — 15 of them. There is
nothing to gain from running that in a cloud session, and one clear thing to
lose: a credential sitting in a cloud environment that Anthropic's own docs
say should not hold credentials.

Two things that look like they should carry the key here, and do not:

| Where you might have put it | What reads it | Reaches a cloud session? |
|---|---|---|
| GitHub repo → Settings → Secrets | GitHub **Actions** workflows only | **No** |
| claude.ai/code → cloud icon → env vars | cloud sessions | Yes, on next start |
| Your own shell | whatever you run locally | n/a — this is the path below |

A GitHub repository secret is invisible to a session that clones the repo.
That is deliberate, and it is why a key set there produces "OPENAI_API_KEY is
NOT set" no matter how many sessions you restart.

## Five commands

```bash
git clone https://github.com/ReloadLightly/actir-shinkaevolve-evolved
cd actir-shinkaevolve-evolved
git checkout claude/project-kickoff-7sdnab
pip install -r requirements.txt openai

cp configs/judge.local.yaml.example configs/judge.local.yaml
export JAPAN_FP_JUDGE_CONFIG=configs/judge.local.yaml
export OPENAI_API_KEY=sk-...        # your key, only ever in your shell
```

Check before spending — this makes no call:

```bash
python scripts/m1_calibration.py --estimate
```

You want all `[ok]` and an `ARMED` line:

```
Preflight
  [ok] OPENAI_API_KEY is set
  [ok] gpt-4.1-mini-2025-04-14 has a price entry
  [ok] temperature 0.0 will be sent (deterministic, per RESEARCH_DESIGN 2.2)
  [--] mode=real, stage_b_authorized=True  (ARMED: real calls will be made)
```

Then run it:

```bash
# The calibration table, ~$0.04
python scripts/m1_calibration.py --real

# Or the version that also checks whether the cheap judge is good enough, ~$0.23
python scripts/m1_calibration.py --real --compare-with gpt-4.1
```

## Which of the two to run

Run **`--compare-with gpt-4.1`**. It scores the five doctrines twice — once
with the configured `gpt-4.1-mini`, once with the 5×-dearer `gpt-4.1` — and
reports the rank correlation between the two orderings.

The extra $0.19 buys the answer to the question that decides whether the rest
of the budget is worth spending at all: **is the cheap judge measuring the
same thing as the dear one?** The judge is the fitness function. If it cannot
rank five deliberately-different doctrines the way a stronger model does, every
number downstream is noise, and you want to know that now rather than after
the search.

## What to look for in the output

The script prints the questions with the table. In short:

1. **Ordering** — is the ranking one a Japan specialist would call arguable?
   It need not match your view; it must be defensible.
2. **Scenario sensitivity** — accommodation should look very different under
   S2 (Taiwan) and S3 (US retrenchment). A flat spread means the judge is
   ignoring the scenario.
3. **The near-twin test** — December 2022 and status-quo-plus are deliberately
   close. Separation of much more than a point means the ±0.5 anchor is not
   landing, and every small mutation will read as signal.
4. **Diminishing returns** — middle-power internationalism spends at 85.4 and
   at 11.3. Similar movement at both means rule 3 is not landing.
5. **Score backfire** — autonomous rearmament should cost something somewhere.
   All-positive means the judge is adding effort, not measuring consequence.

If 3, 4 or 5 fail, the rubric needs fixing before the freeze. That is exactly
what M1 is for, and why the freeze was deferred until after it.

## Afterwards

The run writes its audit trail locally:

```
tasks/japan_fp/judge/cache/     full request + response per call
runs/ledger/judge_calls.jsonl   tokens and cost per call
runs/m1/m1_calibration.{json,md}
```

Commit and push the cache and the ledger — they are tracked deliberately
(KICKOFF hard rule 5, the cache is the audit trail). `runs/m1/` is gitignored;
paste the table into the session instead, or `git add -f` it if you want it
kept.

```bash
git add tasks/japan_fp/judge/cache runs/ledger
git commit -m "M1 calibration: 15 judge calls, real"
git push -u origin claude/project-kickoff-7sdnab
```

Then paste the table back and we read it together.

## Why `configs/judge.local.yaml` rather than editing the shipped file

`configs/judge.yaml` ships with `mode: mock` and `stage_b_authorized: false`,
and `tests/test_end_to_end_mock.py` keeps it that way permanently. Editing it
to run locally would risk committing an armed config, and would make "is this
repo safe" depend on remembering to revert.

Instead the override lives in a file that git cannot see, which you create
deliberately. `JudgeConfig.load()` reads `JAPAN_FP_JUDGE_CONFIG` if it is set
and falls back to the shipped config otherwise — so the shipped guarantee
stays true no matter what you run locally, and unsetting one variable disarms
everything.

```bash
unset JAPAN_FP_JUDGE_CONFIG    # back to the locked mock judge
```
