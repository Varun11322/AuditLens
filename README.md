# AuditLens

Audit anomaly detection for financial transactions. AuditLens empowers auditors and managers to ingest entire transaction populations, execute deterministic audit rules and machine learning anomaly detection, score risk, manage audit disposition reviews, and export comprehensive audit workpapers.

---

## 1. Problem & Solution

### The Problem
Auditors are mandated to evaluate internal controls and verify ledger integrity, but testing 100% of transactions manually is impossible. Traditional audit sampling methods test random subsets of journal entries and disbursements, frequently missing:
- **Split invoices** structured just below approval thresholds to evade management sign-off.
- **Duplicate disbursements** to the same vendor posted within days.
- **Self-approved transactions** violating segregation-of-duties controls.
- **Off-hours or weekend postings** made without authorization.
- **Statistical outliers** exhibiting abnormal velocity, amount spikes, or unusual peer-group behavior.

### The Solution
AuditLens scans 100% of the transaction population within seconds, combining:
1. **Deterministic Audit Rules (R1–R6)**: Enforcing segregation of duties, duplicate detection, approval threshold compliance, round amounts, and off-hour postings.
2. **Benford's Law Conformity**: First-digit frequency distribution analysis (overall and per vendor with Nigrini MAD thresholds).
3. **Machine Learning Anomaly Detection**: Isolation Forest modeling multidimensional transaction features (log amounts, robust vendor z-scores, daily velocity, department percentiles).
4. **Combined Risk Scoring**: Transparent scoring model (0–100) assigning High, Medium, or Low risk tiers with plain-English audit justifications.
5. **Auditor Review Workbench**: Collaborative workflow enabling auditors to review flagged items, record justifications, and secure manager sign-off.
6. **Standardized Workpaper Export**: Multi-sheet Excel (`.xlsx`) deliverables with executive scorecards, audit logs, and formula injection protection.

---

## 2. Architecture & Tech Stack

### Architecture Diagram
```
+-------------------------------------------------------------------------+
|                              User Browser                               |
|                     http://localhost:8501 (Streamlit)                   |
+------------------------------------+------------------------------------+
                                     |  HTTP (Bearer JWT)
                                     v
+-------------------------------------------------------------------------+
|                        AuditLens Frontend Service                       |
|          Streamlit Multi-Page App (No direct database/business logic)    |
|   Pages: Login | Upload | Dashboard | Review | Benford | Reports | Eval |
+------------------------------------+------------------------------------+
                                     |  REST API / HTTP
                                     v
+-------------------------------------------------------------------------+
|                         FastAPI Backend Service                         |
|   Routers: /auth | /uploads | /runs | /flagged | /health                |
|   Services: UploadService | AnalysisService | ReviewService | Report    |
|   Security: JWT Auth, Direct Bcrypt, IP Rate Limiter, Ownership Guards  |
+-------------------+--------------------------------+--------------------+
                    |                                |
                    | ORM / SQL                      | Pure DataFrames
                    v                                v
+----------------------------+   +----------------------------------------+
|    PostgreSQL 16 DB        |   |        Analytics Engine (Pure)         |
|  - users                   |   |  - settings.py   - validation.py       |
|  - uploads                 |   |  - rules.py (R1-R6)                    |
|  - transactions            |   |  - benford.py    - features.py         |
|  - analysis_runs           |   |  - ml.py (Isolation Forest)            |
|  - flagged_transactions    |   |  - scoring.py    - evaluation.py       |
|  - reviews                 |   +----------------------------------------+
|  - audit_logs              |
+----------------------------+
```

### Technology Stack
- **Backend**: FastAPI, Pydantic v2, Uvicorn
- **Database**: PostgreSQL 16, SQLAlchemy 2.x ORM, Alembic migrations
- **Analytics Engine**: Pure Python package using pandas, NumPy, SciPy, scikit-learn
- **Frontend**: Streamlit, Plotly
- **Authentication & Security**: PyJWT, direct bcrypt hashing, rate limiting, formula injection escaping
- **Reporting**: openpyxl (multi-sheet Excel workpapers with formatted numbers)
- **Containerization**: Docker, Docker Compose

---

## 3. How to Run

### Option A: With Docker (Recommended)

