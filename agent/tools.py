"""
Tool layer: search (Tavily), fetch + clean (httpx + trafilatura).

Kept deliberately dumb and synchronous-friendly wrappers so the
executor loop stays readable. No framework tool-calling abstraction —
just plain functions with clear input/output contracts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx
import trafilatura
from tavily import TavilyClient

_tavily_client: TavilyClient | None = None


def _get_tavily() -> TavilyClient:
    global _tavily_client
    if _tavily_client is None:
        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            raise RuntimeError("TAVILY_API_KEY not set in environment")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str


def search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Web search via Tavily. Returns lightweight result stubs (no full page yet)."""
    client = _get_tavily()
    resp = client.search(query=query, max_results=max_results)
    return [
        SearchResult(
            title=r.get("title", ""),
            url=r["url"],
            snippet=r.get("content", ""),
        )
        for r in resp.get("results", [])
    ]


def fetch_and_clean(url: str, timeout: float = 10.0) -> str | None:
    """Fetch a URL and extract main article text, stripping nav/ads/boilerplate.

    Returns None if the fetch fails or no extractable content is found —
    callers must handle this (skip the source, don't crash the loop).
    """
    try:
        resp = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ShodhResearchBot/0.1)"},
        )
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException):
        return None

    extracted = trafilatura.extract(resp.text, include_comments=False, include_tables=False)
    return extracted


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """Simple sliding-window chunker by characters. Swap for a token-aware
    chunker later if citation granularity needs to be tighter."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks
