# UX Flows

Screens (Streamlit pages): Login, Upload, Dashboard, Review, Benford, Reports, (Evaluation).
Overall journey: Login -> Upload -> Run Analysis -> Dashboard -> Review flagged items -> Sign off (manager) -> Export report.

## Flow 1 - Login
1. User opens the app and sees the login form
2. Enters email and password, clicks Login
3. Frontend calls POST /auth/login
4. Token and user info are stored in session state
5. User lands on the Upload page (or the last run's Dashboard)
Success: sidebar shows name and role.
Failure: "Invalid email or password" shown; password field cleared; no hint about which one was wrong.
Session expiry: any 401 clears the session and returns to Login with a message.

## Flow 2 - Upload a file
1. User opens Upload
2. Optionally downloads the CSV template
3. Selects a .csv or .xlsx file and clicks Upload
4. Spinner shown; API validates and stores
5. A validation summary is shown: rows total / accepted / rejected, reasons for rejection, optional columns missing and which rules will be skipped because of that
6. A "Run Analysis" button appears with an Advanced settings expander (thresholds, defaults prefilled)
Loading State: spinner "Validating file...".
Error State: missing required columns listed by name; wrong file type message; too-large message.
Empty State: "No uploads yet. Upload a transaction file to begin." plus the list of previous uploads when they exist.

## Flow 3 - Run analysis
1. User clicks Run Analysis (optionally after changing thresholds)
2. Frontend calls POST /uploads/{id}/analyze and receives a run_id
3. A progress/status indicator polls GET /runs/{id} every 2 seconds
4. On completed: success message and a link to the Dashboard
Loading State: "Analysis running..." with the button disabled.
Error State: if the run failed, show the safe error message and a Retry button.
Warnings: show warnings from the run summary (e.g. ML skipped due to few rows, rules skipped due to missing columns).

## Flow 4 - Dashboard
1. User selects an upload and a completed run
2. Metrics row: total transactions, flagged count, High / Medium / Low counts, total flagged amount
3. Charts: risk distribution, flagged by rule, flagged over time, top vendors by flagged amount
4. Benford summary card (conformity label) with a link to the Benford page
5. A button "Review flagged transactions"
Empty State: "No transactions were flagged for this run" with the thresholds used.
Loading State: skeleton/spinner while fetching.

## Flow 5 - Review flagged transactions
1. User opens Review for a run
2. Filters (risk level, rule, vendor, department, status, date range, amount range) above a paginated table sorted by risk score
3. User clicks a row to open the detail panel: all transaction fields, score breakdown (rule points + ML points), plain-English reasons, duplicate group members, review history
4. User chooses a status and writes a comment (required for False Positive), then clicks Save
5. Table row updates; a progress indicator shows "x of y reviewed"
Success: "Review saved".
Failure: field-level error message (e.g. "A comment is required for False Positive").
Locked State: if the run is signed off, controls are disabled with the message "This run has been signed off".

## Flow 6 - Manager sign-off
1. Manager opens a run's Review page; sees review progress
2. The Sign Off button is enabled only when no items are Open
3. Clicking it asks for confirmation, then calls POST /runs/{id}/sign-off
4. The page shows "Signed off by <name> on <date>" and locks reviewing
Failure: 409 message "n items are still open".

## Flow 7 - Export report
1. User opens Reports (or clicks Export on the Dashboard)
2. Clicks Download Excel report
3. API generates the file; browser downloads it
Empty State: even with zero flagged items a valid report downloads, stating that nothing was flagged.

## Flow 8 - Delete an upload
1. User clicks Delete on an upload
2. A confirmation dialog explains that all related runs and reviews are deleted
3. On confirm: DELETE /uploads/{id}; list refreshes
