# Problems Faced Log

> Maintained by the AI agent (and by me). Add an entry for every real problem hit during development:
> bugs, failing tests, wrong assumptions, design changes, environment issues, and surprising results.
> This file is also my interview material: "Tell me about a challenge you faced in this project."
> Newest entries at the TOP. Keep entries short and concrete.

## Entry template (copy for each problem)
```
### P-000 | [short title]
- Date:
- Phase:
- Status: Open / Resolved / Workaround
- What happened: (symptom, error message, or unexpected result)
- Root cause: (why it really happened)
- How it was fixed: (what changed, which files)
- Alternatives considered:
- Lesson learned:
- Related doc updated: (yes/no, which file)
```

---

## Log

### P-022 | Streamlit AppTest.from_file relative path resolution failure
- Date: 2026-10-25
- Phase: Review Fixes
- Status: Resolved
- What happened: Running `AppTest.from_file("frontend/app.py")` in `tests/unit/test_frontend.py` failed with `FileNotFoundError: AppTest script not found at ...\tests\unit\frontend\app.py`.
- Root cause: Streamlit's `AppTest.from_file()` resolves relative file paths relative to the file containing the test execution caller (`tests/unit/test_frontend.py`), not relative to current working directory (`Path.cwd()`).
- How it was fixed: Specified absolute paths using `Path(__file__).resolve().parent.parent.parent / "frontend" / "app.py"`. Verified all 7 page smoke tests (Login, Upload, Dashboard, Review, Benford, Reports, Evaluation) pass without exceptions.
- Alternatives considered: Changing cwd before running tests; rejected as flaky across test runners.
- Lesson learned: Always use absolute paths derived from `Path(__file__)` when providing file paths to third-party test runners like Streamlit AppTest.
- Related doc updated: yes, docs/PROGRESS.md

### P-021 | Upload endpoint lacked file content / magic bytes validation
- Date: 2026-10-25
- Phase: Review Fixes
- Status: Resolved
- What happened: Code review against `docs/SECURITY.md` revealed that file upload validation only inspected the file extension and MIME type, but did not inspect actual file bytes before saving or parsing. Disguised executable files (e.g. `MZ` Windows EXE, `ELF` binaries) or corrupted binary files named `.csv` or `.xlsx` would pass upload checks.
- Root cause: `app/services/upload_service.py` checked filename extension against allowed list, but omitted binary signature / magic-byte verification.
- How it was fixed: Added `_validate_file_content()` in `app/services/upload_service.py`. For `.xlsx`, it verifies OpenXML ZIP magic bytes (`PK\x03\x04`) and confirms archive validity with `zipfile.is_zipfile()`. For `.csv`, it checks that the file is UTF-8 decodable, rejects dangerous executable magic bytes (`MZ`, `\x7fELF`, Mach-O), and rejects binary files containing embedded null bytes (`\x00`). Added integration tests in `tests/integration/test_uploads.py`.
- Alternatives considered: External `python-magic` library; rejected to avoid C library dependencies on Windows.
- Lesson learned: Always validate file content via header signatures and character decoding in addition to extensions.
- Related doc updated: yes, docs/PROGRESS.md

### P-020 | Vulnerable dependencies flagged by pip-audit and Streamlit pillow conflict
- Date: 2026-10-25
- Phase: Review Fixes
- Status: Resolved
- What happened: Running `pip-audit` detected 50 known CVEs across `pillow` (12.3.0), `certifi` (2026.7.22), and `pip` (25.2). Upgrading `pillow>=13.0.0` caused pip to report: `ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts. streamlit 1.66.0 requires pillow<13,>=9.2.0, but you have pillow 13.0.0 which is incompatible.`
- Root cause: Streamlit 1.66.0 pinned an upper bound `<13` on Pillow before Pillow 13.0.0 released with security patches.
- How it was fixed: Upgraded `pillow` to `13.0.0` and `certifi` to `2026.10.23` in `pyproject.toml` as recommended by `pip-audit`. Ran comprehensive runtime testing of Streamlit, all 7 pages, Plotly charts, and test suites, confirming full runtime compatibility. Re-ran `pip-audit`, confirming 0 known vulnerabilities.
- Alternatives considered: Downgrading Pillow to 12.x; rejected as it leaves high-severity CVEs unpatched.
- Lesson learned: Pin dependencies thoughtfully; audit dependencies periodically and verify upper-bound relaxations when security patches are released.
- Related doc updated: yes, docs/PROGRESS.md

