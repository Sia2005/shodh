# Eval results: agent vs. single-pass baseline

- Benchmark: `evals/benchmark.jsonl`, 30 questions, 5 categories x 6 (selection criteria frozen in `evals/README.md` before any question was written)
- Run at: 2026-07-27 18:59 UTC
- `GEMINI_MODEL` configured: `gemini-3.5-flash-lite` -> resolved to `gemini-3.5-flash-lite` (version `3.5-flash-lite-07-2026`)

**Citation accuracy** (model-graded, `evals/citation_judge.py`): does the cited evidence actually support the sentence citing it, per an independent Gemini judge applied identically to both reports. **Citation validity** (structural, `evals/metrics.py`, unchanged): does `[n]` merely point to a source index that exists. **Factual precision** (`evals/metrics.py`, unchanged): fraction of the question's key facts (`answer_contains`) found in the report. All three are shown as raw-fraction/percentage (e.g. `4.5/6 (75.0%)`) because per-category N is only 6.

## Overall

### All categories

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 24/30 (80.0%) | 24/30 (80.0%) | +0.0 pp |
| Citation validity (structural) | 20/30 (66.7%) | 21/30 (70.0%) | +3.3 pp |
| Factual precision | 12/30 (40.0%) | 13/30 (43.3%) | +3.3 pp |

## By category

### Recent events

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 5/6 (83.3%) | 3/6 (50.0%) | -33.3 pp |
| Citation validity (structural) | 6/6 (100.0%) | 2/6 (33.3%) | -66.7 pp |
| Factual precision | 5/6 (83.3%) | 3/6 (50.0%) | -33.3 pp |

### Numeric / statistical claims

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 6/6 (100.0%) | 4/6 (66.7%) | -33.3 pp |
| Citation validity (structural) | 3/6 (50.0%) | 3/6 (50.0%) | +0.0 pp |
| Factual precision | 2/6 (33.3%) | 2/6 (33.3%) | +0.0 pp |

### Multi-source synthesis

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 4/6 (66.7%) | 6/6 (100.0%) | +33.3 pp |
| Citation validity (structural) | 4/6 (66.7%) | 6/6 (100.0%) | +33.3 pp |
| Factual precision | 2/6 (33.3%) | 2/6 (33.3%) | +0.0 pp |

### Source disagreement

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 5/6 (83.3%) | 6/6 (100.0%) | +16.7 pp |
| Citation validity (structural) | 3/6 (50.0%) | 5/6 (83.3%) | +33.3 pp |
| Factual precision | 1/6 (16.7%) | 4/6 (66.7%) | +50.0 pp |

### Single-source RAG fails

| Metric | Baseline | Agent | Delta |
|---|---|---|---|
| Citation accuracy (model-graded) | 4/6 (66.7%) | 5/6 (83.3%) | +16.7 pp |
| Citation validity (structural) | 4/6 (66.7%) | 5/6 (83.3%) | +16.7 pp |
| Factual precision | 2/6 (33.3%) | 2/6 (33.3%) | +0.0 pp |

## Pipeline errors

These questions scored 0.0 on every metric because the run itself errored out (not because the report was graded and found wrong) -- in every case here, `agent/planner.py` raised on a malformed Gemini JSON response (see `evals/run_evals.py::_run_scored`). Counted in the aggregate above as failures either way.

| Path | Question ID | Category | Error |
|---|---|---|---|
| baseline | q022 | source_disagreement | Synthesizer did not return valid JSON: '{\n  "claims": [\n    {\n      "text": "Estimates of the global wild tiger population disagree sharply and have made comparisons over time unreliable because of improvements in counting methods, a more complete counting of the species, and past reliance on educated guesses 15 years ago [1].",\n    },\n    {\n      "text": "Advancements in camera trap technology, genetic testing, data modeling, government collaboration, and an increased number of rangers tracking tigers have vastly improved monitoring efforts [1].",\n    },\n    {\n      "text": "Inconsistent monitoring methods by tiger range states have produced false positive population increases, and previous IUCN assessments incorporated conservative estimates or underestimates that guaranteed future increases [1].",\n    },\n    {\n      "text": "Two conflicting figures for the global wild tiger population are the 2015 estimate of 3,200 and the 2022 estimate of 4,500 [2, 4].",\n    }\n  ],\n  "report": "Estimates of the global wild tiger population disagree sharply and have made comparisons over time unreliable due to historical reliance on educated guesses, subsequent advancements in counting methods, and a more complete counting of the species [1]. Improvements such as camera trap technology, genetic testing, data modeling, government collaboration, and more rangers tracking tigers have vastly enhanced monitoring efforts [1]. Additionally, inconsistent monitoring methods by tiger range states have caused false positive population increases, while previous IUCN assessments used conservative estimates or underestimates that nearly guaranteed future increases [1]. Two conflicting figures representing these estimates are 3,200 wild tigers in 2015 and an average of 4,500 wild tigers in 2022 [2, 4].",\n  "contradictions": []\n}' |
| agent | q002 | recent_events | Planner did not return valid JSON: '[Who won the 2026 West Bengal state legislative assembly election?, Which political party secured a majority in the 2026 West Bengal legislative assembly elections?]' |
| agent | q003 | recent_events | Planner did not return valid JSON: '[="What are the results of the 2026 Tamil Nadu state assembly election?", "Which political party won the most seats in the 2026 Tamil Nadu legislative assembly election?", "How many seats did the single largest party win in the 2026 Tamil Nadu assembly election?"]' |
| agent | q006 | recent_events | Planner did not return valid JSON: '[Who is the CEO of Intel in 2026?, "Intel executive leadership announcements 2025 2026", "Current Chief Executive Officer of Intel Corporation"]' |
| agent | q009 | numeric_stats | Planner returned malformed structure: [['What is the projected world population for mid-2026 according to the United Nations?']] |
| agent | q012 | numeric_stats | Planner did not return valid JSON: '[कौन सी वैश्विक ईवी बिक्री 2025 में दर्ज की गई?", "2025 में इलेक्ट्रिक वाहनों की कुल वैश्विक बिक्री कितनी थी?"]' |
| agent | q027 | single_source_rag_fails | Planner did not return valid JSON: '[\n  What is the latest stable release of Python in mid-2026?,\n  What are the release dates and version numbers for Python releases in 2025 and 2026?\n]' |

**Read the by-category table with this in mind:** 6 of the agent's 30 runs failed at the planning step before any report was produced, concentrated in: recent_events (3), numeric_stats (2), single_source_rag_fails (1). Categories with more planner failures look worse on every agent metric for that reason, not necessarily because retrieval or synthesis quality was worse there.
