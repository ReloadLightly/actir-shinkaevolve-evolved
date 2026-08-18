#!/usr/bin/env python3
"""Can the mutation ensemble actually produce a valid individual?

    python scripts/mutation_smoke.py --estimate      # free
    python scripts/mutation_smoke.py --run           # ~$0.06

M1 validated the *judge* path. The *mutation* path has never made a single
call, and it is the half that spends the money: RESEARCH_DESIGN §3 predicted,
and docs/BUDGET.md confirmed, that mutation dominates cost by roughly 8:1.

The specific risk this retires: an LLM that cannot reliably emit a
`build_policy()` whose shares sum to exactly 1.0 across 30 dials. That is a
fiddly arithmetic constraint, and a model that gets it wrong most of the time
produces individuals the validity gate rejects — costing a full mutation call
each while contributing nothing. At $2.00 per Stage D arm, a 50% rejection rate
halves an already thin budget. Nobody has checked whether either configured
model can do it.

It also answers a second question cheaply: **is the ensemble really two
models?** `gpt-4.1-nano` is 20× cheaper than `gpt-4.1` and carries the cheap
tier of the mixed-tier requirement. If nano cannot produce valid portfolios,
the UCB1 bandit will learn to ignore it and the ensemble collapses to one
model — which is a finding for the methods section, and an argument for
spending the slot on a different provider.

What it does: sends each configured mutation model the real task system message
and the real seed program, asks for a rewritten EVOLVE-BLOCK, splices the reply
back into the program, executes it, and runs the result through the actual
validity gate. Exactly the loop ShinkaEvolve performs, minus the engine.

Fail-closed: refuses without `--run`, without `OPENAI_API_KEY`, and prints the
estimate first.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_DIR = REPO_ROOT / "tasks" / "japan_fp"
if str(TASK_DIR) not in sys.path:
    sys.path.insert(0, str(TASK_DIR))

import evaluate as evaluator  # noqa: E402
import yaml  # noqa: E402
from judge.client import PRICING_USD_PER_MTOK  # noqa: E402

SEED_PROGRAM = TASK_DIR / "initial.py"
BLOCK_START = "# EVOLVE-BLOCK-START"
BLOCK_END = "# EVOLVE-BLOCK-END"

#: Generous, because the block is ~110 lines of dense Python.
EST_IN, EST_OUT = 4200, 3200
MAX_OUTPUT_TOKENS = 6000

INSTRUCTION = """\
Rewrite the EVOLVE-BLOCK below so the portfolio pursues a materially different \
strategy from the one it currently encodes. Change the allocation substantially \
- this is a search step, not a tidy-up.

Hard requirements, all checked by an automatic validity gate before your work is \
scored:

1. The 30 `share` values are proportions of one finite effort budget and are normalised automatically, so their absolute sum does not matter - but the trade-off does: raising one dial must come at the expense of others.
2. Use ONLY the 30 dial names already present. They are the Lowy Index's own \
submeasures and no others exist. This applies everywhere a dial is named, \
INCLUDING a phase's `focus` list. To propose something the 30 dials cannot \
express, use `custom_initiatives` - that is what the slot is for.
3. Every dial with a share above 0 needs a non-empty `how` string of at most \
240 characters.
4. Phases must be ordered and lie inside 2026-2030.
5. EVERY value in `defence_spending_path` must lie between 0.5 and 3.5 per cent \
of GDP. 3.5 is already far beyond Japan's 2022 decision; anything above it is \
not a defence budget any government would table.
6. Every custom initiative must name the submeasures it targets.

