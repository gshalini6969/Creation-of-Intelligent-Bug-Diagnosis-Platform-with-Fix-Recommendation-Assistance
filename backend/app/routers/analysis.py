"""
Analysis endpoints — POST /api/parse-log, POST /api/analyze.

Mirrors the existing Flask endpoints:
  - POST /api/parse-log <- backend/app/routes/api.py:parse_log
  - POST /api/analyze   <- backend/app/routes/views.py:analyze_bug (POST branch)
                            (was POST /analyze-bug in Flask, which also
                            served the HTML page on GET; that page-serving
                            concern doesn't apply here, so this is POST-only
                            under /api/analyze)

Reuses every AI agent exactly as-is: utils.log_parser, ai.rule_analyzer,
ai.similarity_search, ai.fix_recommender, ai.input_validator. No
internal logic changed. POST /api/analyze additionally calls the RAG
retriever (backend.rag.retriever) for semantic historical context —
purely additive alongside the existing TF-IDF duplicate detection, and
folded into the Fix Recommendation stage; see rag_results/rag_context
in the response.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ai.fix_recommender import generate_recommendation
from ai.input_validator import DEFAULT_INVALID_MESSAGE, validate_bug_report_text
from ai.rule_analyzer import analyze_bug_text
from ai.similarity_search import find_similar_bugs
from rag.retriever import build_context as build_rag_context
from rag.retriever import retrieve as rag_retrieve
from utils.log_parser import parse_log_text

from ..schemas.analysis import AnalyzeRequest, ParseLogRequest

router = APIRouter()


@router.post("/parse-log")
def parse_log(payload: ParseLogRequest):
    """Run the Log Parsing Agent (mirrors Flask POST /api/parse-log)."""
    raw_text = payload.raw_text or ""

    if not raw_text.strip():
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Please provide some log or stack trace text to analyze.",
        })

    parsed = parse_log_text(raw_text)
    return {"status": "success", "parsed": parsed}


@router.post("/analyze")
def analyze(payload: AnalyzeRequest):
    """
    Run the full multi-agent pipeline: Log Parsing -> Rule-based
    Diagnosis (Triage + Root Cause) -> Duplicate Detection -> Fix
    Recommendation. Mirrors Flask's POST /analyze-bug response shape
    exactly (status/analysis/similar_bugs/recommendation).
    """
    raw_text = payload.raw_text or ""

    if not raw_text.strip():
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Please provide a bug report, error log, or stack trace to analyze.",
        })

    validation = validate_bug_report_text(raw_text)
    if not validation["is_valid"]:
        return JSONResponse(status_code=422, content={
            "status": "invalid_input",
            "message": DEFAULT_INVALID_MESSAGE,
        })

    parsed_info = parse_log_text(raw_text)
    analysis = analyze_bug_text(raw_text, parsed_info=parsed_info)
    similar_bugs = find_similar_bugs(raw_text, new_bug_category=analysis["category"])
    similar_bug_ids = [bug["bug_id"] for bug in similar_bugs]

    # RAG Retrieval — semantic historical context. Additive only: TF-IDF
    # duplicate detection above is unchanged and remains the primary
    # similar-bugs signal. If the embedding model/index is unavailable
    # for any reason, fail safe with no RAG results rather than
    # breaking analysis (the embedding layer already has its own
    # offline fallback — see backend/rag/embed.py — so this is an
    # extra safety net on top of that).
    try:
        rag_matches = rag_retrieve(raw_text)
    except Exception:
        rag_matches = []

    rag_results = [
        {
            "bug_id": r.bug_id,
            "title": r.title,
            "category": r.category,
            "severity": r.severity,
            "priority": r.priority,
            "status": r.status,
            "root_cause": r.actual_root_cause,
            "fix": r.actual_fix,
            "resolution_notes": r.resolution_notes,
            "similarity": r.similarity,
        }
        for r in rag_matches
    ]
    rag_context = build_rag_context(rag_matches)

    recommendation = generate_recommendation(
        analysis,
        similar_bug_ids,
        rag_context=[
            {
                "bug_id": r.bug_id,
                "category": r.category,
                "severity": r.severity,
                "status": r.status,
                "actual_root_cause": r.actual_root_cause,
                "actual_fix": r.actual_fix,
            }
            for r in rag_matches
        ],
    )

    return {
        "status": "success",
        "analysis": analysis,
        "similar_bugs": similar_bugs,
        "recommendation": recommendation,
        "rag_results": rag_results,
        "rag_context": rag_context,
    }
