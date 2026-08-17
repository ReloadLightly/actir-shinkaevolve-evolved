"""The frozen judge: the only modelled step in the whole pipeline.

RESEARCH_DESIGN section 2.2. One LLM, pinned to an exact model version,
temperature 0, cached by content hash, and excluded from the mutation
ensemble. Per scenario it receives Japan's 2025 baseline, the scenario
vignette, the portfolio as JSON (never the code), and an anchored rubric; it
returns a delta per Lowy measure plus a one-sentence causal mechanism.

Fail-closed by construction (KICKOFF hard rule 1):

* ``mode`` defaults to ``mock``, which returns all-zero deltas and makes no
  network call of any kind.
* Real calls additionally require ``stage_b_authorized: true`` in the config
  *and* a pinned model id. Missing either raises before any client is built.

Every real call is written to the cache directory as request + response, and
appended to a JSONL ledger with token counts and cost. The cache is the audit
trail (KICKOFF hard rule 5).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from lowy import DELTA_MAX, DELTA_MIN, MEASURES

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------

MOCK = "mock"
REAL = "real"

#: Per-million-token list prices, USD. Checked 2026-08-17 against the Claude
#: pricing table. The ledger records the rate it used, so a later price change
#: does not silently rewrite the cost history of an earlier run.
PRICING_USD_PER_MTOK: Dict[str, Dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 1.00, "output": 5.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
}


@dataclass(frozen=True)
class JudgeConfig:
    """Everything that identifies one judge. Part of the cache key.

    ``temperature`` is only sent to models that accept it. On the Claude 5
    family (Opus 5, Sonnet 5, Fable 5) sampling parameters were removed and a
    request carrying ``temperature`` returns HTTP 400, so the default judge is
    Haiku 4.5 — cheap, frozen, boring, and it still takes temperature 0.
    See ``docs/JUDGE_MODEL_NOTE.md``.
    """

    mode: str = MOCK
    provider: str = "anthropic"
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.0
    max_tokens: int = 2000
    prompt_version: str = "draft-0"
    stage_b_authorized: bool = False
    cache_dir: str = "tasks/japan_fp/judge/cache"
    ledger_path: str = "runs/ledger/judge_calls.jsonl"
    #: Models that reject the `temperature` parameter outright (HTTP 400).
    no_sampling_params: Tuple[str, ...] = (
        "claude-opus-5",
        "claude-sonnet-5",
        "claude-fable-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
    )

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> "JudgeConfig":
        if not data:
            return cls()
        known = set(cls.__dataclass_fields__)  # type: ignore[attr-defined]
        unknown = sorted(set(data) - known)
        if unknown:
            raise KeyError(f"unknown judge config keys: {unknown}")
        kwargs = dict(data)
        if "no_sampling_params" in kwargs:
            kwargs["no_sampling_params"] = tuple(kwargs["no_sampling_params"])
        return cls(**kwargs)

    @classmethod
    def load(cls, path: Optional[str] = None) -> "JudgeConfig":
        """Load from YAML. Env var JAPAN_FP_JUDGE_CONFIG overrides the path."""
        resolved = path or os.environ.get("JAPAN_FP_JUDGE_CONFIG")
        if not resolved:
            repo_root = Path(__file__).resolve().parents[3]
            resolved = str(repo_root / "configs" / "judge.yaml")
        config_path = Path(resolved)
        if not config_path.is_file():
            return cls()
        import yaml  # imported here so the mock path has no hard dependency

        with config_path.open("r", encoding="utf-8") as handle:
            return cls.from_mapping(yaml.safe_load(handle) or {})

    @property
    def sends_temperature(self) -> bool:
        return not any(self.model.startswith(m) for m in self.no_sampling_params)

    def identity(self) -> Dict[str, Any]:
        """The judge's identity, as it enters the cache key."""
        return {
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature if self.sends_temperature else None,
            "prompt_version": self.prompt_version,
        }


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


@dataclass
class JudgeVerdict:
    """One judge call: per-measure deltas plus the causal mechanism sentences."""

    scenario_id: str
    deltas: Dict[str, float]
    mechanisms: Dict[str, str]
    cache_key: str
    cached: bool = False
    mocked: bool = False
    usage: Dict[str, int] = field(default_factory=dict)
    cost_usd: float = 0.0
    raw: Dict[str, Any] = field(default_factory=dict)


