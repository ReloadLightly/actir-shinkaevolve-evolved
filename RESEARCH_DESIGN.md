# Research Design: actir-shinkaevolve

**The third experiment of "After 2022: Japan's Search for a Novel Foreign Policy"**

Draft v1.0 · 2026-08-17 · Status: for discussion. No repo exists yet; nothing here is built.

---

## 0. The design in one sentence

We give ShinkaEvolve a fifth case study: one individual is a Python program that outputs a Japanese foreign-policy portfolio, its fitness is Japan's projected Lowy Asia Power Index composite score in 2030, and everything else — archive, parent sampling, mutation operators, novelty filter, LLM ensemble, ablations — is inherited unchanged from the paper's four case studies.

That is the whole design. Every section below either (a) reports what the four case studies actually did, or (b) fills in the one thing they cannot give us: the task folder (`initial.py`, `evaluate.py`, scenarios, judge prompt).

**Fixed points.** These are your prior decisions. The design treats them as premises, not open questions:

1. A foreign policy is a **program** (code), so the experiment stays true to ShinkaEvolve's character as program evolution. The prototype is pure LLM-enhanced EC — no LLM agents under selection.
2. The **Lowy Asia Power Index is the objective function** — an externally authorized scalarization (8 measures, ~130 indicators, published weights, sensitivity tools), not a construct we invent. Japan 2025: 38.8. China 2025: 73.7.
3. **ShinkaEvolve is the engine**; quality-diversity is explicitly version 2, not this experiment.
4. The instrument combines a **counterfactual engine with a forward look**: the archive shows the alternatives Japan did not choose, the fitness projects what Japan could do next.
5. This experiment is the third and final experiment of the submission, sitting on chapter 13.3 of the Neuroevolution book (LLMs enhance evolution), after slime volleyball (7.2, competitive coevolution) and backprop-NEAT (10.1, NAS).

New decisions taken today (2026-08-17): frozen-judge-plus-validity-gate evaluator; 3-scenario battery with mean fitness; old failure reports enter only after this draft, as a distilled pre-mortem list.

---

## 1. What the four case studies actually did

First the engine, in our vocabulary. ShinkaEvolve is an evolutionary loop in which LLMs are the mutation operators. One cycle: sample a parent program from an archive of islands (weighted by fitness *and* by how few offspring it already has), hand it to a sampled LLM together with inspiration programs and the evaluator's text feedback, receive a code edit (diff edit, full rewrite, or crossover), reject the proposal if it is too similar to existing programs (embedding cosine similarity > 0.95, then an LLM novelty judge for borderline cases), run `evaluate.py` to get one scalar fitness plus public metrics plus text feedback, store all of it in the archive, and update a UCB1 bandit that learns which LLM is currently producing improvements. Every ~10 generations a meta-scratchpad summarizes what worked and injects those lessons into future mutation prompts. (Paper §3, Appendix A.)

The four case studies (paper §4, Appendix B):

| | Circle packing (§4.1) | AIME agent scaffolds (§4.2) | ALE-Bench (§4.3) | MoE load-balancing loss (§4.4) |
|---|---|---|---|---|
| **One individual (genotype)** | Python program that places 26 circles in the unit square | Python agent scaffold (prompts, ensembling, verification logic), base model gpt-4.1-nano | Full C++ contest solution, seeded from ALE-Agent's best | Python loss function, seeded with the standard global-batch LBL |
| **Fitness function** | Sum of radii; validity: no overlap, containment (1e-6 slack during search) | Accuracy on AIME 2024 (30 problems), hard cap of 10 LLM queries per problem, **averaged over 3 independent runs** | Public test-set score of the AtCoder contest task (10 tasks, LITE subset) | r = −(L_CE + L_imb): cross-entropy (last 10M tokens) plus L1 deviation of expert load from uniform; one eval = pretraining a 556M-param MoE on 2B tokens |
| **Search budget** | ~150 evaluations (500 in the async variant, ~$40 API cost) | 75 generations | 50 generations per task | **30 iterations** (evaluation is expensive) |
| **Headline result** | New SOTA 2.6359…, beating AlphaEvolve with orders of magnitude fewer samples | Beats hand-designed scaffolds; discovered 3-experts → critical peer review → editor synthesis, 7 calls | +2.3% avg over ALE-Agent; ahc039 from 5th- to 2nd-place equivalent (2880→3140) | New LBL = global-batch term + entropy-modulated under-usage "safety net" (τ = 0.064/N_E) |
| **Verification after search** | Re-verified with AlphaEvolve's exact checker; slack solution made exact at cost < 1e-6 | Transfer to AIME 2023/2025 and to gpt-4.1-mini, gpt-4.1, o4-mini | Private test set (top-1 vs top-5 private evaluation 1923.5 → 1927.0: no significant overfitting evidence) | Re-trained at 2.7B params / ~30B tokens across three λ values, 7 downstream benchmarks |