### P-019 | AttributeError 'transaction_id' on FlaggedTransaction model in evaluate_analysis_run
- Date: 2026-10-18
- Phase: 7
- Status: Resolved
- What happened: Evaluating an analysis run against ground truth raised `AttributeError: type object 'FlaggedTransaction' has no attribute 'transaction_id'`.
- Root cause: In `evaluate_analysis_run`, the SQLAlchemy join query referenced `FlaggedTransaction.transaction_id == Transaction.id`. In `app/db/models/flagged_transaction.py`, the foreign key column pointing to `transactions.id` is named `transaction_pk`.
- How it was fixed: Updated the query to `.join(FlaggedTransaction, FlaggedTransaction.transaction_pk == Transaction.id)`. Verified by running integration test suite `tests/integration/test_evaluate.py` (4/4 tests passing).
- Alternatives considered: Adding `transaction_id` property or alias to `FlaggedTransaction`, rejected to maintain consistency with existing repositories and declarative model schemas.
- Lesson learned: Always double-check database model foreign key attribute names when authoring ad-hoc join queries.
- Related doc updated: yes, docs/PROGRESS.md

### P-018 | ImportError 'COLOR_SURFACE_CONTAINER' on Streamlit Reports page
- Date: 2026-10-18
- Phase: 6
- Status: Resolved
- What happened: Loading the Reports page in Streamlit raised `ImportError: cannot import name 'COLOR_SURFACE_CONTAINER' from 'frontend.constants'`.
- Root cause: `frontend/pages/reports.py` attempted to import `COLOR_SURFACE_CONTAINER`, but the background surface color token in `frontend/constants.py` is named `COLOR_SURFACE`.
- How it was fixed: Updated `frontend/pages/reports.py` to import and reference `COLOR_SURFACE`. Validated by running an automated `AppTest` suite against `frontend/app.py` in a fresh Python process with `PYTHONPATH` cleared, confirming 0 exceptions and successful rendering of all metrics and download widgets.
- Alternatives considered: Adding `COLOR_SURFACE_CONTAINER` as an alias in `frontend/constants.py`, rejected to keep constants token names canonical and consistent with `docs/DESIGN_SYSTEM.md`.
- Lesson learned: Always run live end-to-end rendering checks in isolated processes to catch import and attribute discrepancies before finishing phase verification.
- Related doc updated: yes, docs/PROGRESS.md

### P-017 | TypeError 'storage_path' when instantiating Upload model in report integration tests
- Date: 2026-10-18
- Phase: 6
- Status: Resolved
- What happened: Running integration tests in `tests/integration/test_report.py` failed with `TypeError: 'storage_path' is an invalid keyword argument for Upload`.
- Root cause: In `test_report.py`, mock `Upload` rows were initialized with `storage_path="uploads/..."` instead of the model column `stored_path`, and were missing the required `file_type="csv"` check constraint attribute.
- How it was fixed: Updated `Upload` instantiations in `test_report.py` to use `stored_path` and `file_type="csv"`. All 79 tests now pass cleanly.
- Alternatives considered: Calling the upload HTTP endpoint in every test, rejected for zero-flag and formula-injection tests to keep tests fast and focused on report generation rather than redundant file parsing.
- Lesson learned: Verify declarative model column names in `app/db/models/` when authoring direct ORM test fixtures.
- Related doc updated: no

