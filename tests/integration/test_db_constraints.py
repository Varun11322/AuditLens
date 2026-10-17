"""Integration tests for database constraints, checks, and cascade deletions."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.analysis_run import AnalysisRun
from app.db.models.audit_log import AuditLog
from app.db.models.flagged_transaction import FlaggedTransaction
from app.db.models.review import Review
from app.db.models.transaction import Transaction
from app.db.models.upload import Upload
from app.db.models.user import User


def test_unique_email_constraint(db_session: Session) -> None:
    """Verifies users.email UNIQUE constraint rejects duplicate email registrations."""
    user1 = User(
        email="auditor@example.com",
        full_name="First Auditor",
        password_hash="hash123",
        role="auditor",
    )
    db_session.add(user1)
    db_session.commit()

    user2 = User(
        email="auditor@example.com",
        full_name="Second Auditor",
        password_hash="hash456",
        role="auditor",
    )
    db_session.add(user2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_positive_amount_check_constraint(db_session: Session) -> None:
    """Verifies ck_transactions_amount_positive rejects zero or negative amounts."""
    user = User(
        email="uploader@example.com",
        full_name="File Uploader",
        password_hash="hash123",
        role="auditor",
    )
    db_session.add(user)
    db_session.commit()

    upload = Upload(
        user_id=user.id,
        original_filename="ledger.csv",
        stored_path="/data/ledger.csv",
        file_type="csv",
    )
    db_session.add(upload)
    db_session.commit()

    now = datetime.now(UTC)

    # Test amount == 0
    zero_txn = Transaction(
        upload_id=upload.id,
        transaction_id="TXN-ZERO",
        posting_date=now,
        amount=Decimal("0.00"),
        vendor_id="VEND-001",
    )
    db_session.add(zero_txn)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Test negative amount
    neg_txn = Transaction(
        upload_id=upload.id,
        transaction_id="TXN-NEG",
        posting_date=now,
        amount=Decimal("-49.99"),
        vendor_id="VEND-001",
    )
    db_session.add(neg_txn)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Test positive amount succeeds
    valid_txn = Transaction(
        upload_id=upload.id,
        transaction_id="TXN-POS",
        posting_date=now,
        amount=Decimal("150.00"),
        vendor_id="VEND-001",
    )
    db_session.add(valid_txn)
    db_session.commit()
    assert valid_txn.id is not None


def test_unique_upload_transaction_id_constraint(db_session: Session) -> None:
    """Verifies (upload_id, transaction_id) uniqueness within each upload."""
    user = User(
        email="test_unique@example.com",
        full_name="Tester",
        password_hash="hash123",
        role="auditor",
    )
    db_session.add(user)
    db_session.commit()

    upload1 = Upload(
        user_id=user.id,
        original_filename="batch1.csv",
        stored_path="/data/batch1.csv",
        file_type="csv",
    )
    upload2 = Upload(
        user_id=user.id,
        original_filename="batch2.csv",
        stored_path="/data/batch2.csv",
        file_type="csv",
    )
    db_session.add_all([upload1, upload2])
    db_session.commit()

    now = datetime.now(UTC)

    # First transaction in upload1
    t1 = Transaction(
        upload_id=upload1.id,
        transaction_id="TXN-001",
        posting_date=now,
        amount=Decimal("100.00"),
        vendor_id="VEND-1",
    )
    db_session.add(t1)
    db_session.commit()

    # Duplicate transaction_id in same upload1 must fail
    t1_dup = Transaction(
        upload_id=upload1.id,
        transaction_id="TXN-001",
        posting_date=now,
        amount=Decimal("200.00"),
        vendor_id="VEND-2",
    )
    db_session.add(t1_dup)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Same transaction_id in different upload2 must succeed
    t2_other_upload = Transaction(
        upload_id=upload2.id,
        transaction_id="TXN-001",
        posting_date=now,
        amount=Decimal("300.00"),
        vendor_id="VEND-1",
    )
    db_session.add(t2_other_upload)
    db_session.commit()
    assert t2_other_upload.id is not None


def test_cascade_delete_upload(db_session: Session) -> None:
    """Verifies that deleting an upload cascades to transactions, runs, flagged items, and reviews.

    Also verifies that the audit log entry is preserved (retention requirement).
    """
    user = User(
        email="manager_cascade@example.com",
        full_name="Manager Cascade",
        password_hash="hash123",
        role="manager",
    )
    db_session.add(user)
    db_session.commit()

    upload = Upload(
        user_id=user.id,
        original_filename="annual_ledger.csv",
        stored_path="/data/annual_ledger.csv",
        file_type="csv",
        row_count_total=1,
        row_count_accepted=1,
    )
    db_session.add(upload)
    db_session.commit()

    now = datetime.now(UTC)
    txn = Transaction(
        upload_id=upload.id,
        transaction_id="TXN-CASCADE-1",
        posting_date=now,
        amount=Decimal("5000.00"),
        vendor_id="VEND-999",
    )
    db_session.add(txn)
    db_session.commit()

    run = AnalysisRun(
        upload_id=upload.id,
        started_by=user.id,
        settings={"flag_threshold": 30},
        status="completed",
    )
    db_session.add(run)
    db_session.commit()

    flagged = FlaggedTransaction(
        run_id=run.id,
        transaction_pk=txn.id,
        risk_score=85,
        risk_level="high",
        rule_points=40,
        ml_points=35,
        ml_norm=0.75,
        triggered_rules=["R1", "R4"],
        reasons=["Self-approval detected", "Just below limit"],
    )
    db_session.add(flagged)
    db_session.commit()

    review = Review(
        flagged_id=flagged.id,
        reviewer_id=user.id,
        status="reviewed",
        comment="Confirmed self-approval with manager.",
    )
    db_session.add(review)

    audit_entry = AuditLog(
        user_id=user.id,
        action="upload",
        entity_type="upload",
        entity_id=str(upload.id),
        details={"filename": "annual_ledger.csv"},
    )
    db_session.add(audit_entry)
    db_session.commit()

    upload_id = upload.id
    txn_id = txn.id
    run_id = run.id
    flagged_id = flagged.id
    review_id = review.id
    audit_id = audit_entry.id

    # Verify all records exist prior to deletion
    assert db_session.get(Upload, upload_id) is not None
    assert db_session.get(Transaction, txn_id) is not None
    assert db_session.get(AnalysisRun, run_id) is not None
    assert db_session.get(FlaggedTransaction, flagged_id) is not None
    assert db_session.get(Review, review_id) is not None
    assert db_session.get(AuditLog, audit_id) is not None

    # Delete the upload
    db_session.delete(upload)
    db_session.commit()

    # Clear identity map so get() performs fresh SELECT queries against the database
    db_session.expunge_all()

    # Verify CASCADE: upload, transactions, runs, flagged items, and reviews are removed
    assert db_session.get(Upload, upload_id) is None
    assert db_session.get(Transaction, txn_id) is None
    assert db_session.get(AnalysisRun, run_id) is None
    assert db_session.get(FlaggedTransaction, flagged_id) is None
    assert db_session.get(Review, review_id) is None

    # Verify audit_log is preserved
    preserved_log = db_session.get(AuditLog, audit_id)
    assert preserved_log is not None
    assert preserved_log.action == "upload"


def test_risk_score_and_level_constraints(db_session: Session) -> None:
    """Verifies check constraints on flagged_transactions risk_score and risk_level."""
    user = User(
        email="test_score@example.com",
        full_name="Tester Score",
        password_hash="hash",
        role="auditor",
    )
    db_session.add(user)
    db_session.commit()

    upload = Upload(
        user_id=user.id,
        original_filename="test.csv",
        stored_path="/data/test.csv",
        file_type="csv",
    )
    db_session.add(upload)
    db_session.commit()

    now = datetime.now(UTC)
    txn = Transaction(
        upload_id=upload.id,
        transaction_id="TXN-SCR",
        posting_date=now,
        amount=Decimal("10.00"),
        vendor_id="V1",
    )
    run = AnalysisRun(upload_id=upload.id, started_by=user.id, settings={})
    db_session.add_all([txn, run])
    db_session.commit()

    # Invalid risk_score > 100
    flagged_high = FlaggedTransaction(
        run_id=run.id,
        transaction_pk=txn.id,
        risk_score=101,
        risk_level="high",
    )
    db_session.add(flagged_high)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid risk_score < 0
    flagged_low = FlaggedTransaction(
        run_id=run.id,
        transaction_pk=txn.id,
        risk_score=-5,
        risk_level="low",
    )
    db_session.add(flagged_low)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid risk_level
    flagged_bad_level = FlaggedTransaction(
        run_id=run.id,
        transaction_pk=txn.id,
        risk_score=50,
        risk_level="critical",  # valid is high, medium, low
    )
    db_session.add(flagged_bad_level)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
