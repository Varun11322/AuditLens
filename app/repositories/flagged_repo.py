"""Flagged transaction repository functions."""

from datetime import datetime
from typing import Any

from sqlalchemy import asc, desc, func, insert, select
from sqlalchemy.orm import Session, joinedload

from app.db.models.flagged_transaction import FlaggedTransaction
from app.db.models.transaction import Transaction


def bulk_create_flagged_transactions(
    db: Session,
    flagged_records: list[dict[str, Any]],
    batch_size: int = 2000,
) -> int:
    """Insert flagged transactions in bulk using chunks to stay under DB parameter limits.

    Args:
        db: Active database session.
        flagged_records: List of dictionaries matching FlaggedTransaction fields.
        batch_size: Number of records per SQL statement chunk.

    Returns:
        int: Number of rows inserted.
    """
    if not flagged_records:
        return 0

    total_inserted = 0
    for i in range(0, len(flagged_records), batch_size):
        chunk = flagged_records[i : i + batch_size]
        stmt = insert(FlaggedTransaction).values(chunk)
        result = db.execute(stmt)
        total_inserted += (
            result.rowcount if result.rowcount is not None and result.rowcount > 0 else len(chunk)
        )
    db.commit()
    return total_inserted


def get_flagged_by_id(db: Session, flagged_id: int) -> FlaggedTransaction | None:
    """Retrieve a flagged transaction by ID with its associated transaction.

    Args:
        db: Active database session.
        flagged_id: Flagged transaction primary key ID.

    Returns:
        FlaggedTransaction | None: Flagged entity if found, else None.
    """
    stmt = (
        select(FlaggedTransaction)
        .where(FlaggedTransaction.id == flagged_id)
        .options(
            joinedload(FlaggedTransaction.transaction),
            joinedload(FlaggedTransaction.reviews),
        )
    )
    return db.scalars(stmt).unique().first()


def count_open_flagged_by_run(db: Session, run_id: int) -> int:
    """Count how many flagged items in a run remain in 'open' review status.

    Args:
        db: Active database session.
        run_id: Associated analysis run ID.

    Returns:
        int: Count of open review items.
    """
    stmt = (
        select(func.count(FlaggedTransaction.id))
        .where(FlaggedTransaction.run_id == run_id)
        .where(FlaggedTransaction.review_status == "open")
    )
    return db.scalar(stmt) or 0


def get_duplicate_group_members(
    db: Session,
    run_id: int,
    duplicate_group_id: str,
) -> list[FlaggedTransaction]:
    """Retrieve all flagged items belonging to a duplicate group within a run.

    Args:
        db: Active database session.
        run_id: Associated analysis run ID.
        duplicate_group_id: Duplicate group identifier string.

    Returns:
        list[FlaggedTransaction]: Flagged items in the group.
    """
    stmt = (
        select(FlaggedTransaction)
        .where(FlaggedTransaction.run_id == run_id)
        .where(FlaggedTransaction.duplicate_group_id == duplicate_group_id)
        .options(joinedload(FlaggedTransaction.transaction))
        .order_by(FlaggedTransaction.id)
    )
    return list(db.scalars(stmt).unique().all())


def get_flagged_transactions_filtered(
    db: Session,
    run_id: int,
    *,
    risk_levels: list[str] | None = None,
    rules: list[str] | None = None,
    vendor_id: str | None = None,
    department: str | None = None,
    review_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    sort_by: str = "risk_score",
    sort_dir: str = "desc",
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[FlaggedTransaction], int]:
    """Retrieve filtered, sorted, and paginated flagged transactions for a run.

    Args:
        db: Active database session.
        run_id: Associated analysis run ID.
        risk_levels: Optional list of risk levels (e.g. ['high', 'medium']).
        rules: Optional list of rule codes to match (e.g. ['R1', 'R2']).
        vendor_id: Optional exact vendor ID filter.
        department: Optional department name filter.
        review_status: Optional review status ('open', 'reviewed', etc.).
        date_from: Optional minimum posting date.
        date_to: Optional maximum posting date.
        amount_min: Optional minimum transaction amount.
        amount_max: Optional maximum transaction amount.
        sort_by: Sorting field ('risk_score', 'amount', 'posting_date').
        sort_dir: Sorting direction ('asc' or 'desc').
        limit: Max items per page.
        offset: Offset for pagination.

    Returns:
        tuple[list[FlaggedTransaction], int]: (Matching items list, total count).
    """
    stmt = (
        select(FlaggedTransaction)
        .join(Transaction, FlaggedTransaction.transaction_pk == Transaction.id)
        .where(FlaggedTransaction.run_id == run_id)
        .options(joinedload(FlaggedTransaction.transaction))
    )
    count_stmt = (
        select(func.count(FlaggedTransaction.id))
        .join(Transaction, FlaggedTransaction.transaction_pk == Transaction.id)
        .where(FlaggedTransaction.run_id == run_id)
    )

    if risk_levels:
        stmt = stmt.where(FlaggedTransaction.risk_level.in_(risk_levels))
        count_stmt = count_stmt.where(FlaggedTransaction.risk_level.in_(risk_levels))

    if rules:
        stmt = stmt.where(FlaggedTransaction.triggered_rules.overlap(rules))
        count_stmt = count_stmt.where(FlaggedTransaction.triggered_rules.overlap(rules))

    if vendor_id:
        stmt = stmt.where(Transaction.vendor_id == vendor_id)
        count_stmt = count_stmt.where(Transaction.vendor_id == vendor_id)

    if department:
        stmt = stmt.where(Transaction.department == department)
        count_stmt = count_stmt.where(Transaction.department == department)

    if review_status:
        stmt = stmt.where(FlaggedTransaction.review_status == review_status)
        count_stmt = count_stmt.where(FlaggedTransaction.review_status == review_status)

    if date_from:
        stmt = stmt.where(Transaction.posting_date >= date_from)
        count_stmt = count_stmt.where(Transaction.posting_date >= date_from)

    if date_to:
        stmt = stmt.where(Transaction.posting_date <= date_to)
        count_stmt = count_stmt.where(Transaction.posting_date <= date_to)

    if amount_min is not None:
        stmt = stmt.where(Transaction.amount >= amount_min)
        count_stmt = count_stmt.where(Transaction.amount >= amount_min)

    if amount_max is not None:
        stmt = stmt.where(Transaction.amount <= amount_max)
        count_stmt = count_stmt.where(Transaction.amount <= amount_max)

    total = db.scalar(count_stmt) or 0

    # Determine sorting column
    sort_column = FlaggedTransaction.risk_score
    if sort_by == "amount":
        sort_column = Transaction.amount
    elif sort_by == "posting_date":
        sort_column = Transaction.posting_date

    order_expr = desc(sort_column) if sort_dir.lower() == "desc" else asc(sort_column)
    # Secondary deterministic order
    secondary_expr = desc(FlaggedTransaction.id)

    stmt = stmt.order_by(order_expr, secondary_expr).limit(limit).offset(offset)
    items = list(db.scalars(stmt).unique().all())

    return items, total


def get_flagged_transactions_by_run(
    db: Session,
    run_id: int,
    *,
    risk_level: str | None = None,
    review_status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[FlaggedTransaction]:
    """Retrieve flagged items for a run with basic filtering."""
    items, _ = get_flagged_transactions_filtered(
        db,
        run_id,
        risk_levels=[risk_level] if risk_level else None,
        review_status=review_status,
        limit=limit,
        offset=offset,
    )
    return items
