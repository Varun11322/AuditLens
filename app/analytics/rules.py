"""Vectorized audit rules R1 through R6 for financial transaction analysis."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.settings import Settings

logger = logging.getLogger(__name__)

RULE_POINTS: dict[str, int] = {
    "R1": 40,
    "R2": 30,
    "R3": 30,
    "R4": 25,
    "R5": 10,
    "R6": 10,
}


def evaluate_rules(
    df: pd.DataFrame,
    settings: Settings,
    missing_optional_columns: list[str] | None = None,
    has_time_part: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Evaluate audit rules R1-R6 on a clean transaction DataFrame in a vectorized manner.

    Follows thresholds and logic defined in AUDIT_RULES.md section 3 and fallback behavior.

    Args:
        df: Clean DataFrame satisfying canonical schema.
        settings: Analysis settings and thresholds.
        missing_optional_columns: Optional columns that were absent in raw upload.
        has_time_part: True if posting_date has time components, False if date-only.

    Returns:
        Tuple of (results_df, rules_summary).
    """
    n_rows = len(df)
    results = pd.DataFrame(index=df.index)
    skipped_rules: dict[str, str] = {}
    missing_cols = set(missing_optional_columns or [])

    # Pre-allocate rule flags
    r1_flags = np.zeros(n_rows, dtype=bool)
    r2_flags = np.zeros(n_rows, dtype=bool)
    r3_flags = np.zeros(n_rows, dtype=bool)
    r4_flags = np.zeros(n_rows, dtype=bool)
    r5_flags = np.zeros(n_rows, dtype=bool)
    r6_flags = np.zeros(n_rows, dtype=bool)

    dup_group_ids = np.array([""] * n_rows, dtype=object)

    if n_rows == 0:
        results["rule_points"] = np.array([], dtype=int)
        results["triggered_rule_codes"] = [[] for _ in range(0)]
        results["rule_reasons"] = [[] for _ in range(0)]
        results["duplicate_group_id"] = np.array([], dtype=str)
        return results, {"skipped_rules": skipped_rules, "counts_per_rule": {}}

    # --- Rule R1: Self-approval ---
    # created_by equals approved_by (case-insensitive, trimmed, both non-empty)
    if "created_by" in missing_cols or "approved_by" in missing_cols:
        skipped_rules["R1"] = "Missing created_by or approved_by column"
    else:
        created = df["created_by"].astype(str).str.strip().str.upper()
        approved = df["approved_by"].astype(str).str.strip().str.upper()
        both_non_empty = (
            (created != "") & (approved != "") & (created != "NAN") & (approved != "NAN")
        )
        r1_flags = both_non_empty & (created == approved)

    # --- Rule R2: Duplicate payment ---
    # Same vendor_id and same amount within duplicate_window_days.
    # All members of the group are flagged and share a duplicate_group_id.
    window_sec = settings.duplicate_window_days * 86400
    sorted_idx = df.sort_values(["vendor_id", "amount", "posting_date"]).index
    v_sorted = df.loc[sorted_idx, "vendor_id"].values
    a_sorted = df.loc[sorted_idx, "amount"].values
    d_sorted = df.loc[sorted_idx, "posting_date"].values

    # Check forward time difference within same vendor & amount
    diff_forward = (d_sorted[1:] - d_sorted[:-1]).astype("timedelta64[s]").astype(float)
    same_va_forward = (v_sorted[:-1] == v_sorted[1:]) & (a_sorted[:-1] == a_sorted[1:])
    close_forward = same_va_forward & (diff_forward <= window_sec) & (diff_forward >= 0)

    # An item is in a duplicate group if it is close to the next item or previous item
    in_dup_sorted = np.zeros(n_rows, dtype=bool)
    in_dup_sorted[:-1] |= close_forward
    in_dup_sorted[1:] |= close_forward

    # Assign duplicate group IDs to contiguous clusters of close duplicate transactions
    # A new group begins whenever vendor changes, amount changes, or time gap exceeds window
    if in_dup_sorted.any():
        is_break = np.ones(n_rows, dtype=bool)
        is_break[1:] = (~same_va_forward) | (diff_forward > window_sec)
        cluster_ids = np.cumsum(is_break)

        # Count sizes of each cluster to ensure only clusters of size >= 2 receive group IDs
        unique_clusters, cluster_counts = np.unique(cluster_ids, return_counts=True)
        dup_clusters = set(unique_clusters[cluster_counts >= 2])

        dup_group_tags = np.array([""] * n_rows, dtype=object)
        for i, c_id in enumerate(cluster_ids):
            if in_dup_sorted[i] and c_id in dup_clusters:
                dup_group_tags[i] = f"DUP-{c_id:06d}"

        # Map back to original indices
        r2_flags[sorted_idx] = in_dup_sorted & (dup_group_tags != "")
        dup_group_ids[sorted_idx] = dup_group_tags

    # --- Rule R3: Missing approver ---
    # approved_by empty and amount >= missing_approver_min_amount
    if "approved_by" in missing_cols:
        skipped_rules["R3"] = "Missing approved_by column"
    else:
        appr_raw = df["approved_by"].astype(str).str.strip().str.upper()
        is_empty = (appr_raw == "") | (appr_raw == "NAN") | df["approved_by"].isna()
        r3_flags = is_empty & (df["amount"] >= settings.missing_approver_min_amount)

    # --- Rule R4: Just below approval limit ---
    # approval_limit * just_below_band <= amount < approval_limit
    lower_bound = settings.approval_limit * settings.just_below_band
    r4_flags = (df["amount"] >= lower_bound) & (df["amount"] < settings.approval_limit)

    # --- Rule R5: Round amount ---
    # amount >= round_min_amount and amount is an exact multiple of round_multiple
    is_sufficient_amt = df["amount"] >= settings.round_min_amount
    amt_mod = np.mod(df["amount"], settings.round_multiple)
    is_exact_round = np.isclose(amt_mod, 0.0, atol=1e-3) | np.isclose(
        amt_mod, settings.round_multiple, atol=1e-3
    )
    r5_flags = is_sufficient_amt & is_exact_round

    # --- Rule R6: Weekend / after-hours posting ---
    # Posting on weekend day, or outside business hours (hour check only if time exists)
    is_weekend = df["posting_date"].dt.dayofweek.isin(settings.weekend_days)
    if has_time_part:
        hour = df["posting_date"].dt.hour
        is_after_hours = (hour < settings.business_hours_start) | (
            hour >= settings.business_hours_end
        )
        r6_flags = is_weekend | is_after_hours
    else:
        r6_flags = is_weekend
        skipped_rules["R6_hour_check"] = "Date-only posting_date (hour check skipped)"

    # Compute rule points and compile triggered rule lists
    rule_pts = (
        r1_flags.astype(int) * RULE_POINTS["R1"]
        + r2_flags.astype(int) * RULE_POINTS["R2"]
        + r3_flags.astype(int) * RULE_POINTS["R3"]
        + r4_flags.astype(int) * RULE_POINTS["R4"]
        + r5_flags.astype(int) * RULE_POINTS["R5"]
        + r6_flags.astype(int) * RULE_POINTS["R6"]
    )
    # Cap total rule points at 100 per AUDIT_RULES.md
    total_rule_points = np.minimum(100, rule_pts)

    # Assemble plain-English reasons and triggered codes per row
    triggered_codes: list[list[str]] = []
    reasons: list[list[str]] = []

    for i in range(n_rows):
        row_codes: list[str] = []
        row_reasons: list[str] = []

        if r1_flags[i]:
            row_codes.append("R1")
            row_reasons.append("Posted and approved by the same user (R1, +40)")
        if r2_flags[i]:
            row_codes.append("R2")
            row_reasons.append(
                f"Duplicate payment posted within {settings.duplicate_window_days} days (R2, +30)"
            )
        if r3_flags[i]:
            row_codes.append("R3")
            min_appr = settings.missing_approver_min_amount
            row_reasons.append(
                f"Missing approver on transaction amount >= {min_appr:,.0f} (R3, +30)"
            )
        if r4_flags[i]:
            row_codes.append("R4")
            row_reasons.append(
                f"Amount just below approval limit of {settings.approval_limit:,.0f} (R4, +25)"
            )
        if r5_flags[i]:
            row_codes.append("R5")
            r_min = settings.round_min_amount
            r_mult = settings.round_multiple
            row_reasons.append(
                f"Round transaction amount >= {r_min:,.0f} multiple of {r_mult:,.0f} (R5, +10)"
            )
        if r6_flags[i]:
            row_codes.append("R6")
            row_reasons.append("Posted on a weekend or outside business hours (R6, +10)")

        triggered_codes.append(row_codes)
        reasons.append(row_reasons)

    results["rule_points"] = total_rule_points
    results["triggered_rule_codes"] = triggered_codes
    results["rule_reasons"] = reasons
    results["duplicate_group_id"] = dup_group_ids

    summary: dict[str, Any] = {
        "skipped_rules": skipped_rules,
        "counts_per_rule": {
            "R1": int(r1_flags.sum()),
            "R2": int(r2_flags.sum()),
            "R3": int(r3_flags.sum()),
            "R4": int(r4_flags.sum()),
            "R5": int(r5_flags.sum()),
            "R6": int(r6_flags.sum()),
        },
        "total_rule_flags": int((total_rule_points > 0).sum()),
    }

    return results, summary
