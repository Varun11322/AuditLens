"""Authentication and user management service layer."""

import logging

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, RateLimitError, UnauthorizedError
from app.core.rate_limit import get_login_rate_limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.repositories.audit_log_repo import create_audit_log
from app.repositories.user_repo import create_user as repo_create_user
from app.repositories.user_repo import get_user_by_email
from app.schemas.auth import LoginRequest, TokenResponse, UserCreateRequest, UserResponse

logger = logging.getLogger(__name__)


def login(db: Session, request: LoginRequest, client_ip: str) -> TokenResponse:
    """Authenticate credentials and generate a JWT access token.

    Args:
        db: Active database session.
        request: Login credentials payload.
        client_ip: Client IP address for rate limiting.

    Returns:
        TokenResponse: Access token and public user profile.

    Raises:
        RateLimitError: If login rate limit exceeded.
        UnauthorizedError: If credentials invalid or account inactive.
    """
    limiter = get_login_rate_limiter()
    if not limiter.is_allowed(client_ip):
        logger.warning("Login rate limit exceeded for IP %s", client_ip)
        raise RateLimitError(
            code="rate_limited",
            message="Too many login attempts. Please wait a minute and try again.",
        )

    user = get_user_by_email(db, request.email)
    if not user or not verify_password(request.password, user.password_hash):
        logger.warning("Failed login attempt for email: %s from IP: %s", request.email, client_ip)
        create_audit_log(
            db,
            action="login_failed",
            entity_type="user",
            details={"email": request.email, "ip": client_ip, "reason": "invalid_credentials"},
        )
        raise UnauthorizedError(
            code="invalid_credentials",
            message="Invalid email or password.",
        )

    if not user.is_active:
        logger.warning("Inactive account login attempt: %s", request.email)
        create_audit_log(
            db,
            action="login_failed",
            entity_type="user",
            entity_id=str(user.id),
            user_id=user.id,
            details={"email": request.email, "ip": client_ip, "reason": "inactive_user"},
        )
        raise UnauthorizedError(
            code="inactive_user",
            message="User account is inactive. Please contact an administrator.",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "role": user.role}
    )

    create_audit_log(
        db,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        details={"ip": client_ip},
    )

    logger.info("User %s successfully logged in", user.email)
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


def create_user_by_manager(
    db: Session,
    request: UserCreateRequest,
    creator: User,
) -> UserResponse:
    """Create a new user account (manager only).

    Args:
        db: Active database session.
        request: User creation payload.
        creator: Currently authenticated manager user.

    Returns:
        UserResponse: Created user profile.

    Raises:
        ConflictError: If email is already registered.
    """
    existing = get_user_by_email(db, request.email)
    if existing:
        raise ConflictError(
            code="email_exists",
            message=f"User with email '{request.email}' already exists.",
        )

    hashed_pw = hash_password(request.password)
    user = repo_create_user(
        db,
        email=request.email,
        full_name=request.full_name,
        password_hash=hashed_pw,
        role=request.role,
        is_active=True,
    )

    create_audit_log(
        db,
        action="create_user",
        entity_type="user",
        entity_id=str(user.id),
        user_id=creator.id,
        details={"email": user.email, "role": user.role},
    )

    logger.info("Manager %s created new %s user: %s", creator.email, user.role, user.email)
    return UserResponse.model_validate(user)