### P-016 | ModuleNotFoundError 'frontend' when running Streamlit without PYTHONPATH
- Date: 2026-10-18
- Phase: 5
- Status: Resolved
- What happened: Running `streamlit run frontend/app.py --server.port 8501` in a fresh terminal with the virtual environment activated failed with `ModuleNotFoundError: No module named 'frontend'`.
- Root cause: When Streamlit runs a script (`frontend/app.py`), Python puts the script's directory (`<project_root>/frontend`) at `sys.path[0]`, not the project root. Consequently, absolute imports such as `from frontend.pages...` look for a nested `frontend` folder inside `frontend/`. In addition, `pyproject.toml` only included `app*` in `[tool.setuptools.packages.find]`, so `frontend` was not installed as an editable package into site-packages.
- How it was fixed: 1) Added a `sys.path` bootstrap at the top of `frontend/app.py` to ensure the project root is always inserted into `sys.path`. 2) Added `"frontend*"` to `pyproject.toml`'s package include list and re-ran `pip install -e .`. Verified in a fresh PowerShell process with `PYTHONPATH` unset that Streamlit starts and `http://localhost:8501` returns HTTP 200.
- Alternatives considered: Requiring users to set `$env:PYTHONPATH = "."` in terminal instructions, rejected because it is error-prone, platform-specific, and violates frictionless setup expectations.
- Lesson learned: Always test entry points in a pristine subprocess with all environment overrides (`PYTHONPATH`, etc.) cleared. Include all top-level application packages in `pyproject.toml`'s package discovery configuration.
- Related doc updated: yes, README.md

### P-015 | Dashboard "Total Transactions" displays 0 due to validation summary key mismatch
- Date: 2026-10-18
- Phase: 5
- Status: Resolved
- What happened: On the Dashboard, "Total Transactions" showed 0 instead of 50,000 for the `ledger.csv` run, causing "% of total" under Flagged Exceptions to display `0.0%` instead of ~2.8%.
- Root cause: `frontend/pages/dashboard.py` attempted to retrieve `val_sum.get("accepted_rows", 0)`. In `app/analytics/validation.py`, the validation summary dictionary returns keys `"valid_rows"` and `"total_rows"`, while the database `Upload` record stores `"row_count_accepted"`. Neither matched `"accepted_rows"`, resolving to 0.
- How it was fixed: Updated `frontend/pages/dashboard.py` to retrieve `val_sum.get("valid_rows") or selected_up.get("row_count_accepted") or val_sum.get("total_rows", 0)` without altering the analytics engine. Applied compact Indian Rupee formatting (`format_compact_currency`), switched timeline to weekly bars, and added regression tests.
- Alternatives considered: Modifying the dictionary keys returned by `validate_and_clean_data`, rejected to avoid breaking other consumers of the pure analytics engine.
- Lesson learned: Always verify key names against the actual schema emitted by pure analytics modules and database models; provide robust fallbacks across summary and upload entities.
- Related doc updated: yes, docs/PROGRESS.md

### P-014 | Review workbench crash on null signed_off_at datetime slicing
- Date: 2026-10-18
- Phase: 5
- Status: Resolved
- What happened: Review page crashed with `TypeError: 'NoneType' object is not subscriptable` at `frontend/pages/review.py` line 107 when opening an unsigned run.
- Root cause: In unsigned runs, `signed_off_at` is `null` in the API JSON response (`None` in Python). Calling `run_detail.get("signed_off_at", "")` returned `None` because the key was present, so the default empty string fallback was bypassed. Slicing `None[:19]` raised a TypeError.
- How it was fixed: Introduced `format_datetime()` in `frontend/components/badges.py` to safely handle `None` and empty values before slicing or formatting. Replaced all raw `.get(...)[:19]` occurrences across `frontend/` (`review.py`, `dashboard.py`, `upload.py`, `benford.py`). Added unit tests covering both signed and unsigned runs.
- Alternatives considered: Inline `(run_detail.get("signed_off_at") or "")[:19]`, rejected in favor of a centralized formatter function returning `"N/A"` or `"—"` consistently.
- Lesson learned: In Python, `dict.get(key, default)` only evaluates the default if the key is missing entirely, not if its value is `None`. All nullable fields must be explicitly sanitized.
- Related doc updated: yes, docs/PROGRESS.md

### P-013 | Triggered rule codes column name mismatch between analytics engine and DB mapping
- Date: 2026-10-18
- Phase: 4
- Status: Resolved
- What happened: Filtering flagged items by rule (`GET /runs/{id}/flagged?rule=R1`) returned 0 results even though R1 anomalies were present and flagged.
- Root cause: `execute_analysis_pipeline` mapped `row.get("triggered_rules")`, whereas the analytics engine in `app/analytics/scoring.py` emitted the column as `"triggered_rule_codes"`. As a result, empty lists were inserted into `flagged_transactions.triggered_rules`.
- How it was fixed: Updated `app/services/analysis_service.py` to extract `row.get("triggered_rule_codes", row.get("triggered_rules", []))`.
- Alternatives considered: Modifying analytics engine column names, rejected to preserve pure analytics interface stability and backward compatibility.
- Lesson learned: Always verify the exact DataFrame column names emitted by upstream pure analytics functions when transforming them into database entities.
- Related doc updated: no

