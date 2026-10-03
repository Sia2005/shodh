"""
Per-query retrieval latency benchmark for the VectorStore interface.

Engine-agnostic on purpose: it imports VectorStore from retrieval.store and
only touches the public add()/query() surface, so the *same* script measures
whichever backend store.py is wired to (Chroma today, khoj after the swap).
That is what makes "before" and "after" directly comparable — identical
corpus, identical queries, identical embedder, only the index changes.

No network and no API keys: the corpus is built from the frozen eval
benchmark text that already lives in the repo, and chunked with a copy of
agent.tools.chunk_text (copied rather than imported so this script never
triggers agent.config.validate(), which would demand GEMINI/TAVILY keys).

Methodology
-----------
Populate one store with a fixed corpus, then for each of the fixed research
questions call store.query() REPEATS times. We report the median of every
per-query wall-clock sample (REPEATS * n_queries samples total); the median
is robust to the occasional scheduler/GC spike. A warmup query is run first
and discarded so the embedding model's one-time load does not pollute the
timings. query() embeds the text and searches, so this is the real cost the
plan-retrieve-critique loop pays per retrieval, not an isolated index micro.

Usage
-----
    python -m evals.bench_retrieval --label chroma   # before the swap
    python -m evals.bench_retrieval --label khoj      # after the swap

Results accumulate (keyed by label) in evals/retrieval_bench.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from retrieval.store import VectorStore

_HERE = Path(__file__).resolve().parent
_BENCHMARK = _HERE / "benchmark.jsonl"
_RESULTS = _HERE / "retrieval_bench.json"

REPEATS = 10
N_RESULTS = 15  # matches the agent's synthesize-phase store.query() call
# Each benchmark question's text is short; tile it into a corpus whose size
# matches the agent's real operating point (a few hundred chunks per question
# store) so the index is exercised at a realistic scale, not on 30 vectors.
CORPUS_TARGET_CHUNKS = 400


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Copy of agent.tools.chunk_text. Duplicated deliberately — see module
    docstring — so importing this benchmark never requires API keys."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _load_questions() -> list[str]:
    """The fixed query set: the questions from the frozen eval benchmark."""
    questions: list[str] = []
    with _BENCHMARK.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line)["question"])
    return questions


def _build_corpus() -> list[str]:
    """Deterministic corpus from the benchmark's own text (question + notes +
    expected-answer fragments). Tiled up to CORPUS_TARGET_CHUNKS so every run
    sees the same realistically sized corpus."""
    blobs: list[str] = []
    with _BENCHMARK.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            parts = [row.get("question", ""), row.get("notes", "")]
            parts.extend(row.get("answer_contains", []))
            blobs.append(" ".join(p for p in parts if p))

    chunks: list[str] = []
    i = 0
    # Tag each tiling pass so chunk texts stay distinct (distinct embeddings),
    # otherwise dedupe-style collapse would shrink the effective corpus.
    while len(chunks) < CORPUS_TARGET_CHUNKS:
        blob = blobs[i % len(blobs)]
        for chunk in _chunk_text(f"[pass {i // len(blobs)}] {blob}"):
            chunks.append(chunk)
            if len(chunks) >= CORPUS_TARGET_CHUNKS:
                break
        i += 1
    return chunks


def _backend_name() -> str:
    """Let store.py self-report its backend if it exposes one; fall back to
    'unknown' so the benchmark never hard-depends on that constant existing."""
    import retrieval.store as store_mod

    return getattr(store_mod, "BACKEND", "unknown")


def run_benchmark(label: str) -> dict:
    questions = _load_questions()
    corpus = _build_corpus()

    store = VectorStore(collection_name=f"bench_{label}")
    store.reset()  # start clean even if a persistent backend has stale state
    ids = [f"doc_{i}" for i in range(len(corpus))]
    metadatas = [
        {"url": f"https://example.test/{i}", "title": f"doc {i}", "sub_question": "bench"}
        for i in range(len(corpus))
    ]
    store.add(ids=ids, documents=corpus, metadatas=metadatas)

    # Warmup: pays the embedding-model load / first-call cost once, discarded.
    store.query(questions[0], n_results=N_RESULTS)

    samples_ms: list[float] = []
    for _ in range(REPEATS):
        for q in questions:
            t0 = time.perf_counter()
            store.query(q, n_results=N_RESULTS)
            samples_ms.append((time.perf_counter() - t0) * 1000.0)

    store.reset()

    result = {
        "label": label,
        "backend": _backend_name(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "corpus_chunks": len(corpus),
        "n_queries": len(questions),
        "repeats": REPEATS,
        "n_results": N_RESULTS,
        "samples": len(samples_ms),
        "median_ms": round(statistics.median(samples_ms), 4),
        "mean_ms": round(statistics.fmean(samples_ms), 4),
        "p90_ms": round(sorted(samples_ms)[int(len(samples_ms) * 0.9)], 4),
        "min_ms": round(min(samples_ms), 4),
        "max_ms": round(max(samples_ms), 4),
    }
    return result


def _save(result: dict) -> None:
    existing: dict = {}
    if _RESULTS.exists():
        existing = json.loads(_RESULTS.read_text(encoding="utf-8"))
    existing[result["label"]] = result
    _RESULTS.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label",
        required=True,
        help="Key to store this run under (e.g. 'chroma' before the swap, 'khoj' after).",
    )
    args = parser.parse_args()

    result = run_benchmark(args.label)
    _save(result)

    print(f"backend={result['backend']}  corpus={result['corpus_chunks']} chunks  "
          f"queries={result['n_queries']}x{result['repeats']}")
    print(f"median per-query retrieval latency: {result['median_ms']:.3f} ms  "
          f"(mean {result['mean_ms']:.3f}, p90 {result['p90_ms']:.3f})")
    print(f"saved -> {_RESULTS.relative_to(_HERE.parent)} [{result['label']}]")


if __name__ == "__main__":
    main()
