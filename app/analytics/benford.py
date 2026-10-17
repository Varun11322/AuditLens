"""Benford's Law analysis for first-digit distribution testing on transaction amounts."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)

# Expected Benford frequencies for digits 1 through 9: P(d) = log10(1 + 1/d)
BENFORD_EXPECTED_PROBABILITIES: dict[int, float] = {
    d: float(np.log10(1.0 + 1.0 / d)) for d in range(1, 10)
}


def _extract_first_digits(amounts: np.ndarray) -> np.ndarray:
    """Extract first significant digits (1-9) from positive transaction amounts."""
    # Filter strictly positive values
    pos_amounts = amounts[amounts > 0]
    if len(pos_amounts) == 0:
        return np.array([], dtype=int)

    # Compute base-10 exponent and extract the leading digit
    powers = np.floor(np.log10(pos_amounts) + 1e-12)
    scales = 10.0**powers
    first_digits = np.floor(pos_amounts / scales).astype(int)
    return np.clip(first_digits, 1, 9)


def calculate_benford_metrics(
    digits: np.ndarray,
) -> dict[str, Any]:
    """Calculate chi-square, p-value, MAD, and Nigrini conformity label for digits 1-9.

    Args:
        digits: 1D array of extracted first digits (values 1 to 9).

    Returns:
        Dictionary of Benford statistics.
    """
    n = len(digits)
    if n == 0:
        return {
            "sample_size": 0,
            "has_sufficient_data": False,
            "observed_counts": {d: 0 for d in range(1, 10)},
            "observed_frequencies": {d: 0.0 for d in range(1, 10)},
            "expected_frequencies": BENFORD_EXPECTED_PROBABILITIES,
            "chi_square": 0.0,
            "p_value": 1.0,
            "mad": 0.0,
            "conformity_label": "Insufficient data",
        }

    # Count frequencies for each digit 1-9
    counts_map: dict[int, int] = {d: 0 for d in range(1, 10)}
    unique, counts = np.unique(digits, return_counts=True)
    for u, c in zip(unique, counts, strict=False):
        if 1 <= u <= 9:
            counts_map[int(u)] = int(c)

    observed_counts = np.array([counts_map[d] for d in range(1, 10)], dtype=float)
    observed_freq = observed_counts / float(n)
    expected_freq = np.array([BENFORD_EXPECTED_PROBABILITIES[d] for d in range(1, 10)], dtype=float)
    expected_counts = expected_freq * float(n)

    # Chi-square statistic and p-value (8 degrees of freedom)
    chi_square = float(np.sum((observed_counts - expected_counts) ** 2 / expected_counts))
    p_value = float(stats.chi2.sf(chi_square, df=8))

    # Mean Absolute Deviation (MAD) = sum(|Obs - Exp|) / 9
    mad = float(np.mean(np.abs(observed_freq - expected_freq)))

    # Nigrini MAD conformity thresholds
    if mad <= 0.006:
        conformity_label = "Close conformity"
    elif mad <= 0.012:
        conformity_label = "Acceptable conformity"
    elif mad <= 0.015:
        conformity_label = "Marginally acceptable conformity"
    else:
        conformity_label = "Non-conformity"

    return {
        "sample_size": n,
        "has_sufficient_data": True,
        "observed_counts": {d: int(observed_counts[d - 1]) for d in range(1, 10)},
        "observed_frequencies": {d: round(float(observed_freq[d - 1]), 5) for d in range(1, 10)},
        "expected_frequencies": {d: round(float(expected_freq[d - 1]), 5) for d in range(1, 10)},
        "chi_square": round(chi_square, 4),
        "p_value": round(p_value, 5),
        "mad": round(mad, 5),
        "conformity_label": conformity_label,
    }


def analyze_benford(
    df: pd.DataFrame,
    overall_min_rows: int = 1000,
    vendor_min_rows: int = 300,
) -> dict[str, Any]:
    """Run Benford's Law analysis on the full upload and per eligible vendor.

    Args:
        df: Clean transaction DataFrame.
        overall_min_rows: Minimum rows to analyze overall upload (default: 1000).
        vendor_min_rows: Minimum transactions to analyze a single vendor (default: 300).

    Returns:
        Dictionary containing overall and vendor-level Benford results.
    """
    total_rows = len(df)
    results: dict[str, Any] = {
        "overall": None,
        "vendors": {},
        "non_conformant_vendors": [],
        "note": "Non-conformity is a signal for investigation, not proof of fraud.",
    }

    # 1. Overall analysis
    if total_rows < overall_min_rows:
        results["overall"] = {
            "sample_size": total_rows,
            "has_sufficient_data": False,
            "conformity_label": "Insufficient data",
            "message": (
                f"Upload has {total_rows} rows; Benford analysis requires "
                f"at least {overall_min_rows} rows."
            ),
        }
    else:
        digits = _extract_first_digits(df["amount"].values)
        results["overall"] = calculate_benford_metrics(digits)

    # 2. Per-vendor analysis
    vendor_counts = df["vendor_id"].value_counts()
    eligible_vendors = vendor_counts[vendor_counts >= vendor_min_rows].index

    for v_id in eligible_vendors:
        v_amounts = df.loc[df["vendor_id"] == v_id, "amount"].values
        v_digits = _extract_first_digits(v_amounts)
        v_metrics = calculate_benford_metrics(v_digits)
        results["vendors"][str(v_id)] = v_metrics
        if v_metrics.get("conformity_label") == "Non-conformity":
            results["non_conformant_vendors"].append(str(v_id))

    return results