### P-012 | Pydantic EmailStr dependency missing in virtual environment
- Date: 2026-10-18
- Phase: 4
- Status: Resolved
- What happened: Pytest failed during test collection with `ImportError: email-validator is not installed, run pip install 'pydantic[email]'`.
- Root cause: `EmailStr` in Pydantic v2 requires the optional third-party library `email-validator`, which was not included in `pyproject.toml` dependencies.
- How it was fixed: Replaced `EmailStr` in `app/schemas/auth.py` with standard Pydantic `Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")`.
- Alternatives considered: Adding `email-validator` to project dependencies, rejected because standard regex validation avoids adding an external library dependency.
- Lesson learned: Check whether specialized Pydantic types carry optional extras before introducing them into schemas.
- Related doc updated: no

### P-011 | Case mismatch on risk_level check constraint ('Medium' vs 'medium')
- Date: 2026-10-18
- Phase: 4
- Status: Resolved
- What happened: Background analysis pipeline failed with `CheckViolation: new row for relation "flagged_transactions" violates check constraint "ck_flagged_transactions_risk_level"` (`DETAIL: Failing row contains (..., Medium, ...)`).
- Root cause: The database table schema defines `CheckConstraint("risk_level IN ('high', 'medium', 'low')")` with lowercase literals, whereas `app/analytics/scoring.py` returns capitalized strings (`'High'`, `'Medium'`, `'Low'`).
- How it was fixed: Normalized `str(row["risk_level"]).lower()` when constructing records in `app/services/analysis_service.py`. Also added `db.rollback()` in the exception handler before recording run failure.
- Alternatives considered: Relaxing the database constraint, rejected because strict lowercase enum constraints align with API query conventions.
- Lesson learned: Enforce case normalization at the service-to-database boundary when mapping analytics engine output to database models.
- Related doc updated: no

### P-010 | PostgreSQL parameter limit exceeded during multi-row bulk insert
- Date: 2026-10-18
- Phase: 4
- Status: Resolved
- What happened: Uploading the 50,000-row `data/ledger.csv` failed with `psycopg.OperationalError: sending query and params failed: number of parameters must be between 0 and 65535`.
- Root cause: A single `insert(Transaction).values(transactions_data)` statement with 50,000 rows across 10 columns resulted in 500,000 bind parameters, far exceeding PostgreSQL's protocol maximum of 65,535 parameters.
- How it was fixed: Implemented chunked batching in `app/repositories/transaction_repo.py` and `app/repositories/flagged_repo.py` with `batch_size=2000` (max 20,000 parameters per chunk).
- Alternatives considered: Raw PostgreSQL `COPY` via psycopg binary stream; chunked batching was preferred for simplicity, portable SQLAlchemy Core compatibility, and sub-second execution on 50,000 rows.
- Lesson learned: Always batch bulk inserts into bounded chunks when inserting tens of thousands of rows into relational databases.
- Related doc updated: yes, `docs/PROGRESS.md`

### P-009 | DetachedInstanceError after db_session.expunge_all() in cascade delete test
- Date: 2026-10-18
- Phase: 3
- Status: Resolved
- What happened: In the cascade-delete test, `db_session.expunge_all()` was called before reading `txn.id`, which detached the instance and raised `DetachedInstanceError` when the expired attribute was loaded.
- Root cause: `expunge_all()` detached the objects, and reading an expired attribute on a detached object cannot trigger a reload.
- How it was fixed: Captured the integer primary keys before the delete and the expunge, then used those keys for the assertions.
- Alternatives considered: none
- Lesson learned: Read and store the values you need (such as primary keys) before detaching or expiring objects.
- Related doc updated: no