Running with Docker starts PostgreSQL, runs database migrations automatically, seeds the initial administrator account, starts the FastAPI backend, and launches the Streamlit frontend.

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd auditlens
   ```

2. **Configure environment**:
   ```bash
   # Linux / macOS / PowerShell
   cp .env.example .env

   # Windows (Command Prompt - cmd.exe)
   copy .env.example .env
   ```
   > [!IMPORTANT]
   > The default admin password in `.env.example` is a placeholder (`change_this_admin_password`). In production (`APP_ENV=production`), the application strictly refuses to start if `JWT_SECRET` is the default placeholder or shorter than 32 characters. Generate a secure random secret (e.g. `openssl rand -hex 32`) and update `SEED_ADMIN_PASSWORD` and `JWT_SECRET` in your `.env` file before deploying.
   >
   > You can also customize allowed frontend domains via `CORS_ORIGINS` (defaults to `http://localhost:8501,http://127.0.0.1:8501`).

3. **Start services**:
   ```bash
   docker compose up --build -d
   ```

4. **Access the application**:
   - **Streamlit Web UI**: [http://localhost:8501](http://localhost:8501)
   - **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **API Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

5. **Log in with seeded credentials**:
   - **Email**: `admin@example.com`
   - **Password**: Value configured in `SEED_ADMIN_PASSWORD` (default: `change_this_admin_password`)

6. **Stop services**:
   ```bash
   docker compose down
   ```

---

### Option B: Without Docker (Local Virtual Environment)

For non-Docker local runs, Streamlit binds to `localhost` by default.

1. **Prerequisites**:
   - Python 3.11+
   - Running PostgreSQL 16 instance

2. **Create and activate a virtual environment**:
   ```bash
   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate

   # Windows (PowerShell)
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   # Note: If script execution is restricted by PowerShell policy, run:
   # Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

   # Windows (Command Prompt - cmd.exe)
   python -m venv .venv
   .venv\Scripts\activate.bat
   ```

3. **Install dependencies**:
   ```bash
   pip install -e .
   ```
   > **Known compatibility note**: Pillow 13 (`pillow>=13.0.0`) is used for security fixes to address known CVEs, although Streamlit declares `pillow<13`. It was thoroughly tested across all pages and charts and works without issues, but is not an officially supported combination by Streamlit's package metadata.

4. **Configure environment**:
   ```bash
   # Linux / macOS / PowerShell
   cp .env.example .env

   # Windows (Command Prompt - cmd.exe)
   copy .env.example .env
   ```
   Edit `.env` to point `DATABASE_URL` to your active PostgreSQL server. If you use Docker only for the database, run:
   ```bash
   docker compose up -d db
   ```
   *(Note: The default `.env` maps the host database port to 5433 via `POSTGRES_PORT=5433` to prevent conflicts with native local PostgreSQL services).*

5. **Run database migrations**:
   ```bash
   alembic upgrade head
   ```

6. **Seed the initial admin account**:
   ```bash
   python scripts/seed_admin.py
   ```

7. **Start the backend API**:
   ```bash
   uvicorn app.main:app --port 8000 --reload
   ```

8. **Start the Streamlit frontend** (in a second terminal):
   ```bash
   streamlit run frontend/app.py --server.port 8501
   ```
   *(Local non-Docker runs bind to `localhost` by default. Binding to `0.0.0.0` is used only inside containerized environments).*

---

## 4. Synthetic Data Generation

AuditLens includes a generator that produces realistic accounting populations with injected anomalies for testing and evaluation:

```bash
python scripts/generate_synthetic_ledger.py --rows 50000 --seed 42 --out-dir data/
```

This generates three files in `data/`:
1. `ledger.csv`: 50,000 transactions containing ~3% injected anomalies across all rule categories and ML outliers.
2. `ledger_clean.csv`: 50,000 transactions with zero injected rule anomalies.
3. `ground_truth.csv`: Relational mapping of `transaction_id`, `anomaly_types`, and `related_transaction_id` for duplicate pairs.

---

## 5. Automated Testing & Verification
 
Run the test suite:
```bash
pytest
```

Run test suite with backend code coverage:
```bash
pytest --cov=app --cov-report=term-missing
```

Run type checking on the analytics engine:
```bash
mypy app/analytics
```

Run code quality and formatting checks:
```bash
ruff check .
ruff format --check .
```

---

## 6. Application Screenshots

### Overview Dashboard
![Dashboard Placeholder](docs/screenshots/dashboard.png)
*Executive risk metrics, exception distribution by rule, and risk rating breakdowns.*

### Flagged Exceptions Review Workbench
![Review Workbench Placeholder](docs/screenshots/review.png)
*Auditor workbench with server-side pagination, rule filters, transaction inspection, and audit dispositions.*

### Benford's Law First-Digit Analysis
![Benford Placeholder](docs/screenshots/benford.png)
*Leading digit distribution comparison, Nigrini conformity ratings, and vendor-level compliance.*

### Excel Workpaper Export
![Excel Report Placeholder](docs/screenshots/excel_report.png)
*Standardized 5-sheet workbook with formatting, audit trail, and formula injection escaping.*

### Model & Rule Evaluation Suite
![Evaluation Placeholder](docs/screenshots/evaluation.png)
*Ground-truth benchmarking displaying strict vs audit-adjusted precision, recall, and anomaly breakdown.*

---

## 7. Known Limitations

1. **Synthetic Data Only**: AuditLens was developed and evaluated against synthetic transaction ledgers adhering to the canonical schema. Real enterprise ledgers have varying chart-of-account formats, custom field names, and missing historical context.
2. **Benford's Law Non-Conformity on Synthetic Data**: Non-conformity to Benford's Law is an investigative indicator, not proof of irregularity or fraud. Certain operational accounts (e.g., standardized contract milestones, fixed service fees, travel allowances) naturally deviate from logarithmic distributions.
3. **Per-Run ML Score Scaling**: Isolation Forest anomaly scores use per-run min-max scaling to [0, 1]. In a completely clean dataset with zero genuine outliers, the statistical tails of normal variance will still result in ~0.66% Low-risk flags.
4. **Weak Supporting Signals (R5 & R6)**: Round amounts (R5) and weekend/after-hours postings (R6) are intentionally assigned 10 risk points each. They do not trigger an audit flag on their own without an accompanying rule trigger or elevated ML score (>= 30 points) to prevent auditor alert fatigue.
5. **In-Memory Rate Limiter**: The SlowAPI rate limiter runs in-memory within a single API process. In multi-worker or multi-container production deployments, an attacker could bypass rate limits across workers without a centralized shared cache (e.g., Redis).
6. **In-Process Background Tasks**: Analysis runs are dispatched via FastAPI's `BackgroundTasks`, executing on the same thread pool and sharing API process memory and CPU. For enterprise scale (millions of rows), runs should be offloaded to an asynchronous distributed task queue (e.g., Celery / ARQ + Redis).
7. **Sign-Off Concurrency**: Manager sign-off inspects flagged item review statuses before recording completion. In a high-concurrency multi-user environment, a race condition could occur if an auditor modifies an item concurrently during sign-off. Production enterprise systems should enforce database-level transaction locking (`SELECT FOR UPDATE`) or an audit freeze state.
8. **Local Deployment Scope**: The architecture is designed for local workstation and containerized evaluation. Multi-tenant SaaS isolation and distributed worker queues (e.g., Celery/Redis) are planned for subsequent iterations.

---

## 8. Future Work

- **Column Mapping UI**: Interactive column-mapping interface to support arbitrary ERP formats (SAP, Oracle NetSuite, Tally, QuickBooks).
- **Public Benchmark Evaluation**: Benchmarking the ML anomaly detection layer on public fraud datasets such as PaySim.
- **Additional Audit Tests**: Vendor master file change detection, sequential check/invoice gap analysis, and vendor bank account matching.
- **Enterprise Cloud Deployment**: Helm charts and Terraform templates for managed Kubernetes/cloud deployment with dedicated task queues.

---

## 9. Security Notice

- All passwords must be stored as bcrypt hashes; never store plain passwords.
- Always change the default admin password (`change_this_admin_password`) and `JWT_SECRET` in `.env`.
- File exports automatically neutralize spreadsheet formula injection (`=`, `+`, `-`, `@` escaped with a leading `'`).
- Ownership guards prevent auditors from viewing or modifying runs belonging to other users.
