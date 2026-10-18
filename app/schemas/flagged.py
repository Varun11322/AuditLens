"""Flagged transaction and review schemas."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ReviewItemResponse(BaseModel):
    """Historical audit review entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    flagged_id: int
    reviewer_id: int
    reviewer_name: str | None = None
    status: str
    comment: str | None = None
    created_at: datetime


class FlaggedItemResponse(BaseModel):
    """Summarized flagged transaction with associated risk metrics."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    run_id: int
    transaction_pk: int
    transaction_id: str
    posting_date: datetime
    amount: float
    vendor_id: str
    department: str | None = None
    account_code: str | None = None
    created_by: str | None = None
    approved_by: str | None = None
    description: str | None = None
    risk_score: int
    risk_level: str
    rule_points: int
    ml_points: int
    ml_norm: float
    triggered_rules: list[str]
    reasons: list[Any] = Field(default_factory=list)
    duplicate_group_id: str | None = None
    review_status: str
    created_at: datetime


class FlaggedListResponse(BaseModel):
    """Paginated list response for flagged transactions."""

    total: int
    page: int
    page_size: int
    items: list[FlaggedItemResponse]


class FlaggedDetailResponse(FlaggedItemResponse):
    """Detailed view of a flagged item including duplicate group and review history."""

    duplicate_group_members: list[FlaggedItemResponse] = Field(default_factory=list)
    reviews: list[ReviewItemResponse] = Field(default_factory=list)


class ReviewRequest(BaseModel):
    """Payload to record or update a review decision."""

    status: Literal["reviewed", "false_positive", "needs_follow_up", "open"]
    comment: str | None = None
