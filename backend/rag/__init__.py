"""
backend/rag — Retrieval-Augmented Generation layer for the historical
bug knowledge base.

    data/bugs.csv (source of truth)
        -> indexer.py      (builds documents, embeds, stores in FAISS)
        -> vector_store.py (FAISS index + metadata, persisted to disk)
        -> retriever.py    (embeds a query, searches, filters, formats)

This is retrieval only — no LLM generation yet, and not wired into
/api/analyze yet. See backend/app/routers/rag.py for the standalone
POST /api/rag/retrieve endpoint used to test this layer.

The existing TF-IDF similarity system (backend/ai/similarity_search.py)
is untouched and remains the production similarity/duplicate-detection
implementation for now.
"""
