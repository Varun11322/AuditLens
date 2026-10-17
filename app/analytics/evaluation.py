"""Evaluation utilities for calculating precision, recall, and detection metrics."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

ALL_ANOMALY_TYPES: list[str] = [
    "duplicate",
    "round",
    "weekend_afterhours",
    "just_below_limit",
    "self_approval",
    "missing_approver",
    "random_outlier",
]


def evaluate_detections(
    flagged_df: pd.DataFrame,
    ground_truth_df: pd.DataFrame,
) -> dict[str, Any]:
    """Compute detection accuracy against known ground truth labels.

    Evaluates overall precision (both strict and audit-adjusted), overall recall,
    and recall per specific anomaly type per AUDIT_RULES.md section 9.

    Args:
        flagged_df: DataFrame of transactions flagged by the pipeline (contains transaction_id).
        ground_truth_df: DataFrame with transaction_id, anomaly_types, related_transaction_id.

    Returns:
        Dictionary containing overall and per-anomaly-type precision and recall metrics.
    """
    flagged_ids = set(flagged_df["transaction_id"].dropna().astype(str))
    injected_ids = set(ground_truth_df["transaction_id"].dropna().astype(str))

    # Donor IDs for duplicates (from related_transaction_id)
    donor_ids = set()
    if "related_transaction_id" in ground_truth_df.columns:
        valid_donors = ground_truth_df["related_transaction_id"].dropna().astype(str).str.strip()
        donor_ids = set(valid_donors[valid_donors != ""])

    total_flagged = len(flagged_ids)
    total_anomalous = len(injected_ids)

    # 1. Strict evaluation (only explicitly injected IDs count as TP)
    strict_tp_ids = flagged_ids.intersection(injected_ids)
    strict_tp_count = len(strict_tp_ids)
    strict_fp_count = total_flagged - strict_tp_count
    strict_fn_count = total_anomalous - strict_tp_count
    strict_precision = round(strict_tp_count / total_flagged, 4) if total_flagged > 0 else 0.0

    # 2. Audit-adjusted evaluation
    # Original donor transactions of duplicate payments are legitimately flagged by R2
    adjusted_valid_ids = injected_ids.union(donor_ids)
    adjusted_tp_ids = flagged_ids.intersection(adjusted_valid_ids)
    adjusted_tp_count = len(adjusted_tp_ids)
    adjusted_fp_count = total_flagged - adjusted_tp_count
    audit_precision = round(adjusted_tp_count / total_flagged, 4) if total_flagged > 0 else 0.0

    # 3. Overall recall on injected anomalies
    overall_recall = round(strict_tp_count / total_anomalous, 4) if total_anomalous > 0 else 0.0

    # 4. Recall per anomaly type
    recall_by_type: dict[str, dict[str, Any]] = {}
    for atype in ALL_ANOMALY_TYPES:
        matching_mask = ground_truth_df["anomaly_types"].str.contains(atype, regex=False)
        target_ids = set(ground_truth_df.loc[matching_mask, "transaction_id"].astype(str))
        n_target = len(target_ids)
        caught_ids = target_ids.intersection(flagged_ids)
        n_caught = len(caught_ids)
        recall_val = round(n_caught / n_target, 4) if n_target > 0 else 0.0

        recall_by_type[atype] = {
            "total_injected": n_target,
            "detected": n_caught,
            "recall": recall_val,
        }

    explanation = (
        "Strict precision counts only the injected duplicate transactions as true positives, "
        "classifying flagged original donor transactions as false positives. "
        "Audit-adjusted precision recognizes both the duplicate copy and its original donor "
        "transaction as valid detections because rule R2 correctly flags all transactions "
        "sharing a duplicate payment window."
    )

    return {
        "total_flagged": total_flagged,
        "total_anomalies": total_anomalous,
        "strict_true_positives": strict_tp_count,
        "strict_false_positives": strict_fp_count,
        "strict_false_negatives": strict_fn_count,
        "strict_precision": strict_precision,
        "audit_adjusted_true_positives": adjusted_tp_count,
        "audit_adjusted_false_positives": adjusted_fp_count,
        "audit_adjusted_precision": audit_precision,
        "overall_recall": overall_recall,
        "recall_by_type": recall_by_type,
        "explanation": explanation,
    }
