"""Review decision database model."""

from datetime import datetime

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Review(Base):
    """Audit review history record for a flagged transaction."""

    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open', 'reviewed', 'false_positive', 'needs_follow_up')",
            name="ck_reviews_status",
        ),
        Index("ix_reviews_flagged_id_created_at", "flagged_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    flagged_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("flagged_transactions.id", ondelete="CASCADE"), nullable=False
    )
    reviewer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    flagged_transaction = relationship("FlaggedTransaction", back_populates="reviews")
    reviewer = relationship("User")
