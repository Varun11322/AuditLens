# Project Brief: AuditLens - Audit Anomaly Detection Platform

> Give this file to the AI agent FIRST. It explains the project at a high level.
> On the first prompt, the agent must only read, summarize, and ask questions. It must NOT write code yet.

## 1. What we are building
AuditLens is a web application that helps an auditor find risky or suspicious financial transactions.
The auditor uploads a transaction file (CSV/Excel). The system runs standard audit tests plus a machine
learning model, gives every transaction a risk score, and shows the flagged ones on a dashboard.
The auditor then reviews each flagged item (Reviewed / False Positive / Needs Follow-up), adds comments,
and exports an exceptions report.

## 2. Why we are building it
- Auditors cannot manually check millions of journal entries or payments, so risky ones can slip through.
- This mirrors the work of an IT, Data & Analytics (ITDA) team inside an Audit & Assurance practice:
  scanning 100% of the data instead of a small sample, and reporting exceptions.
- This is a student portfolio project aimed at data analytics / IT audit analyst roles.
  Quality of the analytics and the ability to explain every decision matter MORE than UI polish.

## 3. Users
- **Auditor:** uploads data, runs analysis, reviews flagged transactions, exports reports.
- **Manager:** views all uploads and results, signs off on completed reviews.

## 4. How it works (high level)
```
Streamlit (frontend)  ->  FastAPI (backend)  ->  PostgreSQL (database)
 upload, dashboard,        auth, validation,       users, uploads, transactions,
 review actions            audit rules + ML        flagged results, reviews
```
1. User logs in and uploads a transaction file.
2. Backend validates the file and stores the transactions.
3. User clicks "Run Analysis". The analytics engine runs: rule-based audit tests, Benford's Law check,
   Isolation Forest anomaly model, then combines them into a 0-100 risk score.
4. Flagged transactions are saved and shown on the dashboard.
5. Auditor reviews items; manager signs off; report is exported as Excel.

## 5. Tech stack (decided - do not change without asking)
| Layer | Technology |
|---|---|
| Frontend | Streamlit (+ Plotly for charts) |
| Backend | FastAPI + Uvicorn |
| Database | PostgreSQL, SQLAlchemy ORM, Alembic migrations |
| Analytics | Python, pandas, NumPy, SciPy, scikit-learn (Isolation Forest) |
| Auth | JWT (PyJWT or python-jose), roles: auditor, manager; passwords hashed with bcrypt |
| Reports | openpyxl (Excel export) |
| Testing | pytest, httpx (API tests) |
| Quality | ruff (lint + format), mypy (optional) |
| Deployment | Docker + docker-compose (Postgres + API + Streamlit) |

## 6. Scope
**Must have (MVP):** login with roles; upload CSV/XLSX; run analysis; 6 audit rules; Benford's Law report;
Isolation Forest scoring; risk score + risk level; flagged-transactions table with filters;
review workflow with comments; Excel exceptions report; synthetic data generator; tests for the analytics engine.

**Should have:** evaluation page (precision/recall on synthetic data with known injected anomalies);
configurable thresholds per analysis run; Docker setup; live deployment.

**Not in scope:** real-time streaming, multi-tenant organizations, payments, email notifications,
custom column-mapping UI, deep-learning models, React frontend.

## 7. Document map
All documents live in `docs/` in the repository (AGENTS.md also goes in the repo root).
| File | Tells the agent |
|---|---|
| PRD.md | What to build: features, acceptance criteria |
| AUDIT_RULES.md | Exact audit tests, ML design, scoring formula (core of the project) |
| AGENTS.md | How the agent must behave |
| CODE_STYLE.md | How code is written |
| SECURITY.md | What must be protected |
| TESTING.md | How we verify it works |
| ARCHITECTURE.md | System structure and folders |
| DATABASE.md | Tables and relationships |
| API.md | Endpoint contracts |
| DESIGN_SYSTEM.md | Look and feel of the Streamlit UI |
| UX_FLOWS.md | Screens and user journeys |
| PROGRESS.md | How much is implemented (agent keeps it updated) |
| PROBLEMS_LOG.md | Problems faced and how they were solved (agent keeps it updated) |

## 8. Build phases (one phase at a time, validate before moving on)
- **Phase 0:** Repo scaffold, docker-compose with PostgreSQL, health-check endpoint, lint/test setup.
- **Phase 1:** Synthetic ledger generator + sample data files (with ground-truth labels).
- **Phase 2:** Analytics engine as a standalone, unit-tested Python package (rules, Benford, Isolation Forest, scoring). No web code.
- **Phase 3:** Database models and Alembic migrations.
- **Phase 4:** FastAPI backend: auth, uploads, analyze, flagged list, review actions.
- **Phase 5:** Streamlit UI against the real API.
- **Phase 6:** Excel report export.
- **Phase 7:** Evaluation page, README with screenshots, Docker finalization, deployment.

## 9. Ground rules for the agent
- Read the relevant docs before each task. Do not invent requirements.
- If two documents conflict, stop and ask. Do not guess.
- The analytics engine must stay independent of FastAPI and Streamlit so it can be tested alone.
- After each phase: run tests and lint, summarize what changed, list anything unfinished.
- After each phase: update docs/PROGRESS.md (what is done and verified) and docs/PROBLEMS_LOG.md (problems faced, causes, fixes, lessons).

## 10. First prompt to the agent
"Read this project brief. Summarize the project in your own words in under 150 words, list any
ambiguities or questions you have, and wait for the next documents. Do not write code yet."
