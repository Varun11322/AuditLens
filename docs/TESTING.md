# Testing

## 1. Testing Goals
Critical functionality:
- Each audit rule (R1-R6) triggers on the right rows and only those
- Benford calculations are correct
- ML layer and scoring are deterministic and bounded
- Authentication, roles, and ownership checks
- Upload validation (good and bad files)
- Review workflow and sign-off rules

## 2. Test Types
### Unit Testing (most important)
Test every rule function with small hand-built DataFrames, including boundary values:
- R4: amount exactly at 90% of limit (flag), exactly at limit (no flag), just under (flag)
- R2: duplicates exactly at the window edge (7 days) vs 8 days
- R5: 9999 (no), 10000 (yes), 10500 (no)
- R6: Saturday, Sunday, 07:59, 08:00, 20:00, date-only input
- R1/R3: case differences, whitespace, empty strings, nulls
- Scoring: cap at 100, level boundaries (29, 30, 49, 50, 69, 70)
- Benford: known distributions (a Benford-conforming sample passes, a uniform-digit sample fails)
- Determinism: same input and seed gives identical output
- Missing optional columns: dependent rules skipped, listed in the summary

### Integration Testing
Test API with httpx + a test PostgreSQL database (or SQLite only if models stay compatible):
- login success/failure, token required, role restrictions, ownership (user B cannot see user A's upload)
- upload valid file, invalid file, oversized file, missing columns
- analyze -> flagged list -> filters -> review update -> sign-off rules
- report export returns a valid xlsx with expected sheets

### End-to-End (manual checklist is acceptable)
Critical journeys:
- Login -> upload synthetic ledger -> run analysis -> dashboard shows data
- Filter flagged items -> mark one False Positive with comment -> reload and confirm saved
- Manager signs off -> export report -> open in Excel

## 3. Testing Tools
Unit and integration: pytest, pytest-cov, httpx (FastAPI TestClient)
Lint: ruff
Types: mypy (analytics package at minimum)

## 4. Test File Structure
tests/
  unit/analytics/   (rules, benford, ml, scoring, features)
  integration/      (auth, uploads, analysis, review, report)
  fixtures/         (tiny CSVs, builders for DataFrames)

## 5. Critical Flow Example
Flow: Analyze and review
Steps:
1. Auditor logs in
2. Uploads synthetic ledger with known anomalies
3. Runs analysis
4. Opens flagged list and filters by High risk
5. Marks an item Reviewed with a comment
Expected result: High-risk items appear first; all injected rule-based anomalies are flagged; the review status and comment persist after reload.

## 6. Coverage
Target: at least 90% on `app/analytics/`, at least 70% overall.
Prioritize: rules, scoring, authentication, authorization, data mutation endpoints.

## 7. Commands
Test: pytest -q
Coverage: pytest --cov=app --cov-report=term-missing
Lint: ruff check . && ruff format --check .
Type Check: mypy app/analytics

## 8. Definition of Done
- [ ] Tests pass
- [ ] Lint passes
- [ ] Type check passes (analytics)
- [ ] Critical flow verified
- [ ] Synthetic-data run: 100% recall for the four strong rule types (duplicate, self-approval, missing approver, just-below-limit); round (R5) and weekend/after-hours (R6) are weak supporting signals worth 10 points each, so they are flagged on their own only when combined with another rule or an ML score; report both rule-fire recall (expected 100%) and flag recall.
- [ ] Clean ledger run produces very few flags
- [ ] No blocking errors
