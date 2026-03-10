"""End-to-end integration smoke test for the full org member auth flow.

Exercises the complete lifecycle: org creation with owner, slug lookup,
JWT login, /me endpoint, cross-org isolation, and API key coexistence.
"""

import pytest
from starlette.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_headers():
    original_secret = settings.BXB_ADMIN_SECRET
    test_secret = "integration-test-admin-secret-that-is-at-least-32-chars"
    settings.BXB_ADMIN_SECRET = test_secret
    yield {"X-Admin-Secret": test_secret}
    settings.BXB_ADMIN_SECRET = original_secret


class TestAuthIntegrationFlow:
    """Full end-to-end auth flow: org creation → login → /me → cross-org isolation."""

    def test_full_auth_flow(self, client: TestClient, admin_headers: dict):
        # ── 1. Create org via admin API with owner email/password ──
        org_resp = client.post(
            "/v1/organizations/",
            headers=admin_headers,
            json={
                "name": "Integration Test Org",
                "owner_email": "integowner@test.com",
                "owner_name": "Integration Owner",
                "owner_password": "supersecure456",
            },
        )
        assert org_resp.status_code == 201
        org_data = org_resp.json()
        assert "owner" in org_data
        assert org_data["owner"]["email"] == "integowner@test.com"
        assert "user_id" in org_data["owner"]
        org_slug = org_data["slug"]
        raw_api_key = org_data["api_key"]["raw_key"]

        # ── 2. GET /v1/organizations/by-slug/{slug} → branding, no secrets ──
        slug_resp = client.get(f"/v1/organizations/by-slug/{org_slug}")
        assert slug_resp.status_code == 200
        branding = slug_resp.json()
        assert branding["name"] == "Integration Test Org"
        assert branding["slug"] == org_slug
        assert "id" not in branding
        assert "hmac_key" not in branding

        # ── 3. POST /v1/auth/login with email + password + org_slug → JWT ──
        login_resp = client.post(
            "/v1/auth/login",
            json={
                "email": "integowner@test.com",
                "password": "supersecure456",
                "org_slug": org_slug,
            },
        )
        assert login_resp.status_code == 200
        login_data = login_resp.json()
        assert "access_token" in login_data
        assert login_data["token_type"] == "bearer"
        assert login_data["role"] == "owner"
        jwt_token = login_data["access_token"]

        # ── 4. GET /v1/auth/me with JWT → user info, org info, role ──
        me_resp = client.get(
            "/v1/auth/me",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["email"] == "integowner@test.com"
        assert me_data["user"]["name"] == "Integration Owner"
        assert me_data["organization"]["slug"] == org_slug
        assert me_data["role"] == "owner"

        # ── 5. POST /v1/auth/login without org_slug → uses first org in DB ──
        # When no slug is provided, the system picks the first org by created_at.
        # If that's the user's org → 200 with token. If not → 401 (no membership).
        # Both are correct behavior; we verify the endpoint doesn't crash.
        login_no_slug = client.post(
            "/v1/auth/login",
            json={
                "email": "integowner@test.com",
                "password": "supersecure456",
            },
        )
        assert login_no_slug.status_code in (200, 401)
        if login_no_slug.status_code == 200:
            assert "access_token" in login_no_slug.json()

        # ── 6. Cross-org isolation: user cannot login to a different org ──
        org2_resp = client.post(
            "/v1/organizations/",
            headers=admin_headers,
            json={"name": "Other Org For Isolation Test"},
        )
        assert org2_resp.status_code == 201
        org2_slug = org2_resp.json()["slug"]

        cross_login = client.post(
            "/v1/auth/login",
            json={
                "email": "integowner@test.com",
                "password": "supersecure456",
                "org_slug": org2_slug,
            },
        )
        assert cross_login.status_code == 401

        # ── 7. API key auth still works: create customer via Bearer API key ──
        cust_resp = client.post(
            "/v1/customers/",
            headers={"Authorization": f"Bearer {raw_api_key}"},
            json={"external_id": "integ-cust-001", "name": "Integration Customer"},
        )
        assert cust_resp.status_code == 201

        # ── 8. JWT token on API-key-only endpoint: get_current_organization fallback ──
        # With the JWT fallback in get_current_organization, a JWT should resolve
        # to the org from its claims and work on org-scoped endpoints.
        jwt_cust_resp = client.post(
            "/v1/customers/",
            headers={"Authorization": f"Bearer {jwt_token}"},
            json={"external_id": "integ-jwt-cust", "name": "JWT Customer"},
        )
        # After JWT fallback implementation, this should succeed (201)
        assert jwt_cust_resp.status_code == 201
