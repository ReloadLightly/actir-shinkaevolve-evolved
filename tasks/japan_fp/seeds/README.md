# The four rival-school seeds

Inputs to the M1 calibration smoke test (KICKOFF Stage B). Together with
`../initial.py` — Japan's actual December 2022 posture — they are the five
portfolios the judge scores across the three scenarios, producing the table
that decides whether the rubric is plausible enough to freeze.

They are **not** evolved individuals and nothing is evolved from them. They
exist to be argued with.

## Why four, and why these four

The calibration test is not "does the judge return numbers". It is "does the
judge return an *ordering a Japan specialist would recognise as arguable*".
That question needs candidates that genuinely disagree — about the alliance,
about China, about whether power is military or economic, and about whether
Japan's real constraint is deterrence or demography.

| Seed | Lineage | Core claim |
|---|---|---|
| `seed_autonomous_rearmament.py` | Nakasone; the post-2022 security right | The American guarantee is a wasting asset. Buy sovereign capability while the alliance still covers the transition. |
| `seed_accommodation.py` | Ozawa–Hatoyama; East Asian Community | The security dilemma *is* the threat. Interdependence is cheaper than deterrence, and the alliance is a war risk as much as a shield. |
| `seed_status_quo_plus.py` | The Kishida–Ishiba mainstream | December 2022 was right. Execute it fully, extend at the margin, invent no new doctrine. |
| `seed_middle_power_internationalism.py` | Ōhira–Fukuda–Takeshita liberal internationalism | Japan's power is rule-making, not force. The binding constraint is demography, not deterrence. |

## What each seed is built to test

Each one is aimed at a specific rule of `../judge_prompt.md`, so that a
miscalibrated rubric fails *visibly* rather than quietly:

- **Autonomous rearmament → rule 2, score backfire.** 44% of marginal effort
  on military capability and only 4% on defence networks. If every measure
  moves up, the judge is adding effort rather than measuring consequence.
- **Accommodation → rule 5, the scenario is the world.** It should read very
  differently under S2 (a Taiwan contingency arrives anyway) and S3 (the ally
  leaves, and accommodation becomes the rational response). A flat spread
  means the scenario is being ignored.
- **Status-quo-plus → the ±0.5 "marginal" anchor.** Deliberately the near-twin
  of December 2022 (L1 = 0.12, about 6% of effort reallocated). If the judge
  separates them by much more than a point, every small mutation will read as
  noise-sized signal and the search will chase artefacts.
- **Middle-power internationalism → rule 3, diminishing returns.** It spends
  heavily on diplomatic influence, where Japan sits at 85.4 with almost no
  headroom, *and* on future resources, where it sits at 11.3 with enormous
  headroom. If both move similarly, the rule is not landing.

## Doctrinal spread

Marginal effort by Lowy measure, and the implied 2030 defence path:

```
                                EconCap   MilCap  EconRel    Resil   FutRes   DefNet   DipInf  CultInf  Def%2030
dec_2022                            13%      29%      13%      14%       6%      15%       6%       4%      2.0%
status_quo_plus                     14%      26%      13%      13%       8%      14%       7%       5%      2.2%
autonomous_rearmament               11%      44%       5%      19%      13%       4%       2%       2%      3.5%
accommodation                       16%       9%      26%      14%      11%       4%      11%       9%      1.0%
middle_power_internationalism       16%      10%      19%      11%      20%       7%       9%       8%      1.8%
```

Pairwise L1 distance between share vectors (0 identical, 2 disjoint):

```
                                dec_2022  status_q  autonomo  accommod  middle_p
dec_2022                            0.00      0.12      0.58      0.76      0.64
status_quo_plus                     0.12      0.00      0.62      0.70      0.56
autonomous_rearmament               0.58      0.62      0.00      1.06      1.02
accommodation                       0.76      0.70      1.06      0.00      0.34
middle_power_internationalism       0.64      0.56      1.02      0.34      0.00
```

Autonomous rearmament and accommodation sit at 1.06 — over half the maximum
possible distance — which is the doctrinal spine of the set. The closest rival
pair is accommodation and middle-power internationalism at 0.34: both civilian
in emphasis, but on different theories of where influence comes from.
`tests/test_seeds.py` enforces a 0.20 floor on every pair except the
designated near-twin, so the set cannot silently collapse into variants of one
position.

## Conventions

Each seed is a standalone program with the same immutable harness as
`initial.py`, so the evaluator loads it exactly as it would an evolved
individual — same loader, same validity gate, same aggregation.

All four state a position on **all 30 dials**, including the zeros. Rubric
rule 6 makes silence a signal, so a deliberate `share=0.00` carrying a `how`
string that says *why* is a different claim from an omission. The seeds always
make the deliberate-zero claim, so the judge is never left guessing which one
it was reading.

## Running them

```bash
# One seed, standalone
python tasks/japan_fp/seeds/seed_accommodation.py

# One seed through the evaluator (mock judge: scores 38.8475)
python tasks/japan_fp/evaluate.py \
    --program_path tasks/japan_fp/seeds/seed_accommodation.py \
    --results_dir runs/scratch

# The whole M1 table
python scripts/m1_calibration.py              # mock, 0 calls, $0
python scripts/m1_calibration.py --estimate   # ~$0.11 against a $1 ceiling
python scripts/m1_calibration.py --real       # refuses unless Stage B is authorized
```

Under the mock judge every portfolio scores 38.8475, because every delta is
zero. That is the correct result and it proves the harness, not the rubric —
the doctrines only separate once a real judge has an opinion.
