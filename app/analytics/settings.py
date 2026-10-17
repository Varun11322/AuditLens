"""Settings and thresholds configuration for the AuditLens analytics engine."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Settings(BaseModel):
    """Audit analysis parameters and thresholds with defaults per AUDIT_RULES.md section 2."""

    model_config = ConfigDict(frozen=True)

    approval_limit: float = Field(
        default=100000.0,
        description="Threshold amount above which secondary approval is required (INR).",
        gt=0,
    )
    just_below_band: float = Field(
        default=0.90,
        description="Fraction of approval limit to flag amounts [band*limit, limit).",
        gt=0,
        lt=1.0,
    )
    duplicate_window_days: int = Field(
        default=7,
        description="Calendar day window for identifying duplicate vendor transactions.",
        ge=0,
    )
    round_multiple: float = Field(
        default=1000.0,
        description="Round denomination multiple for R5 check.",
        gt=0,
    )
    round_min_amount: float = Field(
        default=10000.0,
        description="Minimum amount required to evaluate round amount rule R5.",
        ge=0,
    )
    business_hours_start: int = Field(
        default=8,
        description="Start hour of business day (inclusive, 24-hour clock, e.g. 8 for 08:00).",
        ge=0,
        le=23,
    )
    business_hours_end: int = Field(
        default=20,
        description="End hour of business day (exclusive, 24-hour clock, e.g. 20 for 20:00).",
        ge=0,
        le=24,
    )
    weekend_days: tuple[int, ...] = Field(
        default=(5, 6),
        description="Day of week indices considered weekends (5=Saturday, 6=Sunday).",
    )
    missing_approver_min_amount: float = Field(
        default=10000.0,
        description="Minimum transaction amount requiring an explicit approver for R3.",
        ge=0,
    )
    ml_contamination: float = Field(
        default=0.02,
        description="Expected proportion of anomalies for Isolation Forest.",
        gt=0,
        le=0.5,
    )
    ml_min_rows: int = Field(
        default=50,
        description="Minimum number of rows required to train the Isolation Forest model.",
        ge=1,
    )
    flag_threshold: int = Field(
        default=30,
        description="Minimum combined risk score for a transaction to be flagged.",
        ge=0,
        le=100,
    )
    random_seed: int = Field(
        default=42,
        description="Deterministic random seed for scikit-learn models.",
    )
