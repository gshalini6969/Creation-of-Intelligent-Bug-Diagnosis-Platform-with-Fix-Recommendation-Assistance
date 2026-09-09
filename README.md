# Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance

## About the Project

This project is an AI-based web application developed to help developers analyze and manage software bugs.

The main idea is to take a bug report or log file, analyze the error, find similar bugs from the existing data, and provide useful information about the possible cause and fix.

The project uses **React.js for the frontend and FastAPI for the backend**. It also uses **RAG (Retrieval-Augmented Generation)** with Sentence Transformers and FAISS to retrieve similar bugs from the existing knowledge base.

---

## Features

* Submit new bugs through the web application
* Upload and analyze log files
* Parse error messages and stack traces
* Analyze bugs based on their details
* Identify bug severity and priority
* Find similar or duplicate bugs
* Retrieve related bugs using RAG
* Provide fix recommendations
* Store bug information in the knowledge base
* Mark bugs as resolved
* View bug statistics through the dashboard
* Search and view previously submitted bugs

---

## How the System Works

The basic workflow of the project is:

```text
User submits bug / log
        ↓
Log and stack trace parsing
        ↓
Bug analysis
        ↓
Severity and priority detection
        ↓
Similar bug search
        ↓
RAG retrieval
        ↓
Fix recommendation
        ↓
Bug stored in knowledge base
```

The system uses the existing bug data to find relevant historical bugs that can help with the analysis of a new bug.

---

## RAG Implementation

RAG is one of the main parts of this project.

The historical bug data is stored in:

```text
data/bugs.csv
```

The bug information is converted into embeddings using the **Sentence Transformers** model:

```text
all-MiniLM-L6-v2
```

These embeddings are stored in a **FAISS vector index**.

The process is:

```text
bugs.csv
   ↓
Text processing
   ↓
Sentence Transformer
   ↓
Embeddings
   ↓
FAISS Index
```

When a new bug is analyzed, the system searches the FAISS index and retrieves similar historical bugs.

```text
New Bug
   ↓
Embedding
   ↓
FAISS Search
   ↓
Similar Historical Bugs
   ↓
Used for Diagnosis / Recommendation
```

The generated RAG files are stored in:

```text
backend/rag/index/
├── bugs.faiss
└── bugs_metadata.json
```

If the bug data is changed, the RAG index should be rebuilt.

---

## Technologies Used

### Frontend

* React.js
* TypeScript
* Vite
* React Router
* CSS

### Backend

* Python
* FastAPI
* Uvicorn
* Pydantic

### AI / ML

* Scikit-learn
* Sentence Transformers
* FAISS
* TF-IDF
* Rule-based analysis

### Data

* CSV
* JSON
* FAISS Vector Index

---

## Project Structure

```text
Creation-of-Intelligent-Bug-Diagnosis-Platform-with-Fix-Recommendation-Assistance/
│
├── ai_modules/
│
├── backend/
│   ├── ai/
│   ├── app/
│   │   ├── routers/
│   │   ├── schemas/
│   │   ├── fastapi_config.py
│   │   └── main.py
│   │
│   └── rag/
│       ├── embed.py
│       ├── indexer.py
│       ├── retriever.py
│       ├── vector_store.py
│       └── index/
│
├── data/
│   └── bugs.csv
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── styles/
│   │   ├── App.tsx
│   │   └── main.tsx
│   │
│   ├── package.json
│   └── vite.config.ts
│
├── tests/
│
├── utils/
│
├── seed_data.py
├── requirements.txt
├── LICENSE
└── README.md
```

---

## Setup

### Requirements

Before running the project, install:

* Python 3.11 or above
* Node.js
* npm
* Git

---

## Backend Setup

Clone the repository:

```bash
git clone https://github.com/gshalini6969/Creation-of-Intelligent-Bug-Diagnosis-Platform-with-Fix-Recommendation-Assistance.git
```

Go to the project folder:

```bash
cd Creation-of-Intelligent-Bug-Diagnosis-Platform-with-Fix-Recommendation-Assistance
```

