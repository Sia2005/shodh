"""
Metrics for the agent-vs-baseline comparison.

citation_accuracy: of all inline [n] citations in a report, what fraction
    point to evidence that actually appears in the sources list (i.e. no
    hallucinated citation numbers, no out-of-range references)?

factual_precision: of the benchmark's "answer_contains" checks, what
    fraction of expected substrings actually appear somewhere in the
    generated report? (Simple substring match — good enough for
    dates/figures/named entities; swap for fuzzy match if needed.)
"""

from __future__ import annotations

import re


def citation_accuracy(report: str, n_sources: int) -> float:
    citation_numbers = [int(n) for n in re.findall(r"\[(\d+)\]", report)]
    if not citation_numbers:
        return 0.0
    valid = sum(1 for n in citation_numbers if 1 <= n <= n_sources)
    return valid / len(citation_numbers)


def factual_precision(report: str, answer_contains: list[str]) -> float:
    if not answer_contains:
        return 1.0
    report_lower = report.lower()
    hits = sum(1 for token in answer_contains if token.lower() in report_lower)
    return hits / len(answer_contains)


def aggregate(results: list[dict]) -> dict:
    """results: list of per-question dicts with 'citation_accuracy' and
    'factual_precision' keys already computed."""
    n = len(results) or 1
    return {
        "n_questions": len(results),
        "avg_citation_accuracy": sum(r["citation_accuracy"] for r in results) / n,
        "avg_factual_precision": sum(r["factual_precision"] for r in results) / n,
    }
