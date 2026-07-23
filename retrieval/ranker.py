"""
Dedupe and rerank fetched evidence chunks before they're handed to the
synthesizer. Starts simple (URL/text dedupe + distance sort) — swap the
rerank step for a cross-encoder later if precision needs it.
"""

from __future__ import annotations


def dedupe(chunks: list[dict]) -> list[dict]:
    """Drop near-duplicate chunks (same URL + same text) while preserving order."""
    seen: set[tuple[str, str]] = set()
    out = []
    for c in chunks:
        key = (c.get("url", ""), c.get("text", "")[:200])
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def rerank_by_distance(chunks: list[dict], top_k: int = 10) -> list[dict]:
    """Chroma already returns results sorted by distance; this just
    truncates after dedupe. Kept as its own function so it's an obvious
    slot to swap in a real reranker (e.g. cross-encoder) later."""
    return sorted(chunks, key=lambda c: c.get("distance", 0.0))[:top_k]
