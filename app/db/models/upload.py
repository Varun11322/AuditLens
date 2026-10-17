"""Upload database model."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Upload(Base):
    """Uploaded transaction file model."""

    __tablename__ = "uploads"
    __table_args__ = (
        CheckConstraint("file_type IN ('csv', 'xlsx')", name="ck_uploads_file_type"),
        Index("ix_uploads_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    row_count_total: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    row_count_accepted: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    row_count_rejected: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    validation_summary: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    user = relationship("User", back_populates="uploads")
    transactions = relationship(
        "Transaction",
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    analysis_runs = relationship(
        "AnalysisRun",
        back_populates="upload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
