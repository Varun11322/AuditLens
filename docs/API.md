# API Documentation

## Conventions
Base URL: http://localhost:8000 (config: API_BASE_URL)
Authentication: `Authorization: Bearer <JWT>` on every route except /health and /auth/login
Versioning: unversioned for MVP (prefix /api/v1 is an optional later change; if added, update this file)
Error format: `{"error": {"code": "string_code", "message": "human readable", "details": {...optional}}}`
Pagination: `page` (default 1) and `page_size` (default 50, max 200); responses include `total`, `page`, `page_size`, `items`
Rate limits: login 10/minute per IP
Docs: FastAPI interactive docs at /docs

## Health
### GET /health
Purpose: liveness and database check. Auth: none. Success: 200 `{"status":"ok"}`. If the database is down: 503.

## Auth
### POST /auth/login
Purpose: exchange credentials for a token.
Request: `{"email": "...", "password": "..."}`
Success 200: `{"access_token": "...", "token_type": "bearer", "user": {"id", "email", "full_name", "role"}}`
Errors: 401 invalid credentials; 429 rate limited.
Tests: success, wrong password, unknown email, inactive user.

### GET /auth/me
Purpose: current user. Success 200: user object. Errors: 401.

### POST /users (manager only)
Purpose: create a user. Request: `{"email","full_name","password","role"}`. Success 201: user. Errors: 403, 409 email exists, 422.

## Uploads
### POST /uploads
Purpose: upload and validate a transaction file.
Permission: auditor or manager.
Request: multipart/form-data, field `file` (.csv or .xlsx).
Success 201: `{"id", "original_filename", "row_count_total", "row_count_accepted", "row_count_rejected", "validation_summary"}`
Errors: 413 too large; 415 unsupported type; 422 missing required columns (list them) or empty file.
Side effects: stores file, inserts accepted transactions, writes an audit log.
Validation: see AUDIT_RULES.md section 1.
Tests: valid file, missing columns, bad rows counted, oversized file, wrong type, unauthenticated.

### GET /uploads
Purpose: list uploads (auditor: own; manager: all). Query: page, page_size. Success 200: paginated list.

### GET /uploads/{upload_id}
Purpose: upload detail incl. validation summary. Errors: 404 if not found or not visible.

### DELETE /uploads/{upload_id}
Purpose: delete an upload and all related data. Success 204. Errors: 404. Side effects: cascade delete, audit log entry.

### GET /uploads/template
Purpose: download the CSV template with the canonical columns. Success 200 file.

## Analysis Runs
### POST /uploads/{upload_id}/analyze
Purpose: start an analysis run.
Request (optional overrides): `{"settings": {"approval_limit": 100000, "duplicate_window_days": 7, ...}}` (keys as in AUDIT_RULES.md section 2; unknown keys rejected with 422)
Success 202: `{"run_id": 12, "status": "pending"}`
Errors: 404, 422 invalid settings.
Side effects: creates analysis_runs row; background task runs the pipeline.
Idempotency: each call creates a new run; the UI should disable the button while a run is active.
Tests: valid run, invalid settings, upload belongs to another user.

### GET /runs/{run_id}
Purpose: status and summary. Success 200: `{"id","upload_id","status","settings","summary","error_message","started_at","finished_at","signed_off_by","signed_off_at"}`

### GET /uploads/{upload_id}/runs
Purpose: list runs for an upload.

### GET /runs/{run_id}/benford
Purpose: Benford results (overall and flagged vendors). Success 200: observed vs expected per digit, chi_square, p_value, mad, conformity label, per-vendor list; or `{"available": false, "reason": "insufficient data"}`.

### POST /runs/{run_id}/sign-off (manager only)
Purpose: sign off a completed run.
Errors: 403 not manager; 409 if any flagged item has review_status open; 409 if the run is not completed.
Success 200: updated run.

## Flagged Transactions
### GET /runs/{run_id}/flagged
Purpose: paginated, filterable flagged list.
Query params: page, page_size, risk_level (high|medium|low, repeatable), rule (R1..R6, repeatable), vendor_id, department, review_status, date_from, date_to, amount_min, amount_max, sort_by (risk_score|amount|posting_date, default risk_score), sort_dir (asc|desc, default desc).
Success 200: paginated items with transaction fields + risk_score, risk_level, triggered_rules, review_status.

### GET /flagged/{flagged_id}
Purpose: detail with score breakdown (rule_points, ml_points, ml_norm), reasons, duplicate group members, and review history.

### PATCH /flagged/{flagged_id}/review
Purpose: set review status and comment.
Request: `{"status": "reviewed|false_positive|needs_follow_up|open", "comment": "..."}`
Rules: comment required when status is false_positive; run must not be signed off (409 otherwise).
Success 200: updated item. Side effects: appends a reviews row, updates cached status, writes an audit log.
Errors: 403/404, 409, 422.
Tests: each status, missing comment, signed-off run, other user's run.

## Reports
### GET /runs/{run_id}/report?format=xlsx
Purpose: download the exceptions report.
Sheets: Summary, Flagged Transactions, Rule Counts, Benford, Review Log.
Success 200: file download. Errors: 404; 409 if the run is not completed.
Security: cells starting with = + - @ are neutralized (see SECURITY.md).

## Evaluation (should have)
### POST /runs/{run_id}/evaluate
Purpose: compare the run against a ground_truth CSV (field `file`: transaction_id, anomaly_types).
Success 200: precision, recall, per-anomaly-type recall, counts. Errors: 422 bad file.