### P-008 | result.rowcount evaluated to -1 in bulk inserts with psycopg
- Date: 2026-10-18
- Phase: 3
- Status: Resolved
- What happened: Repository tests for `bulk_create_transactions` and `bulk_create_flagged_transactions` failed with `assert -1 == 5`.
- Root cause: Python's fallback idiom `result.rowcount or len(records)` evaluated to `-1` because `-1` is truthy in Python. With multi-value `insert()`, psycopg does not always populate a positive cursor rowcount prior to consumption.
- How it was fixed: Updated `app/repositories/transaction_repo.py` and `app/repositories/flagged_repo.py` to check `result.rowcount if result.rowcount is not None and result.rowcount > 0 else len(records)`.
- Alternatives considered: Using `insert().returning(...)`, rejected because returning all primary keys over the wire creates unnecessary network and memory overhead during high-volume batch inserts.
- Lesson learned: Never rely on `or` fallback with `rowcount` since negative integers are truthy; explicitly test `rowcount > 0`.
- Related doc updated: no

### P-007 | Native host PostgreSQL service collided with Docker container on port 5432
- Date: 2026-10-18
- Phase: 3
- Status: Resolved
- What happened: Psycopg failed to connect to `localhost:5432` with `FATAL: password authentication failed for user "auditlens"`, even though the Docker container `auditlens-db` was healthy.
- Root cause: A local Windows service `postgresql-x64-18` (PostgreSQL 18 server, PID 8212) was already running and listening on `0.0.0.0:5432`. On Windows, connections to `localhost:5432` prioritized the native winsock listener over Docker Desktop's port forwarder.
- How it was fixed: Parameterized the host port in `docker-compose.yml` to `"${POSTGRES_PORT:-5432}:5432"`, set `POSTGRES_PORT=5433` and `DATABASE_URL=postgresql+psycopg://auditlens:auditlens_password@localhost:5433/auditlens` in `.env`, and restarted the container with `docker compose up -d`.
- Alternatives considered: Stopping the Windows service via `Stop-Service postgresql-x64-18`, which failed due to lack of administrative permissions in non-elevated user shell. Parameterizing the host port is cleaner and maintains environment portability.
- Lesson learned: Port collisions with pre-existing local developer services can silently hijack connections; use environment-variable driven port mappings to prevent hard collisions.
- Related doc updated: yes, `docs/PROGRESS.md`

### P-006 | Per-run min-max ML scaling produces Low-risk flags on clean datasets
- Date: 2026-10-17
- Phase: 2
- Status: Workaround (Known Limitation)
- What happened: Running the analysis pipeline on `ledger_clean.csv` (which contains zero rule violations) flagged 330 out of 50,000 transactions (0.66%) as Low risk, driven purely by ML points.
- Root cause: Isolation Forest anomaly scores are normalized with per-run min-max scaling (`ml_norm = (raw - min) / (max - min)`). Even in a clean dataset without true outliers, the statistical tails of normal variance are stretched to [0, 1], awarding the top ~0.66% rows `ml_points >= 30` which reaches the default `flag_threshold = 30`.
- How it was fixed: Documented as an intended design property and known limitation in `docs/PROGRESS.md`, `docs/AUDIT_RULES.md`, and `docs/PRD.md`.
- Alternatives considered: Possible future improvements:
  1. Fixed absolute score thresholds from reference datasets rather than per-run relative min-max scaling.
  2. Percentile-based cutoffs or calibrating scores against empirical background distributions.
  3. Requiring a supporting rule trigger or a higher minimum raw decision function cutoff for ML-only flags.
- Lesson learned: Min-max normalization on isolated runs creates a relative spread regardless of whether genuine outliers are present; relative scaling must be contextualized with absolute baselines when evaluating clean data.
- Related doc updated: yes, `docs/PROGRESS.md` and `docs/AUDIT_RULES.md`

### P-005 | KeyError in build_feature_matrix when optional department column was absent
- Date: 2026-10-17
- Phase: 2
- Status: Resolved
- What happened: `test_feature_vendor_robust_z_fallback` threw `KeyError: 'department'` when executing `build_feature_matrix` on a DataFrame that did not include the optional department column.
- Root cause: `skip_dept` evaluated `(df["department"].astype(str).str.strip() == "").all()` before checking whether `"department"` existed in `df.columns`.
- How it was fixed: Updated `app/analytics/features.py` to first verify `"department" in df.columns` before indexing the series.
- Alternatives considered: Forcing validation to always add a blank department column beforehand, rejected because feature engineering should be robust to standalone DataFrames without requiring a prior validation step.
- Lesson learned: Always check column membership (`col in df.columns`) before slicing DataFrames in feature engineering functions.
- Related doc updated: no

