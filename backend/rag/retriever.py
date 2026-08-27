"""
retriever.py — semantic retrieval over the RAG vector index.

Given a new bug report's raw text, embeds it and searches the FAISS
index (see vector_store.py) for the most similar historical bugs,
returning the actual stored fields for each match plus a similarity
score, so a caller can judge whether a match is meaningful.

Retrieval-only: this module does not call an LLM and is not wired into
/api/analyze yet (see backend/rag/__init__.py).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .embed import embed_text
from .indexer import INDEX_DIR
from .vector_store import VectorStore

DEFAULT_TOP_K = 3

# Cosine similarity threshold below which a match isn't considered
# meaningful. Empirically chosen against this project's fallback
# embeddings (see embed.py) with the seeded historical bugs: genuine
# matches scored 0.30-0.51, unrelated queries scored at or below 0.08,
# and 0.25 was the tightest threshold that still kept every genuine
# match while dropping incidental noise (e.g. an unrelated bug
# occasionally scoring ~0.20 purely from shared common words).
# NOTE: if/when the real sentence-transformers model is reachable and
# the index is rebuilt with it, re-validate this threshold — dense
# semantic embeddings can have a different score distribution than the
# bag-of-words fallback.
MIN_SIMILARITY = 0.25


@dataclass
class RetrievedBug:
    bug_id: str
    title: str
    category: str
    severity: str
    priority: str
    status: str
    actual_root_cause: str
    actual_fix: str
    resolution_notes: str
    submission_date: str
    similarity: float


_store_cache: Optional[VectorStore] = None


def _load_store(index_dir: Path = INDEX_DIR, force_reload: bool = False) -> Optional[VectorStore]:
    """Load (and process-cache) the persisted vector store. None if it hasn't been built yet."""
    global _store_cache
    if _store_cache is None or force_reload:
        _store_cache = VectorStore.load(index_dir)
    return _store_cache


def retrieve(
    query_text: str,
    top_k: int = DEFAULT_TOP_K,
    min_similarity: float = MIN_SIMILARITY,
) -> List[RetrievedBug]:
    """
    Retrieve the most semantically similar historical bugs to `query_text`.

    Returns an empty list — never a fabricated result — if:
      - query_text is empty/whitespace,
      - the index hasn't been built yet (see indexer.rebuild_and_save),
      - nothing meets `min_similarity`.
    """
    if not query_text or not query_text.strip():
        return []

    store = _load_store()
    if store is None or store.index.ntotal == 0:
        return []

    query_vector = embed_text(query_text.strip())
    raw_results = store.search(query_vector, top_k=top_k)

    results: List[RetrievedBug] = []
    for similarity, meta in raw_results:
        if similarity < min_similarity:
            continue
        results.append(RetrievedBug(
            bug_id=meta.get("bug_id", ""),
            title=meta.get("title", ""),
            category=meta.get("category", ""),
            severity=meta.get("severity", ""),
            priority=meta.get("priority", ""),
            status=meta.get("status", ""),
            actual_root_cause=meta.get("actual_root_cause", ""),
            actual_fix=meta.get("actual_fix", ""),
            resolution_notes=meta.get("resolution_notes", ""),
            submission_date=meta.get("submission_date", ""),
            similarity=round(similarity, 4),
        ))
    return results


def build_context(retrieved: List[RetrievedBug]) -> str:
    """
    Build a compact text context block from retrieved historical bugs,
    for future use by the diagnosis/fix recommendation stage (not wired
    in yet). Returns "" if nothing was retrieved.
    """
    if not retrieved:
        return ""

    blocks = []
    for bug in retrieved:
        lines = [f"Historical Bug ID: {bug.bug_id} (similarity: {bug.similarity:.2f})"]
        if bug.title:
            lines.append(f"Historical Error: {bug.title}")
        if bug.actual_root_cause:
            lines.append(f"Root Cause: {bug.actual_root_cause}")
        if bug.actual_fix:
            lines.append(f"Previous Fix: {bug.actual_fix}")
        lines.append(f"Resolution Status: {bug.status or 'Unknown'}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)
