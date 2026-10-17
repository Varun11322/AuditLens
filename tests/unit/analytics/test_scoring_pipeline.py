"""Unit tests for validation, scoring, end-to-end pipeline, and evaluation."""

from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.evaluation import evaluate_detections
from app.analytics.pipeline import run_analysis
from app.analytics.scoring import compute_risk_scores
from app.analytics.settings import Settings
from app.analytics.validation import validate_and_clean_ledger


def test_validation_clean_and_rejected() -> None:
    """Test validation rejects invalid amounts, unparseable dates, and duplicate IDs."""
    raw_df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1", "TXN-2", "TXN-3", "TXN-4", "TXN-4", "TXN-5"],
            "posting_date": [
                "2025-05-14 10:00:00",
                "invalid-date",  # rejected (bad date)
                "2025-05-14 11:00:00",
                "2025-05-14 12:00:00",  # rejected (duplicate ID)
                "2025-05-14 12:00:00",  # rejected (duplicate ID)
                "2025-05-14 13:00:00",
            ],
            "amount": [
                500.0,
                1000.0,
                -50.0,  # rejected (amount <= 0)
                200.0,
                200.0,
                1200.0,
            ],
            "vendor_id": ["VEND-1", "VEND-2", "VEND-3", "VEND-4", "VEND-4", "VEND-5"],
        }
    )

    clean_df, summary = validate_and_clean_ledger(raw_df)

    assert summary["total_rows"] == 6
    assert summary["valid_rows"] == 2  # Only TXN-1 and TXN-5 are valid
    assert summary["rejected_rows"] == 4
    assert list(clean_df["transaction_id"]) == ["TXN-1", "TXN-5"]
    assert "department" in summary["missing_optional_columns"]


def test_validation_missing_required_column() -> None:
    """Missing required column raises ValueError."""
    bad_df = pd.DataFrame({"transaction_id": ["TXN-1"], "amount": [100.0]})
    with pytest.raises(ValueError, match="missing required canonical columns"):
        validate_and_clean_ledger(bad_df)


def test_scoring_level_boundaries() -> None:
    """Test risk score level boundaries (29, 30, 49, 50, 69, 70, capped at 100)."""
    settings = Settings(flag_threshold=30)
    # Target combined scores: [29, 30, 49, 50, 69, 70, 110 (capped to 100)]
    rule_pts = [20, 20, 35, 40, 55, 60, 90]
    ml_pts = [9, 10, 14, 10, 14, 10, 20]

    rules_df = pd.DataFrame(
        {
            "rule_points": rule_pts,
            "triggered_rule_codes": [[] for _ in range(7)],
            "rule_reasons": [[] for _ in range(7)],
            "duplicate_group_id": [""] * 7,
        }
    )
    ml_df = pd.DataFrame(
        {
            "ml_points": ml_pts,
            "ml_norm": [0.1] * 7,
            "ml_raw": [0.5] * 7,
        }
    )

    scores_df, summary = compute_risk_scores(rules_df, ml_df, settings)
    levels = scores_df["risk_level"].tolist()
    final_scores = scores_df["risk_score"].tolist()

    assert final_scores == [29, 30, 49, 50, 69, 70, 100]
    assert levels == [
        "Not flagged",  # 29 (< 30)
        "Low",  # 30
        "Low",  # 49
        "Medium",  # 50
        "Medium",  # 69
        "High",  # 70
        "High",  # 100
    ]
    assert summary["total_flagged"] == 6
    assert summary["by_level"]["Not flagged"] == 1
    assert summary["by_level"]["Low"] == 2
    assert summary["by_level"]["Medium"] == 2
    assert summary["by_level"]["High"] == 2


def test_pipeline_end_to_end() -> None:
    """Test full analysis pipeline execution, sorting, and output structure."""
    df = pd.DataFrame(
        {
            "transaction_id": ["TXN-1", "TXN-2", "TXN-3"],
            "posting_date": [
                pd.Timestamp("2025-05-14 10:00:00"),
                pd.Timestamp("2025-05-14 11:00:00"),
                pd.Timestamp("2025-05-18 03:00:00"),  # Weekend + after-hours
            ],
            "amount": [5000.0, 95000.0, 25000.0],  # TXN-2: R4 (+25); TXN-3: R5 (+10), R6 (+10)
            "vendor_id": ["VEND-1", "VEND-2", "VEND-3"],
            "created_by": ["alice", "alice", "charlie"],
            "approved_by": ["bob", "alice", "dan"],  # TXN-2: R1 (+40) -> total 65 (Medium)
            "department": ["Finance", "IT", "HR"],
        }
    )

    result = run_analysis(df)
    assert len(result.all_df) == 3
    # TXN-2 triggers R1 (+40) + R4 (+25) = 65 -> flagged
    assert "TXN-2" in result.flagged_df["transaction_id"].values
    assert result.summary["validation"]["valid_rows"] == 3
    assert result.summary["rules"]["total_rule_flags"] > 0


def test_evaluation_detection_metrics() -> None:
    """Test strict vs audit-adjusted precision and anomaly recall calculations."""
    flagged_df = pd.DataFrame(
        {"transaction_id": ["TXN-DUP-COPY", "TXN-DONOR-ORIG", "TXN-ROUND", "TXN-FALSE-POS"]}
    )
    ground_truth_df = pd.DataFrame(
        {
            "transaction_id": ["TXN-DUP-COPY", "TXN-ROUND", "TXN-MISSED"],
            "anomaly_types": ["duplicate", "round", "self_approval"],
            "related_transaction_id": ["TXN-DONOR-ORIG", "", ""],
        }
    )

    metrics = evaluate_detections(flagged_df, ground_truth_df)

    assert metrics["total_flagged"] == 4
    assert metrics["total_anomalies"] == 3

    # Strict: only TXN-DUP-COPY and TXN-ROUND are in ground_truth -> 2 / 4 = 0.50
    assert metrics["strict_true_positives"] == 2
    assert metrics["strict_precision"] == 0.50

    # Audit-adjusted: TXN-DONOR-ORIG is the donor of TXN-DUP-COPY -> 3 / 4 = 0.75
    assert metrics["audit_adjusted_true_positives"] == 3
    assert metrics["audit_adjusted_precision"] == 0.75

    # Recall: 2 out of 3 caught -> 0.6667
    assert round(metrics["overall_recall"], 2) == 0.67

    # Per-type recall:
    assert metrics["recall_by_type"]["duplicate"]["recall"] == 1.0
    assert metrics["recall_by_type"]["round"]["recall"] == 1.0
    assert metrics["recall_by_type"]["self_approval"]["recall"] == 0.0
