# Database

## 1. Database Engine
Database: PostgreSQL 16
Hosting: docker-compose locally; managed Postgres on the deployment platform
ORM and migrations: SQLAlchemy 2.x + Alembic

## 2. Naming Conventions
Tables: plural snake_case
Columns: snake_case
Primary Keys: `id` (BIGINT identity)
Foreign Keys: `<singular_table>_id`
Timestamps: `created_at`, `updated_at` (timestamptz, UTC, default now())

## 3. Tables

### users
Purpose: People who can log in.
Columns: id, email (unique), full_name, password_hash, role (auditor | manager), is_active, created_at, updated_at

### uploads
Purpose: One uploaded transaction file.
Columns: id, user_id (FK users), original_filename, stored_path, file_type (csv | xlsx), row_count_total, row_count_accepted, row_count_rejected, validation_summary (JSONB: rejection reasons and counts, missing optional columns), created_at

### transactions
Purpose: Accepted rows of an upload.
Columns: id, upload_id (FK uploads, ON DELETE CASCADE), transaction_id (text, unique per upload), posting_date (timestamptz), amount (NUMERIC(18,2)), vendor_id, department (nullable), account_code (nullable), created_by (nullable), approved_by (nullable), description (nullable)

### analysis_runs
Purpose: One execution of the analysis on an upload.
Columns: id, upload_id (FK uploads, ON DELETE CASCADE), started_by (FK users), status (pending | running | completed | failed), settings (JSONB: all thresholds used), summary (JSONB: totals, counts by level and rule, skipped rules, warnings, benford results), error_message (nullable), signed_off_by (FK users, nullable), signed_off_at (nullable), started_at, finished_at, created_at

### flagged_transactions
Purpose: Transactions flagged in a run, with scores and reasons.
Columns: id, run_id (FK analysis_runs, ON DELETE CASCADE), transaction_pk (FK transactions), risk_score (SMALLINT 0-100), risk_level (high | medium | low), rule_points (SMALLINT), ml_points (SMALLINT), ml_norm (REAL), triggered_rules (TEXT[] of R1..R6), reasons (JSONB list of strings), duplicate_group_id (nullable), review_status (open | reviewed | false_positive | needs_follow_up), created_at

### reviews
Purpose: History of review decisions (append-only).
Columns: id, flagged_id (FK flagged_transactions, ON DELETE CASCADE), reviewer_id (FK users), status, comment (nullable), created_at

### audit_logs
Purpose: Record of important user actions.
Columns: id, user_id (nullable FK users), action (e.g. login, upload, analyze, review, sign_off, delete_upload), entity_type, entity_id, details (JSONB, never sensitive values), created_at

## 4. Relationships
users -> uploads: one user has many uploads.
uploads -> transactions: one upload has many transactions.
uploads -> analysis_runs: one upload has many runs.
analysis_runs -> flagged_transactions: one run has many flagged items.
flagged_transactions -> reviews: one flagged item has many review records (latest decides the current status, which is also cached in flagged_transactions.review_status).
transactions -> flagged_transactions: one transaction can be flagged in many runs.

## 5. Constraints
Required: users.email, users.password_hash, users.role; transactions.transaction_id, posting_date, amount, vendor_id.
Unique: users.email; (transactions.upload_id, transactions.transaction_id).
Checks: transactions.amount > 0; risk_score BETWEEN 0 AND 100; role and status values restricted by CHECK or enum.
Foreign keys: as in section 4; deleting an upload cascades to its transactions, runs, flagged items, and reviews.

## 6. Indexes
- transactions(upload_id) - loading a run's data
- transactions(upload_id, vendor_id) - vendor lookups
- flagged_transactions(run_id, risk_level) - dashboard and filters
- flagged_transactions(run_id, risk_score DESC) - default sort
- flagged_transactions(run_id, review_status) - progress and sign-off checks
- reviews(flagged_id, created_at)
- analysis_runs(upload_id)
- uploads(user_id)

## 7. Data Validation
- Amount must be a positive number; date must parse; transaction_id must be non-empty and unique within the upload.
- Review status False Positive requires a non-empty comment.
- Validation is enforced in Pydantic/service code and backed by database constraints.

## 8. Soft Delete
No soft delete. Deleting an upload is a hard delete with cascade (a data-retention feature). The `audit_logs` entry for the deletion is kept.

## 9. Auditing
Record: who uploaded, who ran analysis, who reviewed (full history in `reviews`), who signed off (analysis_runs.signed_off_by/at).
Review history is append-only.

## 10. Sensitive Data
Sensitive fields: users.password_hash, users.email, transaction contents.
Protection: bcrypt hashes; never return hashes in the API; do not log transaction contents.

## 11. Migration Rules
Schema changes must:
1. Be documented here
2. Have an Alembic migration (no manual SQL changes)
3. Be tested (upgrade and downgrade on a fresh database)
4. Avoid breaking existing data

## 12. Seed Data
- `scripts/seed_admin.py` creates the first manager from environment variables.
- Demo data comes from `scripts/generate_synthetic_ledger.py`, which writes CSV files; it is not inserted directly into the database.
