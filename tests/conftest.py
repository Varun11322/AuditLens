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
