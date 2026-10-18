"""Authentication and user management schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class LoginRequest(BaseModel):
    """User credential login request payload."""

    email: str = Field(pattern=EMAIL_PATTERN, description="User email address")
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    """Public user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str
    role: str
    is_active: bool = True
    created_at: datetime | None = None


class TokenResponse(BaseModel):
    """JWT access token response."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserCreateRequest(BaseModel):
    """Payload for creating a new user by a manager."""

    email: str = Field(pattern=EMAIL_PATTERN, description="User email address")
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["auditor", "manager"]
