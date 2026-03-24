# BlackBook

A personal intelligence application for structured deep-dive company discovery. BlackBook accepts raw investigator notes via email or file upload, uses AI to extract structured facts (people, org structure, technology, processes, CGKRA analysis), and presents them through a navigable visual interface — after the investigator has reviewed and validated every inference.

## Architecture

- **Backend**: Python / FastAPI / SQLAlchemy (async) / PostgreSQL
- **Frontend**: React / TypeScript / Vite
- **AI**: LLM-based extraction via configurable provider (single-pass per source)
- **Background**: async workers for ingestion, export generation, email polling, cleanup

## Project Structure

```
blackbook/
├── backend/
│   ├── app/
│   │   ├── api/v1/         # FastAPI route handlers (composition layer)
│   │   ├── services/       # Business logic
│   │   ├── repositories/   # Database access (one per table)
│   │   ├── models/         # SQLAlchemy ORM models
│   │   ├── schemas/        # Pydantic request/response models
│   │   └── workers/        # Background tasks (ingestion, export, email, cleanup)
│   ├── alembic/            # Database migrations
│   └── tests/              # pytest (services, repositories, API)
├── frontend/
│   └── src/
│       ├── api/            # Typed API client
│       ├── components/     # React components
│       ├── pages/          # Page-level views
│       ├── hooks/          # Custom React hooks
│       └── types/          # Shared TypeScript types
└── REQUIREMENTS.md         # Complete specification
```

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 15+

## Setup

**Backend:**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Frontend:**

```bash
cd frontend
npm install
```

**Database:**

```bash
createdb blackbook
cd backend
alembic upgrade head
```

**Environment:**

Set the following environment variables (or create a `.env` file in `backend/`):

```
BLACKBOOK_DATABASE_URL=postgresql+asyncpg://localhost:5432/blackbook
BLACKBOOK_LLM_API_KEY=<your-api-key>
BLACKBOOK_LLM_API_URL=<provider-endpoint>
BLACKBOOK_LLM_MODEL=<model-name>
```

See `backend/app/config.py` for all available configuration options.

## Running

**Backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm run dev
```

The frontend dev server proxies `/api` requests to the backend on port 8000.

## Testing

```bash
cd backend
pytest
```

Tests run against a real PostgreSQL database. LLM calls are mocked at the service boundary.

## Specification

The complete requirements, data model, API contracts, LLM integration contract, acceptance flows, and agent instructions are in [`REQUIREMENTS.md`](REQUIREMENTS.md).
