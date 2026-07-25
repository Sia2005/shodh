"""
Executor: for each sub-question, search -> fetch top sources -> chunk ->
store in Chroma -> extract claims with source attribution.
"""

from __future__ import annotations

import uuid

from agent import tools
from agent.state import AgentState
from retrieval.store import VectorStore


def run_sub_question(
    sub_question: str,
    state: AgentState,
    store: VectorStore,
    top_k_sources: int = 3,
    *,
    search_query: str | None = None,
) -> None:
    """Mutates state.evidence in place. One call per sub-question.

    search_query defaults to sub_question, but gap-driven re-search passes
    a different value: the specific failed-claim text to query for, while
    sub_question stays the original sub-question this evidence belongs to
    (used for metadata tagging / grouping, not for the search itself)."""
    search_query = search_query or sub_question
    results = tools.search(search_query, max_results=top_k_sources)
    state.trace.append(f"[SEARCH] '{search_query}' -> {len(results)} results")

    for result in results:
        text = tools.fetch_and_clean(result.url)
        if not text:
            state.trace.append(f"[SKIP] could not fetch/extract {result.url}")
            continue

        chunks = tools.chunk_text(text)
        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        store.add(
            ids=chunk_ids,
            documents=chunks,
            metadatas=[{"url": result.url, "title": result.title, "sub_question": sub_question}] * len(chunks),
        )

        state.evidence.append(
            {
                "sub_question": sub_question,
                "url": result.url,
                "title": result.title,
                "n_chunks": len(chunks),
            }
        )
        # Rough token estimate: ~4 chars/token. Real accounting should use
        # the model's tokenizer once you wire up claim extraction here.
        state.spend(len(text) // 4)

    state.trace.append(f"[DONE] '{sub_question}' -> {len(state.evidence)} sources total so far")
