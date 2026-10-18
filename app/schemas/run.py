"""Analysis run schemas and parameter definitions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalysisSettingsOverride(BaseModel):
    """Optional threshold and parameter overrides matching AUDIT_RULES.md section 2.

    Extra unknown keys are explicitly forbidden per docs/API.md.
    """

    model_config = ConfigDict(extra="forbid")

    approval_limit: float | None = Field(default=None, gt=0)
    just_below_band: float | None = Field(default=None, gt=0, lt=1.0)
    duplicate_window_days: int | None = Field(default=None, ge=0)
    round_multiple: float | None = Field(default=None, gt=0)
    round_min_amount: float | None = Field(default=None, ge=0)
    business_hours_start: int | None = Field(default=None, ge=0, le=23)
    business_hours_end: int | None = Field(default=None, ge=0, le=24)
    weekend_days: tuple[int, ...] | None = None
    missing_approver_min_amount: float | None = Field(default=None, ge=0)
    ml_contamination: float | None = Field(default=None, gt=0, le=0.5)
    ml_min_rows: int | None = Field(default=None, ge=1)
    flag_threshold: int | None = Field(default=None, ge=0, le=100)
    random_seed: int | None = None


class StartAnalysisRequest(BaseModel):
    """Request payload to initiate an analysis run."""

    model_config = ConfigDict(extra="forbid")

    settings: AnalysisSettingsOverride | None = None


class RunCreatedResponse(BaseModel):
    """Initial acceptance response for an analysis run."""

    run_id: int
    status: str = "pending"


class AnalysisRunResponse(BaseModel):
    """Detailed metadata and execution summary for an analysis run."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    upload_id: int
    status: str
    settings: dict[str, Any]
    summary: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    signed_off_by: int | None = None
    signed_off_at: datetime | None = None
    created_at: datetime | None = None


class BenfordUnavailableResponse(BaseModel):
    """Response when Benford analysis results are unavailable."""

    available: bool = False
    reason: str


class BenfordAvailableResponse(BaseModel):
    """Response containing calculated Benford analysis metrics."""

    available: bool = True
    observed: dict[int, float]
    expected: dict[int, float]
    observed_counts: dict[int, int]
    observed_frequencies: dict[int, float]
    expected_frequencies: dict[int, float]
    chi_square: float
    p_value: float
    mad: float
    conformity: str
    conformity_label: str
    sample_size: int
    per_vendor: list[dict[str, Any]] = Field(default_factory=list)
    vendors: dict[str, Any] = Field(default_factory=dict)
    non_conformant_vendors: list[str] = Field(default_factory=list)
