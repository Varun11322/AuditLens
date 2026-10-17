# Audit Rules and Analytics Specification

This is the most important technical document. The analytics engine must implement exactly what is written here.
If something is unclear, ask. Do not invent thresholds or formulas.

## 1. Canonical Input Schema
| Column | Required | Type | Notes |
|---|---|---|---|
| transaction_id | Yes | string | Unique per upload |
| posting_date | Yes | datetime | Date or date+time. Hour-based rules need the time part |
| amount | Yes | number > 0 | Currency INR |
| vendor_id | Yes | string | Vendor / counterparty |
| department | No | string | |
| account_code | No | string | |
| created_by | No | string | User who posted the entry |
| approved_by | No | string | User who approved the entry |
| description | No | string | |

Rules that need a missing optional column are skipped. The run summary must list which rules were skipped and why.
Rows with invalid amount, date, or duplicate transaction_id are rejected and counted in the validation summary.

### Fallback Behavior
- **Missing `created_by` or `approved_by`**: Skip R1 and R3, and list the skipped rules in the run summary.
- **Date-only `posting_date` (no time)**: Skip the hour check in R6 (weekend check still runs), and use `hour_of_day = 12` as the ML feature.
- **Vendor with fewer than 5 transactions, or MAD = 0**: Fall back to global median and MAD for `vendor_amount_robust_z`.
- **Missing `department`**: Skip the `dept_amount_percentile` feature.

## 2. Default Settings (all overridable per run)
| Setting | Default |
|---|---|
| approval_limit | 100000 |
| just_below_band | 0.90 (flag amounts from 90% of the limit up to, but not including, the limit) |
| duplicate_window_days | 7 |
| round_multiple | 1000 |
| round_min_amount | 10000 |
| business_hours | 08:00 to 20:00 |
| weekend_days | Saturday, Sunday |
| missing_approver_min_amount | 10000 |
| ml_contamination | 0.02 |
| ml_min_rows | 50 |
| flag_threshold | 30 |
| random_seed | 42 |

## 3. Rule-Based Tests
Each rule has a code, a plain-English explanation (shown to the auditor), and points.

| Code | Name | Condition | Points |
|---|---|---|---|
| R1 | Self-approval | created_by equals approved_by (case-insensitive, trimmed, both non-empty) | 40 |
| R2 | Duplicate payment | Same vendor_id and same amount, posted within duplicate_window_days of another transaction. All members of the group are flagged and share a duplicate_group_id | 30 |
| R3 | Missing approver | approved_by empty and amount >= missing_approver_min_amount | 30 |
| R4 | Just below approval limit | approval_limit * just_below_band <= amount < approval_limit | 25 |
| R5 | Round amount | amount >= round_min_amount and amount is an exact multiple of round_multiple | 10 |
| R6 | Weekend / after-hours posting | posting on a weekend day, or time outside business_hours (hour check only if a time part exists) | 10 |

Rule points add up for a transaction. Cap total rule points at 100.

## 4. Benford's Law Test (informational, does not add points)
- Applies to positive amounts. Compare the first-digit distribution to the expected: P(d) = log10(1 + 1/d), d = 1..9.
- Run on the whole upload when it has at least 1000 rows, and per vendor when the vendor has at least 300 transactions. Otherwise show "insufficient data".
- Output: observed and expected frequency for each digit, chi-square statistic and p-value, and MAD (mean absolute deviation).
- MAD conformity labels (Nigrini): <= 0.006 Close conformity; <= 0.012 Acceptable; <= 0.015 Marginal; above 0.015 Non-conformity.
- Vendors with Non-conformity are listed in the dashboard as "worth a closer look". They do not change transaction scores.
- Note in UI: non-conformity is a signal for investigation, not proof of fraud.

## 5. ML Anomaly Detection
Model: scikit-learn IsolationForest(n_estimators=200, contamination=ml_contamination, random_state=random_seed).
Skip the ML layer if rows < ml_min_rows (show a warning; ml_points = 0).

Features (computed per transaction):
1. log_amount = log1p(amount)
2. hour_of_day (use 12 if no time part)
3. day_of_week (0-6)
4. is_weekend (0/1)
5. vendor_amount_robust_z = (amount - vendor median) / (1.4826 * vendor MAD); fall back to global values if the vendor has fewer than 5 transactions or MAD is 0
6. vendor_daily_txn_count = number of transactions by the same vendor on the same date
7. dept_amount_percentile = percentile rank of amount within department (skip the feature if no department column)

Score: ml_raw = -model.score_samples(X) (higher means more unusual). ml_norm = min-max scaling of ml_raw to [0, 1] over the run. ml_points = round(ml_norm * 40).

## 6. Combined Risk Score
```
risk_score = min(100, rule_points + ml_points)
```
| Level | Range |
|---|---|
| High | 70 - 100 |
| Medium | 50 - 69 |
| Low | flag_threshold (30) - 49 |
| Not flagged | below flag_threshold |

A transaction is flagged when risk_score >= flag_threshold.
For each flagged transaction store: risk_score, risk_level, rule_points, ml_points, ml_norm, triggered_rule_codes, and a plain-English reasons list.
Example reason: "Posted and approved by the same user (R1, +40)".

## 7. Determinism and Performance
- Same input and same settings must give identical results (fixed seed, stable sort).
- 50,000 rows must complete in under 60 seconds on a laptop. Use vectorized pandas operations, no row-by-row loops.

## 8. Synthetic Data Generator Spec
Script: `scripts/generate_synthetic_ledger.py`. Arguments: --rows (default 50000), --seed (default 42), --out-dir.
- Normal data: about 200 vendors; log-normal amounts with vendor-specific medians; mostly weekday business-hour postings; created_by and approved_by from different users; approved_by present for amounts >= 10000.
- Inject anomalies (about 3% of rows total) and record each in ground_truth.csv (transaction_id, anomaly_types separated by "|"):
  - duplicate (copy a transaction, shift the date by 0-5 days)
  - round (set amount to multiples of 1000 or 5000)
  - weekend_afterhours (move the posting to Sunday or 2-4 AM)
  - just_below_limit (amount between 92% and 99.9% of the approval limit)
  - self_approval (created_by = approved_by)
  - missing_approver (blank approved_by on a large amount)
  - random_outlier (amount 20x to 100x the vendor median, normal in other respects, to test the ML layer)
- Also write a clean `ledger_clean.csv` without anomalies as a sanity check (expect very few flags).

## 9. Evaluation (should have)
When ground_truth is available: precision = flagged and truly anomalous / flagged; recall = flagged and truly anomalous / truly anomalous; also recall per anomaly type. Display these and mention that real data would have far noisier labels.

Note on rule recall vs. flag recall: 100% recall is expected for the four strong rule types (duplicate, self-approval, missing approver, just-below-limit). Round amount (R5) and weekend/after-hours (R6) are weak supporting signals worth 10 points each; they are flagged on their own only when combined with another rule or an elevated ML score (reaching the flag threshold of 30). Reports should distinguish rule-fire recall (expected 100%) from flag recall.
