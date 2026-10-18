"""User management router for manager actions."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_manager
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import UserCreateRequest, UserResponse
from app.services.auth_service import create_user_by_manager

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(
    request: UserCreateRequest,
    current_user: Annotated[User, Depends(require_manager)],
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Create a new user account (Manager only)."""
    return create_user_by_manager(db, request, current_user)
