"""HTTP client for communicating with the AuditLens FastAPI backend."""

import os
from typing import Any

import httpx

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")


class ApiClientError(Exception):
    """Base exception for API communication errors."""

    def __init__(self, message: str, status_code: int | None = None, details: Any = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details


class AuthenticationError(ApiClientError):
    """Raised on 401 Unauthorized errors (session expired or invalid credentials)."""


class ForbiddenError(ApiClientError):
    """Raised on 403 Forbidden errors (e.g. auditor attempting manager actions)."""


class NotFoundError(ApiClientError):
    """Raised on 404 Not Found errors."""


class ConflictError(ApiClientError):
    """Raised on 409 Conflict errors (e.g. signing off with open items)."""


class ValidationError(ApiClientError):
    """Raised on 422 Unprocessable Entity errors."""


class RateLimitError(ApiClientError):
    """Raised on 429 Too Many Requests errors."""


def _handle_response_error(response: httpx.Response) -> None:
    """Parse API standard error format and raise the appropriate exception."""
    status_code = response.status_code
    message = f"Request failed with status code {status_code}"
    details = None

    try:
        data = response.json()
        if isinstance(data, dict):
            if "error" in data and isinstance(data["error"], dict):
                message = data["error"].get("message", message)
                details = data["error"].get("details")
            elif "detail" in data:
                message = str(data["detail"])
    except Exception:
        message = response.text or message

    if status_code == 401:
        raise AuthenticationError(message, status_code=status_code, details=details)
    if status_code == 403:
        raise ForbiddenError(message, status_code=status_code, details=details)
    if status_code == 404:
        raise NotFoundError(message, status_code=status_code, details=details)
    if status_code == 409:
        raise ConflictError(message, status_code=status_code, details=details)
    if status_code == 422:
        raise ValidationError(message, status_code=status_code, details=details)
    if status_code == 429:
        raise RateLimitError(message, status_code=status_code, details=details)

    raise ApiClientError(message, status_code=status_code, details=details)


class ApiClient:
    """Encapsulated client for all AuditLens REST API endpoints."""

    def __init__(self, base_url: str = API_BASE_URL, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self, token: str | None = None) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate with email and password and receive a JWT token."""
        url = f"{self.base_url}/auth/login"
        payload = {"email": email, "password": password}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._headers())
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_me(self, token: str) -> dict[str, Any]:
        """Retrieve profile of currently authenticated user."""
        url = f"{self.base_url}/auth/me"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def upload_file(self, token: str, file_bytes: bytes, filename: str) -> dict[str, Any]:
        """Upload and validate a transaction file (.csv or .xlsx)."""
        url = f"{self.base_url}/uploads"
        files = {"file": (filename, file_bytes)}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, files=files, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def list_uploads(self, token: str, page: int = 1, page_size: int = 50) -> dict[str, Any]:
        """List transaction uploads visible to the authenticated user."""
        url = f"{self.base_url}/uploads"
        params = {"page": page, "page_size": page_size}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_upload(self, token: str, upload_id: int) -> dict[str, Any]:
        """Retrieve upload validation summary and record counts."""
        url = f"{self.base_url}/uploads/{upload_id}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def delete_upload(self, token: str, upload_id: int) -> None:
        """Delete an upload and cascade-delete all related transactions and runs."""
        url = f"{self.base_url}/uploads/{upload_id}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.delete(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)

    def get_template_csv(self, token: str) -> bytes:
        """Download the standard CSV template."""
        url = f"{self.base_url}/uploads/template"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.content

    def start_analysis(
        self, token: str, upload_id: int, settings: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Trigger an analysis pipeline run on an upload."""
        url = f"{self.base_url}/uploads/{upload_id}/analyze"
        payload = {"settings": settings} if settings else {}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_run(self, token: str, run_id: int) -> dict[str, Any]:
        """Fetch analysis run status, configuration settings, and summary metrics."""
        url = f"{self.base_url}/runs/{run_id}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def list_runs_for_upload(self, token: str, upload_id: int) -> list[dict[str, Any]]:
        """List all analysis runs associated with an upload."""
        url = f"{self.base_url}/uploads/{upload_id}/runs"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_benford(self, token: str, run_id: int) -> dict[str, Any]:
        """Fetch Benford's Law analysis results."""
        url = f"{self.base_url}/runs/{run_id}/benford"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def sign_off_run(self, token: str, run_id: int) -> dict[str, Any]:
        """Official manager sign-off for a completed analysis run."""
        url = f"{self.base_url}/runs/{run_id}/sign-off"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def list_flagged(
        self,
        token: str,
        run_id: int,
        page: int = 1,
        page_size: int = 50,
        risk_level: list[str] | None = None,
        rule: list[str] | None = None,
        vendor_id: str | None = None,
        department: str | None = None,
        review_status: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        amount_min: float | None = None,
        amount_max: float | None = None,
        sort_by: str = "risk_score",
        sort_dir: str = "desc",
    ) -> dict[str, Any]:
        """Retrieve paginated and filtered flagged transactions for a run."""
        url = f"{self.base_url}/runs/{run_id}/flagged"
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        }
        if risk_level:
            params["risk_level"] = risk_level
        if rule:
            params["rule"] = rule
        if vendor_id:
            params["vendor_id"] = vendor_id
        if department:
            params["department"] = department
        if review_status and review_status != "all":
            params["review_status"] = review_status
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if amount_min is not None:
            params["amount_min"] = amount_min
        if amount_max is not None:
            params["amount_max"] = amount_max

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_flagged_detail(self, token: str, flagged_id: int) -> dict[str, Any]:
        """Retrieve transaction detail, risk breakdown, duplicate group, and review logs."""
        url = f"{self.base_url}/flagged/{flagged_id}"
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def review_flagged(
        self,
        token: str,
        flagged_id: int,
        status: str,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Record an auditor review decision and justification comment."""
        url = f"{self.base_url}/flagged/{flagged_id}/review"
        payload = {"status": status, "comment": comment}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.patch(url, json=payload, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()

    def get_report(self, token: str, run_id: int, format: str = "xlsx") -> bytes:
        """Download the Excel audit report (.xlsx) for a completed analysis run."""
        url = f"{self.base_url}/runs/{run_id}/report"
        params = {"format": format}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.get(url, params=params, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.content

    def evaluate_run(
        self,
        token: str,
        run_id: int,
        file_content: bytes,
        filename: str = "ground_truth.csv",
    ) -> dict[str, Any]:
        """Submit ground truth CSV for benchmarking a completed analysis run."""
        url = f"{self.base_url}/runs/{run_id}/evaluate"
        files = {"file": (filename, file_content, "text/csv")}
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, files=files, headers=self._headers(token))
            if resp.is_error:
                _handle_response_error(resp)
            return resp.json()


# Shared singleton client instance
api_client = ApiClient()
