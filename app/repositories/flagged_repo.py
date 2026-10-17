"""Flagged transaction repository functions."""

from typing import Any

from sqlalchemy import desc, insert, select
from sqlalchemy.orm import Session

from app.db.models.flagged_transaction import FlaggedTransaction


def bulk_create_flagged_transactions(
    db: Session,
    flagged_records: list[dict[str, Any]],
) -> int:
    """Insert flagged transactions in bulk.

    Args:
        db: Active database session.
        flagged_records: List of dictionaries matching FlaggedTransaction fields.

    Returns:
        int: Number of rows inserted.
    """
    if not flagged_records:
        return 0
    stmt = insert(FlaggedTransaction).values(flagged_records)
    result = db.execute(stmt)
    db.commit()
    return (
        result.rowcount
        if result.rowcount is not None and result.rowcount > 0
        else len(flagged_records)
    )


def get_flagged_transactions_by_run(
    db: Session,
    run_id: int,
    *,
    risk_level: str | None = None,
    review_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FlaggedTransaction]:
    """Retrieve flagged items for a run with optional filtering and sorting.

    Args:
        db: Active database session.
        run_id: Associated analysis run ID.
        risk_level: Optional filter by 'high', 'medium', or 'low'.
        review_status: Optional filter by review status.
        limit: Page size limit.
        offset: Offset for pagination.

    Returns:
        list[FlaggedTransaction]: List of flagged transaction records.
    """
    stmt = select(FlaggedTransaction).where(FlaggedTransaction.run_id == run_id)
    if risk_level:
        stmt = stmt.where(FlaggedTransaction.risk_level == risk_level)
    if review_status:
        stmt = stmt.where(FlaggedTransaction.review_status == review_status)
    stmt = stmt.order_by(desc(FlaggedTransaction.risk_score)).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())
