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

