"""FastAPI dependency injection utilities for database and authentication."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.repositories.user_repo import get_user_by_id

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
    db: Annotated[Session, Depends(get_db)] = None,
) -> User:
    """Validate Bearer JWT token and return authenticated active User.

    Args:
        auth: Bearer token credentials from HTTP header.
        db: Active database session.

    Returns:
        User: Currently authenticated user model.

    Raises:
        UnauthorizedError: If authorization header is missing, token invalid,
            or user does not exist or is inactive.
    """
    if auth is None or not auth.credentials:
        raise UnauthorizedError(
            code="unauthorized",
            message="Authorization token is missing or malformed.",
        )

    payload = decode_access_token(auth.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(
            code="invalid_token",
            message="Token payload is missing subject claim.",
        )

    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError) as e:
        raise UnauthorizedError(
            code="invalid_token",
            message="Invalid subject claim format in token.",
        ) from e

    user = get_user_by_id(db, user_id_int)
    if user is None:
        raise UnauthorizedError(
            code="user_not_found",
            message="User account associated with this token was not found.",
        )

    if not user.is_active:
        raise UnauthorizedError(
            code="inactive_user",
            message="User account is inactive. Please contact your administrator.",
        )

    return user


def require_role(*allowed_roles: str) -> Callable[[User], User]:
    """Dependency factory enforcing allowed user roles.

    Args:
        *allowed_roles: List of accepted role names (e.g. 'manager', 'auditor').

    Returns:
        Callable dependency that verifies user.role.
    """

    def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenError(
                code="forbidden",
                message=f"Access denied. Requires one of roles: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker


require_manager = require_role("manager")
require_auditor_or_manager = require_role("auditor", "manager")


def get_client_ip(request: Request) -> str:
    """Extract client IP address from request, considering proxy headers.

    Args:
        request: Incoming FastAPI request.

    Returns:
        str: Client IP string.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"
