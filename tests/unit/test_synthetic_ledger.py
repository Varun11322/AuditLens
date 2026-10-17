"""Unit tests for synthetic ledger data generator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.generate_synthetic_ledger import (
    ANOMALY_TYPES,
    CANONICAL_COLUMNS,
    generate_synthetic_data,
    save_datasets,
)


def test_synthetic_ledger_schema() -> None:
    """Verify generated ledgers follow the canonical schema from AUDIT_RULES.md."""
    df_ledger, df_ground_truth, df_clean = generate_synthetic_data(rows=200, seed=42)

    # Check canonical columns and order
    assert list(df_ledger.columns) == CANONICAL_COLUMNS
    assert list(df_clean.columns) == CANONICAL_COLUMNS
    assert list(df_ground_truth.columns) == ["transaction_id", "anomaly_types"]

    # Check row counts
    assert len(df_ledger) == 200
    assert len(df_clean) == 200
    assert len(df_ground_truth) > 0

    # Amounts must be positive numbers
    assert (df_ledger["amount"] > 0).all()
    assert (df_clean["amount"] > 0).all()

    # Posting dates must be valid datetimes
    assert pd.api.types.is_datetime64_any_dtype(df_ledger["posting_date"])
    assert pd.api.types.is_datetime64_any_dtype(df_clean["posting_date"])

    # Required fields must not be null
    for req_col in ["transaction_id", "posting_date", "amount", "vendor_id"]:
        assert df_ledger[req_col].notna().all()
        assert df_clean[req_col].notna().all()


def test_synthetic_ledger_deterministic() -> None:
    """Verify same seed produces identical outputs across runs."""
    df_ledger1, df_gt1, df_clean1 = generate_synthetic_data(rows=500, seed=123)
    df_ledger2, df_gt2, df_clean2 = generate_synthetic_data(rows=500, seed=123)

    pd.testing.assert_frame_equal(df_ledger1, df_ledger2)
    pd.testing.assert_frame_equal(df_gt1, df_gt2)
    pd.testing.assert_frame_equal(df_clean1, df_clean2)


def test_synthetic_ledger_ground_truth_anomaly_types() -> None:
    """Verify every anomaly type is present in ground_truth."""
    _, df_ground_truth, _ = generate_synthetic_data(rows=1000, seed=42)

    # Extract all distinct anomaly types (splitting on '|')
    all_observed_types: set[str] = set()
    for types_str in df_ground_truth["anomaly_types"]:
        for t in types_str.split("|"):
            all_observed_types.add(t.strip())

    for expected_type in ANOMALY_TYPES:
        assert expected_type in all_observed_types, (
            f"Missing expected anomaly type '{expected_type}' in ground_truth"
        )


def test_synthetic_ledger_clean_has_no_injected_anomalies() -> None:
    """Verify ledger_clean has no injected anomalies and satisfies all clean invariants."""
    _, df_ground_truth, df_clean = generate_synthetic_data(rows=1000, seed=42)

    # 1. R1 invariant: created_by != approved_by
    assert not (df_clean["created_by"] == df_clean["approved_by"]).any()

    # 2. R3 invariant: approved_by must not be empty on amounts >= 10000
    high_amt = df_clean["amount"] >= 10000.0
    assert df_clean.loc[high_amt, "approved_by"].replace("", None).notna().all()

    # 3. R4 invariant: no amounts between 90,000 and 100,000
    assert not ((df_clean["amount"] >= 90000.0) & (df_clean["amount"] < 100000.0)).any()

    # 4. R5 invariant: no amounts >= 10000 that are exact multiples of 1000
    round_mask = (df_clean["amount"] >= 10000.0) & (df_clean["amount"] % 1000.0 == 0.0)
    assert not round_mask.any()

    # 5. R6 invariant: weekdays only (Mon-Fri) and within business hours (08:00 to 20:00)
    assert not (df_clean["posting_date"].dt.dayofweek >= 5).any()
    assert (df_clean["posting_date"].dt.hour >= 8).all()
    assert (df_clean["posting_date"].dt.hour < 20).all()

    # 6. R2 invariant: no duplicate payments (same vendor and amount within 7 days)
    df_sorted = df_clean.sort_values(["vendor_id", "amount", "posting_date"]).reset_index(drop=True)
    same_vendor = df_sorted["vendor_id"] == df_sorted["vendor_id"].shift(1)
    same_amount = df_sorted["amount"] == df_sorted["amount"].shift(1)
    time_diff = (df_sorted["posting_date"] - df_sorted["posting_date"].shift(1)).dt.total_seconds()
    dup_mask = same_vendor & same_amount & (time_diff < 7 * 86400)
    assert not dup_mask.any()

    # 7. Rows that were modified to be anomalous in ledger.csv are completely clean in ledger_clean
    gt_txns = df_ground_truth["transaction_id"].values
    clean_sub = df_clean[df_clean["transaction_id"].isin(gt_txns)]
    assert not (clean_sub["created_by"] == clean_sub["approved_by"]).any()
    assert not (clean_sub["posting_date"].dt.dayofweek >= 5).any()
    assert (clean_sub["posting_date"].dt.hour >= 8).all()
    assert (clean_sub["posting_date"].dt.hour < 20).all()


def test_synthetic_ledger_unique_transaction_ids() -> None:
    """Verify transaction_ids are unique across both ledger and ledger_clean."""
    df_ledger, _, df_clean = generate_synthetic_data(rows=5000, seed=42)

    assert df_ledger["transaction_id"].is_unique
    assert df_clean["transaction_id"].is_unique


def test_save_datasets_io(tmp_path: Path) -> None:
    """Verify save_datasets writes valid CSV files to the specified directory."""
    df_ledger, df_gt, df_clean = generate_synthetic_data(rows=100, seed=42)
    ledger_path, gt_path, clean_path = save_datasets(df_ledger, df_gt, df_clean, out_dir=tmp_path)

    assert ledger_path.exists()
    assert gt_path.exists()
    assert clean_path.exists()

    loaded_ledger = pd.read_csv(ledger_path)
    assert len(loaded_ledger) == 100
    assert list(loaded_ledger.columns) == CANONICAL_COLUMNS

    loaded_gt = pd.read_csv(gt_path)
    assert list(loaded_gt.columns) == ["transaction_id", "anomaly_types"]
