"""User repository functions."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import User


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Retrieve a user by primary key ID.

    Args:
        db: Active database session.
        user_id: User primary key ID.

    Returns:
        User | None: The user entity if found, else None.
    """
    return db.get(User, user_id)


def get_user_by_email(db: Session, email: str) -> User | None:
    """Retrieve a user by unique email.

    Args:
        db: Active database session.
        email: User email address.

    Returns:
        User | None: The user entity if found, else None.
    """
    stmt = select(User).where(User.email == email)
    return db.scalar(stmt)


def create_user(
    db: Session,
    *,
    email: str,
    full_name: str,
    password_hash: str,
    role: str,
    is_active: bool = True,
) -> User:
    """Create and persist a new user record.

    Args:
        db: Active database session.
        email: Unique email address.
        full_name: Full name of the user.
        password_hash: Hashed password string.
        role: Account role ('auditor' or 'manager').
        is_active: Active status flag.

    Returns:
        User: Created user instance.
    """
    user = User(
        email=email,
        full_name=full_name,
        password_hash=password_hash,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
