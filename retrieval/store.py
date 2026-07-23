"""
Thin wrapper around an embedded Chroma collection. Kept deliberately
minimal — no framework retriever abstraction, just add/query.
"""

from __future__ import annotations

import chromadb


class VectorStore:
    def __init__(self, collection_name: str = "shodh_evidence", persist_dir: str = "./.chroma"):
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(collection_name)

    def add(self, ids: list[str], documents: list[str], metadatas: list[dict]) -> None:
        if not documents:
            return
        self._collection.add(ids=ids, documents=documents, metadatas=metadatas)

    def query(self, query_text: str, n_results: int = 5) -> list[dict]:
        res = self._collection.query(query_texts=[query_text], n_results=n_results)
        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            out.append({"text": doc, "url": meta.get("url"), "title": meta.get("title"), "distance": dist})
        return out

    def reset(self) -> None:
        """Wipe the collection. Useful between eval runs so results don't leak."""
        self._client.delete_collection(self._collection.name)
        self._collection = self._client.get_or_create_collection(self._collection.name)
