"""Integration tests for authentication, user management, and rate limiting."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.rate_limit import get_login_rate_limiter
from app.core.security import hash_password
from app.db.models.user import User


def test_login_success(client: TestClient, auditor_user: User):
    """Test successful user login returning valid JWT."""
    get_login_rate_limiter().reset()
    response = client.post(
        "/auth/login",
        json={"email": auditor_user.email, "password": "Auditor123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == auditor_user.email
    assert data["user"]["role"] == "auditor"


def test_login_wrong_password(client: TestClient, auditor_user: User):
    """Test login failure with invalid password returning 401."""
    get_login_rate_limiter().reset()
    response = client.post(
        "/auth/login",
        json={"email": auditor_user.email, "password": "IncorrectPassword"},
    )
    assert response.status_code == 401
    data = response.json()
    assert data["error"]["code"] == "invalid_credentials"


def test_login_unknown_email(client: TestClient):
    """Test login failure with unregistered email returning 401."""
    get_login_rate_limiter().reset()
    response = client.post(
        "/auth/login",
        json={"email": "nonexistent@example.com", "password": "AnyPassword123!"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


def test_login_inactive_user(client: TestClient, db_session: Session):
    """Test login rejected for inactive account returning 401."""
    get_login_rate_limiter().reset()
    inactive_user = User(
        email="inactive@example.com",
        full_name="Disabled User",
        password_hash=hash_password("Password123!"),
        role="auditor",
        is_active=False,
    )
    db_session.add(inactive_user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "inactive_user"


def test_login_rate_limiting(client: TestClient, auditor_user: User):
    """Test login rate limiting triggers 429 on exceeding 10 requests per minute."""
    limiter = get_login_rate_limiter()
    limiter.reset()

    # Perform 10 requests (all allowed under rate limit)
    for _ in range(10):
        client.post(
            "/auth/login",
            json={"email": auditor_user.email, "password": "BadPassword"},
        )

    # 11th request must be rate limited with 429
    res = client.post(
        "/auth/login",
        json={"email": auditor_user.email, "password": "Auditor123!"},
    )
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"

    # Reset limiter after test
    limiter.reset()


def test_auth_me_authenticated(client: TestClient, auditor_user: User, auditor_token: str):
    """Test /auth/me returns current user profile when authenticated."""
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {auditor_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == auditor_user.id
    assert data["email"] == auditor_user.email
    assert data["role"] == "auditor"


def test_auth_me_unauthenticated(client: TestClient):
    """Test /auth/me rejects missing token with 401."""
    response = client.get("/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


def test_manager_can_create_user(client: TestClient, manager_token: str):
    """Test manager creates an auditor user returning 201."""
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "email": "new.auditor@example.com",
            "full_name": "New Auditor",
            "password": "Password123!",
            "role": "auditor",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new.auditor@example.com"
    assert data["role"] == "auditor"


def test_auditor_cannot_create_user(client: TestClient, auditor_token: str):
    """Test non-manager cannot create users returning 403."""
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {auditor_token}"},
        json={
            "email": "fail@example.com",
            "full_name": "Forbidden User",
            "password": "Password123!",
            "role": "auditor",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_create_user_duplicate_email(client: TestClient, manager_token: str, auditor_user: User):
    """Test creating user with duplicate email returns 409 conflict."""
    response = client.post(
        "/users",
        headers={"Authorization": f"Bearer {manager_token}"},
        json={
            "email": auditor_user.email,
            "full_name": "Duplicate User",
            "password": "Password123!",
            "role": "auditor",
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_exists"
