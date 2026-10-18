"""Security utilities for password hashing and JWT token handling."""

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt directly.

    Args:
        password: Plaintext password to hash.

    Returns:
        str: Bcrypt-hashed password string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: Provided plaintext password.
        hashed_password: Stored bcrypt-hashed password.

    Returns:
        bool: True if password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Payload claims to encode into the token.
        expires_delta: Optional custom token expiration delta.

    Returns:
        str: Encoded JWT access token string.
    """
    settings = get_settings()
    to_encode = data.copy()

    now = datetime.now(UTC)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_expire_minutes)

    to_encode.update({"iat": now, "exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a signed JWT access token.

    Args:
        token: Encoded JWT token string.

    Returns:
        dict[str, Any]: Decoded payload claims.

    Raises:
        UnauthorizedError: If token is expired, invalid, or malformed.
    """
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError as e:
        raise UnauthorizedError(
            code="token_expired",
            message="Access token has expired. Please log in again.",
        ) from e
    except (jwt.InvalidTokenError, Exception) as e:
        raise UnauthorizedError(
            code="invalid_token",
            message="Invalid or malformed authorization token.",
        ) from e
