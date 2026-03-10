"""Smoke tests for auth endpoints, org-by-slug, and org creation with owner."""

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Set up admin secret and return headers for admin-protected endpoints."""
    original_secret = settings.BXB_ADMIN_SECRET
    test_secret = "smoke-test-admin-secret-that-is-at-least-32-chars-long"
    settings.BXB_ADMIN_SECRET = test_secret
    yield {"X-Admin-Secret": test_secret}
    settings.BXB_ADMIN_SECRET = original_secret


@pytest.fixture
def org_with_owner(client: TestClient, admin_headers: dict):
    """Create an organization with a bootstrapped owner user."""
    resp = client.post(
        "/v1/organizations/",
        headers=admin_headers,
        json={
            "name": "Auth Test Org",
            "owner_email": "owner@authtest.com",
            "owner_name": "Auth Owner",
            "owner_password": "securepass123",
        },
    )
    assert resp.status_code == 201
    return resp.json()


def test_create_org_with_owner(org_with_owner):
    """POST /v1/organizations/ with owner fields creates user and membership."""
    data = org_with_owner
    assert "owner" in data
    assert data["owner"]["email"] == "owner@authtest.com"
    assert "user_id" in data["owner"]


def test_get_org_by_slug(client: TestClient, org_with_owner):
    """GET /v1/organizations/by-slug/{slug} returns branding (no secrets)."""
    slug = org_with_owner["slug"]
    resp = client.get(f"/v1/organizations/by-slug/{slug}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Auth Test Org"
    assert data["slug"] == slug
    # Should NOT contain secret fields
    assert "id" not in data
    assert "hmac_key" not in data
    assert "api_key" not in data


def test_get_org_by_slug_not_found(client: TestClient):
    """GET /v1/organizations/by-slug/nonexistent returns 404."""
    resp = client.get("/v1/organizations/by-slug/nonexistent-slug-xyz")
    assert resp.status_code == 404


def test_login_success(client: TestClient, org_with_owner):
    """POST /v1/auth/login with correct credentials returns JWT token."""
    resp = client.post(
        "/v1/auth/login",
        json={
            "email": "owner@authtest.com",
            "password": "securepass123",
            "org_slug": org_with_owner["slug"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "owner@authtest.com"
    assert data["role"] == "owner"


def test_login_wrong_password(client: TestClient, org_with_owner):
    """POST /v1/auth/login with wrong password returns 401."""
    resp = client.post(
        "/v1/auth/login",
        json={
            "email": "owner@authtest.com",
            "password": "wrongpassword",
            "org_slug": org_with_owner["slug"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_login_nonexistent_email(client: TestClient, org_with_owner):
    """POST /v1/auth/login with nonexistent email returns 401."""
    resp = client.post(
        "/v1/auth/login",
        json={
            "email": "nobody@authtest.com",
            "password": "securepass123",
            "org_slug": org_with_owner["slug"],
        },
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid credentials"


def test_me_with_valid_jwt(client: TestClient, org_with_owner):
    """GET /v1/auth/me with valid JWT returns user info."""
    # Login first to get a token
    login_resp = client.post(
        "/v1/auth/login",
        json={
            "email": "owner@authtest.com",
            "password": "securepass123",
            "org_slug": org_with_owner["slug"],
        },
    )
    token = login_resp.json()["access_token"]

    resp = client.get(
        "/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "owner@authtest.com"
    assert data["user"]["name"] == "Auth Owner"
    assert data["organization"]["slug"] == org_with_owner["slug"]
    assert data["role"] == "owner"


def test_me_without_token(client: TestClient):
    """GET /v1/auth/me without token returns 401."""
    resp = client.get("/v1/auth/me")
    assert resp.status_code == 401
