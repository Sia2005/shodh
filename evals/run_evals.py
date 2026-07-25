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
    # No planning happened for the baseline — the question stands in as its
    # own single sub-question.
    result = synthesizer.synthesize(question, [question], evidence)
    return result["report"], len(evidence)


def run_full_agent(question: str) -> tuple[str, int]:
    state = AgentState(question=question)
    store = VectorStore(collection_name=f"agent_{abs(hash(question))}")

    state.sub_questions = planner.plan(question)
    state.advance(Phase.SEARCHING)

    pending = [{"sub_question": sq, "search_query": sq} for sq in state.sub_questions]
    try:
        while True:
            state.tick()
            for task in pending:
                executor.run_sub_question(
                    task["sub_question"], state, store, search_query=task["search_query"]
                )
            pending = []

            state.advance(Phase.SYNTHESIZING)
            evidence = rerank_by_distance(dedupe(store.query(question, n_results=15)))
            # Charge where evidence actually enters a Gemini prompt, not at
            # fetch time (see agent/executor.py) — kept in sync with api/main.py.
            state.spend(sum(len(e.get("text", "")) for e in evidence) // 4)
            result = synthesizer.synthesize(question, state.sub_questions, evidence)
            state.report = result["report"]
            state.claims = result["claims"]
            state.contradictions = result.get("contradictions", [])

            if not state.claims:
                state.advance(Phase.FAILED, "synthesizer produced zero claims")
                return state.report or "", len(state.evidence)

            state.advance(Phase.CRITIQUING)
            state.spend(sum(len(e.get("text", "")) for e in evidence) // 4)
            verdict = critic.critique(state.claims, evidence)
            state.claim_verdicts = verdict["claim_verdicts"]

            if critic.overall_passes(state.claim_verdicts):
                state.advance(Phase.DONE)
                return state.report, len(evidence)

            claims_by_id = {c["id"]: c for c in state.claims}
            failed = [v for v in state.claim_verdicts if v["verdict"] != "supported"]
            state.gaps = [
                {
                    "claim": claims_by_id[v["id"]]["text"],
                    "sub_question": claims_by_id[v["id"]]["sub_question"],
                }
                for v in failed
            ]
            pending = [{"sub_question": g["sub_question"], "search_query": g["claim"]} for g in state.gaps]
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
