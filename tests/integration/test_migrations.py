"""Integration tests for Alembic migration upgrade and downgrade on a fresh database."""

from urllib.parse import urlparse

import psycopg
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.config import get_settings


def test_migration_upgrade_and_downgrade_fresh_database() -> None:
    """Test applying migrations from scratch, reverting them completely, and re-applying."""
    settings = get_settings()
    default_url = settings.database_url.replace("+psycopg", "")
    parsed = urlparse(default_url)

    mig_db_name = "auditlens_mig_test"
    mig_db_url = f"postgresql+psycopg://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port}/{mig_db_name}"

    # Drop and recreate fresh auditlens_mig_test database
    conn = psycopg.connect(
        dbname="auditlens",
        user=parsed.username or "auditlens",
        password=parsed.password or "auditlens_password",
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        autocommit=True,
    )
    with conn.cursor() as cur:
        # Terminate any active connections to mig_db_name
        cur.execute(
            """
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = %s
              AND pid <> pg_backend_pid();
            """,
            (mig_db_name,),
        )
        cur.execute(f"DROP DATABASE IF EXISTS {mig_db_name};")
        cur.execute(f"CREATE DATABASE {mig_db_name};")
    conn.close()

    try:
        # Step 1: Upgrade to head
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", mig_db_url)
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(mig_db_url, pool_pre_ping=True)
        inspector = inspect(engine)
        tables_after_upgrade = set(inspector.get_table_names())

        expected_tables = {
            "users",
            "uploads",
            "transactions",
            "analysis_runs",
            "flagged_transactions",
            "reviews",
            "audit_logs",
            "alembic_version",
        }
        assert expected_tables.issubset(tables_after_upgrade), (
            f"Missing tables after upgrade: {expected_tables - tables_after_upgrade}"
        )

        # Step 2: Downgrade to base
        engine.dispose()
        command.downgrade(alembic_cfg, "base")

        engine = create_engine(mig_db_url, pool_pre_ping=True)
        inspector = inspect(engine)
        tables_after_downgrade = set(inspector.get_table_names())

        # Domain tables should be completely dropped on downgrade to base
        domain_tables = expected_tables - {"alembic_version"}
        remaining_domain_tables = domain_tables.intersection(tables_after_downgrade)
        assert len(remaining_domain_tables) == 0, (
            f"Tables remained after downgrade to base: {remaining_domain_tables}"
        )

        # Step 3: Upgrade to head again
        engine.dispose()
        command.upgrade(alembic_cfg, "head")

        engine = create_engine(mig_db_url, pool_pre_ping=True)
        inspector = inspect(engine)
        tables_reupgraded = set(inspector.get_table_names())
        assert expected_tables.issubset(tables_reupgraded)
        engine.dispose()

    finally:
        # Teardown: drop test database
        conn = psycopg.connect(
            dbname="auditlens",
            user=parsed.username or "auditlens",
            password=parsed.password or "auditlens_password",
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            autocommit=True,
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s
                  AND pid <> pg_backend_pid();
                """,
                (mig_db_name,),
            )
            cur.execute(f"DROP DATABASE IF EXISTS {mig_db_name};")
        conn.close()
