"""Authentication router for AuditLens."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.dependencies import get_client_ip, get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth_service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(
    request: LoginRequest,
    req: Request,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Exchange credentials for a JWT access token.

    Rate limited to 10 requests per minute per IP.
    """
    client_ip = get_client_ip(req)
    return login(db, request, client_ip)


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Retrieve profile of the currently authenticated user."""
    return UserResponse.model_validate(current_user)
