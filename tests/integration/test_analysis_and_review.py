"""Integration tests for the complete analysis, flagged review, and sign-off workflow."""

import io

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def _create_anomalous_ledger_csv() -> io.BytesIO:
    """Create a sample ledger with known rule triggers for testing the pipeline."""
    data = [
        # Normal row 1
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
        # Normal row 2
        {
            "transaction_id": "TXN-NORM-02",
            "posting_date": "2026-01-13 14:30:00",
            "amount": 22000.0,
            "vendor_id": "VEND-11",
            "department": "IT",
            "account_code": "ACC-102",
            "created_by": "alice",
            "approved_by": "bob",
            "description": "Cloud hosting fee",
        },
        # R1: Self-approval anomaly (created_by == approved_by)
        {
            "transaction_id": "TXN-ANOM-R1",
            "posting_date": "2026-01-14 10:15:00",
            "amount": 85000.0,
            "vendor_id": "VEND-20",
            "department": "Finance",
            "account_code": "ACC-101",
            "created_by": "eve",
            "approved_by": "eve",
            "description": "Self approved payment",
        },
        # R2: Duplicate pair part 1
        {
            "transaction_id": "TXN-ANOM-R2A",
            "posting_date": "2026-01-15 09:00:00",
            "amount": 54000.0,
            "vendor_id": "VEND-30",
            "department": "Logistics",
            "account_code": "ACC-103",
            "created_by": "alice",
            "approved_by": "bob",
            "description": "Freight shipment original",
        },
        # R2: Duplicate pair part 2 (same vendor, amount, within 7 days)
        {
            "transaction_id": "TXN-ANOM-R2B",
            "posting_date": "2026-01-17 11:30:00",
            "amount": 54000.0,
            "vendor_id": "VEND-30",
            "department": "Logistics",
            "account_code": "ACC-103",
            "created_by": "charlie",
            "approved_by": "david",
            "description": "Freight shipment duplicate",
        },
        # R3: Missing approver (amount >= 10000, approved_by is blank)
        {
            "transaction_id": "TXN-ANOM-R3",
            "posting_date": "2026-01-18 16:00:00",
            "amount": 45000.0,
            "vendor_id": "VEND-40",
            "department": "Marketing",
            "account_code": "ACC-104",
            "created_by": "frank",
            "approved_by": "",
            "description": "Ad campaign missing approval",
        },
        # R4: Just below limit (approval_limit=100000, amount in [90000, 100000))
        {
            "transaction_id": "TXN-ANOM-R4",
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


def test_full_analysis_review_and_signoff_flow(
    client: TestClient,
    auditor_token: str,
    second_auditor_token: str,
    manager_token: str,
    db_session: Session,
):
    """Test full audit flow: upload -> analyze -> flagged -> review -> manager sign-off."""
    # 1. Auditor uploads dataset
    csv_file = _create_anomalous_ledger_csv()
    upload_res = client.post(
        "/uploads",
        headers={"Authorization": f"Bearer {auditor_token}"},
        files={"file": ("ledger_audit.csv", csv_file, "text/csv")},
    )
    assert upload_res.status_code == 201
    upload_id = upload_res.json()["id"]

    # 2. Reject unknown/invalid settings in analysis request with 422
    invalid_settings_res = client.post(
        f"/uploads/{upload_id}/analyze",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"settings": {"unknown_threshold": 123}},
    )
    assert invalid_settings_res.status_code == 422

    # 3. Auditor 2 cannot start analysis on Auditor 1's upload (404)
    res_unauth_analyze = client.post(
        f"/uploads/{upload_id}/analyze",
        headers={"Authorization": f"Bearer {second_auditor_token}"},
    )
    assert res_unauth_analyze.status_code == 404

    # 4. Auditor 1 triggers analysis run (202 Accepted)
    analyze_res = client.post(
        f"/uploads/{upload_id}/analyze",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"settings": {"approval_limit": 100000.0, "duplicate_window_days": 7}},
    )
    assert analyze_res.status_code == 202
    run_id = analyze_res.json()["run_id"]
    assert analyze_res.json()["status"] == "pending"

    # In TestClient, BackgroundTasks run during the request cycle.
    # Check that run completed
    run_res = client.get(
        f"/runs/{run_id}",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["status"] == "completed"
    assert run_data["summary"] is not None

    # 5. List runs for upload
    runs_list_res = client.get(
        f"/uploads/{upload_id}/runs",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert runs_list_res.status_code == 200
    assert len(runs_list_res.json()) >= 1

    # 6. Check Benford endpoint (returns insufficient data because rows < 1000)
    benford_res = client.get(
        f"/runs/{run_id}/benford",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert benford_res.status_code == 200
    benford_data = benford_res.json()
    assert benford_data["available"] is False
    assert "insufficient" in benford_data["reason"].lower()

    # 7. Get flagged transactions list
    flagged_res = client.get(
        f"/runs/{run_id}/flagged",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert flagged_res.status_code == 200
    flagged_data = flagged_res.json()
    total_flagged = flagged_data["total"]
    assert total_flagged >= 4  # R1, R2A, R2B, R3, R4 flagged

    # Verify filtering by rule R1
    r1_filter_res = client.get(
        f"/runs/{run_id}/flagged?rule=R1",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert r1_filter_res.status_code == 200
    r1_items = r1_filter_res.json()["items"]
    assert len(r1_items) == 1
    assert "R1" in r1_items[0]["triggered_rules"]

    # Verify sorting by risk_score desc
    scores = [item["risk_score"] for item in flagged_data["items"]]
    assert scores == sorted(scores, reverse=True)

    # 8. Detail view of a flagged item
    first_item = flagged_data["items"][0]
    detail_res = client.get(
        f"/flagged/{first_item['id']}",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert "reasons" in detail
    assert "rule_points" in detail
    assert "ml_points" in detail
    assert "duplicate_group_members" in detail

    # 9. Test duplicate payment grouping
    dup_item = next(
        (it for it in flagged_data["items"] if it["transaction_id"] == "TXN-ANOM-R2A"),
        None,
    )
    assert dup_item is not None
    dup_detail_res = client.get(
        f"/flagged/{dup_item['id']}",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    dup_detail = dup_detail_res.json()
    assert len(dup_detail["duplicate_group_members"]) >= 1
    assert dup_detail["duplicate_group_members"][0]["transaction_id"] == "TXN-ANOM-R2B"

    # 10. Review PATCH validation: False positive requires non-empty comment
    bad_review_res = client.patch(
        f"/flagged/{first_item['id']}/review",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"status": "false_positive", "comment": ""},
    )
    assert bad_review_res.status_code == 422
    assert bad_review_res.json()["error"]["code"] == "comment_required"

    # 11. Auditor 2 cannot review Auditor 1's flagged item (404)
    unauth_review = client.patch(
        f"/flagged/{first_item['id']}/review",
        headers={"Authorization": f"Bearer {second_auditor_token}"},
        json={"status": "reviewed", "comment": "Unauthorized review attempt"},
    )
    assert unauth_review.status_code == 404

    # 12. Manager cannot sign off while open review items remain (409)
    premature_signoff = client.post(
        f"/runs/{run_id}/sign-off",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert premature_signoff.status_code == 409
    assert premature_signoff.json()["error"]["code"] == "open_reviews_remaining"

    # 13. Auditor reviews all flagged items
    for item in flagged_data["items"]:
        rev_res = client.patch(
            f"/flagged/{item['id']}/review",
            headers={"Authorization": f"Bearer {auditor_token}"},
            json={
                "status": "reviewed",
                "comment": f"Audited transaction {item['transaction_id']}",
            },
        )
        assert rev_res.status_code == 200
        assert rev_res.json()["review_status"] == "reviewed"

    # 14. Non-manager cannot sign off (403 Forbidden)
    auditor_signoff = client.post(
        f"/runs/{run_id}/sign-off",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert auditor_signoff.status_code == 403
    assert auditor_signoff.json()["error"]["code"] == "forbidden"

    # 15. Manager signs off successfully (200 OK)
    manager_signoff = client.post(
        f"/runs/{run_id}/sign-off",
        headers={"Authorization": f"Bearer {manager_token}"},
    )
    assert manager_signoff.status_code == 200
    signed_run = manager_signoff.json()
    assert signed_run["signed_off_by"] is not None
    assert signed_run["signed_off_at"] is not None

    # 16. Attempting to review an item after sign-off is rejected with 409
    post_signoff_review = client.patch(
        f"/flagged/{first_item['id']}/review",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={"status": "needs_follow_up", "comment": "Post signoff attempt"},
    )
    assert post_signoff_review.status_code == 409
    assert post_signoff_review.json()["error"]["code"] == "run_signed_off"
