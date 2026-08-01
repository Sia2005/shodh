# Eval results: agent vs. single-pass baseline

- Benchmark: `evals/benchmark.jsonl`, 30 questions, 5 categories x 6 (selection criteria frozen in `evals/README.md` before any question was written)
- Run at: 2026-07-31 17:00 UTC
- `GEMINI_MODEL` configured: `gemini-3.5-flash-lite` -> resolved to `gemini-3.5-flash-lite` (version `3.5-flash-lite-07-2026`)

**Citation accuracy** (model-graded, `evals/citation_judge.py`): does the cited evidence actually support the sentence citing it, per an independent Gemini judge applied identically to both reports. **Citation validity** (structural, `evals/metrics.py`, unchanged): does `[n]` merely point to a source index that exists. **Factual precision** (`evals/metrics.py`, unchanged): fraction of the question's key facts (`answer_contains`) found in the report. All three are shown as raw-fraction/percentage (e.g. `4.5/6 (75.0%)`) because per-category N is only 6.

## Overall

### All categories

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 27/30 (90.0%) | 29.6667/30 (98.9%) | +8.9 pp |
| Citation validity (structural) | 23/30 (76.7%) | 25/30 (83.3%) | +6.7 pp |
| Factual precision | 14.5/30 (48.3%) | 19.5/30 (65.0%) | +16.7 pp |

## By category

### Recent events

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 6/6 (100.0%) | 6/6 (100.0%) | +0.0 pp |
| Citation validity (structural) | 3/6 (50.0%) | 1/6 (16.7%) | -33.3 pp |
| Factual precision | 5.5/6 (91.7%) | 5.5/6 (91.7%) | +0.0 pp |

### Numeric / statistical claims

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Citation validity (structural) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Factual precision | 2/6 (33.3%) | 4/6 (66.7%) | +33.3 pp |

### Multi-source synthesis

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 5/6 (83.3%) | 5.66667/6 (94.4%) | +11.1 pp |
| Citation validity (structural) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Factual precision | 2/6 (33.3%) | 3/6 (50.0%) | +16.7 pp |

### Source disagreement

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Citation validity (structural) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Factual precision | 2/6 (33.3%) | 5/6 (83.3%) | +50.0 pp |

### Single-source RAG fails

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 6/6 (100.0%) | 6/6 (100.0%) | +0.0 pp |
| Citation validity (structural) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Factual precision | 3/6 (50.0%) | 2/6 (33.3%) | -16.7 pp |
