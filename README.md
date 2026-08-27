# Creation of Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance

A FastAPI + React application for intelligent bug diagnosis, historical bug retrieval, duplicate detection, and fix recommendation. The platform combines rule-based AI analysis, TF-IDF similarity search, and RAG retrieval over a FAISS vector index.

## Architecture

- **Backend:** FastAPI + Uvicorn
- **Frontend:** React + TypeScript + Vite
- **AI:** Log parsing, validation, triage/root-cause analysis, duplicate detection, fix recommendation
- **RAG:** Sentence Transformers (`all-MiniLM-L6-v2`) + FAISS
- **Storage:** CSV system of record; FAISS/JSON index is rebuildable derived data

## Project Structure

```text
smart-bug-analyzer/
├── backend/
│   ├── ai/                  # Diagnosis, similarity and recommendation logic
│   ├── app/                 # FastAPI app, routers and Pydantic schemas
│   └── rag/                 # Embeddings, FAISS index and retrieval
├── frontend/
│   └── src/                 # React pages, components and API client
├── utils/                   # Log parsing and CSV storage helpers
├── data/bugs.csv            # Historical bug knowledge
├── uploads/                 # Uploaded log files
├── seed_data.py             # Restore/populate seed data
├── requirements.txt
└── README.md
```

## Run the Backend

From the project root:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Backend: `http://127.0.0.1:8000`

## Run the Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend: `http://127.0.0.1:5173`

Vite proxies `/api/*` requests to FastAPI.

## Main Features

1. Bug submission with optional `.txt`/`.log` upload
2. Automatic log/stack-trace parsing
3. Bug category, severity, priority and confidence analysis
4. Root-cause diagnosis
5. TF-IDF duplicate/similar bug detection
6. RAG retrieval using Sentence Transformers + FAISS
7. Historical-fix-aware recommendations with no fabrication of unresolved fixes
8. Searchable/filterable Knowledge Base
9. Bug resolution tracking
10. Dashboard statistics and recent-bug views

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Health check |
| GET | `/api/bugs` | List stored bugs |
| POST | `/api/bugs` | Submit a bug |
| POST | `/api/bugs/{bug_id}/resolve` | Resolve a bug |
| POST | `/api/parse-log` | Parse a log/stack trace |
| POST | `/api/analyze` | Full diagnosis + duplicate detection + RAG + recommendation |
| POST | `/api/rag/retrieve` | Direct RAG retrieval |

## RAG Index

Build/rebuild the derived FAISS index from `data/bugs.csv` with:

```bash
python -m backend.rag.indexer
```

If the embedding model cannot be downloaded, the implementation falls back to a deterministic local embedding so the rest of the pipeline remains executable; real semantic retrieval requires the `all-MiniLM-L6-v2` model weights to be available.
