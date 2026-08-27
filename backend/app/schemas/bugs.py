"""
Request models for bug storage endpoints (GET/POST /api/bugs,
POST /api/bugs/{bug_id}/resolve).

Bug *records* themselves (as read from data/bugs.csv) are intentionally
left as plain dicts rather than strict Pydantic models — their keys are
the actual CSV column names (e.g. "Bug ID", "Bug Title", with spaces),
which aren't valid Python identifiers to alias field-by-field without
risking drift from utils.bug_storage.CSV_HEADERS. Passing them through
as dicts keeps this API layer a thin wrapper over the existing,
unmodified storage logic.
"""

from pydantic import BaseModel


class ResolveBugRequest(BaseModel):
    actual_root_cause: str = ""
    actual_fix: str = ""
    resolution_notes: str = ""
