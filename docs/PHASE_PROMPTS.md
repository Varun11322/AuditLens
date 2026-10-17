# Phase Prompts for Antigravity (AuditLens)

## Setup (do once, before any prompt)
1. Create the project folder and a `docs/` folder inside it.
2. Put ALL 12 .md files in `docs/` (except AGENTS.md, which goes in the project ROOT; keep a copy in docs/ too if you like).
3. Do NOT paste the files into the chat one by one. Keep them in the repo and tell the agent which ones to read in each prompt.
4. Use git from the start: commit after every phase so you can roll back.

Rule for every phase: the agent works on that phase only, then stops and reports.

Two tracking files are included (PROGRESS.md and PROBLEMS_LOG.md). Put them in `docs/` with the others.
- PROGRESS.md shows how much of the project is implemented. The agent updates it after every phase.
- PROBLEMS_LOG.md records every problem faced and how it was fixed. It is also your interview material.
Every phase prompt below already tells the agent to update both. Read them yourself after each phase to check they are honest.

---

## Prompt 0 - Understand the project (no code)
```
Read these files in the docs/ folder: 00_PROJECT_BRIEF.md, PRD.md, AUDIT_RULES.md, PROGRESS.md, PROBLEMS_LOG.md, and AGENTS.md in the repo root.

Tasks:
1. Summarize the project in under 150 words.
2. Explain the risk score formula and each of the 6 audit rules in your own words, so I can check you understood them.
3. List any ambiguities, conflicts between documents, or questions.

Also explain how you will use PROGRESS.md and PROBLEMS_LOG.md during the project.
Do NOT write any code or create any other files yet. Wait for my answers.
```
(Answer its questions, then move on. If it found a real conflict, fix the .md file first.)

---

## Prompt 1 - Phase 0: Repo scaffold
```
Read AGENTS.md, ARCHITECTURE.md, CODE_STYLE.md, TESTING.md, SECURITY.md (sections 3 and 4 only).

Do Phase 0 only:
- Create the project structure exactly as in ARCHITECTURE.md section 7 (empty packages with __init__.py where needed).
- pyproject.toml with dependencies (fastapi, uvicorn, sqlalchemy, alembic, psycopg, pydantic-settings, pandas, numpy, scipy, scikit-learn, openpyxl, streamlit, plotly, httpx, pytest, pytest-cov, ruff, PyJWT, passlib[bcrypt], python-multipart) and ruff/pytest config.
- docker-compose.yml with PostgreSQL 16 (API and Streamlit services can be added later).
- .env.example with placeholders only, and a .gitignore (ignore .env, uploads/, data/, __pycache__, .venv).
- A FastAPI app with GET /health and one passing test for it.
- README.md with setup steps.

Do not implement anything from later phases. When done, run pytest and ruff, then give me a summary: files created, commands run with results, and anything unfinished.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 2 - Phase 1: Synthetic data generator
```
Read AUDIT_RULES.md (sections 1, 2, 8) and PRD.md (Feature 7), plus CODE_STYLE.md and TESTING.md.

Do Phase 1 only: implement scripts/generate_synthetic_ledger.py exactly as specified in AUDIT_RULES.md section 8.
- Arguments: --rows (default 50000), --seed (default 42), --out-dir (default data/).
- Outputs: ledger.csv, ground_truth.csv, ledger_clean.csv.
- Use vectorized pandas/NumPy, seeded randomness, canonical schema from section 1.
- Add pytest tests: same seed gives identical output, schema is correct, every anomaly type is present in ground_truth, ledger_clean has no injected anomalies, transaction_ids are unique.

Then generate the default files, run pytest and ruff, and report: counts per anomaly type, file sizes, test results, and any assumptions you made.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 3 - Phase 2: Analytics engine (most important)
```
Read AUDIT_RULES.md fully, ARCHITECTURE.md (sections 4, 7, 8), CODE_STYLE.md (especially pandas rules), and TESTING.md.

Do Phase 2 only: implement the analytics package in app/analytics/ as a PURE Python package (no FastAPI, no SQLAlchemy, no Streamlit imports):
- settings.py: Settings dataclass/Pydantic model with the defaults from AUDIT_RULES.md section 2
- validation.py: validate/clean an input DataFrame per section 1, returning clean rows plus a validation summary (rejected counts and reasons, missing optional columns)
- rules.py: rules R1 to R6 exactly as in section 3, vectorized, skipping rules when required columns are missing and recording that
- benford.py: Benford test per section 4 (observed, expected, chi-square, p-value, MAD, conformity label, per-vendor)
- features.py and ml.py: features and IsolationForest per section 5, deterministic
- scoring.py: risk score, levels, and plain-English reasons per section 6
- pipeline.py: run_analysis(df, settings) that ties everything together and returns flagged results plus a summary
- evaluation.py: precision/recall overall and per anomaly type against ground_truth

Write thorough unit tests under tests/unit/analytics/ following TESTING.md, including all the boundary cases listed there. Do not change any thresholds or formulas. If something in AUDIT_RULES.md is unclear, ask me.

When done: run pytest with coverage and ruff. Then run the pipeline on the generated data/ledger.csv and report: runtime, number flagged, counts by level and by rule, and precision/recall against ground_truth.csv. Also run it on ledger_clean.csv and report how many get flagged.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```
(Check the numbers it reports. All injected rule-based anomalies should be caught. If recall is below 100% on rule-based types, ask it to explain why.)

