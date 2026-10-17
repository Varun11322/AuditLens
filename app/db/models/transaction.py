"""Transaction database model."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    """Accepted transaction line item model."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        UniqueConstraint(
            "upload_id", "transaction_id", name="uq_transactions_upload_transaction_id"
        ),
        Index("ix_transactions_upload_id", "upload_id"),
        Index("ix_transactions_upload_id_vendor_id", "upload_id", "vendor_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=False), primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("uploads.id", ondelete="CASCADE"), nullable=False
    )
    transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    posting_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    vendor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    account_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    upload = relationship("Upload", back_populates="transactions")
    flagged_items = relationship(
        "FlaggedTransaction",
        back_populates="transaction",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
