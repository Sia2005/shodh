"""
Runs the benchmark against both the full agent loop and a single-pass
RAG baseline, then writes evals/results.md and evals/results.json.

Usage:
    python -m evals.run_evals
    python -m evals.run_evals --limit 5   # quick smoke test
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import google.generativeai as genai

from agent import config, critic, executor, planner, synthesizer
from agent.state import AgentState, BudgetExceeded, Phase
from evals import report
from evals.citation_judge import citation_support_accuracy
from evals.metrics import citation_accuracy, factual_precision
from retrieval.ranker import dedupe, rerank_by_distance
from retrieval.store import VectorStore

BENCHMARK_PATH = Path(__file__).parent / "benchmark.jsonl"
RESULTS_MD_PATH = Path(__file__).parent / "results.md"
RESULTS_JSON_PATH = Path(__file__).parent / "results.json"


def load_benchmark(limit: int | None = None) -> list[dict]:
    items = [json.loads(line) for line in BENCHMARK_PATH.read_text().splitlines() if line.strip()]
    return items[:limit] if limit else items


def resolve_gemini_model() -> tuple[str, str]:
    """GEMINI_MODEL is a "-latest" alias (see agent/config.py) -- it can
    point to a different concrete model on a different day. Resolve it to
    a concrete name + version so results.md is reproducible: someone
    reading it later knows exactly which model actually ran, not just
    which alias was configured."""
    genai.configure(api_key=config.GEMINI_API_KEY)
    name = config.GEMINI_MODEL if config.GEMINI_MODEL.startswith("models/") else f"models/{config.GEMINI_MODEL}"
    model = genai.get_model(name)
    return model.name.removeprefix("models/"), model.version


def run_baseline(question: str) -> tuple[str, list[dict]]:
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
    return result["report"], evidence


def run_full_agent(question: str) -> tuple[str, list[dict]]:
    state = AgentState(question=question)
    store = VectorStore(collection_name=f"agent_{abs(hash(question))}")
    evidence: list[dict] = []

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
                return state.report or "", state.evidence

            state.advance(Phase.CRITIQUING)
            state.spend(sum(len(e.get("text", "")) for e in evidence) // 4)
            verdict = critic.critique(state.claims, evidence)
            state.claim_verdicts = verdict["claim_verdicts"]

            if critic.overall_passes(state.claim_verdicts):
                state.advance(Phase.DONE)
                return state.report, evidence

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
        return state.report or "", evidence


def score(report_text: str, evidence: list[dict], item: dict) -> dict:
    """evidence: the same numbered list handed to the synthesizer for this
    report, so citation [n] means evidence[n-1] here too."""
    semantic_score, n_supported, n_cited = citation_support_accuracy(report_text, evidence)
    return {
        "id": item["id"],
        "category": item["category"],
        # "citation_accuracy" = model-graded semantic support (evals/citation_judge.py) —
        # the metric the eval brief asked for ("do cited sources actually support the claim").
        "citation_accuracy": semantic_score,
        "citation_support_counts": [n_supported, n_cited],
        # "citation_validity" = structural only (evals/metrics.py, author-owned, unchanged):
        # does [n] point to a source index that exists.
        "citation_validity": citation_accuracy(report_text, len(evidence)),
        "factual_precision": factual_precision(report_text, item["answer_contains"]),
    }


def _run_scored(fn, question: str, item: dict) -> dict:
    """Runs one baseline/agent pass and scores it. Gemini's JSON-mode calls
    (agent/planner.py, agent/synthesizer.py, agent/critic.py, and this
    file's own citation_judge.py) each raise ValueError on malformed
    output -- rare, but real: observed in practice as a planner call that
    wrapped its sub-questions in an extra list. That's the model being the
    model, not a bug to fix in those (author-owned) modules. Catching it
    here means one bad generation costs one question's score, not the
    whole 30-question run -- the same spirit as agent/state.py's
    BudgetExceeded handling in run_full_agent, one level up."""
    try:
        report_text, evidence = fn(question)
        return score(report_text, evidence, item)
    except ValueError as e:
        print(f"  ERROR: {e}")
        return {
            "id": item["id"],
            "category": item["category"],
            "error": str(e),
            "citation_accuracy": 0.0,
            "citation_validity": 0.0,
            "factual_precision": 0.0,
        }


def main(limit: int | None = None) -> None:
    model_alias = config.GEMINI_MODEL
    model_resolved, model_version = resolve_gemini_model()
    print(f"GEMINI_MODEL: {model_alias} -> {model_resolved} (version {model_version})\n")

    benchmark = load_benchmark(limit)
    baseline_results, agent_results = [], []

    for item in benchmark:
        q = item["question"]
        print(f"[baseline] {q}")
        t0 = time.time()
        baseline_results.append({**_run_scored(run_baseline, q, item), "seconds": round(time.time() - t0, 1)})

        print(f"[agent]    {q}")
        t0 = time.time()
        agent_results.append({**_run_scored(run_full_agent, q, item), "seconds": round(time.time() - t0, 1)})

    comparison = report.build_comparison(baseline_results, agent_results)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    markdown = report.render_markdown(
        comparison,
        n_questions=len(benchmark),
        gemini_model_alias=model_alias,
        gemini_model_resolved=model_resolved,
        gemini_model_version=model_version,
        timestamp=timestamp,
        baseline_results=baseline_results,
        agent_results=agent_results,
    )
    RESULTS_MD_PATH.write_text(markdown)
    print(f"\n{markdown}")
    print(f"\nComparison table written to {RESULTS_MD_PATH}")

    out = {
        "run_at": timestamp,
        "gemini_model_alias": model_alias,
        "gemini_model_resolved": model_resolved,
        "gemini_model_version": model_version,
        "comparison": comparison,
        "baseline_detail": baseline_results,
        "agent_detail": agent_results,
    }
    RESULTS_JSON_PATH.write_text(json.dumps(out, indent=2))
    print(f"Full raw results written to {RESULTS_JSON_PATH}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    main(limit=args.limit)
