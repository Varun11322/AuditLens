"""Integration tests for POST /runs/{run_id}/evaluate endpoint (Phase 7)."""

import io
from datetime import UTC, datetime

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.analysis_run import AnalysisRun
from app.db.models.upload import Upload
from app.db.models.user import User
from app.services.analysis_service import execute_analysis_pipeline


def _create_test_ledger_csv() -> io.BytesIO:
    """Create a sample ledger with normal and anomalous transactions."""
    data = [
        {
            "transaction_id": "TXN-NORM-01",
            "posting_date": "2026-01-12 11:00:00",
            "amount": 15000.0,
            "vendor_id": "VEND-10",
            "department": "Finance",
            "account_code": "ACC-101",
            "created_by": "alice",
            "approved_by": "bob",
            "description": "Standard software subscription",
        },
        {
            "transaction_id": "TXN-R1-01",
            "posting_date": "2026-01-14 10:15:00",
            "amount": 85000.0,
            "vendor_id": "VEND-20",
            "department": "Finance",
            "account_code": "ACC-101",
            "created_by": "eve",
            "approved_by": "eve",
            "description": "Self approved payment",
        },
        {
            "transaction_id": "TXN-R4-01",
            "posting_date": "2026-01-19 13:00:00",
            "amount": 98500.0,
            "vendor_id": "VEND-50",
            "department": "Legal",
            "account_code": "ACC-105",
            "created_by": "grace",
            "approved_by": "heidi",
            "description": "Consulting invoice split",
        },
    ]
    df = pd.DataFrame(data)
    out = io.BytesIO()
    df.to_csv(out, index=False)
    out.seek(0)
    return out


def _create_ground_truth_csv() -> io.BytesIO:
    """Create a matching ground truth CSV."""
    data = [
        {
            "transaction_id": "TXN-R1-01",
            "anomaly_types": "self_approval",
            "related_transaction_id": "",
        },
        {
            "transaction_id": "TXN-R4-01",
            "anomaly_types": "just_below_limit",
            "related_transaction_id": "",
        },
    ]
    df = pd.DataFrame(data)
    out = io.BytesIO()
    df.to_csv(out, index=False)
    out.seek(0)
    return out


def test_evaluate_valid_file(
    client: TestClient,
    auditor_token: str,
):
    """Test evaluation on a completed run with a valid ground truth CSV."""
    # 1. Upload ledger
    csv_file = _create_test_ledger_csv()
    up_res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("test_eval_ledger.csv", csv_file, "text/csv")},
    )
    assert up_res.status_code == 201
    upload_id = up_res.json()["id"]

    # 2. Run analysis
    run_res = client.post(
        f"/uploads/{upload_id}/analyze",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"settings": {"approval_limit": 100000.0, "flag_threshold": 20}},
    )
    assert run_res.status_code == 202
    run_id = run_res.json()["run_id"]

    # Execute pipeline synchronously
    execute_analysis_pipeline(run_id)

    # 3. Submit valid ground truth CSV
    gt_file = _create_ground_truth_csv()
    eval_res = client.post(
        f"/runs/{run_id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.csv", gt_file, "text/csv")},
    )
    assert eval_res.status_code == 200
    metrics = eval_res.json()

    # 4. Verify metrics structure per docs/API.md
    assert "strict_precision" in metrics
    assert "audit_adjusted_precision" in metrics
    assert "overall_recall" in metrics
    assert "recall_by_type" in metrics
    assert "total_flagged" in metrics
    assert "total_anomalies" in metrics
    assert "explanation" in metrics

    assert metrics["total_anomalies"] == 2
    assert metrics["recall_by_type"]["self_approval"]["total_injected"] == 1
    assert metrics["recall_by_type"]["self_approval"]["detected"] == 1
    assert metrics["recall_by_type"]["self_approval"]["recall"] == 1.0


