"""
FastAPI application configuration and import-path bootstrap.
"""

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent           # backend/app
BACKEND_DIR = APP_DIR.parent                          # backend
PROJECT_ROOT = BACKEND_DIR.parent                      # project root

# `ai/` lives under backend/, `utils/` lives at the project root — both
# must be importable regardless of the working directory uvicorn is
# started from.
for _path in (PROJECT_ROOT, BACKEND_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

API_TITLE = "Smart Bug Analyzer API"
API_VERSION = "1.0.0"

# Permissive for local development against the Vite dev server
# (http://127.0.0.1:5173). Narrow this before any production deployment.
CORS_ALLOW_ORIGINS = ["*"]
