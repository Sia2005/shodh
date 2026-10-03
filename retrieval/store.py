"""
VectorStore backed by the khoj vector search engine (FlatIndex, exact L2),
plus a reused ONNX MiniLM embedder and a Python label->payload sidecar.

Why this shape: khoj is a *pure* vector index — it stores float32 vectors
under sequential uint64 labels and does nearest-neighbour search, nothing
else. That is a narrower job than Chroma, which also silently (1) embedded
text and (2) stored the source documents + metadata. To keep this class's
interface byte-for-byte identical so the plan-retrieve-critique loop needs
no edits, we supply those two pieces here:

  * embedding -- the same all-MiniLM-L6-v2 ONNX model Chroma shipped (384-d),
    reused via chromadb's embedding-function helper. Keeping the identical
    embedder means a before/after retrieval-latency comparison moves only
    the index, not the model. (chromadb therefore stays installed, used
    solely as the embedding model, not as a vector store.)
  * payloads -- FlatIndex.add assigns labels sequentially from its current
    size (0,1,2,...), so a parallel list indexed by label holds each chunk's
    {text,url,title,sub_question}. search() returns labels; we look them up.

FlatIndex (exact) rather than HnswIndex: a per-question evidence store holds
tens to low hundreds of chunks, where an exhaustive scan is sub-millisecond
and sidesteps both HNSW's approximation and its ef_search tuning. Switch to
khoj.HnswIndex only if this ever indexes 1e4+ vectors.

Distance note: khoj L2 returns Euclidean distance; Chroma's l2 space returned
*squared* L2. sqrt is monotonic, so the ranking is identical and retrieval/
ranker.py (which only sorts ascending by distance) is unaffected -- only the
numeric value of the "distance" field changes.

In-memory only: khoj can persist an HNSW graph (save/load) but never the
payloads, and callers build a fresh store per question and never read across
runs -- so there is nothing to persist. collection_name / persist_dir are
kept in the signature for drop-in compatibility and are intentionally unused.
"""

from __future__ import annotations

import numpy as np
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

import khoj

# Self-reported so tooling (e.g. evals/bench_retrieval.py) can label which
# engine produced a result without inspecting internals.
BACKEND = "khoj"

_embedder: ONNXMiniLM_L6_V2 | None = None


def _get_embedder() -> ONNXMiniLM_L6_V2:
    """Module-level singleton: load the ONNX session once and share it across
    every VectorStore (the agent builds one store per question, so a
    per-instance embedder would reload the model each time)."""
    global _embedder
    if _embedder is None:
        _embedder = ONNXMiniLM_L6_V2()
    return _embedder


def _embed(texts: list[str]) -> np.ndarray:
    """texts -> (len(texts), dim) float32, C-contiguous for the khoj bindings."""
    vectors = _get_embedder()(texts)
    return np.asarray(vectors, dtype=np.float32)


class VectorStore:
    def __init__(self, collection_name: str = "shodh_evidence", persist_dir: str = "./.chroma"):
        self._collection_name = collection_name  # retained for parity/logging only
        self._index: khoj.FlatIndex | None = None  # created lazily at known dim
        self._payloads: list[dict] = []  # list index == khoj label

    def _ensure_index(self, dimension: int) -> khoj.FlatIndex:
        if self._index is None:
            self._index = khoj.FlatIndex(dimension=dimension, metric=khoj.Metric.L2)
        return self._index

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        # ids is accepted for interface compatibility; khoj assigns its own
        # sequential labels, and downstream dedupe keys on url+text, so the
        # caller-supplied ids are not needed here.
        if not documents:
            return
        vectors = _embed(documents)
        index = self._ensure_index(vectors.shape[1])
        # add_batch appends in row order starting at the index's current size,
        # i.e. row i -> label len(self._payloads)+i. Grow the sidecar in the
        # same order so label lookups in query() line up.
        index.add_batch(vectors)
        for doc, meta in zip(documents, metadatas):
            self._payloads.append(
                {
                    "text": doc,
                    "url": meta.get("url"),
                    "title": meta.get("title"),
                    "sub_question": meta.get("sub_question"),
                }
            )

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        if self._index is None or not self._payloads:
            return []
        vector = _embed([query_text])[0]
        results = self._index.search(vector, k=n_results)
        out = []
        for r in results:
            payload = self._payloads[r.label]
            out.append(
                {
                    "text": payload["text"],
                    "url": payload["url"],
                    "title": payload["title"],
                    "sub_question": payload["sub_question"],
                    "distance": float(r.distance),
                }
            )
        return out

    def reset(self) -> None:
        """Wipe the index + sidecar. Useful between eval runs so results don't leak."""
        self._index = None
        self._payloads = []
