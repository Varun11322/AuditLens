"""Pure analytics engine for audit rules, statistical tests, and anomaly detection."""

from app.analytics.benford import analyze_benford, calculate_benford_metrics
from app.analytics.evaluation import evaluate_detections
from app.analytics.features import build_feature_matrix
from app.analytics.ml import run_isolation_forest
from app.analytics.pipeline import AnalysisResult, run_analysis
from app.analytics.rules import evaluate_rules
from app.analytics.scoring import compute_risk_scores
from app.analytics.settings import Settings
from app.analytics.validation import validate_and_clean_ledger

__all__ = [
    "AnalysisResult",
    "Settings",
    "analyze_benford",
    "build_feature_matrix",
    "calculate_benford_metrics",
    "compute_risk_scores",
    "evaluate_detections",
    "evaluate_rules",
    "run_analysis",
    "run_isolation_forest",
    "validate_and_clean_ledger",
]
