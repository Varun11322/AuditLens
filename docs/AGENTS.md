# AI Coding Agent Instructions
(Place this file in the repository ROOT. Check how Antigravity discovers rules/instructions and also add it there if needed.)

## 1. Project Context
Project: AuditLens
Purpose: Audit anomaly detection for financial transactions - upload data, run audit rules + ML, score risk, review flagged items, export a report.
Primary Users: Auditors and managers.
Stack: Streamlit (frontend), FastAPI (backend), PostgreSQL + SQLAlchemy + Alembic, pandas/scikit-learn/SciPy, JWT auth, Docker.

## 2. Source of Truth
Before significant changes, read the relevant documents in /docs:
- PROJECT_BRIEF, PRD.md, AUDIT_RULES.md (what and exactly how to detect)
- ARCHITECTURE.md, DATABASE.md, API.md (structure, tables, endpoints)
- SECURITY.md, CODE_STYLE.md, TESTING.md (rules and verification)
- PROGRESS.md and PROBLEMS_LOG.md (read at the start of each task to know where we are; update at the end)
- DESIGN_SYSTEM.md, UX_FLOWS.md (UI)
Do not contradict these documents without first identifying the conflict and asking.

## 3. General Rules
- Understand existing code before modifying it.
- AUDIT_RULES.md is authoritative for thresholds, formulas, and scoring. Never invent or tweak them silently.
- Keep the analytics engine (`app/analytics/`) independent of FastAPI, Streamlit, and the database. It takes DataFrames and settings and returns DataFrames/dicts.
- Streamlit contains no business logic. It only calls the API.
- Reuse existing utilities. Avoid unnecessary dependencies. Do not change unrelated files.
- Do not invent business requirements. Do not expose secrets. Never commit .env files or real data.
- Use only synthetic or public data.

## 4. Planning
Before a non-trivial task:
1. Read the relevant docs and code
2. List affected files and dependencies
3. List database/API changes
4. List tests required
5. Write a concise plan and wait for approval if the task is large

## 5. Implementation
- Work one phase at a time (see build phases in the project brief). Do not start the next phase unprompted.
- Make focused changes. Preserve existing behavior. Keep code readable.
- Use vectorized pandas, not row loops, in the analytics engine.

## 6. Validation
After implementation:
1. Run pytest
2. Run ruff (lint + format check)
3. Start the app (or relevant part) and verify the critical flow
4. Review changed files for unintended edits
Never claim a check passed unless you ran it. Report what you ran and the results.

## 7. Documentation
Update docs when behavior, schema, API contracts, or rules change. Keep README setup steps accurate.

### Tracking files (mandatory)
- `docs/PROGRESS.md`: after every phase (and whenever a feature status changes), update phase status, feature/rule checklists, test results, key metrics, deviations from the docs, limitations, and next steps. Be honest: mark Done only what you ran and verified.
- `docs/PROBLEMS_LOG.md`: add an entry for every real problem (bug, failing test, wrong assumption, design change, environment issue, surprising result): what happened, root cause, fix, alternatives considered, lesson learned. Newest first. If a phase had no problems, say so in your summary.
- Never delete old entries; append or mark them Resolved.

## 8. Conflict Handling
If requirements conflict or are ambiguous: do not guess. State the conflict and ask.

## 9. Completion Criteria
A task is complete only when:
- Requirements and acceptance criteria are met
- Tests and lint pass
- No unintended files changed
- Security rules are respected
- Documentation is updated where needed
- docs/PROGRESS.md and docs/PROBLEMS_LOG.md are updated
- A short summary lists what changed, what was tested, and known limitations