def test_evaluate_bad_file_types_and_content(
    client: TestClient,
    auditor_token: str,
):
    """Test rejection with 422 for non-CSV, malformed, empty, or missing required columns."""
    # 1. Setup completed run
    csv_file = _create_test_ledger_csv()
    up_res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("test_eval_bad.csv", csv_file, "text/csv")},
    )
    assert up_res.status_code == 201
    upload_id = up_res.json()["id"]

    run_res = client.post(
        f"/uploads/{upload_id}/analyze",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    run_id = run_res.json()["run_id"]
    execute_analysis_pipeline(run_id)

    # A. Non-CSV extension
    bad_ext = io.BytesIO(b"some content")
    res_ext = client.post(
        f"/runs/{run_id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.txt", bad_ext, "text/plain")},
    )
    assert res_ext.status_code == 422
    assert res_ext.json()["error"]["code"] == "invalid_ground_truth_file"

    # B. Empty file
    empty_f = io.BytesIO(b"")
    res_empty = client.post(
        f"/runs/{run_id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.csv", empty_f, "text/csv")},
    )
    assert res_empty.status_code == 422

    # C. Missing required columns
    bad_cols_f = io.BytesIO(b"transaction_id,some_other_column\nTXN-01,val1\n")
    res_cols = client.post(
        f"/runs/{run_id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.csv", bad_cols_f, "text/csv")},
    )
    assert res_cols.status_code == 422
    assert res_cols.json()["error"]["code"] == "missing_required_columns"


def test_evaluate_ownership_and_role_access(
    client: TestClient,
    auditor_token: str,
    manager_token: str,
    db_session: Session,
):
    """Test that auditors can only evaluate their own runs, while managers can evaluate any."""
    # 1. Create run owned by manager
    manager = db_session.query(User).filter_by(role="manager").first()
    upload = Upload(
        user_id=manager.id,
        original_filename="mgr_ledger.csv",
        stored_path="uploads/mgr_eval.csv",
        file_type="csv",
        row_count_total=1,
        row_count_accepted=1,
        row_count_rejected=0,
        validation_summary={"total_rows": 1, "valid_rows": 1},
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    run = AnalysisRun(
        upload_id=upload.id,
        started_by=manager.id,
        status="completed",
        settings={"approval_limit": 100000.0, "flag_threshold": 30},
        summary={"scoring": {"total_flagged": 0}},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    # 2. Auditor attempts to evaluate Manager's run -> 404 (ownership check returns 404)
    gt_file = _create_ground_truth_csv()
    auditor_res = client.post(
        f"/runs/{run.id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.csv", gt_file, "text/csv")},
    )
    assert auditor_res.status_code == 404

    # 3. Manager evaluates the run -> 200
    gt_file.seek(0)
    mgr_res = client.post(
        f"/runs/{run.id}/evaluate",
        headers={"Authorization": f"Bearer {manager_token}"},
        files={"file": ("ground_truth.csv", gt_file, "text/csv")},
    )
    assert mgr_res.status_code == 200


def test_evaluate_run_not_completed_conflict(
    client: TestClient,
    auditor_token: str,
    db_session: Session,
):
    """Test that evaluating a run that is not completed returns 409 Conflict."""
    auditor = db_session.query(User).filter_by(role="auditor").first()
    upload = Upload(
        user_id=auditor.id,
        original_filename="pending_ledger.csv",
        stored_path="uploads/pending_eval.csv",
        file_type="csv",
        row_count_total=1,
        row_count_accepted=1,
        row_count_rejected=0,
        validation_summary={"total_rows": 1, "valid_rows": 1},
    )
    db_session.add(upload)
    db_session.commit()
    db_session.refresh(upload)

    run = AnalysisRun(
        upload_id=upload.id,
        started_by=auditor.id,
        status="pending",
        settings={},
        summary={},
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    gt_file = _create_ground_truth_csv()
    res = client.post(
        f"/runs/{run.id}/evaluate",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ground_truth.csv", gt_file, "text/csv")},
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "run_not_completed"