**Seven rules the case studies teach.** These transfer directly; the section numbers are the evidence.

1. **The objective is borrowed, never invented.** Sum of radii, AIME accuracy, AtCoder score, CE + imbalance — all pre-existing, community-accepted numbers. The paper's own stated limitation (§6) is that ShinkaEvolve needs "well-defined numerical objectives." The Lowy composite is exactly that for us, and it is the only such number in our field with published weights and an annual update.
2. **Search on a cheap relaxation, verify exactly afterwards.** Slack-tolerant packing → exact re-verification; 556M-param proxy → 2.7B validation; public → private test sets. Our analogue: a cheap frozen judge during search, a stronger judge plus human reading on the final archive (§4 below).
3. **Fitness is one scalar, but the evaluator returns more.** The API (Appendix A) returns `combined_score` + public metrics + `text_feedback`, and the text is fed to the next mutation. Multi-objectivity lives in the feedback channel, not in the fitness. Our per-measure and per-scenario numbers ride there.
4. **Seed with the real status quo, not with randomness.** ALE-Bench seeds from ALE-Agent's best; the MoE study seeds from the global-batch LBL everyone uses. Our seed is Japan's actual December 2022 posture (the anpo sanbunsho). Warning inherited too: on ALE-Bench, evolution tended to stay near its initialization — our diversity mechanisms have real work to do.
5. **Repeat stochastic evaluations and aggregate.** AIME evaluates every candidate 3 times and averages. Our 3-scenario battery is the same move, with worlds instead of seeds.
6. **Budgets are small.** 150 / 75 / 50 / 30 evaluations. Sample efficiency is the paper's selling point; we plan at that scale, which is what makes a solo, limited-compute experiment feasible at all.
7. **Ablate by removing one mechanism at a time.** The paper's three ablations (§5, Fig. 9): parent selection (best-of-N vs hill climbing vs weighted), LLM ensemble (single vs fixed vs bandit), novelty rejection (off vs threshold vs +LLM-judge). We run the same three on our task — and one of them doubles as our deceptiveness test (§4).

---

## 2. The fifth case study: task specification

### 2.1 The individual: a policy program in Lowy's own vocabulary

Design rule, set by your objection of 2026-08-17: **the same authority that defines the objective also defines the coordinate system.** The dials of a policy are not invented by us — they are the Index's own 30 submeasures under the 8 measures (methodology page, 2025 edition). A policy program is an allocation of Japan's marginal strategic effort across those 30 submeasures for 2026–2030, with one capped sentence per dial saying *how* the effort is spent.

`initial.py` contains an EVOLVE-BLOCK that constructs and returns this allocation. The LLM mutates the code; the harness outside the block is immutable.

```python
# EVOLVE-BLOCK-START
def build_policy() -> PolicyPortfolio:
    p = PolicyPortfolio(horizon=(2026, 2030))
    # dials = Lowy submeasures; share = fraction of Japan's marginal
    # strategic effort (shares sum to 1); how = capped free text
    p.invest("military_capability.signature_capabilities", share=0.08,
             how="stand-off/counterstrike buildout per the 2022 NDS")
    p.invest("defence_networks.regional_defence_diplomacy", share=0.07,
             how="expand OSA beyond PH/VN; deepen Japan-ROK-US trilateral")
    p.invest("economic_relationships.economic_diplomacy", share=0.06,
             how="CPTPP expansion diplomacy")
    # ... remaining submeasure dials ...
    p.sequence([...])                 # ordered phases 2026->2030
    p.custom_initiatives([...])       # free slots; each must name target submeasures
    return p
# EVOLVE-BLOCK-END
```

The dial set, verbatim from the methodology: economic capability (size, international leverage, technology, connectivity) · military capability (defence spending, armed forces, weapons and platforms, signature capabilities, Asian military posture) · resilience (internal stability, resource security, geoeconomic security, geopolitical security, nuclear deterrence) · future resources (economic resources 2035, defence resources 2035, broad resources 2035, demographic resources 2050) · economic relationships (regional trade relations, regional investment ties, economic diplomacy) · defence networks (regional alliance network, regional defence diplomacy, global defence partnerships) · diplomatic influence (diplomatic network, multilateral power, foreign policy) · cultural influence (cultural projection, information flows, people exchanges).

