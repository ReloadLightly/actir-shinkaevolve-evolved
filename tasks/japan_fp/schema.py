"""PolicyPortfolio: the genotype of the Japan foreign-policy task.

One individual is a Python program whose EVOLVE-BLOCK builds a PolicyPortfolio:
an allocation of Japan's marginal strategic effort for 2026-2030 across the 30
Lowy submeasure dials, with one capped sentence per dial saying *how* the
effort is spent, an ordered sequence of phases, and free-slot custom
initiatives (RESEARCH_DESIGN section 2.1).

Design notes that matter for evolution:

* Nothing here raises on bad input. Malformed calls are *recorded* in
  ``construction_errors`` so the Stage 1 validity gate in ``evaluate.py`` can
  return a readable reason string instead of a stack trace. Readable reasons
  are what the mutation LLM sees next.
* ``to_dict()`` is canonical and deterministic: it is both the judge's input
  and the content-hash cache key. Dial order is Lowy's order, never insertion
  order, and shares are rounded to 6 decimals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from lowy import DIALS, MEASURES, SUBMEASURES  # noqa: F401  (re-exported for tasks)

# --------------------------------------------------------------------------
# Caps and bounds. These are the free parameters of the Stage 1 validity gate.
# Defaults live here; configs/task.yaml may override them (RESEARCH_DESIGN
# section 8 lists "feasibility bounds in the validity gate" as an M0 decision).
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class GateLimits:
    """Bounds enforced by the Stage 1 validity gate."""

    horizon: Tuple[int, int] = (2026, 2030)
    share_sum: float = 1.0
    share_sum_tolerance: float = 1e-6
    # Shares are a NORMALISATION CONVENTION, not a substantive claim: only the
    # proportions carry policy meaning, because "marginal strategic effort" has
    # no natural unit. So a proposal whose shares sum to 0.67 is not proposing
    # less effort, it is proposing the same trade-offs with the arithmetic
    # botched. The preflight measured gpt-4.1-nano summing 30 terms to 0.67 and
    # being rejected for it -- a 100% rejection rate that would have burned the
    # pilot's whole ceiling on gate failures.
    #
    # So the gate REPAIRS rather than rejects, rescaling to sum to share_sum,
    # provided the raw sum is inside this band. Outside it the proposal is not
    # a botched allocation but an incoherent one, and is still rejected. The
    # repair rate is published as a metric, never hidden.
    share_sum_repair_min: float = 0.5
    share_sum_repair_max: float = 2.0
    how_char_cap: int = 240
    initiative_name_char_cap: int = 120
    initiative_rationale_char_cap: int = 400
    max_custom_initiatives: int = 6
    phase_label_char_cap: int = 160
    min_phases: int = 1
    max_phases: int = 6
    total_free_text_cap: int = 6000
    # Defence path feasibility (RESEARCH_DESIGN section 2.2: "defense path
    # within a feasibility bound, e.g. <= 3.5% GDP by 2030").
    defence_gdp_min: float = 0.5
    defence_gdp_max: float = 3.5

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> "GateLimits":
        if not data:
            return cls()
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        kwargs: Dict[str, Any] = {}
        for key, value in data.items():
            if key not in known:
                raise KeyError(f"unknown gate limit: {key!r}")
            if key == "horizon":
                kwargs[key] = (int(value[0]), int(value[1]))
            elif key in {
                "how_char_cap",
                "initiative_name_char_cap",
                "initiative_rationale_char_cap",
                "max_custom_initiatives",
                "phase_label_char_cap",
                "min_phases",
                "max_phases",
                "total_free_text_cap",
            }:
                kwargs[key] = int(value)
            else:
                kwargs[key] = float(value)
        return cls(**kwargs)


DEFAULT_LIMITS = GateLimits()

# Japan's actual defence-spending path as of December 2022 (the 2%-of-GDP
# decision of the three security documents), used as the seed default.
SEED_DEFENCE_PATH: Dict[int, float] = {
    2026: 1.6,
    2027: 2.0,
    2028: 2.0,
    2029: 2.0,
    2030: 2.0,
}


# --------------------------------------------------------------------------
# Value objects
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Dial:
    """One Lowy submeasure: how much marginal effort, and how it is spent."""

    dial_id: str
    share: float
    how: str


@dataclass(frozen=True)
class Phase:
    """One ordered phase of the 2026-2030 sequence."""

    years: Tuple[int, int]
    label: str
    focus: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Initiative:
    """A free-slot initiative. Must name the submeasures it targets."""

    name: str
    rationale: str
    targets: Tuple[str, ...]


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def _coerce_years(value: Any) -> Optional[Tuple[int, int]]:
    if isinstance(value, Mapping):
        value = (value.get("start"), value.get("end"))
    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return (int(value[0]), int(value[1]))
        except (TypeError, ValueError):
            return None
    return None


def _coerce_targets(value: Any) -> Tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(_as_text(v) for v in value)
    return ()


# --------------------------------------------------------------------------
# The genotype
# --------------------------------------------------------------------------


class PolicyPortfolio:
    """An allocation of Japan's marginal strategic effort over 2026-2030.

    Example (the shape the EVOLVE-BLOCK produces)::

        p = PolicyPortfolio(horizon=(2026, 2030))
        p.invest("military_capability.signature_capabilities", share=0.08,
                 how="stand-off/counterstrike buildout per the 2022 NDS")
        p.sequence([...])
        p.custom_initiatives([...])
        return p
    """

    def __init__(self, horizon: Tuple[int, int] = (2026, 2030)) -> None:
        coerced = _coerce_years(horizon)
        self.horizon: Tuple[int, int] = coerced if coerced else (0, 0)
        if coerced is None:
            self.construction_errors: List[str] = [
                f"horizon is not a (start, end) pair of years: {horizon!r}"
            ]
        else:
            self.construction_errors = []
        self._dials: Dict[str, Dial] = {}
        self._phases: List[Phase] = []
        self._initiatives: List[Initiative] = []
        self._defence_path: Dict[int, float] = dict(SEED_DEFENCE_PATH)
        self._defence_path_explicit: bool = False
        #: Raw sum before any repair, and whether repair actually fired.
        self.raw_share_sum: Optional[float] = None
        self.shares_repaired: bool = False

    # -- construction API used inside the EVOLVE-BLOCK ---------------------

    def invest(self, dial: str, share: float, how: str = "") -> "PolicyPortfolio":
        """Allocate a fraction of marginal effort to one Lowy submeasure.

        Unknown dial names and non-numeric shares are recorded, not raised:
        the validity gate reports them as a reason string. Investing twice in
        the same dial is last-write-wins.
        """
        dial_id = _as_text(dial).strip()
        try:
            share_value = float(share)
        except (TypeError, ValueError):
            self.construction_errors.append(
                f"share for dial {dial_id!r} is not a number: {share!r}"
            )
            return self
        if not math.isfinite(share_value):
            self.construction_errors.append(
                f"share for dial {dial_id!r} is not finite: {share!r}"
            )
            return self
        self._dials[dial_id] = Dial(
            dial_id=dial_id, share=share_value, how=_as_text(how).strip()
        )
        return self

    def sequence(self, phases: Sequence[Any]) -> "PolicyPortfolio":
        """Set the ordered phases from 2026 to 2030.

        Accepts ``Phase`` objects, mappings with ``years``/``label``/``focus``,
        or ``((start, end), label)`` tuples.
        """
        self._phases = []
        if not isinstance(phases, (list, tuple)):
            self.construction_errors.append(
                f"sequence() expects a list of phases, got {type(phases).__name__}"
            )
            return self
        for index, raw in enumerate(phases):
            phase = self._coerce_phase(raw, index)
            if phase is not None:
                self._phases.append(phase)
        return self

    def _coerce_phase(self, raw: Any, index: int) -> Optional[Phase]:
        if isinstance(raw, Phase):
            return raw
        if isinstance(raw, Mapping):
            years = _coerce_years(raw.get("years"))
            if years is None:
                years = _coerce_years((raw.get("start"), raw.get("end")))
            label = _as_text(raw.get("label", "")).strip()
            focus = _coerce_targets(raw.get("focus"))
        elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
            years = _coerce_years(raw[0])
            label = _as_text(raw[1]).strip()
            focus = _coerce_targets(raw[2]) if len(raw) > 2 else ()
        else:
            self.construction_errors.append(
                f"phase {index} is not a Phase, mapping or (years, label) tuple: "
                f"{raw!r}"
            )
            return None
        if years is None:
            self.construction_errors.append(
                f"phase {index} has no readable (start, end) years: {raw!r}"
            )
            return None
        return Phase(years=years, label=label, focus=focus)

    def custom_initiatives(self, initiatives: Sequence[Any]) -> "PolicyPortfolio":
        """Set the free-slot initiatives. Each must name target submeasures."""
        self._initiatives = []
        if not isinstance(initiatives, (list, tuple)):
            self.construction_errors.append(
                "custom_initiatives() expects a list, got "
                f"{type(initiatives).__name__}"
            )
            return self
        for index, raw in enumerate(initiatives):
            initiative = self._coerce_initiative(raw, index)
            if initiative is not None:
                self._initiatives.append(initiative)
        return self

    def _coerce_initiative(self, raw: Any, index: int) -> Optional[Initiative]:
        if isinstance(raw, Initiative):
            return raw
        if isinstance(raw, Mapping):
            return Initiative(
                name=_as_text(raw.get("name", "")).strip(),
                rationale=_as_text(
                    raw.get("rationale", raw.get("description", ""))
                ).strip(),
                targets=_coerce_targets(raw.get("targets")),
            )
        self.construction_errors.append(
            f"custom initiative {index} is not an Initiative or mapping: {raw!r}"
        )
        return None

    def defence_spending_path(
        self, path: Mapping[Any, Any]
    ) -> "PolicyPortfolio":
        """Declare defence spending as % of GDP per year of the horizon.

        Only the feasibility bound of the validity gate reads this; it is not a
        dial and carries no share. Defaults to Japan's December 2022 path
        (2% of GDP from 2027).
        """
        if not isinstance(path, Mapping):
            self.construction_errors.append(
                f"defence_spending_path() expects a mapping, got {type(path).__name__}"
            )
            return self
        coerced: Dict[int, float] = {}
        for year, value in path.items():
            try:
                coerced[int(year)] = float(value)
            except (TypeError, ValueError):
                self.construction_errors.append(
                    f"defence_spending_path entry {year!r}: {value!r} is not numeric"
                )
                return self
        self._defence_path = coerced
        self._defence_path_explicit = True
        return self

    # -- read-side helpers -------------------------------------------------

    @property
    def dials(self) -> Dict[str, Dial]:
        return dict(self._dials)

    @property
    def phases(self) -> List[Phase]:
        return list(self._phases)

    @property
    def initiatives(self) -> List[Initiative]:
        return list(self._initiatives)

    @property
    def defence_path(self) -> Dict[int, float]:
        return dict(self._defence_path)

    @property
    def defence_path_is_explicit(self) -> bool:
        return self._defence_path_explicit

    def total_share(self) -> float:
        return sum(d.share for d in self._dials.values())

    def normalise_shares(self, limits: "GateLimits") -> bool:
        """Rescale shares to sum to ``limits.share_sum``. Returns True if repaired.

        Called by the Stage 1 gate before the sum is checked. A no-op when the
        shares already sum correctly, when any share is negative (that is a real
        error, not an arithmetic slip), or when the raw sum falls outside the
        repair band -- in all of those cases the gate's own checks still fire.

        Records ``raw_share_sum`` either way, so the repair rate is measurable
        across a whole run rather than inferred.
        """
        total = self.total_share()
        self.raw_share_sum = total
        if not math.isfinite(total) or total <= 0.0:
            return False
        if any(d.share < 0.0 for d in self._dials.values()):
            return False
        if abs(total - limits.share_sum) <= limits.share_sum_tolerance:
            return False
        if not (limits.share_sum_repair_min <= total <= limits.share_sum_repair_max):
            return False
        factor = limits.share_sum / total
        for dial_id, dial in self._dials.items():
            self._dials[dial_id] = Dial(
                dial_id=dial.dial_id, share=dial.share * factor, how=dial.how
            )
        self.shares_repaired = True
        return True

    def unknown_dials(self) -> List[str]:
        return sorted(d for d in self._dials if d not in DIALS)

    def share_by_measure(self) -> Dict[str, float]:
        """Effort share aggregated to the 8 measures (unknown dials ignored)."""
        totals = {m: 0.0 for m in MEASURES}
        for dial_id, dial in self._dials.items():
            if dial_id in DIALS:
                totals[dial_id.split(".", 1)[0]] += dial.share
        return totals

    def free_text_chars(self) -> int:
        chars = sum(len(d.how) for d in self._dials.values())
        chars += sum(len(p.label) for p in self._phases)
        chars += sum(len(i.name) + len(i.rationale) for i in self._initiatives)
        return chars

    # -- canonical serialisation ------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Deterministic dict: the judge's input and the cache key material.

        Known dials appear in Lowy's canonical order; any unknown dial names
        follow, sorted, so that a malformed portfolio still hashes stably.
        """
        ordered_ids = [d for d in DIALS if d in self._dials]
        ordered_ids += sorted(d for d in self._dials if d not in DIALS)
        return {
            "horizon": list(self.horizon),
            "dials": [
                {
                    "dial": dial_id,
                    "share": round(self._dials[dial_id].share, 6),
                    "how": self._dials[dial_id].how,
                }
                for dial_id in ordered_ids
            ],
            "sequence": [
                {
                    "years": list(phase.years),
                    "label": phase.label,
                    "focus": list(phase.focus),
                }
                for phase in self._phases
            ],
            "custom_initiatives": [
                {
                    "name": item.name,
                    "rationale": item.rationale,
                    "targets": list(item.targets),
                }
                for item in self._initiatives
            ],
            "defence_spending_pct_gdp": {
                str(year): round(float(value), 4)
                for year, value in sorted(self._defence_path.items())
            },
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"PolicyPortfolio(horizon={self.horizon}, dials={len(self._dials)}, "
            f"phases={len(self._phases)}, initiatives={len(self._initiatives)}, "
            f"total_share={self.total_share():.4f})"
        )
