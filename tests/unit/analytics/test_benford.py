"""Unit tests for Benford's Law analysis and conformity checks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analytics.benford import analyze_benford, calculate_benford_metrics


def test_benford_conforming_sample() -> None:
    """A sample generated from the theoretical Benford distribution should pass conformity."""
    rng = np.random.default_rng(42)
    # Generate 5,000 samples following P(d) = log10(1 + 1/d)
    digits_probs = [np.log10(1 + 1 / d) for d in range(1, 10)]
    digits_sample = rng.choice(np.arange(1, 10), size=10000, p=digits_probs)

    metrics = calculate_benford_metrics(digits_sample)
    assert metrics["has_sufficient_data"] is True
    assert metrics["sample_size"] == 10000
    assert metrics["conformity_label"] in ("Close conformity", "Acceptable conformity")
    assert metrics["mad"] < 0.012


def test_benford_non_conforming_sample() -> None:
    """A uniform first-digit sample should fail Benford's Law with Non-conformity."""
    # Flat 1/9 across all digits 1-9
    flat_sample = np.repeat(np.arange(1, 10), 1000)

    metrics = calculate_benford_metrics(flat_sample)
    assert metrics["has_sufficient_data"] is True
    assert metrics["sample_size"] == 9000
    assert metrics["conformity_label"] == "Non-conformity"
    assert metrics["mad"] > 0.015


def test_benford_upload_insufficient_data() -> None:
    """An upload with fewer than 1000 rows should report insufficient data."""
    df = pd.DataFrame(
        {
            "amount": [100.0] * 500,
            "vendor_id": ["VEND-001"] * 500,
        }
    )
    result = analyze_benford(df, overall_min_rows=1000)
    assert result["overall"]["has_sufficient_data"] is False
    assert result["overall"]["conformity_label"] == "Insufficient data"


def test_benford_vendor_thresholds() -> None:
    """Vendors with >= 300 rows are analyzed; vendors with < 300 are omitted."""
    # Vendor A has 400 uniform rows (Non-conformity)
    v_a_amounts = np.repeat([10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0], 50)
    # Vendor B has 250 rows (< 300 threshold)
    v_b_amounts = [100.0] * 250
    # Additional background rows so overall >= 1000
    v_c_amounts = [500.0] * 500

    df = pd.DataFrame(
        {
            "amount": np.concatenate([v_a_amounts, v_b_amounts, v_c_amounts]),
            "vendor_id": ["VEND-A"] * len(v_a_amounts)
            + ["VEND-B"] * len(v_b_amounts)
            + ["VEND-C"] * len(v_c_amounts),
        }
    )

    result = analyze_benford(df, overall_min_rows=1000, vendor_min_rows=300)

    assert result["overall"]["has_sufficient_data"] is True
    # VEND-A and VEND-C have >= 300 rows
    assert "VEND-A" in result["vendors"]
    assert "VEND-C" in result["vendors"]
    # VEND-B has < 300 rows -> omitted from vendors map
    assert "VEND-B" not in result["vendors"]

    # VEND-A has uniform amounts -> Non-conformity
    assert "VEND-A" in result["non_conformant_vendors"]
