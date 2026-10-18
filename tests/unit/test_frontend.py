"""Unit tests for frontend API client, exceptions, badges, and chart builders."""

from unittest.mock import patch

import httpx
import pytest

from frontend.api_client import (
    ApiClient,
    ApiClientError,
    AuthenticationError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from frontend.components.badges import format_currency, get_risk_badge_html, get_status_badge_html
from frontend.components.charts import (
    create_benford_chart,
    create_risk_distribution_chart,
    create_rule_counts_chart,
    create_timeline_chart,
    create_top_vendors_chart,
)


def test_api_client_headers():
    client = ApiClient(base_url="http://testserver:8000")
    h_no_token = client._headers()
    assert "Authorization" not in h_no_token
    assert h_no_token["Accept"] == "application/json"

    h_with_token = client._headers("test-jwt-token")
    assert h_with_token["Authorization"] == "Bearer test-jwt-token"


def test_api_client_error_handling_statuses():
    client = ApiClient(base_url="http://testserver:8000")

    def mock_response(status_code: int, json_data: dict):
        resp = httpx.Response(
            status_code=status_code,
            json=json_data,
            request=httpx.Request("POST", "http://testserver:8000/auth/login"),
        )
        return resp

    # 401
    with patch(
        "httpx.Client.post",
        return_value=mock_response(401, {"error": {"message": "Invalid creds"}}),
    ):
        with pytest.raises(AuthenticationError) as exc_info:
            client.login("admin@example.com", "wrong")
        assert "Invalid creds" in str(exc_info.value)
        assert exc_info.value.status_code == 401

    # 403
    with patch(
        "httpx.Client.post",
        return_value=mock_response(403, {"error": {"message": "Managers only"}}),
    ):
        with pytest.raises(ForbiddenError) as exc_info:
            client.sign_off_run("token", 1)
        assert "Managers only" in str(exc_info.value)

    # 404
    with patch(
        "httpx.Client.get", return_value=mock_response(404, {"error": {"message": "Run not found"}})
    ):
        with pytest.raises(NotFoundError) as exc_info:
            client.get_run("token", 999)
        assert "Run not found" in str(exc_info.value)

    # 409
    with patch(
        "httpx.Client.post",
        return_value=mock_response(409, {"error": {"message": "Items still open"}}),
    ):
        with pytest.raises(ConflictError) as exc_info:
            client.sign_off_run("token", 1)
        assert "Items still open" in str(exc_info.value)

    # 422
    with patch(
        "httpx.Client.post",
        return_value=mock_response(422, {"error": {"message": "Validation failed"}}),
    ):
        with pytest.raises(ValidationError) as exc_info:
            client.start_analysis("token", 1, {"unknown_key": 123})
        assert "Validation failed" in str(exc_info.value)

    # 429
    with patch(
        "httpx.Client.post",
        return_value=mock_response(429, {"error": {"message": "Rate limit exceeded"}}),
    ):
        with pytest.raises(RateLimitError) as exc_info:
            client.login("admin@example.com", "pass")
        assert "Rate limit exceeded" in str(exc_info.value)

    # 500
    with patch(
        "httpx.Client.get", return_value=mock_response(500, {"detail": "Internal server error"})
    ):
        with pytest.raises(ApiClientError) as exc_info:
            client.get_me("token")
        assert "Internal server error" in str(exc_info.value)


def test_api_client_successful_methods():
    client = ApiClient(base_url="http://testserver:8000")

    # Login
    with patch(
        "httpx.Client.post",
        return_value=httpx.Response(
            200,
            json={
                "access_token": "token123",
                "user": {"id": 1, "email": "a@b.com", "role": "manager"},
            },
            request=httpx.Request("POST", "http://testserver:8000/auth/login"),
        ),
    ):
        res = client.login("a@b.com", "pass")
        assert res["access_token"] == "token123"

    # Upload file
    with patch(
        "httpx.Client.post",
        return_value=httpx.Response(
            201,
            json={"id": 10, "row_count_accepted": 500, "validation_summary": {}},
            request=httpx.Request("POST", "http://testserver:8000/uploads"),
        ),
    ):
        res = client.upload_file("token123", b"test,content", "test.csv")
        assert res["id"] == 10

    # List uploads
    with patch(
        "httpx.Client.get",
        return_value=httpx.Response(
            200,
            json={"items": [{"id": 1}], "total": 1},
            request=httpx.Request("GET", "http://testserver:8000/uploads"),
        ),
    ):
        res = client.list_uploads("token123", 1, 50)
        assert res["total"] == 1

    # Start analysis
    with patch(
        "httpx.Client.post",
        return_value=httpx.Response(
            202,
            json={"run_id": 5, "status": "pending"},
            request=httpx.Request("POST", "http://testserver:8000/uploads/10/analyze"),
        ),
    ):
        res = client.start_analysis("token123", 10, {"approval_limit": 50000.0})
        assert res["run_id"] == 5

    # List flagged
    with patch(
        "httpx.Client.get",
        return_value=httpx.Response(
            200,
            json={"items": [{"id": 1, "risk_score": 85}], "total": 1},
            request=httpx.Request("GET", "http://testserver:8000/runs/5/flagged"),
        ),
    ):
        res = client.list_flagged("token123", 5, page=1, page_size=50)
        assert len(res["items"]) == 1

    # Review flagged
    with patch(
        "httpx.Client.patch",
        return_value=httpx.Response(
            200,
            json={"id": 1, "review_status": "reviewed"},
            request=httpx.Request("PATCH", "http://testserver:8000/flagged/1/review"),
        ),
    ):
        res = client.review_flagged("token123", 1, status="reviewed", comment="Verified sample")
        assert res["review_status"] == "reviewed"


def test_badge_and_formatting_helpers():
    assert format_currency(1234567.89) == "₹ 1,234,567.89"
    assert format_currency(None) == "₹ 0.00"

    badge_high = get_risk_badge_html("high")
    assert "HIGH" in badge_high
    assert "#C0392B" in badge_high

    badge_status = get_status_badge_html("needs_follow_up")
    assert "Needs Follow-up" in badge_status


def test_plotly_chart_builders():
    # Risk chart
    fig1 = create_risk_distribution_chart({"high": 10, "medium": 20, "low": 30})
    assert len(fig1.data) == 1
    assert list(fig1.data[0].x) == ["High", "Medium", "Low"]

    # Rule counts chart
    fig2 = create_rule_counts_chart({"R1": 5, "R2": 3})
    assert len(fig2.data) == 1

    # Timeline chart
    fig3 = create_timeline_chart([{"date": "2024-01-01", "count": 10}])
    assert len(fig3.data) == 1

    # Top vendors chart
    fig4 = create_top_vendors_chart([{"vendor_id": "V1", "amount": 1000.0}])
    assert len(fig4.data) == 1

    # Benford chart
    fig5 = create_benford_chart({1: 0.301}, {1: 0.301})
    assert len(fig5.data) == 2
