"""Risk scoring and classification combining audit rule points and ML anomaly scores."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.analytics.settings import Settings

logger = logging.getLogger(__name__)


def compute_risk_scores(
    rules_df: pd.DataFrame,
    ml_df: pd.DataFrame,
    settings: Settings,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Compute combined risk score, risk level, and final reasons per AUDIT_RULES.md section 6.

    Formula:
        risk_score = min(100, rule_points + ml_points)

    Levels:
        - High: 70 - 100
        - Medium: 50 - 69
        - Low: flag_threshold (default 30) - 49
        - Not flagged: below flag_threshold

    Args:
        rules_df: DataFrame containing rule_points, triggered_rule_codes,
            rule_reasons, and duplicate_group_id.
        ml_df: DataFrame containing ml_points, ml_norm, ml_raw.
        settings: Analysis settings containing flag_threshold.

    Returns:
        Tuple of (scoring_results_df, scoring_summary_dict).
    """
    n_rows = len(rules_df)
    results = pd.DataFrame(index=rules_df.index)

    if n_rows == 0:
        results["rule_points"] = np.array([], dtype=int)
        results["ml_points"] = np.array([], dtype=int)
        results["ml_norm"] = np.array([], dtype=float)
        results["risk_score"] = np.array([], dtype=int)
        results["risk_level"] = np.array([], dtype=str)
        results["is_flagged"] = np.array([], dtype=bool)
        results["triggered_rule_codes"] = [[] for _ in range(0)]
        results["reasons"] = [[] for _ in range(0)]
        results["duplicate_group_id"] = np.array([], dtype=str)
        return results, {"total_flagged": 0, "by_level": {}}

    rule_pts = rules_df["rule_points"].values
    ml_pts = ml_df["ml_points"].values
    ml_norm = ml_df["ml_norm"].values

    # Combined score capped at 100
    combined_scores = np.minimum(100, rule_pts + ml_pts).astype(int)

    # Classify risk levels
    # High: 70 - 100
    # Medium: 50 - 69
    # Low: flag_threshold - 49
    # Not flagged: below flag_threshold
    risk_levels = np.array(["Not flagged"] * n_rows, dtype=object)

    high_mask = combined_scores >= 70
    med_mask = (combined_scores >= 50) & (~high_mask)
    low_mask = (combined_scores >= settings.flag_threshold) & (~high_mask) & (~med_mask)

    risk_levels[high_mask] = "High"
    risk_levels[med_mask] = "Medium"
    risk_levels[low_mask] = "Low"

    is_flagged = combined_scores >= settings.flag_threshold

    # Build comprehensive reasons list
    rule_reasons = rules_df["rule_reasons"].tolist()
    final_reasons: list[list[str]] = []

    for i in range(n_rows):
        row_reasons = list(rule_reasons[i])
        # If transaction has ML points and is flagged, include the ML explanation
        if is_flagged[i] and ml_pts[i] > 0:
            row_reasons.append(
                f"Unusual statistical profile detected by machine learning model (ML, +{ml_pts[i]})"
            )
        final_reasons.append(row_reasons)

    results["rule_points"] = rule_pts
    results["ml_points"] = ml_pts
    results["ml_norm"] = np.round(ml_norm, 4)
    results["risk_score"] = combined_scores
    results["risk_level"] = risk_levels
    results["is_flagged"] = is_flagged
    results["triggered_rule_codes"] = rules_df["triggered_rule_codes"]
    results["reasons"] = final_reasons
    results["duplicate_group_id"] = rules_df["duplicate_group_id"]

    summary = {
        "total_flagged": int(is_flagged.sum()),
        "by_level": {
            "High": int(high_mask.sum()),
            "Medium": int(med_mask.sum()),
            "Low": int(low_mask.sum()),
            "Not flagged": int((~is_flagged).sum()),
        },
    }

    return results, summary
