"""Full analysis pipeline orchestrating validation, rules, Benford, ML, and scoring."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.analytics.benford import analyze_benford
from app.analytics.features import build_feature_matrix
from app.analytics.ml import run_isolation_forest
from app.analytics.rules import evaluate_rules
from app.analytics.scoring import compute_risk_scores
from app.analytics.settings import Settings
from app.analytics.validation import validate_and_clean_ledger

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Encapsulates the complete results and summary of an audit analysis run."""

    flagged_df: pd.DataFrame
    all_df: pd.DataFrame
    summary: dict[str, Any]
    benford_result: dict[str, Any]


def run_analysis(
    df: pd.DataFrame,
    settings: Settings | None = None,
) -> AnalysisResult:
    """Execute the complete end-to-end AuditLens analytics pipeline on a transaction DataFrame.

    Orchestrates validation, rule checks (R1-R6), Benford's Law analysis,
    Isolation Forest feature extraction and anomaly scoring, and combined risk classification.

    Args:
        df: Raw uploaded transaction DataFrame.
        settings: Analysis settings and thresholds (uses defaults if None).

    Returns:
        AnalysisResult containing flagged_df, all_df, summary, and benford_result.
    """
    start_time = time.perf_counter()
    active_settings = settings or Settings()
    logger.info(
        "Starting audit analysis pipeline on %d input rows", len(df) if df is not None else 0
    )

    # 1. Validation and cleaning
    clean_df, val_summary = validate_and_clean_ledger(df)

    if len(clean_df) == 0:
        duration = time.perf_counter() - start_time
        empty_df = pd.DataFrame()
        summary = {
            "duration_seconds": round(duration, 3),
            "validation": val_summary,
            "rules": {"skipped_rules": {}, "counts_per_rule": {}},
            "ml": {"skipped": True, "warning": "No valid rows to analyze."},
            "scoring": {"total_flagged": 0, "by_level": {}},
            "settings": active_settings.model_dump(),
        }
        return AnalysisResult(
            flagged_df=empty_df,
            all_df=empty_df,
            summary=summary,
            benford_result={"overall": None, "vendors": {}, "non_conformant_vendors": []},
        )

    # 2. Rule evaluation (R1-R6)
    rules_df, rules_summary = evaluate_rules(
        df=clean_df,
        settings=active_settings,
        missing_optional_columns=val_summary.get("missing_optional_columns"),
        has_time_part=val_summary.get("has_time_part", True),
    )

    # 3. Benford's Law test
    benford_summary = analyze_benford(clean_df)

    # 4. Feature engineering and Isolation Forest ML
    features_df, feature_names = build_feature_matrix(
        df=clean_df,
        has_time_part=val_summary.get("has_time_part", True),
        missing_optional_columns=val_summary.get("missing_optional_columns"),
    )
    ml_df, ml_summary = run_isolation_forest(features_df, active_settings)

    # 5. Combined risk scoring and level categorization
    scores_df, scoring_summary = compute_risk_scores(rules_df, ml_df, active_settings)

    # 6. Assemble complete results DataFrame
    all_df = clean_df.copy()
    for col in scores_df.columns:
        all_df[col] = scores_df[col]

    # Flagged transactions sorted by risk_score desc, posting_date desc
    flagged_mask = all_df["is_flagged"]
    flagged_df = (
        all_df.loc[flagged_mask]
        .sort_values(by=["risk_score", "posting_date"], ascending=[False, False])
        .reset_index(drop=True)
    )

    duration = time.perf_counter() - start_time
    logger.info(
        "Analysis pipeline finished in %.2fs: %d flagged out of %d valid transactions",
        duration,
        len(flagged_df),
        len(clean_df),
    )

    pipeline_summary: dict[str, Any] = {
        "duration_seconds": round(duration, 3),
        "validation": val_summary,
        "rules": rules_summary,
        "ml": ml_summary,
        "scoring": scoring_summary,
        "settings": active_settings.model_dump(),
    }

    return AnalysisResult(
        flagged_df=flagged_df,
        all_df=all_df,
        summary=pipeline_summary,
        benford_result=benford_summary,
    )
