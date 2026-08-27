"""
Bug storage endpoints — GET /api/bugs, POST /api/bugs,
POST /api/bugs/{bug_id}/resolve.

Mirrors the existing Flask endpoints as closely as possible:
  - GET  /api/bugs                  <- backend/app/routes/api.py:get_bugs
  - POST /api/bugs                  <- backend/app/routes/views.py:submit_bug_endpoint
                                        (was POST /submit_bug in Flask; moved
                                        under /api for a consistent REST-style
                                        surface for the future React frontend)
  - POST /api/bugs/{bug_id}/resolve <- backend/app/routes/api.py:resolve_bug

Reuses utils.bug_storage exactly as-is — no internal logic changed.
"""

import shutil
from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from utils.bug_storage import (
    create_bug_report,
    is_allowed_log_file,
    read_all_bugs,
    update_bug_resolution,
)

from ..schemas.bugs import ResolveBugRequest

router = APIRouter()

REQUIRED_BUG_FIELDS = [
    "bug_title",
    "bug_description",
    "stack_trace",
    "module_name",
    "category",
    "severity",
    "priority",
    "reporter_name",
]


class _UploadFileAdapter:
    """
    Adapts FastAPI's UploadFile to the minimal Flask FileStorage-like
    interface (`.filename` + `.save(path)`) that utils.bug_storage's
    save_uploaded_log() already expects, without modifying
    bug_storage.py itself.
    """

    def __init__(self, upload_file: UploadFile):
        self.filename = upload_file.filename
        self._upload_file = upload_file

    def save(self, dst) -> None:
        self._upload_file.file.seek(0)
        with open(dst, "wb") as f:
            shutil.copyfileobj(self._upload_file.file, f)


@router.get("/bugs")
def get_bugs():
    """Return all stored bug reports as JSON (mirrors Flask GET /api/bugs)."""
    bugs = read_all_bugs()
    return {"status": "success", "count": len(bugs), "bugs": bugs}


@router.post("/bugs", status_code=201)
def submit_bug(
    bug_title: str = Form(...),
    bug_description: str = Form(...),
    stack_trace: str = Form(...),
    module_name: str = Form(...),
    category: str = Form(...),
    severity: str = Form(...),
    priority: str = Form(...),
    reporter_name: str = Form(...),
    log_file: Optional[UploadFile] = File(None),
):
    """
    Accept a bug report submission, validate it, persist it via
    utils.bug_storage.create_bug_report (unchanged), save any uploaded
    log file, and return the generated Bug ID and timestamp.

    Same validation and response shape as Flask's POST /submit_bug.
    """
    form_data = {
        "bug_title": bug_title,
        "bug_description": bug_description,
        "stack_trace": stack_trace,
        "module_name": module_name,
        "category": category,
        "severity": severity,
        "priority": priority,
        "reporter_name": reporter_name,
    }

    missing_fields = [field for field in REQUIRED_BUG_FIELDS if not form_data[field].strip()]
    if missing_fields:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Missing required fields.",
            "missing_fields": missing_fields,
        })

    adapted_file = None
    if log_file is not None and log_file.filename:
        if not is_allowed_log_file(log_file.filename):
            return JSONResponse(status_code=400, content={
                "status": "error",
                "message": "Only .txt or .log files are allowed.",
            })
        adapted_file = _UploadFileAdapter(log_file)

    try:
        record = create_bug_report(form_data, adapted_file)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"status": "error", "message": str(exc)})
    except OSError:
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": "Failed to save the bug report. Please try again.",
        })

    return {
        "status": "success",
        "message": "Bug submitted successfully.",
        "bug_id": record["Bug ID"],
        "submission_date": record["Submission Date"],
        "submission_time": record["Submission Time"],
    }


@router.post("/bugs/{bug_id}/resolve")
def resolve_bug(bug_id: str, payload: ResolveBugRequest):
    """
    Mark a stored bug as Resolved, persisting the actual root cause,
    fix, and resolution notes via utils.bug_storage (unchanged).

    Same validation and response shape as Flask's
    POST /api/bugs/<bug_id>/resolve.
    """
    actual_root_cause = (payload.actual_root_cause or "").strip()
    actual_fix = (payload.actual_fix or "").strip()
    resolution_notes = (payload.resolution_notes or "").strip()

    if not actual_root_cause or not actual_fix:
        return JSONResponse(status_code=400, content={
            "status": "error",
            "message": "Actual Root Cause and Actual Fix are both required to mark a bug as resolved.",
        })

    updated_bug = update_bug_resolution(bug_id, actual_root_cause, actual_fix, resolution_notes)

    if updated_bug is None:
        return JSONResponse(status_code=404, content={
            "status": "error",
            "message": f"Bug {bug_id} was not found.",
        })

    return {"status": "success", "message": "Bug marked as resolved.", "bug": updated_bug}