Create a virtual environment:

```bash
python -m venv .venv
```

### Windows

Activate the virtual environment:

```powershell
.venv\Scripts\activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

---

## Prepare the Data

The project uses `data/bugs.csv` as the main bug data file.

If the seed data needs to be added again, run:

```bash
python seed_data.py
```

---

## Build the RAG Index

To create or update the FAISS index, run:

```bash
python -m backend.rag.indexer
```

This will generate the required files inside:

```text
backend/rag/index/
```

---

## Run the Backend

From the project root, run:

```bash
uvicorn backend.app.main:app --reload
```

The backend will run on:

```text
http://127.0.0.1:8000
```

FastAPI Swagger documentation can be opened at:

```text
http://127.0.0.1:8000/docs
```

---

## Run the Frontend

Open another terminal and go to the frontend folder:

```bash
cd frontend
```

Install the dependencies:

```bash
npm install
```

Start the frontend:

```bash
npm run dev
```

The frontend will normally run at:

```text
http://127.0.0.1:5173
```

The frontend uses the Vite proxy to communicate with the FastAPI backend.

---

## API Endpoints

Some of the main API endpoints used in the project are:

| Method | Endpoint                     | Purpose                         |
| ------ | ---------------------------- | ------------------------------- |
| GET    | `/api/health`                | Check backend status            |
| GET    | `/api/bugs`                  | Get stored bugs                 |
| POST   | `/api/bugs`                  | Submit a new bug                |
| POST   | `/api/bugs/{bug_id}/resolve` | Mark a bug as resolved          |
| POST   | `/api/parse-log`             | Parse a log file                |
| POST   | `/api/analyze`               | Analyze a bug                   |
| POST   | `/api/rag/retrieve`          | Retrieve similar bugs using RAG |

---

## Main Pages

### Home Page

Provides an introduction to the platform and its main features.

### Submit Bug

Used to submit a new bug and provide the required details or log information.

### Analyze Bug

Analyzes the submitted bug and provides the diagnosis, similar bugs, and recommendations.

### Knowledge Base

Displays the existing bug information and allows users to view historical bugs.

### Dashboard

Shows the overall bug statistics and recent bug information.

---

## Bug Analysis

The analysis process combines different techniques to get useful results from a bug report.

```text
Bug Input
   ↓
Log Parsing
   ↓
Bug Analysis
   ↓
Similarity Search
   ↓
RAG Retrieval
   ↓
Recommendation
```

The similarity search helps identify bugs that are similar to the current bug, while RAG retrieves relevant information from the historical bug data.

---

## Data Storage

The main bug information is stored in:

```text
data/bugs.csv
```

The CSV file is used as the main source of bug data.

The RAG system uses the following generated files:

```text
backend/rag/index/bugs.faiss
backend/rag/index/bugs_metadata.json
```

If `bugs.csv` is updated, the FAISS index should also be rebuilt.

---

## Testing

The following points can be checked before running the final project:

* Backend starts without errors
* `/api/health` works
* Frontend starts correctly
* Dashboard loads
* New bugs can be submitted
* Log files can be analyzed
* Bug analysis returns results
* Similar bugs can be retrieved
* RAG retrieval works
* Fix recommendations are displayed
* Knowledge Base displays the stored bugs
* Bugs can be marked as resolved
* Dashboard statistics are updated

---

## Future Improvements

Some improvements that can be added in the future are:

* Add more historical bug data
* Improve the bug classification model
* Add authentication and user roles
* Add a proper database instead of CSV storage
* Add automated testing
* Improve RAG retrieval and ranking
* Add Docker support
* Deploy the application to the cloud
* Add more detailed analytics to the dashboard

---

## Project Information

**Project Title:** Creation of Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance

**Domain:** Artificial Intelligence / Software Engineering

**Frontend:** React.js + TypeScript + Vite

**Backend:** FastAPI

**RAG:** Sentence Transformers + FAISS

**Data Source:** CSV-based historical bug dataset

---

## License

This project is licensed under the MIT License.
