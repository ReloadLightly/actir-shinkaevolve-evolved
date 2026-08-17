# API keys: which ones, for what, and when

Two different layers of this project call LLMs, and they need **different
keys at different stages**. Providing the wrong one is the easiest way to
arrive at a gate and find you cannot pass it.

## The two layers

| Layer | What it is | Provider | Needed at |
|---|---|---|---|
| **The judge** | The frozen world model. Scores portfolios, returns 8 deltas. One pinned model, temperature 0, cached. | Anthropic **or** OpenAI — both backends implemented; which one is an open decision | **M1** (next gate) |
| **The second judge** | A different model family, for the judge-swap check (RESEARCH_DESIGN §4). | Whichever the judge is not | **M4** |
| **The mutation ensemble** | The four models that write candidate programs. | Mixed: Anthropic, OpenAI, Google | **Stage C** (the pilot) |

The judge is *never* a member of the mutation ensemble (KICKOFF hard rule 2),
so those two lists never overlap.

## What this means in practice

**Both providers now work as the judge.** As of 2026-08-17 the client has an
OpenAI backend alongside the Anthropic one, because §4's judge-swap check
needs a second model family regardless of what M1 uses. Both send byte-identical
prompts, so a swap differs in the model and nothing else.

**Decided 2026-08-17: the judge is OpenAI `gpt-4.1-2025-04-14`.** So:

- **M1 needs `OPENAI_API_KEY`.** 15 calls, ~$0.19 against a $1 ceiling.
- **M4 needs `ANTHROPIC_API_KEY`** for the judge-swap check against
  `claude-haiku-4-5-20251001`, a different model family per §4.

Both keys are eventually wanted, just not at the same gate.

## Check before you authorize

`--estimate` now preflights everything checkable without making a call:

```bash
python scripts/m1_calibration.py --estimate
```

```
Preflight
  [ok] OPENAI_API_KEY is set
  [ok] gpt-4.1-2025-04-14 has a price entry
  [ok] temperature 0.0 will be sent (deterministic, per RESEARCH_DESIGN 2.2)
  [--] mode=mock, stage_b_authorized=False  (locked: no real call possible)
```

An armed run whose preflight fails refuses to start rather than dying partway
through having already spent money.

**Verify the OpenAI prices before spending.** The OpenAI rows in
`PRICING_USD_PER_MTOK` are from memory and flagged as unverified in the code.
The Anthropic rows were checked. Run `--estimate` and sanity-check the figure
against the ceiling before authorizing.

## Setting them

Environment variables, read at runtime by the SDKs:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."      # needed for M1
export OPENAI_API_KEY="sk-..."             # needed for Stage C, not before
export GOOGLE_API_KEY="..."                # ditto, if Gemini stays in the ensemble
```

The names matter exactly. The Anthropic SDK reads `ANTHROPIC_API_KEY` and the
OpenAI SDK reads `OPENAI_API_KEY`; neither will find a key under any other
name. `OPEN_API_KEY` in particular is read by nothing.

For a local file instead, put them in `.env` (already gitignored) and load it:

```bash
set -a; source .env; set +a
```

In a Claude Code on the web environment, set them under the environment's
variables. **Changes take effect in the next session, not the running one** —
a container started before the variable was added will not see it. Check with:

```bash
python -c "import os; print('ANTHROPIC_API_KEY' in os.environ)"
```

Never commit a key. `.gitignore` covers `.env`; nothing else in the repo
should ever contain one.

## A key alone authorizes nothing

Adding a key does not enable a call. Stage B additionally requires *both*
flags in `configs/judge.yaml`:

```yaml
mode: real
stage_b_authorized: true
```

Either alone raises before the network is touched, and `--real` on the M1
script is not authorization either — it only stops the script from reporting
mock zeros as if they were judgements. This is KICKOFF hard rule 1 and it is
enforced in code, not by convention. Flipping those flags is a decision taken
in chat, and it is recorded in `DECISIONS.md` when it happens.

So the safe order is: add the key, confirm the environment sees it, run
`python scripts/m1_calibration.py --estimate` to check the cost against the
ceiling, *then* authorize Stage B.

## The ensemble list is still a placeholder

`configs/pilot.yaml` and `configs/main.yaml` name four mutation models. Two of
them are placeholders that may not correspond to models you can actually
reach, and this has never been verified against your accounts:

- `gpt-5.4` — placeholder
- `gemini-3-flash-preview` — placeholder

Before Stage C these need replacing with real ids you have access to, or the
pilot will fail on its first mutation. That is pending decision 2 in
`DECISIONS.md`. It does not block M1.