Concrete policy content — counterstrike, OSA, CPTPP — appears inside Lowy's categories (the "how" strings and `custom_initiatives`), not as a rival taxonomy. One distinction remains, and it is the judge's whole job: a dial says where effort goes; the judge says, per scenario, whether that effort actually moves the measure scores — including backfire (heavy effort on signature capabilities can lower economic relationships under S1). Without that step a program could buy index points directly, and the search would be arithmetic instead of discovery.

The space stays "almost infinite": 30 continuous shares under a budget constraint × the content of 30 "how" strings × sequencing × free initiatives. `custom_initiatives` is the open-ended slot where a *novel* policy — Erwin's novelty, not just recombination — would have to appear.

### 2.2 The evaluator: validity gate, then frozen judge

`evaluate.py` has two stages, mirroring the paper's structure (constraint check → score).

**Stage 1, programmatic validity gate (free, instant).** Schema completeness; intensity levels in range; budget arithmetic consistent (shares sum to 100 ± ε; defense path within a feasibility bound, e.g. ≤ 3.5% GDP by 2030 — bound adjustable by you); rationale strings within caps. Invalid → fitness 0 plus a reason string, exactly like the paper's patch-parsing feedback. This is our circle-overlap check: no judge call is spent on malformed programs, and rhetoric cannot be scored because free text is capped and the judge never sees the code.

**Stage 2, frozen judge (the world model).** One LLM, pinned to an exact API version, temperature 0, cached by content hash, and **excluded from the mutation ensemble** — variation proposes, a separate environment disposes. Per scenario, the judge receives: (a) Japan's real 2025 baseline across the 8 measures, (b) the scenario vignette, (c) the portfolio as JSON (never the code), (d) an anchored rubric. It outputs, per measure, a delta Δ ∈ [−15, +15] on the Lowy 0–100 scale plus a one-sentence causal mechanism. Anchor example in the rubric: "+3 on military capability ≈ the scale of the December 2022 counterstrike + 2%-GDP decision." The judge tier is the paper's meta/novelty tier (they used gpt-5-nano / gpt-4.1 / gpt-5-mini at temperature 0) — cheap, frozen, boring.

> **Correction, 2026-08-18 (preflight run 32084865677).** "Frozen" here means
> *pinned configuration* — one model, one API version, one rubric, excluded
> from the mutation ensemble. It does **not** mean deterministic output, and
> this section previously implied that it did. Three identical requests at
> temperature 0 returned per-measure deltas differing by up to 1.000, with one
> measure changing sign; at the composite level the self-noise is 0.17. The
> content-hash cache therefore freezes whichever *draw* arrived first rather
> than reproducing a judgement. See `docs/PREFLIGHT_FINDINGS.md` §1 for what
> this does and does not invalidate — briefly: doctrine-scale ranking survives
> at 4.2× signal-to-noise, increment-scale ranking does not.

**Aggregation is Lowy's own formula, not ours.** With baseline scores b_m and published weights w_m (economic capability 17.5%, military capability 17.5%, economic relationships 15%, resilience 10%, future resources 10%, defence networks 10%, diplomatic influence 10%, cultural influence 10%):

```
composite(s) = Σ_m  w_m · clip(b_m + Δ_m,s , 0, 100)        for scenario s
fitness      = mean over the 3 scenarios
```

Sanity anchor: with Japan's 2025 measure scores (25.4, 30.1, 36.9, 34.3, 11.3, 56.5, 85.4, 48.5) these weights reproduce the official composite, 38.8. So if the judge returns all-zero deltas, fitness = 38.8, and **fitness reads directly as "projected Lowy points in 2030."** The only modeled step in the whole pipeline is the judge's per-measure deltas; everything downstream is the published index.

Returned to the archive: `combined_score` = mean composite; public metrics = per-scenario composites, worst case, per-measure mean deltas; `text_feedback` = the judge's mechanism sentences (≤ ~1,200 chars). That feedback is what steers the next mutation — the Shinka loop, unchanged.

### 2.3 The three worlds

