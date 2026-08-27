"""Request models for the analysis endpoints (POST /api/parse-log, POST /api/analyze)."""

from pydantic import BaseModel


class ParseLogRequest(BaseModel):
    raw_text: str = ""


class AnalyzeRequest(BaseModel):
    raw_text: str = ""
