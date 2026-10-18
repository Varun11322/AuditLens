"""Flagged transaction detail and review action router."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.flagged import FlaggedDetailResponse, FlaggedItemResponse, ReviewRequest
from app.services.flagged_service import get_flagged_detail, review_flagged_transaction

router = APIRouter(prefix="/flagged", tags=["flagged"])


@router.get("/{flagged_id}", response_model=FlaggedDetailResponse)
def get_flagged_detail_route(
    flagged_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FlaggedDetailResponse:
    """Retrieve detailed information for a flagged transaction.

    Includes score breakdown, plain English reasons, duplicate group members,
    and historical audit review trail.
    """
    return get_flagged_detail(db, flagged_id, current_user)


@router.patch("/{flagged_id}/review", response_model=FlaggedItemResponse)
def review_flagged_item_route(
    flagged_id: int,
    request: ReviewRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FlaggedItemResponse:
    """Update review status and append justification notes for a flagged transaction."""
    return review_flagged_transaction(db, flagged_id, request, current_user)