Three fixed vignettes (~250 words each), written and frozen **before any run**, stored in the repo: (S1) grinding status quo — competition without rupture; (S2) Taiwan contingency in the window to 2030; (S3) US retrenchment/transactional turn. Fitness is the mean; the worst case is exposed as a public metric so we can always see which policies are robust rather than lucky. Freezing the vignettes and the judge prompt before the first run is our pre-registration; changing them afterwards means starting a new experiment, not editing this one.

---

## 3. Configuration and cost

Taken from the paper's per-task tables (Appendix B, Tables 1–3), adapted only where our task differs:

| Parameter | Value | Parameter | Value |
|---|---|---|---|
| Archive size | 40 | Elite selection ratio | 0.3 |
| Islands | 2 | Migration interval / rate | 10 / 0.1 |
| Parent selection | weighted, λ = 10 | Inspirations | 4 archive + top-2 |
| Patch types | [diff, full, cross] | Patch probabilities | [0.6, 0.3, 0.1] |
| Generations | pilot 30 → main 150 | Parallel jobs | 1–2 |
| Meta-scratchpad | every 10 gens, max 5 recs | Embedding filter | text-embedding-3-small, η = 0.95, + LLM novelty judge |
| LLM selection | UCB1, exploration 1.0 | Mutation ensemble | 4 models, mixed tiers, temps [0.0, 0.5, 1.0] |
| Judge / meta / novelty models | one cheap frozen model, temp 0, pinned version, **not** in the mutation ensemble | Fitness | mean Lowy composite over 3 scenarios |

Cost, ballpark and honest. One evaluation = 3 judge calls of ~2–3k tokens: a main run of 150 evaluations is ~1–1.5M judge-side tokens — single-digit euros at the frozen-judge tier. The mutation side dominates: the paper reports ~$40 cumulative for 500 proposals (Fig. 11) and ~$6 for 75 (Fig. 12), so a 150-evaluation main run lands around $10–40 depending on ensemble mix. The full study — 1 main run + 2 baselines + 3 ablations at the same budget — is roughly $100–250 and each run takes hours, not days, because our evaluation is seconds (we are the circle-packing case, not the MoE case). Pilot first (30 generations) before any long run.

---

## 4. Baselines, ablations, and what counts as evidence

