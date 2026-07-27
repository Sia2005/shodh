"""
Per-category + overall aggregation and the evals/results.md comparison
table. Kept separate from evals/run_evals.py so the execution loop and the
reporting/formatting logic aren't tangled together -- this module is pure
computation over already-scored results, no API calls.
"""

from __future__ import annotations

from collections import defaultdict

_CATEGORY_ORDER = [
    "recent_events",
    "numeric_stats",
    "multi_source_synthesis",
    "source_disagreement",
    "single_source_rag_fails",
]

_CATEGORY_LABELS = {
    "recent_events": "Recent events",
    "numeric_stats": "Numeric / statistical claims",
    "multi_source_synthesis": "Multi-source synthesis",
    "source_disagreement": "Source disagreement",
    "single_source_rag_fails": "Single-source RAG fails",
}

# (result dict key, column label)
_METRICS = [
    ("citation_accuracy", "Citation accuracy (model-graded)"),
    ("citation_validity", "Citation validity (structural)"),
    ("factual_precision", "Factual precision"),
]


def _group_by_category(results: list[dict]) -> dict[str, list[dict]]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        groups[r["category"]].append(r)
    return groups


def _raw_fraction(results: list[dict], key: str) -> tuple[float, int]:
    """(sum of per-question scores, n questions) -- the numerator/denominator
    whose ratio is the average. Returned as a pair, not just the average, so
    results.md can show e.g. "4.5/6" next to "75.0%" instead of a bare
    percentage that hides how small N is."""
    return sum(r[key] for r in results), len(results)


def _fmt_fraction(numerator: float, denominator: int) -> str:
    if denominator == 0:
        return "n/a"
    pct = numerator / denominator * 100
    num_str = f"{numerator:g}"  # whole-number sums print without a trailing ".0"
    return f"{num_str}/{denominator} ({pct:.1f}%)"


def _pct(numerator: float, denominator: int) -> float:
    return (numerator / denominator * 100) if denominator else 0.0


def compare(baseline: list[dict], agent: list[dict]) -> dict:
    """Baseline vs. agent on all three metrics for one slice of results
    (a category, or the whole benchmark)."""
    out = {}
    for key, _ in _METRICS:
        b_num, b_den = _raw_fraction(baseline, key)
        a_num, a_den = _raw_fraction(agent, key)
        out[key] = {
            "baseline_fraction": _fmt_fraction(b_num, b_den),
            "agent_fraction": _fmt_fraction(a_num, a_den),
            "baseline_pct": _pct(b_num, b_den),
            "agent_pct": _pct(a_num, a_den),
        }
    return out


def build_comparison(baseline_results: list[dict], agent_results: list[dict]) -> dict:
    """Returns {"overall": {...}, "by_category": {category: {...}}}."""
    b_groups = _group_by_category(baseline_results)
    a_groups = _group_by_category(agent_results)
    by_category = {
        category: compare(b_groups.get(category, []), a_groups.get(category, []))
        for category in _CATEGORY_ORDER
    }
    overall = compare(baseline_results, agent_results)
    return {"overall": overall, "by_category": by_category}


def _table(title: str, block: dict) -> list[str]:
    lines = [f"### {title}", "", "| Metric | Baseline | Agent | Delta |", "|---|---|---|---|"]
    for key, label in _METRICS:
        cell = block[key]
        delta = cell["agent_pct"] - cell["baseline_pct"]
        lines.append(
            f"| {label} | {cell['baseline_fraction']} | {cell['agent_fraction']} | {delta:+.1f} pp |"
        )
    lines.append("")
    return lines


def render_error_notes(baseline_results: list[dict], agent_results: list[dict]) -> list[str]:
    """Questions where the pipeline itself errored out (e.g. a Gemini JSON-mode
    call returned a malformed shape) are scored 0.0 across the board so they
    still count against the aggregate -- but a bare 0.0 reads as "got every
    fact wrong," which isn't what happened. This makes the distinction
    visible instead of burying it in results.json."""
    errors = [("baseline", r) for r in baseline_results if "error" in r] + [
        ("agent", r) for r in agent_results if "error" in r
    ]
    if not errors:
        return []
    agent_error_categories = [r["category"] for path, r in errors if path == "agent"]
    concentration = defaultdict(int)
    for c in agent_error_categories:
        concentration[c] += 1

    lines = [
        "## Pipeline errors",
        "",
        "These questions scored 0.0 on every metric because the run itself "
        "errored out (not because the report was graded and found wrong) -- "
        "in every case here, `agent/planner.py` raised on a malformed Gemini "
        "JSON response (see `evals/run_evals.py::_run_scored`). Counted in "
        "the aggregate above as failures either way.",
        "",
        "| Path | Question ID | Category | Error |",
        "|---|---|---|---|",
    ]
    for path, r in errors:
        lines.append(f"| {path} | {r['id']} | {r['category']} | {r['error']} |")
    lines.append("")

    if concentration:
        n_agent_errors = len(agent_error_categories)
        breakdown = ", ".join(f"{c} ({n})" for c, n in sorted(concentration.items(), key=lambda x: -x[1]))
        lines.append(
            f"**Read the by-category table with this in mind:** {n_agent_errors} of the "
            f"agent's {len(agent_results)} runs failed at the planning step before any "
            f"report was produced, concentrated in: {breakdown}. Categories with more "
            "planner failures look worse on every agent metric for that reason, not "
            "necessarily because retrieval or synthesis quality was worse there."
        )
        lines.append("")
    return lines


def render_markdown(
    comparison: dict,
    *,
    n_questions: int,
    gemini_model_alias: str,
    gemini_model_resolved: str,
    gemini_model_version: str,
    timestamp: str,
    baseline_results: list[dict] | None = None,
    agent_results: list[dict] | None = None,
) -> str:
    lines = [
        "# Eval results: agent vs. single-pass baseline",
        "",
        f"- Benchmark: `evals/benchmark.jsonl`, {n_questions} questions, 5 categories x 6 "
        "(selection criteria frozen in `evals/README.md` before any question was written)",
        f"- Run at: {timestamp}",
        f"- `GEMINI_MODEL` configured: `{gemini_model_alias}` -> resolved to "
        f"`{gemini_model_resolved}` (version `{gemini_model_version}`)",
        "",
        "**Citation accuracy** (model-graded, `evals/citation_judge.py`): does the cited "
        "evidence actually support the sentence citing it, per an independent Gemini judge "
        "applied identically to both reports. **Citation validity** (structural, "
        "`evals/metrics.py`, unchanged): does `[n]` merely point to a source index that "
        "exists. **Factual precision** (`evals/metrics.py`, unchanged): fraction of the "
        "question's key facts (`answer_contains`) found in the report. All three are shown "
        "as raw-fraction/percentage (e.g. `4.5/6 (75.0%)`) because per-category N is only 6.",
        "",
        "## Overall",
        "",
        *_table("All categories", comparison["overall"]),
        "## By category",
        "",
    ]
    for category in _CATEGORY_ORDER:
        lines.extend(_table(_CATEGORY_LABELS[category], comparison["by_category"][category]))
    if baseline_results is not None and agent_results is not None:
        lines.extend(render_error_notes(baseline_results, agent_results))
    return "\n".join(lines)
