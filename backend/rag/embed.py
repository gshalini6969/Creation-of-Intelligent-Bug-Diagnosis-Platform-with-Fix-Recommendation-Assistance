"""
embed.py — Embedding generation for the RAG pipeline.

Primary implementation: sentence-transformers ("all-MiniLM-L6-v2"),
loaded once and cached (a fresh model load per call would be far too
slow). Produces 384-dimensional, L2-normalized embeddings, so cosine
similarity and inner-product search are equivalent.

Offline fallback: sentence-transformers downloads model weights from
huggingface.co on first use. If that host isn't reachable (e.g. a
network-restricted environment), a deterministic local hashing-based
embedding of the same dimensionality is used instead, purely so the
rest of the RAG pipeline (indexing, storage, retrieval, thresholding)
stays exercisable and testable. This fallback is NOT a semantic
embedding model — it's a bag-of-words hash into a fixed-size vector.
Whenever it activates, `is_using_fallback_embeddings()` reports it and
a warning is logged; rebuild the index once the real model is
reachable to get genuine semantic retrieval.
"""

import logging
import re
import zlib
from functools import lru_cache
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSIONS = 384

_using_fallback = False


@lru_cache(maxsize=1)
def _load_model():
    """Load (once) and cache the sentence-transformers model, or fall back to None."""
    global _using_fallback
    try:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        logger.info("Loaded embedding model '%s'.", EMBEDDING_MODEL_NAME)
        return model
    except Exception as exc:  # e.g. OSError: can't reach huggingface.co
        _using_fallback = True
        logger.warning(
            "Could not load sentence-transformers model '%s' (%s). "
            "Falling back to a local deterministic hashing embedding — "
            "this is NOT a semantic model. Rebuild the index "
            "(python -m backend.rag.indexer) once the real model is "
            "reachable.",
            EMBEDDING_MODEL_NAME,
            exc,
        )
        return None


def is_using_fallback_embeddings() -> bool:
    """True if the real embedding model couldn't be loaded and the local fallback is active."""
    _load_model()
    return _using_fallback


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_CAMEL_CASE_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _fallback_embed(texts: List[str]) -> np.ndarray:
    """
    Deterministic, dependency-light stand-in for a real embedding model.
    Hashes word tokens (with CamelCase splitting so identifiers like
    "NullPointerException" also contribute "Null"/"Pointer"/"Exception")
    into a fixed EMBEDDING_DIMENSIONS-length bag-of-words vector,
    L2-normalized. Uses zlib.crc32 rather than Python's built-in hash()
    because str hashing is randomized per-process by default — this
    must stay identical across the indexer process and the retriever
    process (or any process restart) for search results to be valid.
    """
    vectors = np.zeros((len(texts), EMBEDDING_DIMENSIONS), dtype="float32")
    for i, text in enumerate(texts):
        expanded = f"{text} {_CAMEL_CASE_BOUNDARY.sub(' ', text)}"
        for token in _TOKEN_RE.findall(expanded.lower()):
            idx = zlib.crc32(token.encode("utf-8")) % EMBEDDING_DIMENSIONS
            vectors[i, idx] += 1.0

    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Generate normalized embeddings for a list of texts.

    Returns:
        np.ndarray, shape (len(texts), EMBEDDING_DIMENSIONS), float32,
        L2-normalized (so inner product == cosine similarity). Returns
        an empty (0, EMBEDDING_DIMENSIONS) array for an empty input list.
    """
    if not texts:
        return np.zeros((0, EMBEDDING_DIMENSIONS), dtype="float32")

    model = _load_model()
    if model is None:
        return _fallback_embed(texts)

    embeddings = model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
    return embeddings.astype("float32")


def embed_text(text: str) -> np.ndarray:
    """Generate a normalized embedding for a single text. Shape: (EMBEDDING_DIMENSIONS,)."""
    return embed_texts([text])[0]
