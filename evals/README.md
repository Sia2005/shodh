# Eval harness

Compares the full agent loop (plan → search → synthesize → critique →
targeted re-search) against a single-pass RAG baseline (one search, one
fetch round, one synthesis call, no critique) on a fixed 30-question
benchmark.

This file is written, and the categories below are fixed, **before** a
single benchmark question is drafted. That ordering is the point: the
selection criteria can't be quietly reshaped around whichever questions
turn out to make the agent look good.

## Rules for keeping this honest

1. **Criteria before questions.** The five categories and their
   definitions below were fixed first. Every question in
   `benchmark.jsonl` is written to satisfy a category definition that
   already existed, not the other way around.
2. **Reference answers come from primary/independent sources, looked up
   directly** (official statistics, primary reporting, or — for
   recency-sensitive facts — a live web search against current sources)
   — never by running the agent or baseline and copying what it said.
   `answer_contains` is finalized before either path is ever run on that
   question.
3. **One run each.** The baseline and the full agent each run exactly
   once against the frozen benchmark, at the end, to produce
   `results.md`. No re-running individual questions, no swapping
   `answer_contains` after seeing which path got what.
4. **No post-hoc tuning.** If the agent underperforms the baseline on a
   category, that's a reported result, not a prompt to go tune the agent
   (or the benchmark) until it isn't. `agent/` is explicitly off-limits
   for this reason — see the repo's `CLAUDE.md`.
5. **The 30/6-per-category shape is enforced by
   `tests/test_benchmark.py`**, not just this document, so a future edit
   that quietly drops a hard question or rebalances categories fails CI
   instead of going unnoticed.

### Known limitation

The same author (me, in this sitting) both wrote the harness and
authored the benchmark questions. That's weaker than a benchmark
written by a separate party with no stake in the agent's score — I
can't claim full independence, only that I followed the rules above
(criteria fixed first, answers sourced independently, no peeking before
finalizing, no edits after scoring) and that the constraints are now
encoded as tests rather than just intentions.

## Categories (6 questions each, 30 total)

**`recent_events`** — Facts that changed or were established recently
enough that a model's training data is a poor bet and the agent has to
actually retrieve current information. Good questions here have a
single, stable, checkable answer (a name, a date, a count) sourced from
current reporting at benchmark-freeze time.

**`numeric_stats`** — Questions whose answer is a specific number from
an official or authoritative source (population, GDP, market cap,
transaction volume, etc.). Tests whether the agent gets the *exact*
figure right rather than a plausible-sounding one — numbers are where
RAG hallucination is easiest to catch and easiest to fudge.

**`multi_source_synthesis`** — Answering correctly requires combining
facts that don't both appear on any single page (e.g. comparing a
figure across two entities, or a total that has to be assembled from
parts reported separately). A one-shot single-source RAG pass is
structurally unlikely to have gathered everything it needs; this is
where planning/decomposition should earn its keep.

**`source_disagreement`** — Topics with real, citable disagreement
between sources (disputed counts, conflicting estimates, differently
computed statistics). There isn't one clean ground truth to pattern-match
against; `answer_contains` captures the commonly-cited figures/positions
on record rather than declaring one side correct. This category is
mainly a qualitative check — does the report surface the disagreement
(the agent has an explicit `contradictions` output for this) instead of
silently picking a side — more than a strict substring-match win.

**`single_source_rag_fails`** — Questions engineered so that the
obvious top search result gives a wrong or incomplete answer: entity
disambiguation traps (two things share a name), figures that need a
small computation rather than being stated verbatim anywhere, or
questions where the first hit is outdated relative to the current
answer. This is the category the whole critique/re-search loop exists
for.

## Metrics

- **Factual precision** (`evals/metrics.py`, author-owned, unchanged):
  fraction of a question's `answer_contains` key facts that appear
  verbatim in the report. Simple substring match — deliberately cheap
  and deterministic, good enough for names/dates/figures.
- **Citation accuracy** — whether a cited source *actually supports* the
  sentence citing it. `evals/metrics.py::citation_accuracy` only checks
  that `[n]` points to a source that exists in range; it does not check
  semantic support, and it's author-owned so it isn't being changed here.
  `evals/citation_judge.py` adds a model-graded check on top: it pairs
  each cited sentence with the actual evidence text at that citation
  index and asks Gemini, independently of the agent's own critic,
  whether it's actually supported. This is the metric reported as
  "citation accuracy" in `results.md`; the structural check is reported
  separately as "citation validity" so the two aren't conflated.

  Why not reuse `agent/critic.py`'s grading for this? The agent loop is
  optimized to satisfy its own critic (that's literally the re-search
  trigger), so scoring the agent with its own critic would bias the
  comparison in its favor — and the baseline has no critic to begin
  with. One external judge applied the same way to both reports after
  the fact is the only apples-to-apples comparison.

  This makes citation accuracy non-deterministic (an LLM judge, not a
  fixed rule) and adds one extra Gemini call per report. That's a real
  cost, and the judge can itself be wrong in the same way the thing it's
  checking can be wrong — but a purely structural check can't answer the
  question that was actually asked ("do the sources support the claim"),
  so the extra call is the tradeoff being made here.

## Reproducibility

`results.md` logs the configured `GEMINI_MODEL` value (an alias, e.g.
`gemini-flash-latest`) alongside the concrete model name and version it
resolved to at run time (via `genai.get_model()`), since aliases can
point to a different underlying model on a different day.
