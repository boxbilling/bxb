"""Smoke tests for member management endpoints."""

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
            "name": "Members Test Org",
            "owner_email": "owner@memberstest.com",
            "owner_name": "Members Owner",
            "owner_password": "securepass123",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest.fixture
def owner_token(client: TestClient, org_with_owner: dict) -> str:
    """Log in as the owner and return the JWT token."""
    resp = client.post(
        "/v1/auth/login",
        json={
            "email": "owner@memberstest.com",
            "password": "securepass123",
            "org_slug": org_with_owner["slug"],
        },
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(owner_token: str) -> dict:
    """Return authorization headers with the owner JWT."""
    return {"Authorization": f"Bearer {owner_token}"}


def test_invite_member(client: TestClient, auth_headers: dict):
    """POST /v1/organizations/current/members/ invites a new member."""
    resp = client.post(
        "/v1/organizations/current/members/",
        headers=auth_headers,
        json={
            "email": "newmember@memberstest.com",
            "name": "New Member",
            "password": "memberpass123",
            "role": "member",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "newmember@memberstest.com"
    assert data["role"] == "member"
    assert data["invited_by"] is not None


def test_list_members(client: TestClient, auth_headers: dict):
    """GET /v1/organizations/current/members/ lists all members."""
    # First invite a member
    client.post(
        "/v1/organizations/current/members/",
        headers=auth_headers,
        json={
            "email": "listmember@memberstest.com",
            "name": "List Member",
            "password": "memberpass123",
            "role": "member",
        },
    )

    resp = client.get(
        "/v1/organizations/current/members/",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least the owner + the invited member
    assert len(data) >= 2
    assert "X-Total-Count" in resp.headers


def test_update_member_role(client: TestClient, auth_headers: dict):
    """PATCH /v1/organizations/current/members/{id} updates role."""
    # Invite a member
    invite_resp = client.post(
        "/v1/organizations/current/members/",
        headers=auth_headers,
        json={
            "email": "updatemember@memberstest.com",
            "name": "Update Member",
            "password": "memberpass123",
            "role": "member",
        },
    )
    member_id = invite_resp.json()["id"]

    # Update role to admin
    resp = client.patch(
        f"/v1/organizations/current/members/{member_id}",
        headers=auth_headers,
        json={"role": "admin"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_delete_member(client: TestClient, auth_headers: dict):
    """DELETE /v1/organizations/current/members/{id} removes a member."""
    # Invite a member
    invite_resp = client.post(
        "/v1/organizations/current/members/",
        headers=auth_headers,
        json={
            "email": "deletemember@memberstest.com",
            "name": "Delete Member",
            "password": "memberpass123",
            "role": "member",
        },
    )
    member_id = invite_resp.json()["id"]

    # Delete the member
    resp = client.delete(
        f"/v1/organizations/current/members/{member_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


def test_cannot_remove_yourself(client: TestClient, auth_headers: dict):
    """DELETE yourself returns 400."""
    # Get the list to find the owner's member ID
    list_resp = client.get(
        "/v1/organizations/current/members/",
        headers=auth_headers,
    )
    members = list_resp.json()
    owner_member = next(m for m in members if m["role"] == "owner")

    resp = client.delete(
        f"/v1/organizations/current/members/{owner_member['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Cannot remove yourself"
