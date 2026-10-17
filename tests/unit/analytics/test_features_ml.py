"""Unit tests for ML feature engineering and Isolation Forest anomaly detection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics.features import build_feature_matrix
from app.analytics.ml import run_isolation_forest
from app.analytics.settings import Settings


def test_feature_engineering_full() -> None:
    """Verify all 7 features are extracted when all columns and time parts exist."""
    df = pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:03d}" for i in range(10)],
            "posting_date": pd.date_range("2025-05-14 09:00:00", periods=10, freq="h"),
            "amount": [
                1000.0,
                1500.0,
                2000.0,
                2500.0,
                3000.0,
                3500.0,
                4000.0,
                4500.0,
                5000.0,
                5500.0,
            ],
            "vendor_id": ["VEND-A"] * 6 + ["VEND-B"] * 4,
            "department": ["Finance"] * 5 + ["IT"] * 5,
        }
    )

    features, names = build_feature_matrix(df, has_time_part=True)
    expected_cols = [
        "log_amount",
        "hour_of_day",
        "day_of_week",
        "is_weekend",
        "vendor_amount_robust_z",
        "vendor_daily_txn_count",
        "dept_amount_percentile",
    ]
    assert names == expected_cols
    assert list(features.columns) == expected_cols
    assert not features.isna().any().any()


def test_feature_fallback_date_only_and_missing_dept() -> None:
    """Verify hour_of_day is 12 when date-only, and dept feature skipped when missing."""
    df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1", "TXN-2"],
            "posting_date": [
                pd.Timestamp("2025-05-14 00:00:00"),
                pd.Timestamp("2025-05-15 00:00:00"),
            ],
            "amount": [1000.0, 2000.0],
            "vendor_id": ["VEND-A", "VEND-B"],
        }
    )

    features, names = build_feature_matrix(
        df, has_time_part=False, missing_optional_columns=["department"]
    )
    assert "dept_amount_percentile" not in names
    assert (features["hour_of_day"] == 12).all()


def test_feature_vendor_robust_z_fallback() -> None:
    """Vendor with < 5 transactions or MAD == 0 falls back to global median/MAD."""
    # VEND-A has 3 transactions (< 5)
    # VEND-B has 6 identical transactions (MAD == 0)
    # VEND-C has 6 diverse transactions (normal MAD > 0)
    df = pd.DataFrame(
        {
            "transaction_id": [f"TXN-{i:03d}" for i in range(15)],
            "posting_date": pd.date_range("2025-05-14 10:00:00", periods=15, freq="D"),
            "amount": [100.0, 200.0, 300.0]  # VEND-A (3 rows)
            + [500.0] * 6  # VEND-B (6 rows, MAD=0)
            + [1000.0, 1200.0, 1500.0, 1800.0, 2200.0, 2600.0],  # VEND-C (6 rows)
            "vendor_id": ["VEND-A"] * 3 + ["VEND-B"] * 6 + ["VEND-C"] * 6,
        }
    )

    features, _ = build_feature_matrix(df, has_time_part=True)
    robust_z = features["vendor_amount_robust_z"].values

    # None of the robust_z values should be NaN or inf
    assert not np.isnan(robust_z).any()
    assert not np.isinf(robust_z).any()


def test_ml_skipped_when_rows_below_threshold() -> None:
    """Isolation Forest is skipped with a warning when row count < ml_min_rows (50)."""
    settings = Settings(ml_min_rows=50)
    features = pd.DataFrame({"feat1": np.arange(30), "feat2": np.arange(30)})

    results, summary = run_isolation_forest(features, settings)
    assert summary["skipped"] is True
    assert summary["warning"] is not None
    assert (results["ml_points"] == 0).all()
    assert (results["ml_norm"] == 0.0).all()


def test_ml_deterministic_scoring() -> None:
    """Same seed and data produces identical Isolation Forest scores across runs."""
    settings = Settings(ml_min_rows=50, random_seed=42)
    rng = np.random.default_rng(123)
    data = rng.normal(size=(100, 4))
    features = pd.DataFrame(data, columns=["f1", "f2", "f3", "f4"])

    results1, _ = run_isolation_forest(features, settings)
    results2, _ = run_isolation_forest(features, settings)

    pd.testing.assert_frame_equal(results1, results2)
    assert (results1["ml_points"] >= 0).all()
    assert (results1["ml_points"] <= 40).all()
    assert (results1["ml_norm"] >= 0.0).all()
    assert (results1["ml_norm"] <= 1.0).all()