def zero_verdict(scenario_id: str, cache_key: str = "mock") -> JudgeVerdict:
    return JudgeVerdict(
        scenario_id=scenario_id,
        deltas={m: 0.0 for m in MEASURES},
        mechanisms={m: "MOCK: no judge call was made." for m in MEASURES},
        cache_key=cache_key,
        mocked=True,
    )


# --------------------------------------------------------------------------
# Response schema: 8 deltas + 8 mechanism sentences, nothing else
# --------------------------------------------------------------------------


def _response_schema() -> Dict[str, Any]:
    measure_entry = {
        "type": "object",
        "properties": {
            "delta": {
                "type": "number",
                "description": (
                    f"Change on the Lowy 0-100 scale by 2030, "
                    f"between {DELTA_MIN} and {DELTA_MAX}."
                ),
            },
            "mechanism": {
                "type": "string",
                "description": "One sentence naming the causal mechanism.",
            },
        },
        "required": ["delta", "mechanism"],
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {m: dict(measure_entry) for m in MEASURES},
        "required": list(MEASURES),
        "additionalProperties": False,
    }


RESPONSE_SCHEMA = _response_schema()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


# --------------------------------------------------------------------------
# The client
# --------------------------------------------------------------------------


class JudgeClient:
    """Content-hash-cached client for the frozen judge.

    Usage::

        client = JudgeClient(JudgeConfig.load())
        verdict = client.score(
            scenario_id="S1",
            scenario_text=...,
            prompt_text=...,
            portfolio=portfolio.to_dict(),
        )
    """

    def __init__(
        self, config: Optional[JudgeConfig] = None, repo_root: Optional[Path] = None
    ) -> None:
        self.config = config or JudgeConfig.load()
        self.repo_root = repo_root or Path(__file__).resolve().parents[3]
        if self.config.mode not in {MOCK, REAL}:
            raise ValueError(
                f"judge mode must be {MOCK!r} or {REAL!r}, got {self.config.mode!r}"
            )

    # -- paths -------------------------------------------------------------

    def _abs(self, relative: str) -> Path:
        path = Path(relative)
        return path if path.is_absolute() else self.repo_root / path

    @property
    def cache_dir(self) -> Path:
        return self._abs(self.config.cache_dir)

    @property
    def ledger_path(self) -> Path:
        return self._abs(self.config.ledger_path)

    # -- cache key ---------------------------------------------------------

    def cache_key(
        self,
        scenario_id: str,
        scenario_text: str,
        prompt_text: str,
        portfolio: Mapping[str, Any],
    ) -> str:
        """Hash of everything that could change the answer.

        Includes the judge's identity, the frozen scenario and rubric texts,
        the response schema, and the portfolio — so a rubric edit or a model
        change invalidates the cache instead of silently reusing old verdicts.
        """
        material = {
            "judge": self.config.identity(),
            "scenario_id": scenario_id,
            "scenario_sha256": _sha256(scenario_text),
            "prompt_sha256": _sha256(prompt_text),
            "schema_sha256": _sha256(_canonical(RESPONSE_SCHEMA)),
            "portfolio": portfolio,
        }
        return _sha256(_canonical(material))

    # -- public API --------------------------------------------------------

    def score(
        self,
        scenario_id: str,
        scenario_text: str,
        prompt_text: str,
        portfolio: Mapping[str, Any],
    ) -> JudgeVerdict:
        """Score one portfolio under one scenario.

        The judge never sees the program, only ``portfolio`` — the JSON the
        validity gate already accepted.
        """
        key = self.cache_key(scenario_id, scenario_text, prompt_text, portfolio)

        if self.config.mode == MOCK:
            return zero_verdict(scenario_id, key)

        cached = self._read_cache(key)
        if cached is not None:
            verdict = self._verdict_from_payload(scenario_id, key, cached)
            verdict.cached = True
            return verdict

        self._assert_real_calls_authorized()
        payload = self._call_api(scenario_id, scenario_text, prompt_text, portfolio)
        self._write_cache(key, payload)
        self._append_ledger(key, scenario_id, payload)
        return self._verdict_from_payload(scenario_id, key, payload)

    # -- fail-closed gate --------------------------------------------------

    def _assert_real_calls_authorized(self) -> None:
        """KICKOFF hard rule 1: no real LLM call before Roland authorizes Stage B."""
        if self.config.mode != REAL:
            raise RuntimeError("internal error: real call attempted in mock mode")
        if not self.config.stage_b_authorized:
            raise RuntimeError(
                "Refusing to make a real judge call: judge config has "
                "stage_b_authorized=false. Stage B must be authorized explicitly "
                "before any LLM call is made (KICKOFF hard rule 1)."
            )
        if not self.config.model:
            raise RuntimeError("Refusing to make a real judge call: no model pinned.")
        if self.config.provider != "anthropic":
            raise RuntimeError(
                f"provider {self.config.provider!r} has no implemented backend; "
                "only 'anthropic' is wired up. Choosing the judge model is an M0 "
                "decision (RESEARCH_DESIGN section 8)."
            )

    # -- the one place that touches the network ----------------------------

    def _call_api(
        self,
        scenario_id: str,
        scenario_text: str,
        prompt_text: str,
        portfolio: Mapping[str, Any],
    ) -> Dict[str, Any]:
        import anthropic  # imported here: Stage A never needs the dependency

        user_content = (
            f"{prompt_text}\n\n"
            f"## Scenario {scenario_id}\n\n{scenario_text}\n\n"
            "## Portfolio under assessment (JSON)\n\n"
            "```json\n"
            f"{json.dumps(dict(portfolio), indent=2, ensure_ascii=False)}\n"
            "```\n\n"
            "Return one delta and one mechanism sentence per Lowy measure."
        )

        request: Dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": user_content}],
            "output_config": {
                "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}
            },
        }
        if self.config.sends_temperature:
            request["temperature"] = self.config.temperature

        client = anthropic.Anthropic()
        response = client.messages.create(**request)

        if response.stop_reason == "refusal":
            raise RuntimeError(
                f"judge refused to score scenario {scenario_id}: "
                f"{getattr(response, 'stop_details', None)}"
            )
        if response.stop_reason == "max_tokens":
            raise RuntimeError(
                f"judge response truncated for scenario {scenario_id}; "
                f"raise max_tokens above {self.config.max_tokens}"
            )

        text = next((b.text for b in response.content if b.type == "text"), "")
        parsed = json.loads(text)

        usage = {
            "input_tokens": int(getattr(response.usage, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(response.usage, "output_tokens", 0) or 0),
        }
        return {
            "scenario_id": scenario_id,
            "judge": self.config.identity(),
            "request_user_content_sha256": _sha256(user_content),
            "request_user_content": user_content,
            "response_text": text,
            "parsed": parsed,
            "usage": usage,
            "cost_usd": self._cost(usage),
            "stop_reason": response.stop_reason,
            "response_id": getattr(response, "id", None),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def _cost(self, usage: Mapping[str, int]) -> float:
        rates = PRICING_USD_PER_MTOK.get(self.config.model)
        if rates is None:
            return 0.0
        return (
            usage.get("input_tokens", 0) * rates["input"]
            + usage.get("output_tokens", 0) * rates["output"]
        ) / 1_000_000

    # -- cache and ledger --------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def _read_cache(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._cache_path(key)
        if not path.is_file():
            return None
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _write_cache(self, key: str, payload: Mapping[str, Any]) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self._cache_path(key)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(dict(payload), handle, indent=2, ensure_ascii=False, sort_keys=True)

    def _append_ledger(
        self, key: str, scenario_id: str, payload: Mapping[str, Any]
    ) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": payload.get("created_at"),
            "cache_key": key,
            "scenario_id": scenario_id,
            "model": self.config.model,
            "prompt_version": self.config.prompt_version,
            "usage": payload.get("usage", {}),
            "cost_usd": payload.get("cost_usd", 0.0),
            "pricing_usd_per_mtok": PRICING_USD_PER_MTOK.get(self.config.model),
        }
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # -- parsing -----------------------------------------------------------

    def _verdict_from_payload(
        self, scenario_id: str, key: str, payload: Mapping[str, Any]
    ) -> JudgeVerdict:
        parsed = payload.get("parsed") or {}
        deltas: Dict[str, float] = {}
        mechanisms: Dict[str, str] = {}
        for measure in MEASURES:
            entry = parsed.get(measure) or {}
            try:
                raw_delta = float(entry.get("delta", 0.0))
            except (TypeError, ValueError):
                raw_delta = 0.0
            deltas[measure] = min(DELTA_MAX, max(DELTA_MIN, raw_delta))
            mechanisms[measure] = str(entry.get("mechanism", "")).strip()
        return JudgeVerdict(
            scenario_id=scenario_id,
            deltas=deltas,
            mechanisms=mechanisms,
            cache_key=key,
            usage=dict(payload.get("usage", {})),
            cost_usd=float(payload.get("cost_usd", 0.0)),
            raw=dict(payload),
        )
