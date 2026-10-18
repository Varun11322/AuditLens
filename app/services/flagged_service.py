"""Flagged transactions and review service layer."""

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.flagged_transaction import FlaggedTransaction
from app.db.models.user import User
from app.repositories.audit_log_repo import create_audit_log
from app.repositories.flagged_repo import (
    get_duplicate_group_members,
    get_flagged_by_id,
    get_flagged_transactions_filtered,
)
from app.repositories.review_repo import create_review, get_reviews_by_flagged_id
from app.repositories.user_repo import get_user_by_id
from app.schemas.flagged import (
    FlaggedDetailResponse,
    FlaggedItemResponse,
    ReviewItemResponse,
    ReviewRequest,
)
from app.services.analysis_service import get_run_detail

logger = logging.getLogger(__name__)


def _to_flagged_item_response(flagged: FlaggedTransaction) -> FlaggedItemResponse:
    """Helper converting a FlaggedTransaction ORM entity to FlaggedItemResponse schema."""
    txn = flagged.transaction
    return FlaggedItemResponse(
        id=flagged.id,
        run_id=flagged.run_id,
        transaction_pk=flagged.transaction_pk,
        transaction_id=txn.transaction_id,
        posting_date=txn.posting_date,
        amount=float(txn.amount),
        vendor_id=txn.vendor_id,
        department=txn.department,
        account_code=txn.account_code,
        created_by=txn.created_by,
        approved_by=txn.approved_by,
        description=txn.description,
        risk_score=flagged.risk_score,
        risk_level=flagged.risk_level,
        rule_points=flagged.rule_points,
        ml_points=flagged.ml_points,
        ml_norm=flagged.ml_norm,
        triggered_rules=flagged.triggered_rules or [],
        reasons=flagged.reasons or [],
        duplicate_group_id=flagged.duplicate_group_id,
        review_status=flagged.review_status,
        created_at=flagged.created_at,
    )


def list_flagged_transactions(
    db: Session,
    run_id: int,
    current_user: User,
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
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[FlaggedItemResponse], int]:
    """Retrieve filtered, sorted, and paginated flagged transactions for a run.

    Args:
        db: Active database session.
        run_id: Analysis run primary key ID.
        current_user: Authenticated user.
        risk_levels: Optional risk level filters.
        rules: Optional triggered rule filters.
        vendor_id: Optional vendor filter.
        department: Optional department filter.
        review_status: Optional review status filter.
        date_from: Optional minimum posting date.
        date_to: Optional maximum posting date.
        amount_min: Optional minimum amount.
        amount_max: Optional maximum amount.
        sort_by: Column to sort by.
        sort_dir: Direction ('asc' or 'desc').
        page: Page number (1-indexed).
        page_size: Page size limit.

    Returns:
        tuple[list[FlaggedItemResponse], int]: (Flagged items, total count).
    """
    get_run_detail(db, run_id, current_user)

    offset = (page - 1) * page_size
    items, total = get_flagged_transactions_filtered(
        db,
        run_id=run_id,
        risk_levels=risk_levels,
        rules=rules,
        vendor_id=vendor_id,
        department=department,
        review_status=review_status,
        date_from=date_from,
        date_to=date_to,
        amount_min=amount_min,
        amount_max=amount_max,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=page_size,
        offset=offset,
    )

    responses = [_to_flagged_item_response(item) for item in items]
    return responses, total


def get_flagged_detail(
    db: Session,
    flagged_id: int,
    current_user: User,
) -> FlaggedDetailResponse:
    """Retrieve flagged item detail including reasons, duplicate group, and review history.

    Args:
        db: Active database session.
        flagged_id: Flagged transaction ID.
        current_user: Authenticated user.

    Returns:
        FlaggedDetailResponse: Flagged item detail.

    Raises:
        NotFoundError: If flagged transaction is not found or not visible.
    """
    flagged = get_flagged_by_id(db, flagged_id)
    if not flagged:
        raise NotFoundError(
            code="not_found",
            message=f"Flagged transaction {flagged_id} not found.",
        )

    get_run_detail(db, flagged.run_id, current_user)

    # Duplicate group members if applicable
    dup_members: list[FlaggedItemResponse] = []
    if flagged.duplicate_group_id:
        members = get_duplicate_group_members(db, flagged.run_id, flagged.duplicate_group_id)
        dup_members = [_to_flagged_item_response(m) for m in members if m.id != flagged.id]

    # Review history
    reviews_raw = get_reviews_by_flagged_id(db, flagged_id)
    review_items: list[ReviewItemResponse] = []
    for r in reviews_raw:
        reviewer = get_user_by_id(db, r.reviewer_id)
        review_items.append(
            ReviewItemResponse(
                id=r.id,
                flagged_id=r.flagged_id,
                reviewer_id=r.reviewer_id,
                reviewer_name=reviewer.full_name if reviewer else None,
                status=r.status,
                comment=r.comment,
                created_at=r.created_at,
            )
        )

    base = _to_flagged_item_response(flagged)
    return FlaggedDetailResponse(
        **base.model_dump(),
        duplicate_group_members=dup_members,
        reviews=review_items,
    )


def review_flagged_transaction(
    db: Session,
    flagged_id: int,
    request: ReviewRequest,
    current_user: User,
) -> FlaggedItemResponse:
    """Record a review decision and update cached review status.

    Args:
        db: Active database session.
        flagged_id: Flagged transaction ID.
        request: Review status and optional justification comment.
        current_user: Authenticated user performing the review.

    Returns:
        FlaggedItemResponse: Updated flagged transaction item.

    Raises:
        NotFoundError: If flagged transaction is not found or unauthorized.
        ConflictError: If the analysis run has already been signed off.
        ValidationError: If false_positive status is submitted without a comment.
    """
    flagged = get_flagged_by_id(db, flagged_id)
    if not flagged:
        raise NotFoundError(
            code="not_found",
            message=f"Flagged transaction {flagged_id} not found.",
        )

    run = get_run_detail(db, flagged.run_id, current_user)

    if run.signed_off_at is not None:
        raise ConflictError(
            code="run_signed_off",
            message="Cannot update review on an item belonging to a signed-off run.",
        )

    if request.status == "false_positive" and (not request.comment or not request.comment.strip()):
        raise ValidationError(
            code="comment_required",
            message="A non-empty comment is required when marking a transaction as false positive.",
        )

    create_review(
        db,
        flagged_id=flagged_id,
        reviewer_id=current_user.id,
        status=request.status,
        comment=request.comment.strip() if request.comment else None,
    )

    create_audit_log(
        db,
        action="review",
        entity_type="flagged_transaction",
        entity_id=str(flagged_id),
        user_id=current_user.id,
        details={"status": request.status, "has_comment": bool(request.comment)},
    )

    logger.info(
        "User %s updated review on flagged item %d to %s",
        current_user.email,
        flagged_id,
        request.status,
    )
    db.refresh(flagged)
    return _to_flagged_item_response(flagged)
