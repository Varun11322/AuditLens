"""Feature engineering pipeline for machine learning anomaly detection."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_feature_matrix(
    df: pd.DataFrame,
    has_time_part: bool = True,
    missing_optional_columns: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """Compute ML features per transaction per AUDIT_RULES.md section 5.

    Features:
    1. log_amount = log1p(amount)
    2. hour_of_day (use 12 if no time part exists)
    3. day_of_week (0-6)
    4. is_weekend (0/1)
    5. vendor_amount_robust_z = (amount - vendor median) / (1.4826 * vendor MAD);
       fall back to global values if vendor has < 5 transactions or MAD is 0
    6. vendor_daily_txn_count = number of transactions by same vendor on same date
    7. dept_amount_percentile = percentile rank of amount within department
       (skipped if department column is missing)

    Args:
        df: Clean transaction DataFrame.
        has_time_part: Whether posting_date has meaningful time information.
        missing_optional_columns: Columns absent in raw upload.

    Returns:
        Tuple of (feature_dataframe, feature_names_list).
    """
    n_rows = len(df)
    missing_cols = set(missing_optional_columns or [])
    features = pd.DataFrame(index=df.index)

    if n_rows == 0:
        return features, []

    # 1. log_amount
    features["log_amount"] = np.log1p(df["amount"].values)

    # 2. hour_of_day (fallback to 12 if date-only)
    if has_time_part:
        features["hour_of_day"] = df["posting_date"].dt.hour.values
    else:
        features["hour_of_day"] = np.full(n_rows, 12, dtype=int)

    # 3. day_of_week (0-6)
    dow = df["posting_date"].dt.dayofweek.values
    features["day_of_week"] = dow

    # 4. is_weekend (0/1)
    features["is_weekend"] = (dow >= 5).astype(int)

    # 5. vendor_amount_robust_z
    # Global median and MAD fallback
    amounts = df["amount"].values
    global_median = float(np.median(amounts))
    global_mad = float(np.median(np.abs(amounts - global_median)))

    # Compute per-vendor median and MAD
    vendor_groups = df.groupby("vendor_id")["amount"]
    vendor_counts = vendor_groups.transform("count").values
    vendor_medians = vendor_groups.transform("median").values

    # Vectorized vendor MAD: absolute diff from vendor median, then group median
    abs_diff = np.abs(amounts - vendor_medians)
    df_diff = pd.DataFrame({"vendor_id": df["vendor_id"], "abs_diff": abs_diff}, index=df.index)
    vendor_mads = df_diff.groupby("vendor_id")["abs_diff"].transform("median").values

    # Determine which rows must fall back to global statistics
    use_fallback = (vendor_counts < 5) | (vendor_mads <= 1e-6)

    robust_z = np.zeros(n_rows, dtype=float)

    # Calculate vendor-specific robust z-scores
    normal_mask = ~use_fallback
    if normal_mask.any():
        denom = 1.4826 * vendor_mads[normal_mask]
        robust_z[normal_mask] = (amounts[normal_mask] - vendor_medians[normal_mask]) / denom

    # Calculate fallback robust z-scores using global median and global MAD
    if use_fallback.any():
        if global_mad > 1e-6:
            global_denom = 1.4826 * global_mad
            robust_z[use_fallback] = (amounts[use_fallback] - global_median) / global_denom
        else:
            robust_z[use_fallback] = 0.0

    features["vendor_amount_robust_z"] = robust_z

    # 6. vendor_daily_txn_count
    # Group by vendor and date
    dates = df["posting_date"].dt.date
    df_vd = pd.DataFrame({"vendor_id": df["vendor_id"], "date": dates}, index=df.index)
    daily_counts = df_vd.groupby(["vendor_id", "date"])["vendor_id"].transform("count").values
    features["vendor_daily_txn_count"] = daily_counts

    # 7. dept_amount_percentile (skip if department is missing or empty)
    has_dept = "department" in df.columns and "department" not in missing_cols
    skip_dept = (not has_dept) or (df["department"].astype(str).str.strip() == "").all()
    if not skip_dept:
        dept_rank = df.groupby("department")["amount"].rank(pct=True).values
        features["dept_amount_percentile"] = dept_rank

    feature_names = list(features.columns)
    return features, feature_names
