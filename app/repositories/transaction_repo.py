"""Transaction repository functions."""

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction


def bulk_create_transactions(
    db: Session,
    transactions_data: list[dict[str, Any]],
) -> int:
    """Insert transaction rows using efficient bulk insert.

    Args:
        db: Active database session.
        transactions_data: List of transaction field dictionaries.

    Returns:
        int: Number of rows inserted.
    """
    if not transactions_data:
        return 0
    stmt = insert(Transaction).values(transactions_data)
    result = db.execute(stmt)
    db.commit()
    return (
        result.rowcount
        if result.rowcount is not None and result.rowcount > 0
        else len(transactions_data)
    )


def get_transactions_by_upload(
    db: Session,
    upload_id: int,
    limit: int = 1000,
    offset: int = 0,
) -> list[Transaction]:
    """Retrieve transactions belonging to an upload with pagination.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.
        limit: Maximum number of rows to return.
        offset: Offset for pagination.

    Returns:
        list[Transaction]: Matching transaction records.
    """
    stmt = (
        select(Transaction)
        .where(Transaction.upload_id == upload_id)
        .order_by(Transaction.id)
        .limit(limit)
        .offset(offset)
    )
    return list(db.scalars(stmt).all())
