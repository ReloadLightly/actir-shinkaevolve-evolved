"""Policy instruments: the things Japan can actually decide.

A review of 2026-08-18 identified this as one of two foundational errors:

> "economic size", "demographic resources 2050" and "cultural influence" are
> not actions Japan can select. They are outcomes produced by many instruments
> and external conditions.

That is right, and the precise version is sharper than "instruments are
missing". They were never missing — the December 2022 seed says "Rapidus, TSMC
Kumamoto, chip subsidies", "43 trillion yen procurement", "2% of GDP by 2027".
Those ARE instruments. **They were in the wrong layer.** They lived in free-text
`how` strings that the validity gate only length-checks and that the search can
only rewrite as prose, while the structured, searched object was an allocation
over *outcomes*. So the LLM mutated numbers attached to outcomes and wrote
sentences about instruments, and the search operated on the layer that Japan
does not control.

This module promotes the instruments to the searched layer and makes the Lowy
exposure **derived** rather than chosen:

    instruments (chosen)  ->  exposure map (declared)  ->  Lowy measures
                                                            (judge scores)

Three things follow that were impossible before.

* **Feasibility becomes checkable.** An allocation over outcomes cannot be
  fiscally infeasible, because outcomes have no price. Instruments do, so
  `coherence_report` can test a portfolio against a fiscal envelope, a
  political-capital envelope, legal prerequisites, lead times against the
  2026-2030 horizon, and pairs that contradict each other. That is review
  point 3, which was unfixable while the search ran over outcomes.
* **The search space becomes the space of decisions.** Two portfolios that
  differ in *how* they buy military capability are now different genotypes,
  where before they differed only in prose.
* **The nuclear question becomes expressible.** In preflight 32086108143
  gpt-4.1-nano tried to invent `military_capability.nuclear_deterrence` and had
  its portfolio thrown away. It was reaching for something real that Lowy's
  ontology has no dial for. `nuclear_latency_posture` is in the catalogue below.

## What is a modelling assumption here, and what is not

**Not assumed:** the eight Lowy measures and their weights, which are Lowy's
own, and the instruments themselves, which are drawn from Japan's actual
2022-2026 policy debate and are named so a Japan specialist can dispute any of
them by name.

**Assumed, and declared:** the `exposure` vectors — which measures each
instrument plausibly moves, and in which direction. These are ours. They encode
ordinary IR reasoning (arms-export liberalisation deepens defence networks and
industrial ties; immigration liberalisation is the only real lever on Japan's
11.3 future-resources score) and every one is arguable. They are *coefficients
of a stated model*, not measurements, and the point of writing them down is that
a reader can attack them individually instead of attacking a black box.

**Deliberately NOT here:** any claim that these exposures predict a Lowy score.
The judge still estimates the world's response; the exposure map only says which
outcomes an instrument is *pointed at*. See `lowy.py` on why our projection is
not Lowy's published procedure.

**STATUS: DRAFT.** Preregistered and hashed into FROZEN.json. The exposure
vectors are declared coefficients of a stated model, not measurements, and are
open to revision under the same rule as world.py: a defect statable without
reference to which arm it favours, a version bump, and a full rerun.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from lowy import MEASURES

# --------------------------------------------------------------------------
# Legal authority required. Japan's constraints here are real and ordered:
# a cabinet reinterpretation is a decision, Diet legislation is a session, and
# constitutional amendment needs two-thirds of both houses plus a referendum
# that has never been held.
# --------------------------------------------------------------------------

NONE = "none"                       # executive/budget action
CABINET = "cabinet_decision"        # cabinet decision or reinterpretation
DIET = "diet_legislation"           # ordinary legislation
TREATY = "treaty_ratification"      # Diet approval of a treaty
CONSTITUTION = "constitutional_amendment"   # 2/3 both houses + referendum

LEGAL_DIFFICULTY: Dict[str, float] = {
    NONE: 0.0, CABINET: 0.10, DIET: 0.25, TREATY: 0.20, CONSTITUTION: 0.80,
}


@dataclass(frozen=True)
class Instrument:
    """One lever a Japanese government can pull, and what pulling it costs."""

    ident: str
    label: str
    #: What the instrument is, concretely enough to argue with.
    detail: str
    #: Marginal fiscal cost at full intensity, as share of GDP per year.
    #: Japan carries ~260% debt/GDP, so this is the genuinely scarce resource.
    fiscal_gdp_pct: float
    #: Political capital at full intensity, on 0-1 where 1.0 is a government's
    #: entire term of capital. Legal difficulty is added on top.
    political_cost: float
    legal: str
    #: Years before the instrument delivers most of its effect. The horizon is
    #: 2026-2030, so anything above 5 cannot fully land inside it.
    lead_time_years: int
    #: The declared model: which Lowy measures this is pointed at, signed.
    #: Magnitudes are relative within an instrument, not across instruments.
    exposure: Dict[str, float]
    #: Instruments this one works against, and why.
    tension_with: Tuple[str, ...] = ()

    @property
    def total_political_cost(self) -> float:
        return self.political_cost + LEGAL_DIFFICULTY.get(self.legal, 0.0)


def _exp(**kwargs: float) -> Dict[str, float]:
    unknown = set(kwargs) - set(MEASURES)
    if unknown:
        raise KeyError(f"exposure names unknown Lowy measures: {sorted(unknown)}")
    return dict(kwargs)


#: The catalogue. Every entry is a decision taken, debated or explicitly
#: declined in Japan between the December 2022 documents and 2026.
CATALOGUE: Tuple[Instrument, ...] = (
    Instrument(
        "defence_budget", "Defence budget share of GDP",
        "The 2022 NSS path to 2% of GDP by FY2027, and whether to go beyond it.",
        fiscal_gdp_pct=1.5, political_cost=0.25, legal=NONE, lead_time_years=1,
        exposure=_exp(military_capability=1.0, defence_networks=0.2,
                      economic_capability=-0.1),
    ),
    Instrument(
        "counterstrike", "Standoff and counterstrike procurement",
        "Tomahawk purchase, Type-12 extended-range upgrade, hypersonics.",
        fiscal_gdp_pct=0.25, political_cost=0.20, legal=CABINET, lead_time_years=3,
        exposure=_exp(military_capability=1.0, defence_networks=0.3,
                      economic_relationships=-0.1),
    ),
    Instrument(
        "defence_exports", "Defence-industrial export liberalisation",
        "Relaxing the Three Principles on Defence Equipment Transfer; "
        "co-development with the UK and Italy (GCAP).",
        fiscal_gdp_pct=0.05, political_cost=0.35, legal=DIET, lead_time_years=2,
        exposure=_exp(defence_networks=0.8, economic_relationships=0.4,
                      military_capability=0.3),
    ),
    Instrument(
        "host_nation_support", "Host-nation support to US forces",
        "Omoiyari yosan; basing, dispersal and munitions co-location.",
        fiscal_gdp_pct=0.12, political_cost=0.15, legal=NONE, lead_time_years=1,
        exposure=_exp(defence_networks=1.0, military_capability=0.2),
    ),
    Instrument(
        "minilateral_formats", "Minilateral security architecture",
        "Quad, Japan-US-ROK trilateral, AUKUS Pillar 2, reciprocal access "
        "agreements with Australia, the UK and the Philippines.",
        fiscal_gdp_pct=0.05, political_cost=0.15, legal=TREATY, lead_time_years=2,
        exposure=_exp(defence_networks=1.0, diplomatic_influence=0.5,
                      military_capability=0.2),
    ),
    Instrument(
        "oda_infrastructure", "ODA and quality infrastructure finance",
        "Partnership for Quality Infrastructure; JICA and JBIC lending.",
        fiscal_gdp_pct=0.20, political_cost=0.10, legal=NONE, lead_time_years=3,
        exposure=_exp(economic_relationships=0.8, diplomatic_influence=0.7),
    ),
    Instrument(
        "official_security_assistance", "Official Security Assistance",
        "OSA, created 2023: grant military aid to partner forces, distinct "
        "from ODA. Coast-guard and maritime-domain-awareness transfers.",
        fiscal_gdp_pct=0.04, political_cost=0.15, legal=NONE, lead_time_years=2,
        exposure=_exp(defence_networks=0.8, diplomatic_influence=0.4),
    ),
    Instrument(
        "economic_security_regime", "Economic security regulation",
        "Economic Security Promotion Act: supply-chain screening, export "
        "controls on advanced nodes, inbound investment review.",
        fiscal_gdp_pct=0.08, political_cost=0.25, legal=DIET, lead_time_years=2,
        exposure=_exp(resilience=0.9, military_capability=0.2,
                      economic_relationships=-0.4),
        tension_with=("china_engagement",),
    ),
    Instrument(
        "semiconductor_policy", "Semiconductor industrial policy",
        "Rapidus 2nm, TSMC Kumamoto, Kioxia; multi-trillion-yen subsidy.",
        fiscal_gdp_pct=0.35, political_cost=0.20, legal=DIET, lead_time_years=5,
        exposure=_exp(economic_capability=0.9, resilience=0.5,
                      future_resources=0.4),
    ),
    Instrument(
        "energy_diversification", "Energy security and nuclear restart",
        "Restarting reactors under the GX plan, LNG supplier diversification, "
        "offshore wind build-out.",
        fiscal_gdp_pct=0.25, political_cost=0.45, legal=DIET, lead_time_years=4,
        exposure=_exp(resilience=0.9, economic_capability=0.4,
                      future_resources=0.3),
    ),
    Instrument(
        "immigration_liberalisation", "Labour immigration liberalisation",
        "Replacing the technical-intern system; expanding specified-skilled "
        "visas and a path to settlement. The only real lever on the "
        "demographic collapse behind Japan's 11.3 future-resources score.",
        fiscal_gdp_pct=0.10, political_cost=0.60, legal=DIET, lead_time_years=3,
        exposure=_exp(future_resources=1.0, economic_capability=0.5,
                      resilience=-0.1, cultural_influence=0.2),
    ),
    Instrument(
        "female_labour_participation", "Female and older-worker participation",
        "Childcare capacity, spousal tax-deduction reform, working-hours law.",
        fiscal_gdp_pct=0.20, political_cost=0.30, legal=DIET, lead_time_years=4,
        exposure=_exp(future_resources=0.7, economic_capability=0.5),
    ),
    Instrument(
        "trade_architecture", "Trade architecture leadership",
        "CPTPP stewardship including the accession queue, RCEP "
        "implementation, IPEF, the Japan-EU EPA.",
        fiscal_gdp_pct=0.03, political_cost=0.25, legal=TREATY, lead_time_years=3,
        exposure=_exp(economic_relationships=1.0, diplomatic_influence=0.6),
    ),
    Instrument(
        "cyber_active_defence", "Active cyber defence",
        "Legislation permitting pre-emptive access to hostile infrastructure, "
        "against Article 21's secrecy-of-communications guarantee.",
        fiscal_gdp_pct=0.10, political_cost=0.40, legal=DIET, lead_time_years=3,
        exposure=_exp(military_capability=0.6, resilience=0.6),
    ),
    Instrument(
        "space_isr", "Space-based ISR",
        "Satellite constellation for maritime domain awareness and missile "
        "warning; QZSS expansion.",
        fiscal_gdp_pct=0.15, political_cost=0.10, legal=NONE, lead_time_years=4,
        exposure=_exp(military_capability=0.6, future_resources=0.3,
                      defence_networks=0.3),
    ),
    Instrument(
        "unsc_reform", "UN Security Council reform campaign",
        "G4 permanent-seat bid; a decades-long play with no near-term payoff.",
        fiscal_gdp_pct=0.02, political_cost=0.15, legal=NONE, lead_time_years=8,
        exposure=_exp(diplomatic_influence=0.8),
    ),
    Instrument(
        "cultural_diplomacy", "Cultural and content diplomacy",
        "Japan Foundation, JET, and the Cool Japan content-export strategy.",
        fiscal_gdp_pct=0.05, political_cost=0.05, legal=NONE, lead_time_years=3,
        exposure=_exp(cultural_influence=1.0, diplomatic_influence=0.3),
    ),
    Instrument(
        "critical_minerals", "Critical minerals de-risking",
        "Stockpiles, JOGMEC equity in non-Chinese sources, recycling.",
        fiscal_gdp_pct=0.08, political_cost=0.10, legal=NONE, lead_time_years=3,
        exposure=_exp(resilience=0.8, economic_relationships=0.2),
    ),
    Instrument(
        "china_engagement", "Economic engagement with China",
        "Trade and investment posture, from de-risking to re-engagement. "
        "China is Japan's largest trading partner; the dial runs both ways.",
        fiscal_gdp_pct=0.0, political_cost=0.35, legal=NONE, lead_time_years=1,
        exposure=_exp(economic_relationships=0.9, economic_capability=0.3,
                      resilience=-0.5, defence_networks=-0.3),
        tension_with=("economic_security_regime", "counterstrike"),
    ),
    Instrument(
        "collective_self_defence", "Constitutional revision on collective self-defence",
        "Beyond the 2014 reinterpretation: amending Article 9 itself. Requires "
        "two-thirds of both houses and a referendum never yet held.",
        fiscal_gdp_pct=0.0, political_cost=0.70, legal=CONSTITUTION,
        lead_time_years=5,
        exposure=_exp(military_capability=0.7, defence_networks=0.6,
                      economic_relationships=-0.2),
    ),
    Instrument(
        "nuclear_latency_posture", "Nuclear latency and extended deterrence",
        "From the Rokkasho reprocessing hedge and plutonium stockpile toward "
        "explicit hedging, nuclear sharing, or NPT exit. In preflight "
        "32086108143 a mutation model tried to express this and had its "
        "portfolio discarded, because Lowy's ontology has no dial for it.",
        fiscal_gdp_pct=0.10, political_cost=0.85, legal=TREATY, lead_time_years=5,
        exposure=_exp(military_capability=0.8, defence_networks=-0.4,
                      diplomatic_influence=-0.5, economic_relationships=-0.3),
        tension_with=("unsc_reform", "minilateral_formats"),
    ),
)

BY_ID: Dict[str, Instrument] = {i.ident: i for i in CATALOGUE}
INSTRUMENT_IDS: Tuple[str, ...] = tuple(i.ident for i in CATALOGUE)


# --------------------------------------------------------------------------
# Envelopes. These are the scarce things a government actually runs out of,
# and they are what make a portfolio infeasible rather than merely unpopular.
# --------------------------------------------------------------------------

#: Marginal fiscal room, as share of GDP per year, for NEW commitments over
#: 2026-2030. Japan's debt is ~260% of GDP and the 2022 defence decision alone
#: consumed a large part of the available space, so this is deliberately tight.
#: A portfolio spending more than this is not a policy, it is a wish.
FISCAL_ENVELOPE_GDP_PCT: float = 2.20

#: Political capital available across one government's effective term, on the
#: same scale as Instrument.political_cost, with legal difficulty added.
#:
#: CALIBRATED AGAINST HISTORY, which is the only defensible way to set it. The
#: December 2022 decision -- the counterstrike reversal, the 2%-of-GDP path, the
#: economic security act, the export-rule relaxation, all at once -- is the
#: largest political push any recent Japanese government has actually sustained.
#: Encoded as instrument intensities (see tests) it comes to 2.60. So the
#: envelope is set just above it: December 2022 must come out FEASIBLE, because
#: it happened, and it should come out STRETCHED, because it nearly broke the
#: government that did it. Anything materially beyond it is a plan no
#: administration has demonstrated it can carry.
#:
#: An envelope that rules the actual historical decision infeasible is not a
#: strict model, it is a wrong one. The first draft of this constant said 1.60
#: and did exactly that.
POLITICAL_ENVELOPE: float = 3.00

#: The planning horizon. An instrument whose lead time exceeds this cannot
#: deliver inside the window, which does not forbid it -- some bets are
#: deliberately long -- but does cap how much of it counts.
HORIZON_YEARS: int = 5


def _intensities(portfolio: Mapping[str, Any]) -> Dict[str, float]:
    raw = portfolio.get("instruments") or {}
    out: Dict[str, float] = {}
    for ident, value in raw.items():
        try:
            out[ident] = float(value)
        except (TypeError, ValueError):
            continue
    return out


def fiscal_cost(intensities: Mapping[str, float]) -> float:
    return sum(BY_ID[i].fiscal_gdp_pct * v
               for i, v in intensities.items() if i in BY_ID)


def political_cost(intensities: Mapping[str, float]) -> float:
    return sum(BY_ID[i].total_political_cost * v
               for i, v in intensities.items() if i in BY_ID)


def lowy_exposure(intensities: Mapping[str, float]) -> Dict[str, float]:
    """Derived exposure of a set of instrument choices onto the 8 measures.

    Signed and unnormalised: a portfolio can be pointed AWAY from a measure,
    which is the whole point of `china_engagement` and `nuclear_latency_posture`
    carrying negative terms. Normalisation into effort shares happens in
    `effort_shares`, which is what the judge is shown.
    """
    totals = {m: 0.0 for m in MEASURES}
    for ident, value in intensities.items():
        instrument = BY_ID.get(ident)
        if instrument is None:
            continue
        for measure, weight in instrument.exposure.items():
            totals[measure] += weight * value
    return totals


def effort_shares(intensities: Mapping[str, float]) -> Dict[str, float]:
    """Exposure as non-negative shares summing to 1.0, for the judge's view.

    Negative exposure is clipped here rather than subtracted, because a share
    is a share of *attention*, and pointing away from a measure still means
    the portfolio is engaging with it. The signed version stays available in
    `lowy_exposure` and is what the coherence checks read.
    """
    exposure = lowy_exposure(intensities)
    positive = {m: max(0.0, v) for m, v in exposure.items()}
    total = sum(positive.values())
    if total <= 0.0:
        return {m: 1.0 / len(MEASURES) for m in MEASURES}
    return {m: v / total for m, v in positive.items()}


@dataclass
class CoherenceReport:
    """What a portfolio would cost, and where it contradicts itself."""

    fiscal_gdp_pct: float
    political: float
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def feasible(self) -> bool:
        return not self.violations


def coherence_report(portfolio: Mapping[str, Any],
                     fiscal_envelope: float = FISCAL_ENVELOPE_GDP_PCT,
                     political_envelope: float = POLITICAL_ENVELOPE
                     ) -> CoherenceReport:
    """Test a portfolio against the constraints a real government faces.

    This is what review point 3 asked for, and it is only possible now that the
    search runs over instruments: an allocation over *outcomes* cannot be
    fiscally infeasible, because outcomes have no price.

    Violations make a portfolio invalid. Warnings do not -- a portfolio that
    picks a fight it can barely afford, or bets past its horizon, is a
    legitimate strategic choice and the archive should be able to hold it.
    """
    intensities = _intensities(portfolio)
    report = CoherenceReport(fiscal_cost(intensities), political_cost(intensities))

    for ident, value in intensities.items():
        if ident not in BY_ID:
            report.violations.append(
                f"unknown instrument {ident!r}; the catalogue has "
                f"{len(INSTRUMENT_IDS)} and no others exist"
            )
        elif not 0.0 <= value <= 1.0:
            report.violations.append(
                f"intensity for {ident} must lie in [0, 1], got {value}"
            )

    if report.fiscal_gdp_pct > fiscal_envelope:
        report.violations.append(
            f"fiscally infeasible: {report.fiscal_gdp_pct:.2f}% of GDP per year "
            f"in new commitments against an envelope of {fiscal_envelope:.2f}%. "
            f"Japan carries ~260% debt/GDP; this is the binding constraint on "
            f"every post-2022 plan."
        )
    elif report.fiscal_gdp_pct > 0.85 * fiscal_envelope:
        report.warnings.append(
            f"fiscally stretched: {report.fiscal_gdp_pct:.2f}% of "
            f"{fiscal_envelope:.2f}% envelope"
        )

    if report.political > political_envelope:
        report.violations.append(
            f"politically infeasible: {report.political:.2f} of capital against "
            f"an envelope of {political_envelope:.2f}. No Japanese government "
            f"has sustained this many simultaneous fights."
        )
    elif report.political > 0.85 * political_envelope:
        report.warnings.append(
            f"politically stretched: {report.political:.2f} of "
            f"{political_envelope:.2f}"
        )

    for ident, value in intensities.items():
        instrument = BY_ID.get(ident)
        if instrument is None or value < 0.35:
            continue
        for other in instrument.tension_with:
            if intensities.get(other, 0.0) >= 0.35:
                report.warnings.append(
                    f"{ident} at {value:.2f} works against {other} at "
                    f"{intensities[other]:.2f}; the portfolio is pulling in two "
                    f"directions and the judge should be expected to price that"
                )
        if instrument.lead_time_years > HORIZON_YEARS:
            report.warnings.append(
                f"{ident} has a {instrument.lead_time_years}-year lead time "
                f"against a {HORIZON_YEARS}-year horizon; most of its effect "
                f"falls outside the window being scored"
            )
        if instrument.legal == CONSTITUTION:
            report.warnings.append(
                f"{ident} at {value:.2f} requires constitutional amendment: "
                f"two-thirds of both houses plus a referendum never yet held"
            )

    return report


def describe_catalogue() -> List[Dict[str, Any]]:
    """The catalogue as data, for manifests and for the mutation prompt."""
    return [
        {
            "id": i.ident, "label": i.label, "detail": i.detail,
            "fiscal_gdp_pct": i.fiscal_gdp_pct,
            "political_cost": round(i.total_political_cost, 3),
            "legal": i.legal, "lead_time_years": i.lead_time_years,
            "exposure": i.exposure, "tension_with": list(i.tension_with),
        }
        for i in CATALOGUE
    ]


# --------------------------------------------------------------------------
# The bridge. This is what makes the rewrite a rewrite of the ENGINE and not of
# the whole car: an instrument choice becomes an ordinary PolicyPortfolio, so
# the judge, the validity gate, the behaviour descriptors, MAP-Elites, the
# archive adapter, the novelty analysis and the cost ledger all keep working
# untouched. The review asked for exactly this separation and it holds.
# --------------------------------------------------------------------------


def _submeasure_split(measure_share: float, submeasures: Sequence[str]
                      ) -> Dict[str, float]:
    """Spread a measure's share evenly across its submeasures.

    A SIMPLIFICATION, stated rather than hidden. Instruments are declared to
    point at measures, not at individual submeasures, because assigning 21
    instruments across 30 submeasures would multiply the invented coefficients
    roughly fourfold for no gain: the behaviour descriptors, the MAP-Elites
    axes and the composite all aggregate to measure level anyway. If a later
    version needs submeasure resolution, this is the one function to change.
    """
    if not submeasures:
        return {}
    each = measure_share / len(submeasures)
    return {s: each for s in submeasures}


def to_portfolio(intensities: Mapping[str, float],
                 horizon: Tuple[int, int] = (2026, 2030),
                 phases: Optional[Sequence[Any]] = None,
                 initiatives: Optional[Sequence[Any]] = None,
                 defence_path: Optional[Mapping[int, float]] = None):
    """Build a PolicyPortfolio from a set of instrument decisions.

    Two things are derived rather than chosen, and that is the point:

    * **Dial shares** come from the exposure map, so the allocation over Lowy
      outcomes is a CONSEQUENCE of the instruments rather than a free choice.
      A search that moves an instrument moves the outcome exposure with it.
    * **The `how` string** for each dial names the instruments actually
      pointed at that measure. Prose can no longer drift away from the
      allocation it describes, because it is generated from it. In the old
      representation the two were independent and nothing checked them against
      each other.

    The defence-spending path is derived from `defence_budget` intensity unless
    given explicitly, so the two cannot contradict one another either.
    """
    from lowy import SUBMEASURES, measure_of  # noqa: F401
    from schema import DEFAULT_LIMITS, Phase, PolicyPortfolio

    shares = effort_shares(intensities)

    # Which instruments point at each measure, strongest first, for the prose.
    pointed: Dict[str, List[Tuple[str, float]]] = {m: [] for m in MEASURES}
    for ident, value in intensities.items():
        instrument = BY_ID.get(ident)
        if instrument is None or value <= 0.0:
            continue
        for measure, weight in instrument.exposure.items():
            if weight > 0:
                pointed[measure].append((instrument.label, weight * value))
    for measure in pointed:
        pointed[measure].sort(key=lambda pair: -pair[1])

    portfolio = PolicyPortfolio(horizon=horizon)
    # Record the decisions, so the validity gate can price them.
    portfolio.instruments = {k: float(v) for k, v in intensities.items()}
    for measure in MEASURES:
        subs = SUBMEASURES[measure]
        drivers = [label for label, _ in pointed[measure][:3]]
        how = ("; ".join(drivers) if drivers
               else "no instrument is pointed at this measure")
        if len(how) > DEFAULT_LIMITS.how_char_cap:
            how = how[:DEFAULT_LIMITS.how_char_cap - 1] + "…"
        dial_ids = [f"{measure}.{sub}" for sub in subs]
        for dial_id, share in _submeasure_split(shares[measure], dial_ids).items():
            portfolio.invest(dial_id, share=share, how=how)

    start, end = horizon
    if phases:
        portfolio.sequence(phases)
    else:
        # Phase boundaries follow the instruments' own lead times: what can
        # land early goes first. Another thing that used to be chosen freely
        # and could contradict the content it was supposed to sequence.
        early = [BY_ID[i].label for i, v in intensities.items()
                 if i in BY_ID and v > 0.2 and BY_ID[i].lead_time_years <= 2]
        late = [BY_ID[i].label for i, v in intensities.items()
                if i in BY_ID and v > 0.2 and BY_ID[i].lead_time_years > 2]
        portfolio.sequence([
            Phase(label=("short lead time: " + ", ".join(early[:4]))[:150]
                  or "near term", years=(start, start + 2), focus=()),
            Phase(label=("long lead time: " + ", ".join(late[:4]))[:150]
                  or "later", years=(start + 2, end), focus=()),
        ])

    if initiatives:
        portfolio.custom_initiatives(initiatives)

    if defence_path:
        portfolio.defence_spending_path(defence_path)
    else:
        # Derived from the defence_budget instrument, so the headline number
        # and the allocation cannot disagree. 1.0% is the pre-2022 baseline;
        # full intensity reaches the 2%-of-GDP path and somewhat beyond.
        level = intensities.get("defence_budget", 0.0)
        target = 1.0 + 1.6 * max(0.0, min(1.0, level))
        path = {}
        for offset, year in enumerate(range(start, end + 1)):
            fraction = min(1.0, (offset + 1) / 4)
            path[year] = round(1.0 + (target - 1.0) * fraction, 2)
        portfolio.defence_spending_path(path)

    return portfolio
