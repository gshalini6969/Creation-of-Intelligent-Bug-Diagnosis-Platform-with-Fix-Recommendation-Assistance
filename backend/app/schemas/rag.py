"""Request/response models for POST /api/rag/retrieve."""

from typing import List

from pydantic import BaseModel


class RagRetrieveRequest(BaseModel):
    query: str = ""


class RetrievedBugModel(BaseModel):
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


class RagRetrieveResponse(BaseModel):
    status: str
    query: str
    retrieved_bugs: List[RetrievedBugModel]
    context: str
    message: str = ""
