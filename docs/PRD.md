# Product Requirements Document

## 1. Product Overview
Product Name: AuditLens
One-Line Description: A web app that scans financial transactions with audit rules and ML, scores their risk, and manages the auditor's review of flagged items.
Product Type: Internal tool / data analytics application (portfolio project)
Primary Platform: Web (Streamlit UI + FastAPI backend)

## 2. Problem
What problem are we solving? Auditors cannot manually inspect every transaction. Sampling can miss duplicate payments, split invoices, self-approved entries, and unusual postings.
Why does this matter? Undetected errors or fraud lead to misstated financials and control failures.
How do users solve this today? Manual sampling in Excel, ad hoc filters and pivot tables, and expensive proprietary tools.

## 3. Goal
Primary Goal: Let an auditor upload a ledger and within minutes see every high-risk transaction, with the reasons it was flagged.
Secondary Goals:
- Make every flag explainable (which rule fired, or that the ML model found it unusual).
- Support a review workflow that mirrors real audit practice.
- Produce an exceptions report an auditor could hand to a client.

## 4. Target Users
### User Type 1 - Auditor
Description: Audit/analytics associate who tests client data.
Needs: fast upload, clear risk ranking, ability to filter and document review decisions.
Pain Points: too many transactions, too many false positives, no audit trail of decisions.
### User Type 2 - Manager
Description: Senior who oversees engagements.
Needs: see all uploads and results, confirm reviews are complete, sign off.
Pain Points: no visibility into what has been reviewed and why.

## 5. User Stories
- As an auditor, I want to upload a transaction file so that the whole population is tested.
- As an auditor, I want each flagged transaction to show its risk score and triggered rules so that I know why to look at it.
- As an auditor, I want to filter flagged items by risk level, vendor, department, and date so that I can prioritize.
- As an auditor, I want to mark an item Reviewed / False Positive / Needs Follow-up and add a comment so that my decision is documented.
- As an auditor, I want to export an Excel exceptions report so that I can share findings.
- As a manager, I want to see all uploads and review progress and sign off so that nothing is left unreviewed.
- As a user, I want to log in securely so that financial data is protected.

## 6. Core Features

### Feature 1 - Authentication and Roles
Purpose: Restrict access; separate auditor and manager abilities.
Inputs: email, password.
Outputs: JWT access token; role-based access.
Acceptance Criteria:
- Login with email and password returns a token; wrong credentials return 401.
- Auditors see only their own uploads; managers see all.
- Only managers can sign off.
Edge Cases: expired token; disabled user; role changed mid-session.

### Feature 2 - File Upload and Validation
Purpose: Ingest the transaction population.
Inputs: CSV or XLSX following the canonical schema (see AUDIT_RULES.md section 1).
Outputs: upload record, validation summary (rows accepted/rejected, reasons).
Acceptance Criteria:
- Accepts .csv and .xlsx up to the configured max size.
- Required columns are checked; missing columns return a clear error listing them.
- Rows with invalid amount/date are rejected and counted, not silently dropped.
- A downloadable template file is available.
Edge Cases: empty file; duplicate transaction_id values; negative amounts; mixed date formats; extra unknown columns (ignored).

### Feature 3 - Analysis Run
Purpose: Execute audit rules, Benford test, and ML model; produce risk scores.
Inputs: upload id, optional threshold overrides.
Outputs: analysis run record, risk score and level per transaction, flagged list, summary stats.
Acceptance Criteria:
- All rules in AUDIT_RULES.md are implemented exactly as specified.
- Each flagged transaction stores its score, level, triggered rule codes, and ML anomaly score.
- Re-running with the same data and the same settings gives identical results (fixed random seed).
- Run status is visible: pending / running / completed / failed.
Edge Cases: dataset with fewer than 50 rows (ML skipped, warning shown); missing optional columns (dependent rules skipped, listed in the run summary); all transactions flagged.

