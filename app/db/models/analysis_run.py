"""Analysis run database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnalysisRun(Base):
    """Analysis execution record on an uploaded dataset."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name="ck_analysis_runs_status",
        ),
        Index("ix_analysis_runs_upload_id", "upload_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    started_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", server_default="pending"
    )
    settings: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    summary: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    signed_off_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=True
    )
    signed_off_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    upload = relationship("Upload", back_populates="analysis_runs")
    starter = relationship("User", foreign_keys=[started_by])
    signer = relationship("User", foreign_keys=[signed_off_by])
    flagged_transactions = relationship(
        "FlaggedTransaction",
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
