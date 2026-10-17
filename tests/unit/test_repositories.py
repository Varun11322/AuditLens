"""Unit and repository tests for AuditLens database repositories and seed script."""

from datetime import UTC, datetime
from decimal import Decimal

import bcrypt
from sqlalchemy.orm import Session

from app.repositories.audit_log_repo import create_audit_log, get_audit_logs
from app.repositories.flagged_repo import (
    bulk_create_flagged_transactions,
    get_flagged_transactions_by_run,
)
from app.repositories.review_repo import create_review, get_reviews_by_flagged_id
from app.repositories.run_repo import (
    create_analysis_run,
    get_analysis_run_by_id,
    update_analysis_run_status,
)
from app.repositories.transaction_repo import (
    bulk_create_transactions,
    get_transactions_by_upload,
)
from app.repositories.upload_repo import create_upload, delete_upload, get_upload_by_id
from app.repositories.user_repo import create_user, get_user_by_email, get_user_by_id
from scripts.seed_admin import hash_password, seed_admin


def test_seed_admin_hash_password_and_execution(db_session: Session) -> None:
    """Test seed_admin hashing and idempotency."""
    pw = "SecretPassword123!"
    hashed = hash_password(pw)
    assert bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))

    # Execute seed_admin
    exit_code1 = seed_admin(db_session)
    assert exit_code1 == 0

    # Verify admin in database
    admin_user = get_user_by_email(db_session, "admin@example.com")
    assert admin_user is not None
    assert admin_user.role == "manager"
    assert admin_user.is_active is True

    # Re-run for idempotency
    exit_code2 = seed_admin(db_session)
    assert exit_code2 == 0


def test_user_repository(db_session: Session) -> None:
    """Test User repository functions."""
    user = create_user(
        db_session,
        email="auditor_repo@example.com",
        full_name="Repo Auditor",
        password_hash="hashed_pw",
        role="auditor",
    )
    assert user.id is not None

    fetched_by_id = get_user_by_id(db_session, user.id)
    assert fetched_by_id is not None
    assert fetched_by_id.email == "auditor_repo@example.com"

    fetched_by_email = get_user_by_email(db_session, "auditor_repo@example.com")
    assert fetched_by_email is not None
    assert fetched_by_email.id == user.id

    assert get_user_by_id(db_session, 999999) is None
    assert get_user_by_email(db_session, "nonexistent@example.com") is None


def test_upload_repository(db_session: Session) -> None:
    """Test Upload repository functions."""
    user = create_user(
        db_session,
        email="upload_user@example.com",
        full_name="Upload User",
        password_hash="pw",
        role="auditor",
    )
    upload = create_upload(
        db_session,
        user_id=user.id,
        original_filename="transactions.csv",
        stored_path="/storage/transactions.csv",
        file_type="csv",
        row_count_total=10,
        row_count_accepted=9,
        row_count_rejected=1,
        validation_summary={"rejected_reasons": {"amount_negative": 1}},
    )
    assert upload.id is not None

    fetched = get_upload_by_id(db_session, upload.id)
    assert fetched is not None
    assert fetched.original_filename == "transactions.csv"

    # Test delete
    deleted = delete_upload(db_session, upload.id)
    assert deleted is True
    assert get_upload_by_id(db_session, upload.id) is None
    assert delete_upload(db_session, upload.id) is False


def test_transaction_repository(db_session: Session) -> None:
    """Test Transaction repository bulk operations and queries."""
    user = create_user(
        db_session,
        email="txn_user@example.com",
        full_name="Txn User",
        password_hash="pw",
        role="auditor",
    )
    upload = create_upload(
        db_session,
        user_id=user.id,
        original_filename="txns.csv",
        stored_path="/storage/txns.csv",
        file_type="csv",
    )
    now = datetime.now(UTC)
    batch = [
        {
            "upload_id": upload.id,
            "transaction_id": f"TXN-{i:03d}",
            "posting_date": now,
            "amount": Decimal("100.50") + i,
            "vendor_id": f"VEND-{i % 2}",
        }
        for i in range(5)
    ]
    count = bulk_create_transactions(db_session, batch)
    assert count == 5

    txns = get_transactions_by_upload(db_session, upload.id, limit=3, offset=0)
    assert len(txns) == 3
    assert txns[0].transaction_id == "TXN-000"

    # Empty insert returns 0
    assert bulk_create_transactions(db_session, []) == 0


