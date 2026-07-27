"""
Structural integrity guard for evals/benchmark.jsonl.

This is the enforcement mechanism behind evals/README.md's "don't
cherry-pick" rules: the benchmark's shape (30 questions, 6 per category)
is meant to be frozen, so a future edit that quietly drops a hard question
or rebalances categories should fail here instead of going unnoticed.
"""

from __future__ import annotations

import json
from pathlib import Path

BENCHMARK_PATH = Path(__file__).parent.parent / "evals" / "benchmark.jsonl"

EXPECTED_CATEGORIES = {
    "recent_events",
    "numeric_stats",
    "multi_source_synthesis",
    "source_disagreement",
    "single_source_rag_fails",
}
QUESTIONS_PER_CATEGORY = 6


def _load_benchmark() -> list[dict]:
    return [json.loads(line) for line in BENCHMARK_PATH.read_text().splitlines() if line.strip()]


def test_benchmark_has_thirty_questions():
    benchmark = _load_benchmark()
    assert len(benchmark) == len(EXPECTED_CATEGORIES) * QUESTIONS_PER_CATEGORY


def test_benchmark_categories_are_balanced():
    benchmark = _load_benchmark()
    counts: dict[str, int] = {}
    for item in benchmark:
        counts[item["category"]] = counts.get(item["category"], 0) + 1

    assert set(counts) == EXPECTED_CATEGORIES
    assert all(count == QUESTIONS_PER_CATEGORY for count in counts.values()), counts


def test_benchmark_ids_are_unique():
    benchmark = _load_benchmark()
    ids = [item["id"] for item in benchmark]
    assert len(ids) == len(set(ids))


def test_benchmark_required_fields_present():
    benchmark = _load_benchmark()
    for item in benchmark:
        assert item.get("id"), item
        assert item.get("question"), item
        assert item.get("category") in EXPECTED_CATEGORIES, item
        assert isinstance(item.get("answer_contains"), list) and item["answer_contains"], item
        assert all(isinstance(fact, str) and fact for fact in item["answer_contains"]), item
        assert item.get("notes"), item  # sourcing/rationale, per README rule 2
