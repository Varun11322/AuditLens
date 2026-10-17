# Security Guidelines
Financial data is sensitive. Even though this project uses synthetic data, build it as if it were real.

## 1. Authentication
Method: email + password -> JWT access token (short expiry, e.g. 60 minutes).
Passwords: hashed with bcrypt (using the bcrypt library directly, not passlib). Never store or log plain passwords.
No public self-registration in production mode. Seed an initial manager account via a CLI/seed script using environment variables. Managers can create auditor accounts.

## 2. Authorization
Roles: manager, auditor.
### Auditor
- Upload files, run analysis on own uploads, view own uploads/runs, review flagged items from own runs, export own reports.
### Manager
- Everything an auditor can do, view all uploads and runs, create users, sign off a run.
Authorization is enforced server-side in FastAPI dependencies, never only in the UI. Ownership checks on every upload/run/flagged-item endpoint (return 404 for items the user cannot see).

## 3. Secrets
- Never hard-code credentials. Never commit .env. Provide `.env.example` with placeholders only.
- Secrets (JWT secret, DB URL, seed admin password) come from environment variables.
- JWT secret must be at least 32 random characters; the app refuses to start in production mode with the default value.

## 4. Environment Variables
Public/config: APP_ENV, MAX_UPLOAD_MB, API_BASE_URL (Streamlit)
Private: DATABASE_URL, JWT_SECRET, JWT_EXPIRE_MINUTES, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD

## 5. API Security
Input validation: Pydantic schemas for all request bodies and query params; validate pagination limits.
Rate limiting: login endpoint limited (e.g. slowapi, 10/minute per IP); document as a minimum.
CORS: allow only the Streamlit origin from config. No wildcard in production.
Authentication: every route except /health and /auth/login requires a valid token.
Errors: never return stack traces or SQL errors to the client.

## 6. Data Protection
Sensitive data: transaction contents, vendor ids, user emails, password hashes.
Encryption: HTTPS in deployment; database credentials not exposed.
Retention: provide a delete-upload endpoint that removes the upload and its transactions, runs, and reviews (cascade).
Never use real client data in this project.

## 7. Logging
Never log: passwords, tokens, raw uploaded rows, secrets.
Log: login success/failure, upload, analysis run start/end, review changes, sign-offs, errors.
Keep an `audit_logs` table for user actions (see DATABASE.md).

## 8. File Uploads
Allowed file types: .csv, .xlsx (check extension and content, not only the extension).
Maximum size: MAX_UPLOAD_MB (default 25).
Validation: reject unknown types; parse with pandas safely; never execute or evaluate cell contents; neutralize formula injection on export (prefix cells starting with = + - @ with a single quote in Excel/CSV exports).
Storage: parsed rows go to the database; the original file is stored in a non-public `uploads/` directory with a generated filename (never the user-supplied name).

## 9. Security Checklist
- [ ] Authentication implemented (JWT + bcrypt)
- [ ] Role and ownership checks on every endpoint
- [ ] Server-side validation with Pydantic
- [ ] Secrets only in env, .env ignored by git
- [ ] Login rate limiting
- [ ] File upload validated (type, size, content)
- [ ] Export is protected against formula injection
- [ ] Errors do not expose sensitive details
- [ ] Dependencies reviewed (pip-audit or similar)
