# Document Intelligence Pipeline
Django + Prefect + PostgreSQL + ChromaDB + OpenAI
This project implements a full workflow for PDF ingestion, classification, entity extraction, and semantic search, built using:
Django REST API
Prefect orchestration
PostgreSQL (DLT-style schema)
ChromaDB (vector embeddings)
OpenAI embeddings
Pytest + pytest-django (automated tests)
The system ingests PDFs, extracts structured information (cost items, project tasks, regulatory rules), stores them in PostgreSQL, generates vector embeddings, and makes them searchable through a semantic search API.

## Features
Upload PDF
Triggers a Prefect flow to:
Extract text
Detect PDF type
Parse cost items / tasks / rules
Generate embeddings
Save entities in PostgreSQL
Store vectors in ChromaDB
Semantic Search
Vector search across all PDF chunks using OpenAI embeddings.
Automated Tests
Three pytest tests validate:
PDF upload
Document listing API
Search API

#  Local Setup Instructions

Follow the steps below to run the project in a local development environment.

##  Clone the Repository
git clone https://github.com/<your-repo>.git
cd <your-repo>

##  Create Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

##  Install Python Dependencies
pip install --upgrade pip
pip install -r requirements.txt

##  Configure Environment Variables

Create a .env file in the project root:

DJANGO_SECRET_KEY=devsecret
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=pdf_dataset

# OpenAI
OPENAI_API_KEY=your_openai_key

# ChromaDB local persistent directory
CHROMA_DISK_PATH=./vectorstore/chroma

##  Start PostgreSQL (Local)

If you don’t already have Postgres running:

docker run --name postgres-pdf \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=pdf_dataset \
  -p 5432:5432 -d postgres


Alternatively use local Postgres installation.

Create schema required by DLT-style tables:
CREATE SCHEMA pdf_dataset;

##  Django Migrations
python manage.py migrate

## Start Django Server
python manage.py runserver 8000


API hosted at:

👉 http://localhost:8000

## Start Prefect Worker

Start a Prefect worker on the default queue:

prefect worker start -q default


This worker executes the PDF ingestion pipeline when triggered from Django.

# PDF Ingestion Flow
Upload a PDF:
curl -X POST -F "file=@sample.pdf" http://localhost:8000/api/upload-pdf/


Expected response:

{
  "message": "PDF uploaded and ingestion started",
  "file_saved_as": "documents/sample.pdf",
  "prefect_state": "success"
}

# List Documents
curl http://localhost:8000/api/documents/


Example output:

[
  {
    "document_id": 1,
    "pdf_name": "sample.pdf",
    "pdf_type": "ura_circular",
    "cost_items": 12,
    "project_tasks": 4,
    "ura_rules": 3
  }
]

# Semantic Search
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "height restriction"}'


Example output:

{
  "results": [
    {
      "text": "Building height must not exceed 12m.",
      "metadata": {"document_id": 1},
      "score": 0.11
    }
  ]
}

# Automated Tests

The project includes pytest + pytest-django tests verifying ingestion and search logic.

Run tests:
pytest -v


Expected output:

3 passed in 3.12s
