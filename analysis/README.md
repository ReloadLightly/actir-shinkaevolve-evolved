# Analysis (M4)

Figures planned in RESEARCH_DESIGN section 4, mirroring the paper:

- improvement trajectory with cumulative cost (their Fig. 5)
- program evolution tree (ShinkaEvolve's own visualizer)
- archive embedding map coloured by fitness — the option map
- per-measure radar, champion vs. the 2022 seed
- baseline and ablation curves (their Fig. 9)

`archive_analysis.py` is built and working. It reads any archive in the
standard record shape — surrogate or real — and emits `report.md`,
`analysis.json`, and standalone SVG figures:

```bash
python scripts/offline_evolution.py --generations 300 --seed 0   # free, no LLM
python analysis/archive_analysis.py --archive runs/offline/archive.jsonl
```

`example/` holds the output of exactly that command, so the figures can be
inspected without running anything.

SVG is hand-emitted rather than drawn with matplotlib: Stage A's dependency
list is pyyaml and pytest, and an analysis layer that needs a scientific stack
installed is one more thing to go wrong at the worst moment.

**Anything produced from a surrogate archive is stamped NOT A RESULT**, in the
JSON, in the report, and on stdout. A surrogate trajectory is visually
indistinguishable from a real one and the two mean entirely different things.
