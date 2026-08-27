"""
POST /api/rag/retrieve — standalone endpoint for testing the RAG
retrieval layer (backend/rag/retriever.py) independently of /api/analyze.

Retrieval-only: does not call an LLM, and is not wired into the main
/api/analyze pipeline yet (see backend/rag/__init__.py).
"""

from fastapi import APIRouter

from rag.retriever import build_context, retrieve

from ..schemas.rag import RagRetrieveRequest, RagRetrieveResponse

router = APIRouter()


@router.post("/rag/retrieve", response_model=RagRetrieveResponse)
def rag_retrieve(payload: RagRetrieveRequest):
    query = (payload.query or "").strip()

    if not query:
        return RagRetrieveResponse(
            status="error",
            query=query,
            retrieved_bugs=[],
            context="",
            message="Please provide a query to search the historical bug knowledge base.",
        )

    results = retrieve(query)

    return RagRetrieveResponse(
        status="success",
        query=query,
        retrieved_bugs=[
            {
                "bug_id": r.bug_id,
                "title": r.title,
                "category": r.category,
                "severity": r.severity,
                "priority": r.priority,
                "status": r.status,
                "actual_root_cause": r.actual_root_cause,
                "actual_fix": r.actual_fix,
                "resolution_notes": r.resolution_notes,
                "submission_date": r.submission_date,
                "similarity": r.similarity,
            }
            for r in results
        ],
        context=build_context(results),
        message="" if results else "No sufficiently similar historical bugs found.",
    )
