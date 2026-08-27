"""
indexer.py — builds/rebuilds the RAG vector index from data/bugs.csv.

The vector index is a derived artifact: data/bugs.csv remains the
source of truth. Run this whenever historical bug data changes:

    python -m backend.rag.indexer

Safe to run repeatedly — each run rebuilds the index from scratch from
the current contents of data/bugs.csv (no incremental/append logic),
so edits/resolutions to existing bugs are always reflected and no
stale or duplicate vectors accumulate.
"""

import logging
from pathlib import Path

from utils.bug_storage import read_all_bugs

from .embed import EMBEDDING_DIMENSIONS, embed_texts, is_using_fallback_embeddings
from .vector_store import VectorStore

logger = logging.getLogger(__name__)

INDEX_DIR = Path(__file__).resolve().parent / "index"

# Fields included in each bug's embedded document, in priority order,
# paired with a human-readable label. Only fields that are actually
# present (non-empty) on a given bug are included — this module never
# invents/fabricates historical information for missing fields.
_DOCUMENT_FIELDS = [
    ("Bug Title", "Title"),
    ("Bug Description", "Description"),
    ("Stack Trace", "Stack Trace / Error Message"),
    ("Module Name", "Module"),
    ("Category", "Category"),
    ("Severity", "Severity"),
    ("Priority", "Priority"),
    ("Status", "Status"),
    ("Actual Root Cause", "Actual Root Cause"),
    ("Actual Fix", "Actual Fix"),
    ("Resolution Notes", "Resolution Notes"),
]


def build_document(bug: dict) -> str:
    """Build the embeddable document text for one historical bug, using only fields actually present."""
    parts = []
    for csv_field, label in _DOCUMENT_FIELDS:
        value = (bug.get(csv_field) or "").strip()
        if value:
            parts.append(f"{label}: {value}")
    return "\n".join(parts)


def _build_metadata(bug: dict) -> dict:
    """Metadata stored alongside each vector, used to reconstruct RetrievedBug results."""
    return {
        "bug_id": bug.get("Bug ID", ""),
        "title": bug.get("Bug Title", ""),
        "category": bug.get("Category", ""),
        "severity": bug.get("Severity", ""),
        "priority": bug.get("Priority", ""),
        "status": bug.get("Status", ""),
        "actual_root_cause": bug.get("Actual Root Cause", ""),
        "actual_fix": bug.get("Actual Fix", ""),
        "resolution_notes": bug.get("Resolution Notes", ""),
        "submission_date": bug.get("Submission Date", ""),
    }


def build_index() -> VectorStore:
    """Read all historical bugs, embed them, and build a fresh VectorStore (not yet persisted)."""
    bugs = read_all_bugs()

    documents = []
    metadata = []
    for bug in bugs:
        document = build_document(bug)
        if not document:
            continue  # nothing usable to embed for this row
        documents.append(document)
        metadata.append(_build_metadata(bug))

    store = VectorStore(dimensions=EMBEDDING_DIMENSIONS)
    if documents:
        vectors = embed_texts(documents)
        store.add(vectors, metadata)

    return store


def rebuild_and_save(index_dir: Path = INDEX_DIR) -> int:
    """Rebuild the index from data/bugs.csv and persist it. Returns the number of bugs indexed."""
    store = build_index()
    store.save(index_dir)
    logger.info("RAG index rebuilt: %d historical bugs indexed at %s.", len(store.metadata), index_dir)
    return len(store.metadata)


if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path

    # Allow running as `python -m backend.rag.indexer` from the project root.
    _project_root = _Path(__file__).resolve().parent.parent.parent
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    _backend_dir = _project_root / "backend"
    if str(_backend_dir) not in sys.path:
        sys.path.insert(0, str(_backend_dir))

    logging.basicConfig(level=logging.INFO)
    count = rebuild_and_save()
    note = " (using local fallback embeddings — see embed.py)" if is_using_fallback_embeddings() else ""
    print(f"Indexed {count} historical bugs into the RAG vector store{note}.")
