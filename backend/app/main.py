"""
FastAPI application entry point.

FastAPI is the sole backend framework (the earlier Flask implementation
has been removed — this app fully replaced it, see the migration plan
and framework audit for history).

Run with (from the project root):
    uvicorn backend.app.main:app --reload

Endpoints (all under /api):
    GET  /api/health
    GET  /api/bugs
    POST /api/bugs
    POST /api/bugs/{bug_id}/resolve
    POST /api/parse-log
    POST /api/analyze
    POST /api/rag/retrieve
"""

# Import first: sets up sys.path so `ai.*` and `utils.*` are importable
# below and inside the routers, before anything else is imported.
from . import fastapi_config

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import analysis, bugs, rag

app = FastAPI(title=fastapi_config.API_TITLE, version=fastapi_config.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=fastapi_config.CORS_ALLOW_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bugs.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(rag.router, prefix="/api")


@app.get("/api/health")
def health_check():
    """Simple liveness check for the API layer (mirrors Flask GET /api/health)."""
    return {"status": "ok", "service": "smart-bug-analyzer-api"}
