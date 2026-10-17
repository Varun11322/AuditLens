# Architecture

## 1. System Overview
AuditLens is a three-tier app: a Streamlit frontend that calls a FastAPI backend, which stores data in PostgreSQL. The analytics engine is a pure Python package used by the backend (and testable on its own).

## 2. Architecture Pattern
Pattern: Modular monolith (one backend service, one frontend service, one database), layered inside the backend.
Reason: Simple to build, run, test, and deploy for a solo project, while still showing clean separation of concerns.

## 3. Technology Stack
Frontend: Streamlit + Plotly
Backend: FastAPI + Uvicorn, Pydantic v2
Database: PostgreSQL 16, SQLAlchemy 2.x ORM, Alembic migrations
Analytics: pandas, NumPy, SciPy, scikit-learn
Authentication: JWT (PyJWT or python-jose) + bcrypt (direct library, not passlib)
Storage: local `uploads/` directory (not public) for original files
Hosting: Docker + docker-compose locally; live hosting is optional, decided later
Reports: openpyxl
Other: pytest, ruff, python-dotenv or pydantic-settings

## 4. System Components
### Frontend (Streamlit)
- Login, upload, run analysis, dashboard, flagged review, report download.
- Holds the JWT in session state and sends it with each API call.
- No business logic and no direct database access.
### Backend (FastAPI)
- Auth, validation, ownership checks, orchestration of analysis runs, persistence, report generation.
- Analysis runs execute in a background task; the client polls run status.
### Analytics engine (`app/analytics`)
- Pure functions: validate/clean, features, rules R1-R6, Benford, Isolation Forest, scoring, evaluation.
- Input: DataFrame + Settings. Output: DataFrames/dicts. No web, no database imports.
### Database
- Stores users, uploads, transactions, analysis runs, flagged results, reviews, audit logs.

## 5. Architecture Diagram
```
User -> Streamlit UI -> FastAPI routers -> Services -> Repositories -> PostgreSQL
                                              |
                                              +-> Analytics engine (pandas / sklearn)
```

## 6. Data Flow (analysis)
1. Auditor uploads a file in Streamlit
2. Frontend sends it to POST /uploads with the JWT
3. API authenticates, validates type/size/columns, parses the file
4. Valid rows are bulk-inserted into `transactions`; rejected rows are summarized
5. Auditor clicks Run Analysis -> POST /uploads/{id}/analyze creates an `analysis_runs` row (status pending)
6. Background task loads the transactions into a DataFrame and calls the analytics engine
7. Results are bulk-inserted into `flagged_transactions`; run summary saved; status completed
8. Frontend polls GET /runs/{id}, then loads summary and flagged list
9. Auditor reviews items via PATCH; changes are stored in `reviews` and `audit_logs`

## 7. Project Structure
```
auditlens/
  AGENTS.md
  README.md
  docker-compose.yml
  pyproject.toml
  .env.example
  docs/                      (all the md documents)
  app/
    main.py                  (FastAPI app factory)
    core/                    (config, security, logging, dependencies)
    db/                      (session, base, models/, migrations via alembic/)
    schemas/                 (Pydantic request/response models)
    routers/                 (auth, users, uploads, runs, flagged, reports, health)
    services/                (upload_service, analysis_service, review_service, report_service)
    repositories/            (database access functions)
    analytics/               (PURE: settings.py, validation.py, features.py, rules.py,
                              benford.py, ml.py, scoring.py, pipeline.py, evaluation.py)
  frontend/
    app.py                   (Streamlit entry)
    pages/                   (1_Upload, 2_Dashboard, 3_Review, 4_Benford, 5_Reports, 6_Evaluation)
    api_client.py            (all HTTP calls to the backend)
    components/              (charts, tables, filters)
  scripts/
    generate_synthetic_ledger.py
    seed_admin.py
  data/                      (generated sample files; gitignored if large)
  tests/                     (unit/, integration/, fixtures/)
  alembic/
```

## 8. Dependency Rules
- analytics must not import from routers, services, db, or frontend.
- routers call services; services call repositories and analytics; repositories call the database.
- Routers never contain business logic or SQL.
- Streamlit calls only `api_client.py`, which calls the HTTP API.
- Settings and thresholds come from one `Settings` object; no magic numbers elsewhere.

## 9. Key Technical Decisions
Decision: Analytics engine as a standalone pure package.
Context: We need to test and explain the audit logic without web or DB setup.
Alternatives: Logic inside API handlers or SQL stored procedures.
Reason: Easier unit testing, reuse, and interview explanation.

Decision: Streamlit frontend + FastAPI backend.
Context: Analytics-focused role; React skills are not the goal.
Alternatives: React, or Streamlit-only.
Reason: A real frontend/backend split with fast UI development.

Decision: Background task for analysis, polling for status.
Context: 50K-row runs can take tens of seconds.
Alternatives: Synchronous request; Celery/Redis queue.
Reason: FastAPI BackgroundTasks is enough for MVP; a queue is a documented future upgrade.

## 10. Performance Considerations
- Bulk inserts (SQLAlchemy `insert` with lists / `COPY`-style batching), not row-by-row.
- Index the columns used for filtering (see DATABASE.md).
- Paginate flagged lists server-side. Never send 50,000 rows to Streamlit.
- 50,000-row analysis under 60 seconds.

## 11. Scalability Considerations
- Single-instance design is fine for the portfolio scope.
- Future: Celery + Redis for runs, object storage for files, per-tenant organizations.

## 12. Failure Scenarios
- Database unavailable: API returns 503 with a generic message; /health reports degraded.
- Analysis fails midway: run status set to failed with a safe error message; partial results are not shown; the user can re-run.
- Invalid file: 422 with a list of problems; nothing is stored.
- Token expired: 401; Streamlit sends the user back to login.
- Streamlit cannot reach the API: show a friendly error and a retry option.