**Baselines, same evaluation budget, same seed.** (a) *Blind random search*: sample portfolios uniformly from the schema. Your draft asserts the space is "clearly too vast for a blind random search" — this baseline turns the assertion into a measurement. (b) *Hill climbing*: always mutate the current best (the paper's greedy arm). This is also, in effect, "ask one LLM to iteratively improve Japan's foreign policy 150 times" — the non-evolutionary alternative a skeptical reviewer will name first. (c) *Full ShinkaEvolve*.

**Ablations, copied from paper §5:** parent selection (best-of-N / hill climbing / weighted), LLM ensemble (single / fixed / bandit), novelty rejection (off / threshold / + LLM judge). Ablation (i) is doing double duty: in Fig. 9 hill climbing plateaus early while weighted sampling keeps improving — the signature of a deceptive landscape. If that same pattern appears on our task, the submission's central claim (the search space is deceptive) stops being a metaphor and becomes a measured property of the fitness landscape.

**Research questions → evidence:**

| RQ | Question | Evidence |
|---|---|---|
| RQ1 | Does evolution find portfolios scoring above the projected status quo and above every hand-written seed? | Best-fitness trajectory vs. the 38.8-anchored seed; baseline comparison |
| RQ2 | Is the landscape deceptive? | Hill-climbing plateau vs. weighted-sampling improvement; multiple distinct high-fitness clusters |
| RQ3 | Does the machinery hold diversity — an option map, not one answer? | Embedding map of the archive; cluster count in the top decile; novelty-rejection ablation |
| RQ4 | What do high-fitness portfolios have in common, and where does Japan's actual 2022–26 policy sit in the archive? | Qualitative reading of top-K + the actual policy scored by the same evaluator |

RQ4 is where the study returns to Japanese Studies: the quantitative search runs first, the qualitative phase reads its output — the inversion your draft announces ("postpone the qualitative phase of inquiry").

**Figures plan, mirroring the paper:** improvement trajectory with cumulative cost (their Fig. 5); program evolution tree (their visualizer ships with the repo); archive embedding map colored by fitness — the option map; per-measure radar of champion vs. 2022 seed; baseline/ablation curves (their Fig. 9).

**Verification after search (rule 2).** The final top-20 archive is re-scored by a second frozen judge from a different model family; we report the rank correlation. High correlation = the discovery is about policies, not about one judge's taste. Then the human reading.

---

## 5. The counterfactual engine, made concrete

The archive is the counterfactual mechanism you set as the chassis. Every evaluated program is a policy Japan could have chosen; the evolution tree records which stepping stones led where; the embedding map shows the families of alternatives — the novelties history discards and does not preserve (Erwin). The forward look is the fitness itself: a projection to 2030, so the champions are candidate answers to "what should Japan do next," and the worst-case public metric shows what each answer costs under the scenario Japan fears most. Nothing extra is built for this: it is a reading of artifacts the run produces anyway.

---

## 6. Honest limitations (for the paper's conclusion, not for fixing now)

1. **The judge is a world model, not the world.** Per-measure deltas are an LLM's causal guesses. Mitigations inside the design: anchored rubric, frozen version, judge-swap check, human reading. The residual is the oracle problem — named in the conclusion, as you decided.
2. **Prior-boundedness.** Mutation LLMs and judge share a training distribution; a policy that is novel-but-good may be generated rarely and scored conservatively. Novelty rejection helps the variation side only.
3. **Three scenarios domesticate radical uncertainty.** A battery of named futures is a small-world construction; the large-world objection (Rosato's, in your framing) survives and belongs in the conclusion.
4. **One country, no adversary.** Fitness scores Japan alone; China and the US are scenario furniture, not adapting players. Coevolution is exactly what the slime-volleyball chapter of the submission handles, and a two-population version is future work.
5. **A power index is not a welfare function.** Lowy measures power; the multi-objective texture (security, prosperity, autonomy) enters through the 8 measures and the scenarios, not as separate objectives. This is the price of an externally authorized scalar, and it is stated openly.

---

## 7. Repo plan and milestones (nothing is created until you say go)

Name (decided 2026-08-17): `actir-shinkaevolve-evolved`. Structure:

```
actir-shinkaevolve-evolved/
├── tasks/japan_fp/
│   ├── initial.py          # 2022 seed portfolio (EVOLVE-BLOCK)
│   ├── evaluate.py         # validity gate + frozen judge + Lowy aggregation
│   ├── scenarios/          # S1–S3, frozen text
│   └── judge_prompt.md     # frozen rubric incl. 2025 baseline table
├── configs/                # pilot.yaml, main.yaml, ablations/
├── analysis/               # figures, embedding map, tree export
└── RESEARCH_DESIGN.md      # this document
```

Milestones, one at a time, each ending with something you can see and judge:

- **M0 — Freeze the spec.** You approve the Lowy-submeasure dial set (a yes/no — the list is Lowy's, not ours), the three scenario texts, and the judge rubric. Output: frozen task folder.
- **M1 — Calibration smoke test (go/no-go, no evolution yet).** The judge scores the 2022 seed plus 3–4 hand-written rival schools (autonomous rearmament; accommodation; status-quo-plus; middle-power internationalism). If the ordering is implausible, the evaluator is not ready and no search budget is spent. ~15 judge calls, cents.
- **M2 — Pilot.** 30 generations. Output: first trajectory, first tree, cost check.
- **M3 — Main run + baselines + ablations.** 150 evaluations each.
- **M4 — Analysis and writing.** Figures, judge-swap verification, qualitative reading, the experiment section of the submission.

Between M0 and M1 we do the failure-report pre-mortem you chose: you send the old reports (or a bullet list), and every past failure mode is checked against this design — guardrails adopted, architecture untouched.

---

## 8. Decision log

Premises (yours, prior): policy-as-program · Lowy as objective function · ShinkaEvolve engine, QD deferred to v2 · counterfactual + forward-looking chassis · third experiment of the "After 2022" submission.

Decided 2026-08-17: frozen judge + validity gate · 3-scenario battery, mean fitness, worst case public · failure reports as post-draft pre-mortem · search space expressed in Lowy's own 30-submeasure ontology, no bespoke instrument taxonomy.

Open (yours to take, in M0): the three scenario texts · judge model choice · feasibility bounds in the validity gate. Repo name: decided, `actir-shinkaevolve-evolved`.

---

*Paper references: Lange, Imajuku & Cetin (2025), "ShinkaEvolve: Towards Open-Ended and Sample-Efficient Program Evolution," arXiv:2509.19349, Sakana AI — §3 method, §4 case studies, §5 ablations, §6 limitations, Appendix A API, Appendix B task configs. Lowy data: power.lowyinstitute.org (2025 edition; Japan country page; published measure weights).*
