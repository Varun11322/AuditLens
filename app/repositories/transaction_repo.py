"""Transaction repository functions."""

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.orm import Session

from app.db.models.transaction import Transaction


def bulk_create_transactions(
    db: Session,
    transactions_data: list[dict[str, Any]],
    batch_size: int = 2000,
) -> int:
    """Insert transaction rows using efficient chunked bulk insert.

    Avoids PostgreSQL's maximum 65,535 parameters limit per statement.

    Args:
        db: Active database session.
        transactions_data: List of transaction field dictionaries.
        batch_size: Number of records per SQL statement chunk.

    Returns:
        int: Number of rows inserted.
    """
    if not transactions_data:
        return 0

    total_inserted = 0
    for i in range(0, len(transactions_data), batch_size):
        chunk = transactions_data[i : i + batch_size]
        stmt = insert(Transaction).values(chunk)
        result = db.execute(stmt)
        total_inserted += (
            result.rowcount if result.rowcount is not None and result.rowcount > 0 else len(chunk)
        )
    db.commit()
    return total_inserted


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


def get_all_transactions_for_analysis(
    db: Session,
    upload_id: int,
) -> list[Transaction]:
    """Retrieve all transactions for an upload to supply to analytics engine.

    Args:
        db: Active database session.
        upload_id: Upload primary key ID.

    Returns:
        list[Transaction]: All transaction records for the upload.
    """
    stmt = select(Transaction).where(Transaction.upload_id == upload_id).order_by(Transaction.id)
    return list(db.scalars(stmt).all())
