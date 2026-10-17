"""Machine learning anomaly detection using scikit-learn IsolationForest."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.analytics.settings import Settings

logger = logging.getLogger(__name__)


def run_isolation_forest(
    features_df: pd.DataFrame,
    settings: Settings,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Train Isolation Forest and score transaction features per AUDIT_RULES.md section 5.

    Args:
        features_df: Engineered feature matrix.
        settings: Analysis settings containing ml_contamination, ml_min_rows, and random_seed.

    Returns:
        Tuple of (ml_results_df, ml_summary_dict).
    """
    n_rows = len(features_df)
    results = pd.DataFrame(index=features_df.index)

    # Check minimum row threshold
    if n_rows < settings.ml_min_rows:
        warning_msg = (
            f"ML layer skipped: dataset has {n_rows} rows "
            f"(minimum required is {settings.ml_min_rows}). ml_points set to 0."
        )
        logger.warning(warning_msg)
        results["ml_raw"] = np.zeros(n_rows, dtype=float)
        results["ml_norm"] = np.zeros(n_rows, dtype=float)
        results["ml_points"] = np.zeros(n_rows, dtype=int)

        summary: dict[str, Any] = {
            "skipped": True,
            "warning": warning_msg,
            "n_estimators": 200,
            "contamination": settings.ml_contamination,
            "features_used": list(features_df.columns),
        }
        return results, summary

    # Fit Isolation Forest
    model = IsolationForest(
        n_estimators=200,
        contamination=settings.ml_contamination,
        random_state=settings.random_seed,
    )
    model.fit(features_df)

    # ml_raw = -score_samples (higher means more unusual)
    raw_scores = -model.score_samples(features_df)

    # ml_norm = min-max scaling of ml_raw to [0, 1] over the run
    min_score = float(np.min(raw_scores))
    max_score = float(np.max(raw_scores))
    if max_score > min_score:
        ml_norm = (raw_scores - min_score) / (max_score - min_score)
    else:
        ml_norm = np.zeros(n_rows, dtype=float)

    # ml_points = round(ml_norm * 40)
    ml_points = np.round(ml_norm * 40).astype(int)

    results["ml_raw"] = raw_scores
    results["ml_norm"] = ml_norm
    results["ml_points"] = ml_points

    summary = {
        "skipped": False,
        "warning": None,
        "n_estimators": 200,
        "contamination": settings.ml_contamination,
        "features_used": list(features_df.columns),
        "min_raw_score": round(min_score, 4),
        "max_raw_score": round(max_score, 4),
    }

    return results, summary
