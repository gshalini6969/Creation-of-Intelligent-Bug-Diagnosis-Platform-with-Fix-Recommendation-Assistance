"""
vector_store.py — FAISS-backed vector index with sidecar metadata.

Wraps a FAISS IndexFlatIP (exact inner-product search; embeddings are
L2-normalized so inner product == cosine similarity) plus a parallel
list of metadata dicts, one per vector, so search results can be mapped
back to the originating Bug ID / historical record. Persisted to disk
as two files: a FAISS index file and a JSON metadata sidecar — treat
both as a derived, rebuildable artifact, never hand-edited.
"""

import json
from pathlib import Path
from typing import List, Optional, Tuple

import faiss
import numpy as np


class VectorStore:
    def __init__(self, dimensions: int):
        self.dimensions = dimensions
        self.index = faiss.IndexFlatIP(dimensions)
        self.metadata: List[dict] = []

    def add(self, vectors: np.ndarray, metadata: List[dict]) -> None:
        """Add a batch of vectors and their corresponding metadata dicts (same order, same length)."""
        if vectors.shape[0] != len(metadata):
            raise ValueError("vectors and metadata must have the same length")
        if vectors.shape[0] == 0:
            return
        self.index.add(vectors.astype("float32"))
        self.metadata.extend(metadata)

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> List[Tuple[float, dict]]:
        """
        Search for the top_k nearest vectors to query_vector.

        Returns:
            List of (similarity, metadata) tuples, best match first.
            similarity is the raw inner-product score (== cosine
            similarity, since vectors are L2-normalized). Empty list if
            the index has no vectors.
        """
        if self.index.ntotal == 0:
            return []

        query = query_vector.reshape(1, -1).astype("float32")
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query, k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((float(score), self.metadata[idx]))
        return results

    def save(self, directory: Path) -> None:
        """Persist the index and metadata to `directory` (created if missing)."""
        directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(directory / "bugs.faiss"))
        with open(directory / "bugs_metadata.json", "w", encoding="utf-8") as f:
            json.dump({"dimensions": self.dimensions, "metadata": self.metadata}, f)

    @classmethod
    def load(cls, directory: Path) -> Optional["VectorStore"]:
        """Load a previously persisted index from `directory`, or None if it doesn't exist yet."""
        index_path = directory / "bugs.faiss"
        metadata_path = directory / "bugs_metadata.json"
        if not index_path.exists() or not metadata_path.exists():
            return None

        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        store = cls(dimensions=data["dimensions"])
        store.index = faiss.read_index(str(index_path))
        store.metadata = data["metadata"]
        return store