---

## Prompt 4 - Phase 3: Database models and migrations
```
Read DATABASE.md, ARCHITECTURE.md (sections 7, 8), CODE_STYLE.md, SECURITY.md (sections 1 and 2).

Do Phase 3 only:
- SQLAlchemy 2.x models for all tables in DATABASE.md, with constraints, indexes, and cascades as specified
- Alembic setup and an initial migration
- scripts/seed_admin.py creating the first manager from environment variables
- Repository functions for basic create/read operations needed later (keep them minimal)
- Tests: migration upgrade and downgrade on a fresh database, constraint checks (unique email, positive amount, cascade delete)

Do not build API endpoints yet. Run migrations against the docker-compose Postgres, run pytest and ruff, and report what you did and any deviations from DATABASE.md.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 5 - Phase 4: FastAPI backend
```
Read API.md, SECURITY.md, ARCHITECTURE.md, DATABASE.md, CODE_STYLE.md, TESTING.md, and PRD.md (Features 1 to 5).

Do Phase 4 only: implement the backend exactly per API.md.
- Auth (JWT + bcrypt, roles), user creation, login rate limiting
- Uploads (validation using app/analytics/validation.py), list/detail/delete, template download
- Analysis runs in a background task that calls app/analytics/pipeline.py; status polling
- Benford endpoint, flagged list with filters/sorting/pagination, flagged detail, review PATCH, manager sign-off
- Role and ownership checks on every endpoint, consistent error format
- Services and repositories layering per ARCHITECTURE.md; no business logic in routers

Write integration tests per TESTING.md (auth, ownership, upload validation, analyze -> flagged -> review -> sign-off). Skip the report export and evaluation endpoints for now.

Run pytest and ruff, then summarize: endpoints implemented, tests, deviations from API.md, and anything left. Do not build any UI.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 6 - Phase 5: Streamlit UI
```
Read UX_FLOWS.md, DESIGN_SYSTEM.md, API.md, and AGENTS.md.

Do Phase 5 only: build the Streamlit frontend in frontend/.
- All HTTP calls go through frontend/api_client.py; no business logic and no database access in Streamlit
- Pages: Login, Upload, Dashboard, Review, Benford, per UX_FLOWS.md flows 1 to 6 and 8
- Follow DESIGN_SYSTEM.md: Plotly charts, risk badges with text labels, empty/loading/error states, server-side pagination
- Role-aware UI (manager-only sign-off), session expiry handling
- .streamlit/config.toml with the theme

Show me how to run it with the backend and the seeded admin user. Verify the flow login -> upload data/ledger.csv -> run analysis -> dashboard -> review one item, and report what you verified and what you could not verify.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 7 - Phase 6: Excel report
```
Read API.md (Reports section), PRD.md (Feature 6), SECURITY.md (section 8 on formula injection), TESTING.md.

Do Phase 6 only:
- Implement GET /runs/{run_id}/report?format=xlsx with sheets: Summary, Flagged Transactions, Rule Counts, Benford, Review Log. Include the run settings and run date.
- Neutralize cells starting with = + - @
- Add a Download button on the Reports page in Streamlit
- Tests: valid xlsx, expected sheets, zero-flag case, formula injection case

Run pytest and ruff, then summarize the changes.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 8 - Phase 7: Evaluation, Docker, README
```
Read PRD.md (Feature 8), AUDIT_RULES.md (section 9), API.md (Evaluation), ARCHITECTURE.md, SECURITY.md.

Do Phase 7 only:
1. Evaluation: POST /runs/{run_id}/evaluate and an Evaluation page in Streamlit showing precision, recall, and per-anomaly-type recall.
2. Docker: Dockerfiles and docker-compose so that `docker compose up` starts Postgres, the API (with migrations), and Streamlit.
3. README.md: overview, architecture diagram, setup, how to generate data, how to run tests, screenshots placeholder section, limitations, and future work.
4. Re-check SECURITY.md checklist item by item and tell me which are done and which are not.

Run all tests and lint, and report a final summary including any documentation that no longer matches the code.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## Prompt 9 - Final review (before putting it on your resume)
```
Review the whole repository against PRD.md, AUDIT_RULES.md, API.md, SECURITY.md, and TESTING.md. Report concrete findings with file locations: deviations from the docs, missing tests, security gaps, performance problems (run the 50,000-row timing), and documentation that is out of date. Separate verified issues from questions. Do not claim a check passed unless you ran it. Do not change code yet.

Before you finish, also update the two tracking files:
- docs/PROGRESS.md: set this phase's status, date, test results, key metrics, deviations from the docs, known limitations, and next steps. Only mark things Done if you actually ran and verified them.
- docs/PROBLEMS_LOG.md: add an entry (using the template in that file) for every problem you hit in this phase - what happened, root cause, how you fixed it, and what you learned. If there were no problems, write that explicitly in your summary.
```

---

## If something goes wrong
- Agent skipped ahead: "Stop. You were only asked to do Phase N. Revert anything outside that phase."
- Agent changed a threshold or formula: "AUDIT_RULES.md is authoritative. Restore the specified values."
- Tests fail repeatedly: "Explain the root cause first, then make the smallest fix. Do not rewrite unrelated code."
- Docs and code disagree: decide which is right, update the .md file, then tell the agent to re-read it.