def test_analysis_run_repository(db_session: Session) -> None:
    """Test AnalysisRun repository functions."""
    user = create_user(
        db_session,
        email="run_user@example.com",
        full_name="Run User",
        password_hash="pw",
        role="auditor",
    )
    upload = create_upload(
        db_session,
        user_id=user.id,
        original_filename="run.csv",
        stored_path="/storage/run.csv",
        file_type="csv",
    )
    run = create_analysis_run(
        db_session,
        upload_id=upload.id,
        started_by=user.id,
        settings={"flag_threshold": 30},
    )
    assert run.id is not None
    assert run.status == "pending"

    # Update status
    updated = update_analysis_run_status(
        db_session,
        run.id,
        status="completed",
        summary={"total_flagged": 5},
    )
    assert updated is not None
    assert updated.status == "completed"
    assert updated.summary == {"total_flagged": 5}

    fetched = get_analysis_run_by_id(db_session, run.id)
    assert fetched is not None
    assert fetched.status == "completed"


def test_flagged_and_review_repositories(db_session: Session) -> None:
    """Test FlaggedTransaction and Review repositories."""
    user = create_user(
        db_session,
        email="review_user@example.com",
        full_name="Review User",
        password_hash="pw",
        role="manager",
    )
    upload = create_upload(
        db_session,
        user_id=user.id,
        original_filename="review.csv",
        stored_path="/storage/review.csv",
        file_type="csv",
    )
    now = datetime.now(UTC)
    txn_data = [
        {
            "upload_id": upload.id,
            "transaction_id": "TXN-REV-1",
            "posting_date": now,
            "amount": Decimal("250.00"),
            "vendor_id": "VEND-1",
        }
    ]
    bulk_create_transactions(db_session, txn_data)
    txn = get_transactions_by_upload(db_session, upload.id)[0]

    run = create_analysis_run(
        db_session,
        upload_id=upload.id,
        started_by=user.id,
        settings={},
    )

    flagged_records = [
        {
            "run_id": run.id,
            "transaction_pk": txn.id,
            "risk_score": 90,
            "risk_level": "high",
            "rule_points": 50,
            "ml_points": 40,
            "ml_norm": 0.8,
            "triggered_rules": ["R1", "R2"],
            "reasons": ["Self-approval", "Duplicate payment"],
            "review_status": "open",
        }
    ]
    created_count = bulk_create_flagged_transactions(db_session, flagged_records)
    assert created_count == 1

    flagged_items = get_flagged_transactions_by_run(db_session, run.id, risk_level="high")
    assert len(flagged_items) == 1
    flagged = flagged_items[0]
    assert flagged.risk_score == 90
    assert flagged.review_status == "open"

    # Create a review
    review = create_review(
        db_session,
        flagged_id=flagged.id,
        reviewer_id=user.id,
        status="false_positive",
        comment="Legitimate recurring license subscription.",
    )
    assert review.id is not None
    assert review.status == "false_positive"

    # Check that flagged_transactions cached review_status is updated
    db_session.refresh(flagged)
    assert flagged.review_status == "false_positive"

    reviews = get_reviews_by_flagged_id(db_session, flagged.id)
    assert len(reviews) == 1
    assert reviews[0].id == review.id


def test_audit_log_repository(db_session: Session) -> None:
    """Test AuditLog repository functions."""
    user = create_user(
        db_session,
        email="audit_user@example.com",
        full_name="Audit Log User",
        password_hash="pw",
        role="auditor",
    )
    log = create_audit_log(
        db_session,
        action="login",
        entity_type="user",
        entity_id=str(user.id),
        user_id=user.id,
        details={"ip": "127.0.0.1"},
    )
    assert log.id is not None
    assert log.action == "login"

    logs = get_audit_logs(db_session, user_id=user.id, action="login")
    assert len(logs) == 1
    assert logs[0].entity_id == str(user.id)
