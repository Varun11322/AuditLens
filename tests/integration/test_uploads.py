"""Integration tests for file uploads, schema validation, and ownership."""

import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models.user import User


def _create_sample_csv(rows: int = 5) -> io.BytesIO:
    """Helper generating a valid in-memory canonical CSV file."""
    data = []
    for i in range(1, rows + 1):
        data.append(
            {
                "transaction_id": f"TXN-{i:04d}",
                "posting_date": f"2026-02-{i:02d} 10:00:00",
                "amount": float(i * 1000.0),
                "vendor_id": f"VEND-{i:02d}",
                "department": "Finance",
                "account_code": "ACC-100",
                "created_by": "alice",
                "approved_by": "bob",
                "description": f"Test transaction {i}",
            }
        )
    df = pd.DataFrame(data)
    out = io.BytesIO()
    df.to_csv(out, index=False)
    out.seek(0)
    return out


def test_upload_valid_csv(client: TestClient, auditor_token: str):
    """Test uploading a valid CSV file returning 201 and validation summary."""
    csv_file = _create_sample_csv(5)
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ledger.csv", csv_file, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["row_count_total"] == 5
    assert data["row_count_accepted"] == 5
    assert data["row_count_rejected"] == 0
    assert "validation_summary" in data


def test_upload_valid_xlsx(client: TestClient, auditor_token: str):
    """Test uploading a valid Excel (.xlsx) file returning 201."""
    data = [
        {
            "transaction_id": "TXN-EXCEL-01",
            "posting_date": "2026-03-01 12:00:00",
            "amount": 25000.0,
            "vendor_id": "VEND-99",
            "department": "Operations",
            "account_code": "ACC-200",
            "created_by": "carol",
            "approved_by": "dave",
            "description": "Excel upload test",
        }
    ]
    df = pd.DataFrame(data)
    out = io.BytesIO()
    df.to_excel(out, index=False)
    out.seek(0)

    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={
            "file": (
                "ledger.xlsx",
                out,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201
    assert response.json()["row_count_accepted"] == 1


def test_upload_missing_required_columns(client: TestClient, auditor_token: str):
    """Test uploading a file missing required canonical columns returns 422."""
    bad_df = pd.DataFrame(
        [
            {"amount": 500.0, "vendor_id": "VEND-01"}  # Missing transaction_id and posting_date
        ]
    )
    out = io.BytesIO()
    bad_df.to_csv(out, index=False)
    out.seek(0)

    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("invalid.csv", out, "text/csv")},
    )
    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "missing_required_columns"
    assert "missing_columns" in data["error"]["details"]


def test_upload_empty_file(client: TestClient, auditor_token: str):
    """Test uploading a zero-byte file returns 422."""
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("empty.csv", io.BytesIO(b""), "text/csv")},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "empty_file"


def test_upload_unsupported_file_type(client: TestClient, auditor_token: str):
    """Test uploading an unsupported format (e.g. .txt) returns 415."""
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("notes.txt", io.BytesIO(b"hello world"), "text/plain")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_template_download(client: TestClient, auditor_token: str):
    """Test template download requires auth (401 without token, 200 with token)."""
    # Unauthenticated request returns 401
    unauth_res = client.get("/uploads/template")
    assert unauth_res.status_code == 401

    # Authenticated request returns 200 with CSV attachment
    response = client.get(
        "/uploads/template",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().splitlines()
    assert "transaction_id,posting_date,amount,vendor_id" in lines[0]


def test_uploads_ownership_and_visibility(
    client: TestClient,
    auditor_token: str,
    second_auditor_token: str,
    manager_token: str,
):
    """Test auditor views only their own uploads, while manager views all."""
    # Auditor 1 uploads a file
    csv1 = _create_sample_csv(3)
    res1 = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("auditor1_ledger.csv", csv1, "text/csv")},
    )
    upload1_id = res1.json()["id"]

    # Auditor 2 uploads a file
    csv2 = _create_sample_csv(2)
    res2 = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {second_auditor_token}"},
        files={"file": ("auditor2_ledger.csv", csv2, "text/csv")},
    )
    upload2_id = res2.json()["id"]

    # Auditor 1 list contains upload1, not upload2
    res_a1_list = client.get(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    ids_a1 = [u["id"] for u in res_a1_list.json()["items"]]
    assert upload1_id in ids_a1
    assert upload2_id not in ids_a1

    # Auditor 1 accessing upload2 detail returns 404
    res_a1_detail = client.get(
        f"/uploads/{upload2_id}",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert res_a1_detail.status_code == 404

    # Manager list contains both uploads
    res_mgr_list = client.get(
        "/uploads",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    ids_mgr = [u["id"] for u in res_mgr_list.json()["items"]]
    assert upload1_id in ids_mgr
    assert upload2_id in ids_mgr


def test_delete_upload_cascades(
    client: TestClient,
    auditor_token: str,
    auditor_user: User,
    db_session: Session,
):
    """Test deleting an upload cascades to transactions and creates audit log."""
    csv_file = _create_sample_csv(4)
    upload_res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("to_delete.csv", csv_file, "text/csv")},
    )
    upload_id = upload_res.json()["id"]

    # Verify transactions exist in DB
    txns_count = db_session.execute(
        text("SELECT COUNT(*) FROM transactions WHERE upload_id = :u"),
        {"u": upload_id},
    ).scalar()
    assert txns_count == 4

    # Delete upload
    del_res = client.delete(
        f"/uploads/{upload_id}",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert del_res.status_code == 204

    # Confirm transactions were cascade-deleted
    txns_after = db_session.execute(
        text("SELECT COUNT(*) FROM transactions WHERE upload_id = :u"),
        {"u": upload_id},
    ).scalar()
    assert txns_after == 0

    # Confirm audit log entry was written
    log_count = db_session.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE action = 'delete_upload' AND entity_id = :e"),
        {"e": str(upload_id)},
    ).scalar()
    assert log_count >= 1


def test_upload_disguised_executable_as_csv(client: TestClient, auditor_token: str):
    """Test uploading an executable disguised as .csv is rejected with 415 invalid_file_content."""
    fake_exe = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("malware.csv", io.BytesIO(fake_exe), "text/csv")},
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "invalid_file_content"


def test_upload_corrupted_xlsx_header(client: TestClient, auditor_token: str):
    """Test uploading non-ZIP data disguised as .xlsx is rejected with 415 invalid_file_content."""
    not_a_zip = b"This is plain text with an .xlsx extension"
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={
            "file": (
                "fake.xlsx",
                io.BytesIO(not_a_zip),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 415
    data = response.json()
    assert data["error"]["code"] == "invalid_file_content"


def test_upload_csv_with_null_bytes(client: TestClient, auditor_token: str):
    """Test uploading a file with null bytes disguised as .csv is rejected with 415."""
    null_byte_data = b"transaction_id,posting_date,amount\x00,vendor_id\nTXN-1,2026-01-01,100,V-1"
    response = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("corrupt.csv", io.BytesIO(null_byte_data), "text/csv")},
    )
    assert response.status_code == 415
    assert response.json()["error"]["code"] == "invalid_file_content"
