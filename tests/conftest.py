"""Pytest fixtures for AuditLens tests."""

from collections.abc import Generator
from urllib.parse import urlparse

import psycopg
import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import get_settings


def get_test_db_url() -> str:
    """Return database URL pointing to the auditlens_test database."""
    base_url = get_settings().database_url
    if base_url.endswith("/auditlens"):
        return base_url[: -len("/auditlens")] + "/auditlens_test"
    return base_url + "_test"


@pytest.fixture(scope="session")
def setup_test_database() -> str:
    """Ensure auditlens_test exists and is migrated to head."""
    settings = get_settings()
    default_url = settings.database_url.replace("+psycopg", "")
    test_db_url = get_test_db_url()

    parsed = urlparse(default_url)
    conn = psycopg.connect(
        dbname="auditlens",
        user=parsed.username or "auditlens",
        password=parsed.password or "auditlens_password",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        autocommit=True,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = 'auditlens_test';")
        if not cur.fetchone():
            cur.execute("CREATE DATABASE auditlens_test;")
    conn.close()

    # Apply Alembic migrations to test database
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)
    command.upgrade(alembic_cfg, "head")

    # Point SessionLocal to the test database for background tasks
    from app.db.session import SessionLocal

    test_engine = create_engine(test_db_url, pool_pre_ping=True)
    SessionLocal.configure(bind=test_engine)

    return test_db_url


@pytest.fixture
def db_session(setup_test_database: str) -> Generator[Session, None, None]:
    """Provide a clean database session for a test with automatic cleanup."""
    engine = create_engine(setup_test_database, pool_pre_ping=True)
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = testing_session_local()

    # Truncate tables before each test to guarantee test isolation
    with session.begin():
        session.execute(
            text(
                "TRUNCATE TABLE reviews, flagged_transactions, transactions, "
                "analysis_runs, uploads, audit_logs, users RESTART IDENTITY CASCADE;"
            )
        )

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator:
    """Provide a TestClient instance with get_db overridden to use db_session."""
    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app

    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def manager_user(db_session: Session):
    """Seed and return a manager user."""
    from app.core.security import hash_password
    from app.db.models.user import User

    user = User(
        email="manager@example.com",
        full_name="Test Manager",
        password_hash=hash_password("Manager123!"),
        role="manager",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def manager_token(manager_user) -> str:
    """Generate a valid JWT bearer token for manager_user."""
    from app.core.security import create_access_token

    return create_access_token(
        {"sub": str(manager_user.id), "email": manager_user.email, "role": manager_user.role}
    )


@pytest.fixture
def auditor_user(db_session: Session):
    """Seed and return a primary auditor user."""
    from app.core.security import hash_password
    from app.db.models.user import User

    user = User(
        email="auditor1@example.com",
        full_name="Primary Auditor",
        password_hash=hash_password("Auditor123!"),
        role="auditor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auditor_token(auditor_user) -> str:
    """Generate a valid JWT bearer token for auditor_user."""
    from app.core.security import create_access_token

    return create_access_token(
        {"sub": str(auditor_user.id), "email": auditor_user.email, "role": auditor_user.role}
    )


@pytest.fixture
def second_auditor(db_session: Session):
    """Seed and return a secondary auditor user for ownership isolation testing."""
    from app.core.security import hash_password
    from app.db.models.user import User

    user = User(
        email="auditor2@example.com",
        full_name="Second Auditor",
        password_hash=hash_password("Auditor2Secret!"),
        role="auditor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def second_auditor_token(second_auditor) -> str:
    """Generate a valid JWT bearer token for second_auditor."""
    from app.core.security import create_access_token

    return create_access_token(
        {"sub": str(second_auditor.id), "email": second_auditor.email, "role": second_auditor.role}
    )
