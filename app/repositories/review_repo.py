"""Review repository functions."""

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models.flagged_transaction import FlaggedTransaction
from app.db.models.review import Review


def create_review(
    db: Session,
    *,
    flagged_id: int,
    reviewer_id: int,
    status: str,
    comment: str | None = None,
) -> Review:
    """Create an append-only review record and update cached status on flagged transaction.

    Args:
        db: Active database session.
        flagged_id: Associated flagged transaction ID.
        reviewer_id: ID of reviewing user.
        status: Review decision status ('reviewed', 'false_positive', 'needs_follow_up', etc.).
        comment: Optional auditor notes or justification.

    Returns:
        Review: Created review entity.
    """
    review = Review(
        flagged_id=flagged_id,
        reviewer_id=reviewer_id,
        status=status,
        comment=comment,
    )
    db.add(review)

    # Update cached review_status on FlaggedTransaction
    flagged = db.get(FlaggedTransaction, flagged_id)
    if flagged:
        flagged.review_status = status

    db.commit()
    db.refresh(review)
    return review


def get_reviews_by_flagged_id(db: Session, flagged_id: int) -> list[Review]:
    """Retrieve full audit review history for a flagged item in chronological order.

    Args:
        db: Active database session.
        flagged_id: Associated flagged transaction ID.

    Returns:
        list[Review]: List of review history records.
    """
    stmt = select(Review).where(Review.flagged_id == flagged_id).order_by(desc(Review.created_at))
    return list(db.scalars(stmt).all())