Return ONLY the Python code of the replacement block, starting with \
`def build_policy() -> PolicyPortfolio:`. No prose before or after, no markdown \
fences.
"""


def _load_ensemble(config_path: Path) -> List[str]:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return list(config["evo_config"].get("llm_models") or [])


def _seed_block() -> str:
    text = SEED_PROGRAM.read_text(encoding="utf-8")
    start = text.index(BLOCK_START) + len(BLOCK_START)
    return text[start:text.index(BLOCK_END)].strip("\n")


def _splice(new_block: str) -> str:
    text = SEED_PROGRAM.read_text(encoding="utf-8")
    head = text[:text.index(BLOCK_START) + len(BLOCK_START)]
    tail = text[text.index(BLOCK_END):]
    return f"{head}\n{new_block}\n{tail}"


def _strip_fences(reply: str) -> str:
    """Models often wrap code in markdown despite being told not to."""
    fenced = re.search(r"```(?:python)?\s*\n(.*?)```", reply, re.S)
    body = fenced.group(1) if fenced else reply
    index = body.find("def build_policy")
    return body[index:].rstrip() if index != -1 else body.strip()


def _call_model(model: str, prompt: str) -> Dict[str, Any]:
    import openai

    request: Dict[str, Any] = {
        "model": model,
        "max_completion_tokens": MAX_OUTPUT_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    # Same rule as the judge: the GPT-5 series rejects `temperature` outright.
    if not model.startswith(("gpt-5", "o1", "o3", "o4")):
        request["temperature"] = 1.0        # mutation wants variety, not determinism

    response = openai.OpenAI().chat.completions.create(**request)
    choice = response.choices[0]
    usage = response.usage
    return {
        "text": choice.message.content or "",
        "finish_reason": choice.finish_reason,
        "input_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "output_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
    }


def _cost(model: str, usage: Dict[str, Any]) -> float:
    rates = PRICING_USD_PER_MTOK.get(model)
    if rates is None:
        return 0.0
    return (usage["input_tokens"] * rates["input"]
            + usage["output_tokens"] * rates["output"]) / 1e6


def _evaluate_reply(reply_text: str) -> Dict[str, Any]:
    """Splice, execute, gate. Exactly what ShinkaEvolve would do next."""
    block = _strip_fences(reply_text)
    outcome: Dict[str, Any] = {"parsed": False, "executed": False, "valid": False,
                               "reasons": [], "total_share": None}
    program = _splice(block)

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "candidate.py"
        path.write_text(program, encoding="utf-8")
        try:
            compile(program, str(path), "exec")
            outcome["parsed"] = True
        except SyntaxError as exc:
            outcome["reasons"] = [f"SyntaxError: {exc}"]
            return outcome

        import importlib.util

        spec = importlib.util.spec_from_file_location("candidate", path)
        module = importlib.util.module_from_spec(spec)      # type: ignore[arg-type]
        try:
            os.environ["JAPAN_FP_TASK_DIR"] = str(TASK_DIR)
            spec.loader.exec_module(module)                 # type: ignore[union-attr]
            portfolio = module.build_policy()
            outcome["executed"] = True
        except Exception as exc:                            # noqa: BLE001
            outcome["reasons"] = [f"{type(exc).__name__}: {exc}"]
            return outcome

    valid, reasons = evaluator.validity_gate(portfolio)
    outcome["valid"] = valid
    outcome["reasons"] = reasons
    try:
        outcome["total_share"] = round(portfolio.total_share(), 6)
    except Exception:                                       # noqa: BLE001
        pass
    return outcome


def estimate(models: List[str], repeats: int = 1) -> None:
    repeats = max(1, int(repeats))
    print(f"Mutation smoke test: {len(models)} models, {repeats} call(s) each")
    total = 0.0
    for model in models:
        rates = PRICING_USD_PER_MTOK.get(model)
        if rates is None:
            print(f"  {model:22} no price entry")
            continue
        cost = repeats * (EST_IN * rates["input"] + EST_OUT * rates["output"]) / 1e6
        total += cost
        print(f"  {model:22} ~${cost:.4f}  "
              f"(~{EST_IN} in / ~{EST_OUT} out at ${rates['input']}/${rates['output']}"
              f"{f', x{repeats}' if repeats > 1 else ''})")
    print(f"  {'TOTAL':22} ~${total:.4f}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default="configs/pilot.yaml")
    parser.add_argument(
        "--repeats", type=int, default=1,
        help="attempts per model. 1 gives a binary that cannot "
             "distinguish 0%% from 30%%; the pilot decision needs a RATE, "
             "so use 3 or more when it matters.")
    parser.add_argument(
        "--models", default=None,
        help="comma-separated model override. Without it the config's "
             "llm_models are used. Use this to ask whether a gate failure "
             "is the prompt or the model tier -- the 2026-08-18 preflight "
             "could not tell, because pilot.yaml declares one model.")
    parser.add_argument("--estimate", action="store_true")
    parser.add_argument("--run", action="store_true",
                        help="actually call the models. Without this, nothing is spent.")
    parser.add_argument("--out", default="runs/mutation_smoke")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = REPO_ROOT / config_path
    models = ([m.strip() for m in args.models.split(",") if m.strip()]
              if args.models else _load_ensemble(config_path))
    if not models:
        print(f"{config_path} declares no llm_models", file=sys.stderr)
        return 2

    if args.estimate or not args.run:
        estimate(models, args.repeats)
        if not args.run:
            print("\nNothing was spent. Pass --run to make the calls.")
        return 0

    if not os.environ.get("OPENAI_API_KEY"):
        print("Refusing: OPENAI_API_KEY is not set.", file=sys.stderr)
        return 2

    prompt = f"{INSTRUCTION}\n\n```python\n{_seed_block()}\n```\n"

    repeats = max(1, int(args.repeats))
    results, spent = [], 0.0
    for model in models:
        for attempt in range(repeats):
            label = f"{model} ({attempt + 1}/{repeats})" if repeats > 1 else model
            print(f"  mutating with {label} ...", flush=True)
            try:
                reply = _call_model(model, prompt)
            except Exception as exc:                        # noqa: BLE001
                print(f"    call FAILED: {type(exc).__name__}: {exc}")
                results.append({"model": model, "attempt": attempt,
                                "call_failed": str(exc)})
                continue
            cost = _cost(model, reply)
            spent += cost
            outcome = _evaluate_reply(reply["text"])
            outcome.update({
                "model": model, "attempt": attempt, "cost_usd": round(cost, 6),
                "finish_reason": reply["finish_reason"],
                "input_tokens": reply["input_tokens"],
                "output_tokens": reply["output_tokens"],
            })
            results.append(outcome)

    print()
    print("| model                  | parsed | ran | gate | shares    | cost    |")
    print("|------------------------|--------|-----|------|-----------|---------|")
    for r in results:
        if "call_failed" in r:
            print(f"| {r['model']:22} | {'CALL FAILED':^31} |         |")
            continue
        share = f"{r['total_share']}" if r["total_share"] is not None else "-"
        print(f"| {r['model']:22} | {'yes' if r['parsed'] else 'NO':^6} | "
              f"{'yes' if r['executed'] else 'NO':^3} | "
              f"{'PASS' if r['valid'] else 'FAIL':^4} | {share:>9} | "
              f"${r['cost_usd']:.4f} |")

    print()
    for r in results:
        if r.get("reasons"):
            print(f"{r['model']} rejected for:")
            for reason in r["reasons"][:6]:
                print(f"    - {reason}")

    usable = [r for r in results if r.get("valid")]
    print()
    print("Gate pass rate per model")
    rates = {}
    for model in models:
        mine = [r for r in results if r["model"] == model]
        ok = sum(1 for r in mine if r.get("valid"))
        rate = ok / len(mine) if mine else 0.0
        rates[model] = {"passed": ok, "attempts": len(mine), "rate": round(rate, 4)}
        print(f"  {model:22} {ok}/{len(mine)}  ({rate:.0%})")
    print()
    print(f"Spent ${spent:.4f}. {len(usable)}/{len(results)} attempts produced a "
          f"portfolio the gate accepts.")
    if not usable:
        print("NONE of the configured mutation models can produce a valid "
              "individual. The pilot would spend its entire ceiling on gate "
              "rejections. Fix the ensemble or the task system message first.")
    elif len(usable) < len(results):
        print("Some attempts fail. In the real loop this is less fatal than it")
        print("looks: ShinkaEvolve feeds the gate's reason string back to the")
        print("model, so a rejection buys a corrected retry rather than nothing.")
        print("The rate still sets how much of the budget goes to retries, and")
        print("the UCB1 bandit will learn to avoid whichever model fails most.")

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "mutation_smoke.json").write_text(
        json.dumps({"spent_usd": round(spent, 6), "pass_rates": rates,
                    "results": results}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_dir / 'mutation_smoke.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
