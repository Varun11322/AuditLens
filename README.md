# AuditLens

Audit anomaly detection for financial transactions. AuditLens empowers auditors and managers to upload transaction ledgers, execute deterministic audit rules and machine learning anomaly detection, score risk, review exceptions, and export comprehensive audit workpapers.

---

## Architecture & Tech Stack

- **Backend**: FastAPI, Pydantic v2, Uvicorn
- **Database**: PostgreSQL 16, SQLAlchemy 2.x ORM, Alembic migrations
- **Analytics Engine**: Pure Python package using pandas, NumPy, SciPy, scikit-learn
- **Frontend**: Streamlit, Plotly
- **Authentication**: JWT (PyJWT) + bcrypt
- **Reporting**: openpyxl
- **Tooling**: pytest, pytest-cov, ruff

---

## Project Structure

```
auditlens/
  app/                       Backend application
    core/                    Config, security, dependencies, logging
    db/                      Database session, base, models, migrations
    schemas/                 Pydantic request and response models
    routers/                 API endpoint routers (auth, uploads, runs, health, etc.)
    services/                Business logic and service orchestration
    repositories/            Database query and persistence layer
    analytics/               Pure analytics engine (rules, Benford, ML, scoring)
  frontend/                  Streamlit web application
    pages/                   Multi-page Streamlit views
    components/              Reusable UI components
    api_client.py            Backend API client
  scripts/                   Utility and data generation scripts
  data/                      Sample datasets and test files
  tests/                     Automated test suite (unit, integration, fixtures)
  alembic/                   Database migrations
  docs/                      Project specification and architecture documentation
  docker-compose.yml         Local multi-container development environment
  pyproject.toml             Dependencies and tool configurations
```

---

## Getting Started

### 1. Prerequisites

- Python 3.11 or newer (Python 3.13 supported)
- Docker and Docker Compose (for PostgreSQL)
- Git

### 2. Environment Setup

Clone the repository and enter the directory:

```bash
git clone <repository-url>
cd auditlens
```

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -e .
```

### 3. Environment Variables

Copy the example environment configuration:

```bash
# Windows (PowerShell)
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Review `.env` and adjust database credentials or secrets if needed.

### 4. Database Setup

Start the local PostgreSQL 16 container:

```bash
docker compose up -d db
```

To stop the database:

```bash
docker compose down
```

### 5. Running the API

Start the FastAPI development server:

```bash
uvicorn app.main:app --reload --port 8000
```

Verify that the service is running:

- Health check: [http://localhost:8000/health](http://localhost:8000/health)
- Interactive API documentation: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Running Tests & Linting

Run automated tests:

```bash
pytest
```

Run test coverage report:

```bash
pytest --cov=app --cov-report=term-missing
```

Run code formatting and lint checks:

```bash
ruff check .
ruff format --check .
```
