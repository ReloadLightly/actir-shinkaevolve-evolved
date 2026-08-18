# Preflight, 2026-08-18: three failures, one of them fatal to the pilot

Run [32084865677](https://github.com/ReloadLightly/actir-shinkaevolve-evolved/actions/runs/32084865677).
Judge `gpt-4.1-mini-2025-04-14`, temperature 0.0, 10 judge calls + 1 mutation
call, **$0.0232**. Every workflow step reported success — the *steps* passed;
three of the four *probes* did not.

This is what preflight is for. Each finding below would have been discovered
anyway, but only by spending the pilot's $2.00 to learn it.

| Probe | Verdict | Consequence |
|---|---|---|
| Determinism | **FAIL** | "Frozen judge" is not a true description. Claim withdrawn. |
| Observability | **NOT ESTABLISHED** | The probe could not tell sight from noise. My bug, now fixed. |
| Rubric v2 | **FAIL** | Scenario sensitivity 0.20, at the self-noise floor of 0.17. |
| Mutation | **FAIL, blocking** | 0/1 models produced a portfolio the gate accepted. |

---

## 1. The judge is not deterministic at temperature 0

Three identical requests, cache bypassed:

| measure | run 1 | run 2 | run 3 | spread |
|---|---|---|---|---|
| economic_capability | +1.5 | +1.5 | +1.5 | 0.000 |
| military_capability | +3.5 | +3.0 | +3.5 | 0.500 |
| **economic_relationships** | **+0.5** | **−0.5** | **−0.5** | **1.000** |
| resilience | +1.0 | +1.0 | +1.0 | 0.000 |
| future_resources | +0.3 | +0.5 | +0.5 | 0.200 |
| defence_networks | +2.0 | +2.0 | +2.0 | 0.000 |
| diplomatic_influence | +0.2 | +0.5 | +0.5 | 0.300 |
| cultural_influence | +0.1 | +0.3 | +0.3 | 0.200 |

Two observations the aggregate hides.

**Runs 2 and 3 are identical; run 1 is the outlier.** This is not uniform
randomness. It is a mostly-deterministic model that occasionally diverges —
the familiar consequence of batching and expert-routing nondeterminism in
production serving, not of a temperature setting we control. We cannot turn
it off.

**One measure changed sign.** On identical input the judge said Japan's
economic relationships both improve and deteriorate. Magnitude noise degrades
a ranking; a sign flip corrupts the *mechanism sentence* attached to it, and
those sentences are the qualitative output this project exists to produce.

### The composite is a different story, and both halves matter

Lowy's weights spread across eight measures, so independent per-measure errors
partly cancel:

```
composite by run     40.1575   39.9900   40.0775
self-noise (spread)   0.1675
```

Set against what M1 measured:

| | |
|---|---|
| Judge self-noise, identical input | **0.17** |
| Effect across five opposite doctrines (M1) | **0.696** |
| Inter-judge disagreement, mini vs 4.1 (M1) | **0.921** |

**Doctrine-scale signal-to-self-noise is 4.2×.** That is much better than the
raw per-measure table suggests, and it is a genuine correction to the gloomier
reading in `docs/M1_FINDINGS.md`: the judge *can* separate accommodation from
autonomous rearmament well clear of its own noise.

But evolution does not compare doctrines. **It compares a portfolio with its
own mutated child.** Any mutation moving the composite by less than ~0.17 is
scored by a coin flip, and most single-dial reallocations are far smaller than
that. The honest statement is:

> The judge resolves **doctrines**, not **increments**.

### What this changes

- **"Frozen judge" is withdrawn.** The content-hash cache freezes whichever
  sample arrived first; replaying it reproduces a *draw*, not a *judgement*.
  The cache remains a valid audit trail and a valid cost control. It is not
  determinism, and the writeup must not call it that.
- **It vindicates the MAP-Elites decision, but not the argument I gave for
  it.** Coverage — the count of filled behaviour cells — needs no comparison
  at all and is immune to this. But MAP-Elites' per-cell "is this better than
  the current occupant" question compares *behaviourally similar* portfolios,
  which is precisely the regime where the judge is weakest. So coverage is
  robust; **which elite occupies each cell is noisy**, and the writeup must
  claim only the former.
- **Averaging works, if bought.** Self-noise is sampling noise, so n draws cut
  it by √n. At $0.0023/call, n=3 over a 200-evaluation pilot is ~$4.14 — over
  the $2.00 ceiling. So: n=1 during search, n=3 when re-scoring the final
  archive, where it is affordable and where the reported numbers live.

---

## 2. Observability: my probe was wrong, not the judge

The probe reported shifts of 1.0–1.3 for flattened phases, removed initiatives
and a raised defence path, and concluded *"All fields are visible to the
judge."*

It could not have known that. The test was `noticed = shift > 1e-9` — any
nonzero difference counted as sight. The determinism probe, **in the same
run**, measured up to 1.000 of pure self-noise on the same scale. A 1.0 shift
is indistinguishable from the judge resampling.

Fixed: the significance threshold is now the measured self-noise, per-measure
*and* composite, and a shift that clears neither is reported as `within noise`,
one that clears both as `SEEN`, and one that clears exactly one as `marginal`.
Mock and surrogate backends are closed-form, so their floor is exactly zero by
construction rather than by measurement. With no floor available the probe
prints `UNCALIBRATED` and returns no verdict.

The original question — *is 40% of the mutation budget spent on fields fitness
cannot see?* — is therefore **still open**. Answering it properly needs
repeated draws per variant, which is the expensive version of this probe.

---

## 3. Rubric revision 2 did not fix scenario sensitivity

Accommodation, the doctrine that most depends on the scenario:

```
S1 39.11   S2 39.06   S3 38.91     spread 0.20
```

Run #1 gave 0.19. The correction moved it by 0.01, and S3 (US retrenchment) is
still its worst scenario, which remains backwards for a doctrine premised on
accommodating a region where the US is withdrawing.

The reading has changed, though. **0.20 sits at the 0.17 self-noise floor.**
Accommodation's measured scenario sensitivity is not weak; it is *unresolvable
at n=1*. Rewording the rubric a third time cannot fix a measurement below the
noise floor — only repeated draws can. `FROZEN.json` therefore stays at
`0.3.0-m1-corrected`, status **DRAFT**, and rule 5 is a known open item rather
than a fixed one.

---

## 4. The blocker: no mutation model could produce a valid portfolio

```
| model        | parsed | ran | gate | shares | cost    |
| gpt-4.1-nano |  yes   | yes | FAIL |   0.67 | $0.0008 |

gpt-4.1-nano rejected for:
    - shares must sum to 1.0 (+/- 1e-06), they sum to 0.670000
```

The model wrote a coherent portfolio. It then failed to make 30 decimals add to
1.0 — and the pilot config uses nano alone, so **0/1**. Every mutation would
have been rejected and the pilot would have burned its entire $2.00 ceiling
without producing one scored individual.

The prompt already said *"must sum to EXACTLY 1.0. Check your arithmetic."*
Saying it louder is not a fix.

### The fix: repair, not rejection

Shares are a **normalisation convention**. "Marginal strategic effort" has no
natural unit, so only the *proportions* carry policy meaning. A portfolio
summing to 0.67 is not proposing less effort — it is proposing the same
trade-offs with the arithmetic botched. Rescaling it is information-preserving,
and rejecting it discards a good proposal over a bad sum.

So the gate now rescales, provided the raw sum lands in `[0.5, 2.0]`. Outside
that band, and for any negative share, it still rejects — those are incoherent
allocations rather than slipped sums, and repair would hide them.

The trade-off constraint, which is the substantive one, survives intact: after
normalisation, raising one dial still lowers every other. The prompt now says
that instead of demanding arithmetic:

> Shares are proportions of one finite budget of effort, and are normalised for
> you — so do not spend effort on arithmetic, spend it on the allocation.

The repair rate is published as `shares_repaired` and `share_sum_raw` on every
individual, so "how often did the models need rescuing" is a **reported
statistic about model capability**, never a hidden convenience.

---

## What this does to the plan

**The pilot does not run until a re-flighted mutation probe passes.** That is
the whole point of having run this first: $0.0232 bought the finding that
$2.00 would have been wasted.

Ordered:

1. ~~Repair-not-reject in the gate; retarget the prompt at trade-offs.~~ Done.
2. ~~Calibrate the observability verdict against measured self-noise.~~ Done.
3. Re-run preflight (~$0.03). Gate: **mutation must pass**.
4. Then, and only then, the pilot.
5. Report coverage as the primary result. Per-cell elites carry a noise caveat.
6. Re-score the final archive at n=3 and report the standard error.

## What survives unchanged

The pilot's *plumbing* was validated for free in the same dispatch
([run 32084867474](https://github.com/ReloadLightly/actir-shinkaevolve-evolved/actions/runs/32084867474)):
real ShinkaEvolve installed from source and confirmed to be the evolution
engine rather than the identically-named image-upscaling package, all configs
validated against the live API, the typed spend gate correctly holding at
no-spend with every spending step skipped. None of the four failures is
infrastructural.