### Feature 4 - Dashboard
Purpose: Give an immediate picture of the risk.
Acceptance Criteria:
- Shows total transactions, total flagged, count by risk level, total amount flagged.
- Charts: risk-level distribution, flagged count by rule, flagged over time, top vendors by flagged amount.
- Benford's Law chart (expected vs actual first-digit frequency) with conformity result.
Edge Cases: no flagged items (show empty state), very large datasets (paginate, do not render everything).

### Feature 5 - Flagged Transactions Review
Purpose: Let auditors investigate and document.
Acceptance Criteria:
- Table with sort and filters: risk level, rule, vendor, department, date range, review status, amount range.
- Detail view shows all fields, risk score breakdown (rule points + ML points), and triggered rules in plain English.
- Auditor sets status (Open, Reviewed, False Positive, Needs Follow-up) and comment; each change is saved with user and timestamp.
- Manager can set Signed Off only when no item in the run is Open.
Edge Cases: two users editing the same item (last write wins, history kept); empty comment on False Positive (comment required).

### Feature 6 - Exceptions Report Export
Purpose: Produce a shareable deliverable.
Acceptance Criteria:
- Excel file with sheets: Summary, Flagged Transactions, Rule Counts, Benford, Review Log.
- Includes run settings (thresholds) and run date for traceability.
Edge Cases: zero flagged items still produces a valid file.

### Feature 7 - Synthetic Data Generator (developer tool)
Purpose: Provide realistic test data with known ground truth.
Acceptance Criteria:
- Script generates N transactions (default 50,000) following the canonical schema.
- Injects labeled anomalies of each type (duplicate, round, weekend/after-hours, just-below-limit, self-approval, missing approver, plus a few random outliers).
- Writes `ledger.csv` and a separate `ground_truth.csv` (transaction_id, anomaly_types).
- Seeded for reproducibility.

### Feature 8 - Evaluation Page (should have)
Purpose: Show how well the system detects injected anomalies.
Acceptance Criteria: if a ground_truth file is uploaded for a run, show precision, recall, and per-anomaly-type recall.

## 7. Non-Goals
- Real-time ingestion, multi-organization tenancy, payments, email alerts.
- Custom column mapping UI, deep-learning models, React frontend.
- Claiming that flagged items are fraud: the tool flags items for human review only.

## 8. MVP Scope
Must Have: Features 1-7.
Nice to Have: Feature 8, threshold overrides in the UI, Docker deployment with live link.
Future: column mapping UI, additional rules (vendor master checks, sequence gaps), scheduled runs, SHAP-style explanations for ML flags.

## 9. Success Metrics
Primary: on synthetic data, 100% recall for the four strong rule types (duplicate, self-approval, missing approver, just-below-limit); round (R5) and weekend/after-hours (R6) are weak supporting signals worth 10 points each, so they are flagged on their own only when combined with another rule or an ML score; report both rule-fire recall (expected 100%) and flag recall. ML layer catches a majority of injected random outliers with a reasonable false-positive rate (report the numbers).
Secondary: analysis of 50,000 rows completes in under 60 seconds on a laptop; dashboard loads in under 5 seconds.

## 10. Constraints
Technical: Python stack as defined in ARCHITECTURE.md; runs locally with docker-compose.
Business: portfolio project, no real client data - synthetic or public data only. Local-only demo with Docker; live hosting is optional and decided later.
Design: simple and clean; analytics quality over visual polish.
Timeline: [today it self now i want to make project]

## 11. Assumptions
- Currency is INR; amounts are positive numbers.
- Uploaded files follow the canonical schema; no custom mapping.
- One organization, a small number of users.

## 12. Open Questions
- Hosting: local only with docker-compose for now
- Data: synthetic data only for the MVP; PaySim is an optional extra after the MVP works

## 13. Definition of Done
The product is complete when:
- [ ] All Must Have features work end to end
- [ ] Analytics engine unit tests pass
- [ ] API integration tests pass
- [ ] Lint and build succeed
- [ ] Security requirements are satisfied
- [ ] README has setup steps, architecture diagram, and screenshots
- [ ] Documentation matches the implemented behavior
