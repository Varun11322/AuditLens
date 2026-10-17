"""Flagged transaction database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    String,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FlaggedTransaction(Base):
    """Transaction flagged by audit rules or machine learning scoring."""

    __tablename__ = "flagged_transactions"
    __table_args__ = (
        CheckConstraint(
            "risk_score >= 0 AND risk_score <= 100",
            name="ck_flagged_transactions_risk_score",
        ),
        CheckConstraint(
            "risk_level IN ('high', 'medium', 'low')",
            name="ck_flagged_transactions_risk_level",
        ),
        CheckConstraint(
            "review_status IN ('open', 'reviewed', 'false_positive', 'needs_follow_up')",
            name="ck_flagged_transactions_review_status",
        ),
        Index("ix_flagged_transactions_run_id_risk_level", "run_id", "risk_level"),
        Index("ix_flagged_transactions_run_id_risk_score_desc", "run_id", desc("risk_score")),
        Index("ix_flagged_transactions_run_id_review_status", "run_id", "review_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    transaction_pk: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    risk_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    rule_points: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )
    ml_points: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0", nullable=False
    )
    ml_norm: Mapped[float] = mapped_column(Float, default=0.0, server_default="0.0", nullable=False)
    triggered_rules: Mapped[list[str]] = mapped_column(
        ARRAY(String(10)), default=list, server_default="{}", nullable=False
    )
    reasons: Mapped[list[Any]] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )
    duplicate_group_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(50), default="open", server_default="open", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    run = relationship("AnalysisRun", back_populates="flagged_transactions")
    transaction = relationship("Transaction", back_populates="flagged_items")
    reviews = relationship(
        "Review",
        back_populates="flagged_transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
