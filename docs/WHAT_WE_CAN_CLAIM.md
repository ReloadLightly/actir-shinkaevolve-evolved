# What this project can claim, and what it cannot

Written 2026-08-17, after M1 run #1 and the offline pipeline. The question it
answers: **is there a reportable result for the submission, and can we
demonstrate in principle how LLM-powered search could assist Japan in
formulating foreign policy?**

Short answer: yes to both. But the demonstration belongs somewhere other than
where the design originally pointed it, and the evidence now says where.

---

## The reframe

The design never actually claimed the search would find the best policy.
RESEARCH_DESIGN §5 calls the archive "the counterfactual engine … a map of
alternatives, not an answer", and §6 forbids presenting any output as Japan's
optimal policy or as a forecast. §6.1 names the oracle problem as the residual
limitation, "named in the conclusion".

M1 turned that named limitation into a **measured quantity**. That is an
upgrade, not a retreat, and it is the strongest thing here.

So the claim moves from

> *evolution found a better Japanese foreign policy*

which the evidence does not support, to

> *evolutionary search with an LLM world model produces a navigable map of
> strategic alternatives, and the map's resolution is bounded by an oracle
> disagreement we measure directly*

which the evidence does support, and which is more useful to a methods
audience.

---

## Three claims, in ascending order of interest

### Claim 1 — the architecture works. Demonstrated, cost $0.

Mechanised generation of internally-consistent policy portfolios across a
30-dimensional space, constraint enforcement, LLM evaluation, archive with
lineage, analysis. The offline run (301 evaluations, $0.00, reproducible from a
seed) shows the machinery works on a landscape with known structure:

* the validity gate rejected 11 of 11 deliberate invariant breaches and 9 of 36
  out-of-bounds defence paths under machine-generated adversarial input;
* selection found the *correct* exploit — it moved effort into economic
  capability rather than future resources, which is right because 74.6 headroom
  × 0.175 weight beats 88.7 × 0.10;
* champion lineage depth 15, i.e. cumulative improvement rather than one lucky
  draw.

This is the *in-principle* demonstration, and it is already done. It says: the
pipeline from policy genotype to scored archive is real and mechanisable.

### Claim 2 — LLM-as-fitness has a measurable resolution floor. Demonstrated, cost $0.19.

Two judges from the same family, both at temperature 0, differing only in tier,
ranked five hand-constructed doctrines at Spearman **−0.300**. More precisely:

| | |
|---|---|
| `gpt-4.1` spread across five opposite doctrines | **0.696** |
| mean inter-judge disagreement | **0.437** |
| max inter-judge disagreement | **0.921** |
| signal-to-noise | **1.59** |

The disagreement between judges is larger than the range the stronger judge
assigns to the entire doctrinal space. This is quantified, reproducible from the
committed cache, and **generalises well beyond Japan** — it is a caution for any
design that uses an LLM judge as a fitness function over a weighted-index
objective.

### Claim 3 — is that floor reducible? The pivotal question, cost $0.008.

This is where the determinism probe stops being hygiene and becomes the decisive
experiment.

* **If the judge is non-deterministic**, the disagreement is sampling error.
  Averaging works: ~20 independent repeats buys 0.10-point resolution, which is
  ~9,000 calls ≈ **$23** on `gpt-4.1-mini`. Out of reach at $15, but the method
  *scales* — the paper can say resolution is purchasable and quote the price.
* **If the judge is deterministic**, the disagreement is systematic, between
  models. No number of repeats helps, at any budget. The method then requires
  *panels* of judges and the reporting of distributions rather than point
  estimates — a substantive design conclusion.

Both answers are publishable, and they imply different future work. That is what
a methods contribution looks like.

---

## What LLM-powered search can demonstrably offer Japanese foreign-policy work

Independent of whether the ranking is reliable, four capabilities are shown:

1. **Option generation at scale under hard constraints.** 301 internally
   consistent portfolios in seconds, every one obeying budget closure, dial
   vocabulary, sequencing and a defence-spending feasibility bound. Enumerating
   the option space is itself analytically useful.
2. **Surfacing trade-off structure.** The search discovers *which* measures are
   purchasable and at what cost to others — the backfire terms, the headroom
   asymmetry between diplomatic influence at 85.4 and future resources at 11.3.
3. **An auditable corpus of causal claims.** Every judge call returns a
   mechanism sentence. A pilot yields several hundred traceable "if Japan does X
   then Y because Z" statements, each attached to a specific allocation. That is
   a stress-testing instrument for an analyst, not an oracle.
4. **Locating genuine controversy.** The −0.300 is not only a defect. It says
   two reasonable world models rank *autonomous rearmament* against
   *middle-power internationalism* in opposite orders — and that is a live
   division in Japanese strategic thought, not a technical artefact. The system
   identified where the judgement is actually contested rather than settled.

Point 4 is the one worth writing carefully. A tool that reliably tells you
*where reasonable analysts will disagree* is doing real work even when it cannot
tell you who is right.

---

## What cannot be claimed

State these plainly; they are load-bearing for the paper's honesty.

* **Not** that any evolved portfolio is better than the December 2022 seed. At
  30 evaluations per arm with noise of 0.4–0.9 composite points, a champion's
  margin is inside the error bar.
* **Not** that the numbers forecast Lowy Index values. The judge is a world
  model, not the world.
* **Not** that three scenarios span the relevant uncertainty (RESEARCH_DESIGN
  §6.3 already concedes this).
* **Not** that the ranking is stable, which is the whole point of Claim 2.

---

## What it costs to get there

| Step | Buys | Cost |
|---|---|---|
| Determinism probe | Decides Claim 3 — the pivotal one | $0.008 |
| Rubric v2 re-test | Whether the M1 correction restored scenario sensitivity | $0.008 |
| Mutation smoke | Whether the loop can run at all | $0.036 |
| One real pilot | A real archive: the map, the trajectory, the mechanism corpus | ~$1.00 |
| Judge-swap on that archive | Claim 2 measured on *evolved* candidates, not just hand-written seeds | ~$0.20 |
| **Total** | | **~$1.25** |

$0.19 of $15 is spent. The remaining programme costs about a tenth of what is
left, which leaves room to repeat it after a rubric correction.

**The binding constraint was never the budget.** It is the oracle's resolution,
and more money would not have moved it — which is itself the finding.

---

## Recommended shape for the submission

*The Japan case is the vehicle; the measurement is the contribution.*

1. **Method** — portfolio genotype over the Index's own 30 submeasures, two-stage
   evaluation, frozen judge, archive. Note the deviations already logged in
   `DECISIONS.md`.
2. **In-principle demonstration** — the offline surrogate run. The machinery
   works, with a control whose structure is known in advance, at zero cost. This
   isolates the oracle as the variable under test.
3. **The measurement** — M1 and the judge swap. The resolution floor, quantified.
4. **The pilot** — one real archive as the illustrative map of alternatives, with
   the mechanism corpus and the trajectory, explicitly *not* presented as a
   ranking.
5. **Conclusion** — the oracle problem, no longer as a caveat but as a number,
   with the determinism result deciding whether it is purchasable or structural.

The surrogate control in step 2 is what makes step 3 credible: the same search
machinery succeeds where the landscape has known structure and degrades where
the oracle supplies it. That contrast is the argument.
