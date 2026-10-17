"""Seed initial administrator/manager account from environment variables."""

import logging
import sys

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.user import User
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """Hash a password using the bcrypt library directly.

    Args:
        password: Plain text password string.

    Returns:
        str: Bcrypt-hashed password string.
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def _seed_with_session(db: Session, email: str, password: str) -> int:
    stmt = select(User).where(User.email == email)
    existing_user = db.scalar(stmt)

    if existing_user:
        logger.info("Manager account '%s' already exists (ID: %s).", email, existing_user.id)
        return 0

    hashed = hash_password(password)
    admin_user = User(
        email=email,
        full_name="Admin Manager",
        password_hash=hashed,
        role="manager",
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    logger.info("Successfully created manager account '%s' (ID: %s).", email, admin_user.id)
    return 0


def seed_admin(db: Session | None = None) -> int:
    """Seed the initial manager account using settings from environment variables.

    Args:
        db: Optional active database session (used for testing).

    Returns:
        int: 0 on success, non-zero on error.
    """
    settings = get_settings()
    email = settings.seed_admin_email
    password = settings.seed_admin_password

    if not email or not password:
        logger.error("SEED_ADMIN_EMAIL and SEED_ADMIN_PASSWORD must be configured.")
        return 1

    if db is not None:
        return _seed_with_session(db, email, password)

    with SessionLocal() as session:
        return _seed_with_session(session, email, password)


if __name__ == "__main__":
    sys.exit(seed_admin())
