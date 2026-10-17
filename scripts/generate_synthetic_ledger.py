"""Synthetic ledger data generator for AuditLens.

Generates realistic financial transactions adhering to the canonical schema,
with clean baselines and injected audit anomalies for testing and evaluation.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

CANONICAL_COLUMNS: list[str] = [
    "transaction_id",
    "posting_date",
    "amount",
    "vendor_id",
    "department",
    "account_code",
    "created_by",
    "approved_by",
    "description",
]

ANOMALY_TYPES: list[str] = [
    "duplicate",
    "round",
    "weekend_afterhours",
    "just_below_limit",
    "self_approval",
    "missing_approver",
    "random_outlier",
]

APPROVAL_LIMIT: float = 100000.0
ROUND_MIN_AMOUNT: float = 10000.0
MISSING_APPROVER_MIN_AMOUNT: float = 10000.0

DEPARTMENTS: list[str] = [
    "Finance",
    "Operations",
    "IT",
    "Sales",
    "Marketing",
    "HR",
    "Legal",
    "Procurement",
]

ACCOUNT_DESCRIPTIONS: dict[str, str] = {
    "600100": "Consulting and professional services",
    "600200": "Software licenses and SaaS subscriptions",
    "600300": "Hardware infrastructure and computing equipment",
    "600400": "Office supplies and administrative consumables",
    "600500": "Travel lodging and transportation",
    "600600": "Legal retainer and regulatory advisory",
    "600700": "Facility maintenance utilities and cleaning",
    "600800": "Digital advertising and brand marketing",
}


def _build_vendor_profiles(
    num_vendors: int = 200,
    seed: int = 42,
) -> tuple[list[str], np.ndarray, np.ndarray, list[str], list[str]]:
    """Build synthetic vendor profiles with specific medians, sigmas, and departments.

    Args:
        num_vendors: Number of vendors to generate (default: 200).
        seed: Random seed for deterministic vendor creation.

    Returns:
        Tuple of (vendor_ids, vendor_medians, vendor_sigmas, vendor_depts, vendor_accounts).
    """
    rng = np.random.default_rng(seed)
    vendor_ids = [f"VEND-{i:04d}" for i in range(1, num_vendors + 1)]

    # Median amounts log-uniform between 3,000 and 120,000 INR
    log_min = np.log(3000.0)
    log_max = np.log(120000.0)
    vendor_medians = np.exp(rng.uniform(log_min, log_max, size=num_vendors))
    vendor_sigmas = rng.uniform(0.35, 0.55, size=num_vendors)

    account_keys = list(ACCOUNT_DESCRIPTIONS.keys())
    vendor_depts = [DEPARTMENTS[i % len(DEPARTMENTS)] for i in range(num_vendors)]
    vendor_accounts = [account_keys[i % len(account_keys)] for i in range(num_vendors)]

    return vendor_ids, vendor_medians, vendor_sigmas, vendor_depts, vendor_accounts


def _generate_clean_ledger(
    rows: int,
    seed: int,
    vendor_profiles: tuple[list[str], np.ndarray, np.ndarray, list[str], list[str]],
) -> pd.DataFrame:
    """Generate a clean baseline transaction DataFrame with no injected anomalies.

    Args:
        rows: Number of transactions to generate.
        seed: Random seed.
        vendor_profiles: Output of _build_vendor_profiles.

    Returns:
        DataFrame strictly following canonical schema with clean transactions.
    """
    rng = np.random.default_rng(seed)
    vendor_ids, vendor_medians, vendor_sigmas, vendor_depts, vendor_accounts = vendor_profiles
    num_vendors = len(vendor_ids)

    # 1. Vendor selection
    vendor_indices = rng.integers(0, num_vendors, size=rows)
    v_ids = np.array(vendor_ids)[vendor_indices]
    v_depts = np.array(vendor_depts)[vendor_indices]
    v_accs = np.array(vendor_accounts)[vendor_indices]
    v_meds = vendor_medians[vendor_indices]
    v_sigs = vendor_sigmas[vendor_indices]

    # 2. Amounts: log-normal distribution around vendor medians
    raw_amounts = np.exp(rng.normal(np.log(v_meds), v_sigs))
    # Cap to avoid extreme spontaneous outliers in clean data (max 3.5x vendor median)
    capped_amounts = np.minimum(raw_amounts, v_meds * 3.5)
    # Ensure minimum amount of 100 INR
    amounts = np.maximum(capped_amounts, 100.0)
    amounts = np.round(amounts, 2)

    # Clean invariants:
    # Avoid R4 (just below limit: 90,000 to 100,000)
    in_r4_mask = (amounts >= 90000.0) & (amounts < 100000.0)
    amounts[in_r4_mask] -= 15000.0

    # Avoid R5 (round amounts: exact multiple of 1000 and >= 10000)
    is_round_mask = (amounts >= 10000.0) & (np.mod(np.round(amounts), 1000.0) == 0.0)
    amounts[is_round_mask] += 13.47
    amounts = np.round(amounts, 2)

    # Ensure cents exist on rows to prevent accidental exact multiples
    zero_cents = np.mod(amounts, 1.0) == 0.0
    amounts[zero_cents] += 0.35
    amounts = np.round(amounts, 2)

    # 3. Posting dates: weekday business hours (09:00 - 17:59:59)
    # Base year 2025: start Monday 2025-01-06
    base_monday = pd.Timestamp("2025-01-06 00:00:00")
    weeks = rng.integers(0, 52, size=rows)
    weekdays = rng.integers(0, 5, size=rows)  # 0=Monday to 4=Friday
    seconds_in_day = rng.integers(9 * 3600, 18 * 3600, size=rows)  # 09:00:00 to 17:59:59

    total_seconds = weeks * 7 * 86400 + weekdays * 86400 + seconds_in_day
    posting_dates = base_monday + pd.to_timedelta(total_seconds, unit="s")

    # 4. Creators and Approvers (disjoint sets to guarantee created_by != approved_by)
    creators = [f"USR_CREATOR_{i:02d}" for i in range(1, 21)]
    approvers = [f"USR_APPROVER_{i:02d}" for i in range(1, 11)]

    created_by = np.array(creators)[rng.integers(0, len(creators), size=rows)]
    approved_by = np.array(approvers)[rng.integers(0, len(approvers), size=rows)]

    # 5. Descriptions
    descriptions = [
        f"{ACCOUNT_DESCRIPTIONS[acc]} - Vendor {v_id}"
        for acc, v_id in zip(v_accs, v_ids, strict=False)
    ]

    df_clean = pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i + 1:06d}" for i in range(rows)],
            "posting_date": posting_dates,
            "amount": amounts,
            "vendor_id": v_ids,
            "department": v_depts,
            "account_code": v_accs,
            "created_by": created_by,
            "approved_by": approved_by,
            "description": descriptions,
        }
    )

    # Sort chronologically and reassign transaction_ids
    df_clean = df_clean.sort_values("posting_date").reset_index(drop=True)
    df_clean["transaction_id"] = [f"TXN-{i + 1:06d}" for i in range(rows)]

    # Sanity check: deduplicate identical amounts for the same vendor within 7 days
    df_sorted = df_clean.sort_values(["vendor_id", "amount", "posting_date"]).reset_index()
    same_vendor = df_sorted["vendor_id"] == df_sorted["vendor_id"].shift(1)
    same_amount = df_sorted["amount"] == df_sorted["amount"].shift(1)
    time_diff = (df_sorted["posting_date"] - df_sorted["posting_date"].shift(1)).dt.total_seconds()
    near_dup = same_vendor & same_amount & (time_diff < 7 * 86400)

    if near_dup.any():
        collision_orig_indices = df_sorted.loc[near_dup, "index"].values
        df_clean.loc[collision_orig_indices, "amount"] = np.round(
            df_clean.loc[collision_orig_indices, "amount"] + 0.23, 2
        )

    return df_clean[CANONICAL_COLUMNS]


def _inject_anomalies(
    df: pd.DataFrame,
    seed: int,
    vendor_profiles: tuple[list[str], np.ndarray, np.ndarray, list[str], list[str]],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Inject labelled anomalies into a copy of the clean transactions using vectorized operations.

    Args:
        df: Clean baseline DataFrame.
        seed: Random seed.
        vendor_profiles: Output of _build_vendor_profiles.

    Returns:
        Tuple of (anomalous_ledger_df, ground_truth_df).
    """
    rng = np.random.default_rng(seed)
    ledger_df = df.copy()
    rows = len(ledger_df)
    _, vendor_medians, _, _, _ = vendor_profiles
    vendor_median_map = {f"VEND-{i + 1:04d}": vendor_medians[i] for i in range(len(vendor_medians))}

    # Target approx 3% total anomalies (at least 7 rows so every type can exist)
    total_anomalies = max(7, int(round(rows * 0.03)))
    n_types = len(ANOMALY_TYPES)
    base_count = total_anomalies // n_types

    counts = {atype: base_count for atype in ANOMALY_TYPES}
    remainder = total_anomalies - base_count * n_types
    for atype in ANOMALY_TYPES[:remainder]:
        counts[atype] += 1

    # Select distinct indices for primary anomaly assignments
    selected_indices = rng.choice(rows, size=total_anomalies, replace=False)

    assigned_types: dict[int, list[str]] = {}
    type_slices: dict[str, np.ndarray] = {}
    ptr = 0
    for atype in ANOMALY_TYPES:
        c = counts[atype]
        idx_slice = selected_indices[ptr : ptr + c]
        type_slices[atype] = idx_slice
        for idx in idx_slice:
            assigned_types[int(idx)] = [atype]
        ptr += c

    # Vectorized Injections

    # 1. Duplicate: copy transaction, shift date by 0-5 days
    dup_indices = type_slices["duplicate"]
    n_dup = len(dup_indices)
    clean_pool = np.setdiff1d(np.arange(rows), selected_indices)
    donor_indices = rng.choice(clean_pool, size=n_dup, replace=True)

    donor_sub = ledger_df.iloc[donor_indices]
    ledger_df.loc[dup_indices, "vendor_id"] = donor_sub["vendor_id"].values
    ledger_df.loc[dup_indices, "amount"] = donor_sub["amount"].values
    ledger_df.loc[dup_indices, "department"] = donor_sub["department"].values
    ledger_df.loc[dup_indices, "account_code"] = donor_sub["account_code"].values
    ledger_df.loc[dup_indices, "description"] = (
        "Duplicate payment: " + donor_sub["description"].values
    )

    shift_days = rng.integers(0, 6, size=n_dup)
    shift_mins = rng.integers(-60, 61, size=n_dup)
    dup_dates = (
        donor_sub["posting_date"].values
        + pd.to_timedelta(shift_days, unit="D")
        + pd.to_timedelta(shift_mins, unit="m")
    )
    ledger_df.loc[dup_indices, "posting_date"] = dup_dates

    # Track donor transaction_ids for duplicate payments
    related_txns: dict[int, str] = {}
    for dup_idx, donor_txn in zip(dup_indices, donor_sub["transaction_id"].values, strict=False):
        related_txns[int(dup_idx)] = str(donor_txn)

    # 2. Round amount (multiples of 1000 or 5000 >= 10000)
    round_indices = type_slices["round"]
    round_vals = np.array(
        [10000, 15000, 20000, 25000, 30000, 50000, 75000, 120000, 150000], dtype=float
    )
    ledger_df.loc[round_indices, "amount"] = rng.choice(round_vals, size=len(round_indices))

    # 3. Just below limit (92% to 99.9% of approval limit 100,000)
    just_below_indices = type_slices["just_below_limit"]
    jb_amts = np.round(rng.uniform(92000.0, 99900.0, size=len(just_below_indices)), 2)
    # Ensure not round
    jb_amts[jb_amts % 1000.0 == 0.0] += 45.50
    ledger_df.loc[just_below_indices, "amount"] = np.round(jb_amts, 2)

    # 4. Random outlier (20x to 100x vendor median)
    outlier_indices = type_slices["random_outlier"]
    outlier_vids = ledger_df.loc[outlier_indices, "vendor_id"].values
    outlier_vmeds = np.array([vendor_median_map[vid] for vid in outlier_vids])
    multipliers = rng.uniform(20.0, 100.0, size=len(outlier_indices))
    outlier_amts = np.round(outlier_vmeds * multipliers, 2)
    outlier_amts[outlier_amts % 1000.0 == 0.0] += 37.19
    in_band = (outlier_amts >= 90000.0) & (outlier_amts < 100000.0)
    outlier_amts[in_band] += 25000.0
    ledger_df.loc[outlier_indices, "amount"] = np.round(outlier_amts, 2)

    # 5. Weekend / after-hours
    wkah_indices = type_slices["weekend_afterhours"]
    n_wkah = len(wkah_indices)
    half = n_wkah // 2
    sunday_indices = wkah_indices[:half]
    afterhours_indices = wkah_indices[half:]

    if len(sunday_indices) > 0:
        s_dates = ledger_df.loc[sunday_indices, "posting_date"]
        days_to_sunday = (6 - s_dates.dt.dayofweek) % 7
        days_to_sunday = np.where(days_to_sunday == 0, 7, days_to_sunday)
        ledger_df.loc[sunday_indices, "posting_date"] = s_dates + pd.to_timedelta(
            days_to_sunday, unit="D"
        )

    if len(afterhours_indices) > 0:
        ah_dates = ledger_df.loc[afterhours_indices, "posting_date"]
        ah_hours = rng.integers(2, 5, size=len(afterhours_indices))
        ah_mins = rng.integers(0, 60, size=len(afterhours_indices))
        ah_secs = rng.integers(0, 60, size=len(afterhours_indices))
        ledger_df.loc[afterhours_indices, "posting_date"] = (
            ah_dates.dt.floor("D")
            + pd.to_timedelta(ah_hours, unit="h")
            + pd.to_timedelta(ah_mins, unit="m")
            + pd.to_timedelta(ah_secs, unit="s")
        )

    # 6. Self-approval: created_by == approved_by
    self_indices = type_slices["self_approval"]
    ledger_df.loc[self_indices, "approved_by"] = ledger_df.loc[self_indices, "created_by"].values

    # 7. Missing approver on large amounts (>= 10,000)
    missing_indices = type_slices["missing_approver"]
    under_min = ledger_df.loc[missing_indices, "amount"] < MISSING_APPROVER_MIN_AMOUNT
    if under_min.any():
        fix_indices = missing_indices[under_min]
        ledger_df.loc[fix_indices, "amount"] = np.round(
            rng.uniform(15000.0, 75000.0, size=len(fix_indices)), 2
        )
    ledger_df.loc[missing_indices, "approved_by"] = ""

    # Add secondary anomalies to ~5% of anomaly rows to test multi-anomaly labels
    n_multi = max(1, total_anomalies // 20) if total_anomalies >= 20 else 0
    if n_multi > 0:
        multi_indices = rng.choice(selected_indices, size=n_multi, replace=False)
        for idx in multi_indices:
            current = assigned_types[int(idx)][0]
            if current in ("round", "just_below_limit", "random_outlier"):
                compat = ["weekend_afterhours", "self_approval"]
            elif current in ("weekend_afterhours", "self_approval"):
                compat = ["round", "just_below_limit"]
            else:
                compat = ["weekend_afterhours"]
            secondary = str(rng.choice(compat))
            if secondary not in assigned_types[int(idx)]:
                assigned_types[int(idx)].append(secondary)
                if secondary == "self_approval":
                    ledger_df.at[idx, "approved_by"] = ledger_df.at[idx, "created_by"]
                elif secondary == "weekend_afterhours":
                    d = ledger_df.at[idx, "posting_date"]
                    ledger_df.at[idx, "posting_date"] = d.replace(hour=3, minute=15, second=0)
                elif secondary == "round":
                    ledger_df.at[idx, "amount"] = 50000.0
                elif secondary == "just_below_limit":
                    ledger_df.at[idx, "amount"] = 96500.0

    # Build ground truth DataFrame
    ground_truth_records = []
    for idx in sorted(assigned_types.keys()):
        txn_id = ledger_df.at[idx, "transaction_id"]
        type_str = "|".join(assigned_types[idx])
        related_id = related_txns.get(idx, "")
        ground_truth_records.append(
            {
                "transaction_id": txn_id,
                "anomaly_types": type_str,
                "related_transaction_id": related_id,
            }
        )

    df_ground_truth = pd.DataFrame(ground_truth_records)
    return ledger_df[CANONICAL_COLUMNS], df_ground_truth


def generate_synthetic_data(
    rows: int = 50000,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generate synthetic financial transaction datasets for AuditLens.

    Args:
        rows: Number of transactions to generate (default: 50,000).
        seed: Random seed for reproducibility (default: 42).

    Returns:
        Tuple of (ledger_df, ground_truth_df, ledger_clean_df).
    """
    logger.info("Generating synthetic data: rows=%d, seed=%d", rows, seed)
    vendor_profiles = _build_vendor_profiles(num_vendors=200, seed=seed)
    df_clean = _generate_clean_ledger(rows=rows, seed=seed, vendor_profiles=vendor_profiles)
    df_ledger, df_ground_truth = _inject_anomalies(
        df_clean, seed=seed, vendor_profiles=vendor_profiles
    )
    logger.info(
        "Data generation completed. Anomalous rows: %d (%.2f%%)",
        len(df_ground_truth),
        (len(df_ground_truth) / rows) * 100.0,
    )
    return df_ledger, df_ground_truth, df_clean


def save_datasets(
    df_ledger: pd.DataFrame,
    df_ground_truth: pd.DataFrame,
    df_clean: pd.DataFrame,
    out_dir: Path | str,
) -> tuple[Path, Path, Path]:
    """Write generated DataFrames to CSV files.

    Args:
        df_ledger: Ledger with injected anomalies.
        df_ground_truth: Ground truth anomaly labels.
        df_clean: Clean baseline ledger without anomalies.
        out_dir: Target output directory.

    Returns:
        Tuple of (ledger_path, ground_truth_path, ledger_clean_path).
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    ledger_path = out_path / "ledger.csv"
    ground_truth_path = out_path / "ground_truth.csv"
    ledger_clean_path = out_path / "ledger_clean.csv"

    logger.info("Saving datasets to %s", out_path.resolve())

    df_ledger.to_csv(
        ledger_path,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
        float_format="%.2f",
    )
    df_ground_truth.to_csv(ground_truth_path, index=False)
    df_clean.to_csv(
        ledger_clean_path,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
        float_format="%.2f",
    )

    logger.info(
        "Files saved successfully: ledger (%s), ground_truth (%s), ledger_clean (%s)",
        ledger_path.name,
        ground_truth_path.name,
        ledger_clean_path.name,
    )
    return ledger_path, ground_truth_path, ledger_clean_path


def main() -> None:
    """CLI entry point for synthetic ledger generation."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic financial ledger datasets for AuditLens."
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=50000,
        help="Number of transactions to generate (default: 50000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default="data",
        help="Output directory for generated CSV files (default: data)",
    )

    args = parser.parse_args()
    df_ledger, df_ground_truth, df_clean = generate_synthetic_data(
        rows=args.rows,
        seed=args.seed,
    )
    save_datasets(df_ledger, df_ground_truth, df_clean, out_dir=args.out_dir)


if __name__ == "__main__":
    main()