### P-004 | Injected duplicate payment detections counted original donor transactions as false positives under strict matching
- Date: 2026-10-17
- Phase: 2
- Status: Resolved
- What happened: Under strict precision calculation, the pipeline achieved 84.42% precision on `ledger.csv` because all 215 legitimate original donor transactions flagged by rule R2 were counted as false positives.
- Root cause: Audit rule R2 intentionally flags all members of a duplicate group (both the original donor and the duplicate payment). Ground truth originally only recorded the injected copy's ID.
- How it was fixed: Implemented audit-adjusted precision in `app/analytics/evaluation.py` that includes donor transactions (`related_transaction_id`) as valid detections, achieving 99.93% audit-adjusted precision with 100% recall on duplicates.
- Alternatives considered: Changing R2 to only flag the latter duplicate transaction, rejected because AUDIT_RULES.md section 3 explicitly specifies: "All members of the group are flagged and share a duplicate_group_id".
- Lesson learned: Metric calculations in domain-specific systems (like audit risk scoring) must align with domain definitions; report both strict and domain-adjusted metrics with clear explanatory documentation.
- Related doc updated: yes, `docs/PROGRESS.md`

### P-003 | Ground truth lacked duplicate pair relation (related_transaction_id)
- Date: 2026-10-17
- Phase: 2
- Status: Resolved
- What happened: Ground truth CSV contained only `transaction_id` and `anomaly_types`, making it impossible to programmatic trace which original donor transaction was cloned to create an injected duplicate payment.
- Root cause: Phase 1 generator only recorded the newly injected copy ID without capturing the donor row index mapping.
- How it was fixed: Updated `scripts/generate_synthetic_ledger.py` and its tests to track donor IDs and add `related_transaction_id` to `ground_truth.csv`. Regenerated default datasets in `data/`.
- Alternatives considered: Performing nearest-neighbor searches during evaluation, rejected because deterministic linking in ground truth is more reliable and robust.
- Lesson learned: Ground truth datasets for relational anomalies (duplicates, cycles) must store the relational foreign keys alongside anomaly labels.
- Related doc updated: yes, `docs/PROGRESS.md`

### P-002 | Slow generation due to iterative row updates in anomaly injection
- Date: 2026-10-17
- Phase: 1
- Status: Resolved
- What happened: The initial anomaly injection implementation used Python dictionary and row iteration with `.at[idx, ...]`, resulting in slow performance (~13s during unit tests).
- Root cause: Repeated scalar `.at` or `.loc` assignments in pandas incur large overhead across hundreds of rows.
- How it was fixed: Fully vectorized anomaly injections in `scripts/generate_synthetic_ledger.py` using NumPy index slicing and array assignments. 50,000 rows now generate in ~0.28s.
- Alternatives considered: Retaining row iteration for logic simplicity, rejected because AUDIT_RULES.md and CODE_STYLE.md mandate vectorized pandas operations.
- Lesson learned: Always apply vectorized operations across slices in pandas/NumPy to ensure sub-second dataset generation.
- Related doc updated: no

### P-001 | Flawed test assertion assuming disjoint transaction IDs between clean and anomalous ledgers
- Date: 2026-10-17
- Phase: 1
- Status: Resolved
- What happened: `test_synthetic_ledger_clean_has_no_injected_anomalies` failed with `assert len(gt_txns.intersection(clean_txns)) == 0 (30 == 0)`.
- Root cause: The test assumed `ledger_clean.csv` and `ground_truth.csv` had disjoint transaction IDs. In reality, `ledger.csv` is derived from `ledger_clean.csv`, sharing the baseline IDs (`TXN-000001` to `TXN-050000`).
- How it was fixed: Updated the test in `tests/unit/test_synthetic_ledger.py` to assert the true invariant: all transactions in `ledger_clean` (including those corresponding to ground truth entries in `ledger.csv`) violate none of the audit rules and satisfy all clean criteria.
- Alternatives considered: Prefixing clean IDs with `TXN-CLN-`, rejected because keeping 1-to-1 ID alignment allows direct row-level comparison between baseline and corrupted transactions.
- Lesson learned: Unit test assertions should validate business domain invariants rather than superficial structural assumptions.
- Related doc updated: no

