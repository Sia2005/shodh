"""
Runs the benchmark against both the full agent loop and a single-pass
RAG baseline, then prints a comparison table.

Usage:
    python -m evals.run_evals
    python -m evals.run_evals --limit 5   # quick smoke test
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from agent import critic, executor, planner, synthesizer
from agent.state import AgentState, BudgetExceeded, Phase
from evals.metrics import aggregate, citation_accuracy, factual_precision
from retrieval.ranker import dedupe, rerank_by_distance
from retrieval.store import VectorStore

BENCHMARK_PATH = Path(__file__).parent / "benchmark.jsonl"


def load_benchmark(limit: int | None = None) -> list[dict]:
    items = [json.loads(line) for line in BENCHMARK_PATH.read_text().splitlines() if line.strip()]
    return items[:limit] if limit else items


def run_baseline(question: str) -> str:
    """Single-pass RAG: one search, one fetch round, one synthesis call.
    No planning, no critique, no re-retrieval. This is the floor the
    agent needs to beat."""
    from agent import tools

    store = VectorStore(collection_name=f"baseline_{abs(hash(question))}")
    results = tools.search(question, max_results=5)
    for r in results:
        text = tools.fetch_and_clean(r.url)
        if not text:
            continue
        chunks = tools.chunk_text(text)
        ids = [f"{abs(hash(question))}_{i}" for i in range(len(chunks))]
        store.add(ids=ids, documents=chunks, metadatas=[{"url": r.url, "title": r.title}] * len(chunks))

    evidence = rerank_by_distance(dedupe(store.query(question, n_results=10)))
    result = synthesizer.synthesize(question, evidence)
    return result["report"], len(evidence)


def run_full_agent(question: str) -> tuple[str, int]:
    state = AgentState(question=question)
    store = VectorStore(collection_name=f"agent_{abs(hash(question))}")

    state.sub_questions = planner.plan(question)
    state.advance(Phase.SEARCHING)

    pending = list(state.sub_questions)
    try:
        while True:
            state.tick()
            for sq in pending:
                executor.run_sub_question(sq, state, store)
            pending = []

            state.advance(Phase.SYNTHESIZING)
            evidence = rerank_by_distance(dedupe(store.query(question, n_results=15)))
            result = synthesizer.synthesize(question, evidence)
            state.report = result["report"]

            state.advance(Phase.CRITIQUING)
            summary = "\n".join(f"- {e['title']} ({e['url']})" for e in state.evidence)
            verdict = critic.critique(state.report, summary)

            if verdict["passes"]:
                state.advance(Phase.DONE)
                return state.report, len(evidence)

            pending = verdict["gaps"] or [question]
            state.advance(Phase.SEARCHING)
    except BudgetExceeded:
        return state.report or "", len(state.evidence)


def score(report: str, n_sources: int, item: dict) -> dict:
    return {
        "id": item["id"],
        "citation_accuracy": citation_accuracy(report, n_sources),
        "factual_precision": factual_precision(report, item["answer_contains"]),
    }


def main(limit: int | None = None) -> None:
    benchmark = load_benchmark(limit)
    baseline_results, agent_results = [], []

    for item in benchmark:
        q = item["question"]
        print(f"[baseline] {q}")
        t0 = time.time()
        b_report, b_n = run_baseline(q)
        baseline_results.append({**score(b_report, b_n, item), "seconds": round(time.time() - t0, 1)})

        print(f"[agent]    {q}")
        t0 = time.time()
        a_report, a_n = run_full_agent(q)
        agent_results.append({**score(a_report, a_n, item), "seconds": round(time.time() - t0, 1)})

    baseline_agg = aggregate(baseline_results)
    agent_agg = aggregate(agent_results)

    print("\n=== Results ===")
    print(f"{'Metric':<25}{'Baseline':<12}{'Agent':<12}{'Delta':<10}")
    for key in ("avg_citation_accuracy", "avg_factual_precision"):
        b, a = baseline_agg[key], agent_agg[key]
        delta = f"{(a - b) * 100:+.1f}%"
        print(f"{key:<25}{b:<12.3f}{a:<12.3f}{delta:<10}")

    out = {"baseline": baseline_agg, "agent": agent_agg, "baseline_detail": baseline_results, "agent_detail": agent_results}
    out_path = Path(__file__).parent / "results.json"
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    main(limit=args.limit)
