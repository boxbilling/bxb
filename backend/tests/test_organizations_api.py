"""Organization API router tests."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.main import app
from app.models.organization import Organization
from app.repositories.api_key_repository import ApiKeyRepository
from app.routers.organizations import OrganizationCreateResponse
from app.schemas.api_key import ApiKeyCreate
from tests.conftest import DEFAULT_ORG_ID

NONEXISTENT_ORG_ID = uuid.UUID("99999999-9999-9999-9999-999999999999")


@pytest.fixture
def db_session():
    """Create a database session for direct repository testing."""
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def authed_client(db_session):
    """Create a test client with a valid API key for the default org."""
    repo = ApiKeyRepository(db_session)
    _, raw_key = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Test Auth Key"))
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {raw_key}"
    return client


@pytest.fixture
def second_org(db_session):
    """Create a second organization for isolation testing."""
    org = Organization(
        id=uuid.uuid4(),
        name="Second Test Organization",
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def second_org_client(db_session, second_org):
    """Create a test client authed to the second org."""
    repo = ApiKeyRepository(db_session)
    _, raw_key = repo.create(second_org.id, ApiKeyCreate(name="Second Org Key"))
    client = TestClient(app)
    client.headers["Authorization"] = f"Bearer {raw_key}"
    return client


class TestListOrganizations:
    def test_list_organizations(self, client):
        """Test listing organizations returns the default org."""
        response = client.get("/v1/organizations/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert any(org["name"] == "Default Test Organization" for org in data)
        assert "X-Total-Count" in response.headers

    def test_list_organizations_after_create(self, client):
        """Test that newly created orgs appear in the list."""
        client.post("/v1/organizations/", json={"name": "List Test Org"})
        response = client.get("/v1/organizations/")
        data = response.json()
        assert any(org["name"] == "List Test Org" for org in data)


class TestCreateOrganization:
    def test_create_organization_minimal(self, client):
        """Test creating an organization with minimal fields."""
        response = client.post(
            "/v1/organizations/",
            json={"name": "New Org"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Org"
        assert data["default_currency"] == "USD"
        assert data["timezone"] == "UTC"
        assert data["invoice_grace_period"] == 0
        assert data["net_payment_term"] == 30
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Should return an initial API key
        assert "api_key" in data
        api_key = data["api_key"]
        assert "raw_key" in api_key
        assert api_key["raw_key"].startswith("bxb_")
        assert api_key["name"] == "Initial API Key"
        assert api_key["status"] == "active"
        assert "key_prefix" in api_key

    def test_create_organization_all_fields(self, client):
        """Test creating an organization with all fields."""
        response = client.post(
            "/v1/organizations/",
            json={
                "name": "Full Org",
                "default_currency": "EUR",
                "timezone": "Europe/London",
                "hmac_key": "secret123",
                "document_number_prefix": "INV-",
                "invoice_grace_period": 5,
                "net_payment_term": 45,
                "logo_url": "https://example.com/logo.png",
                "email": "billing@example.com",
                "legal_name": "Full Org Inc.",
                "address_line1": "123 Main St",
                "address_line2": "Suite 100",
                "city": "London",
                "state": "Greater London",
                "zipcode": "EC1A 1BB",
                "country": "GB",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Full Org"
        assert data["default_currency"] == "EUR"
        assert data["timezone"] == "Europe/London"
        assert data["hmac_key"] == "secret123"
        assert data["document_number_prefix"] == "INV-"
        assert data["invoice_grace_period"] == 5
        assert data["net_payment_term"] == 45
        assert data["logo_url"] == "https://example.com/logo.png"
        assert data["email"] == "billing@example.com"
        assert data["legal_name"] == "Full Org Inc."
        assert data["address_line1"] == "123 Main St"
        assert data["address_line2"] == "Suite 100"
        assert data["city"] == "London"
        assert data["state"] == "Greater London"
        assert data["zipcode"] == "EC1A 1BB"
        assert data["country"] == "GB"
        assert "api_key" in data

    def test_create_organization_missing_name(self, client):
        """Test that name is required."""
        response = client.post(
            "/v1/organizations/",
            json={},
        )
        assert response.status_code == 422

    def test_create_organization_api_key_works(self, client):
        """Test that the returned API key can be used to authenticate."""
        response = client.post(
            "/v1/organizations/",
            json={"name": "Auth Test Org"},
        )
        assert response.status_code == 201
        raw_key = response.json()["api_key"]["raw_key"]
        org_id = response.json()["id"]

        # Use the returned API key to fetch the current org
        current = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert current.status_code == 200
        assert current.json()["id"] == org_id
        assert current.json()["name"] == "Auth Test Org"


class TestGetCurrentOrganization:
    def test_get_current_organization(self, authed_client):
        """Test getting the current organization."""
        response = authed_client.get("/v1/organizations/current")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(DEFAULT_ORG_ID)
        assert data["name"] == "Default Test Organization"

    def test_get_current_organization_no_auth(self, client):
        """Test getting current org without auth falls back to default."""
        response = client.get("/v1/organizations/current")
        assert response.status_code == 200
        assert response.json()["id"] == str(DEFAULT_ORG_ID)

    def test_get_current_organization_invalid_key(self, client):
        """Test getting current org with invalid key returns 401."""
        response = client.get(
            "/v1/organizations/current",
            headers={"Authorization": "Bearer bxb_invalidkey"},
        )
        assert response.status_code == 401

    def test_get_current_org_second_org(self, second_org_client, second_org):
        """Test that the second org client sees its own org."""
        response = second_org_client.get("/v1/organizations/current")
        assert response.status_code == 200
        assert response.json()["id"] == str(second_org.id)
        assert response.json()["name"] == "Second Test Organization"

    def test_get_current_organization_not_found(self, client):
        """Test 404 when organization_id from auth doesn't exist in DB."""
        app.dependency_overrides[get_current_organization] = lambda: NONEXISTENT_ORG_ID
        try:
            response = client.get("/v1/organizations/current")
            assert response.status_code == 404
            assert response.json()["detail"] == "Organization not found"
        finally:
            app.dependency_overrides.pop(get_current_organization, None)


class TestUpdateCurrentOrganization:
    def test_update_current_organization(self, authed_client):
        """Test updating the current organization."""
        response = authed_client.put(
            "/v1/organizations/current",
            json={"name": "Updated Default Org"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Default Org"
        assert data["id"] == str(DEFAULT_ORG_ID)

    def test_update_current_organization_partial(self, authed_client):
        """Test partial update preserves other fields."""
        response = authed_client.put(
            "/v1/organizations/current",
            json={"email": "new@example.com"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "new@example.com"
        assert data["name"] == "Default Test Organization"

    def test_update_current_organization_all_fields(self, authed_client):
        """Test updating all fields at once."""
        response = authed_client.put(
            "/v1/organizations/current",
            json={
                "name": "Fully Updated",
                "default_currency": "GBP",
                "timezone": "Europe/London",
                "hmac_key": "newkey",
                "document_number_prefix": "DOC-",
                "invoice_grace_period": 7,
                "net_payment_term": 60,
                "logo_url": "https://example.com/new.png",
                "email": "updated@example.com",
                "legal_name": "Updated Inc.",
                "address_line1": "456 Oak Ave",
                "address_line2": "Floor 3",
                "city": "Manchester",
                "state": "Lancashire",
                "zipcode": "M1 1AA",
                "country": "GB",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Fully Updated"
        assert data["default_currency"] == "GBP"
        assert data["timezone"] == "Europe/London"
        assert data["hmac_key"] == "newkey"
        assert data["document_number_prefix"] == "DOC-"
        assert data["invoice_grace_period"] == 7
        assert data["net_payment_term"] == 60

    def test_update_current_organization_no_auth(self, client):
        """Test updating without auth falls back to default org."""
        response = client.put(
            "/v1/organizations/current",
            json={"name": "No Auth Update"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "No Auth Update"

    def test_update_current_organization_not_found(self, client):
        """Test 404 when organization_id from auth doesn't exist in DB."""
        app.dependency_overrides[get_current_organization] = lambda: NONEXISTENT_ORG_ID
        try:
            response = client.put(
                "/v1/organizations/current",
                json={"name": "Ghost Org"},
            )
            assert response.status_code == 404
            assert response.json()["detail"] == "Organization not found"
        finally:
            app.dependency_overrides.pop(get_current_organization, None)


class TestCreateApiKey:
    def test_create_api_key(self, authed_client):
        """Test creating a new API key."""
        response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "My New Key"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My New Key"
        assert data["status"] == "active"
        assert "raw_key" in data
        assert data["raw_key"].startswith("bxb_")
        assert "key_prefix" in data
        assert "id" in data
        assert data["organization_id"] == str(DEFAULT_ORG_ID)

    def test_create_api_key_without_name(self, authed_client):
        """Test creating an API key without a name."""
        response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] is None
        assert "raw_key" in data

    def test_create_api_key_with_expiry(self, authed_client):
        """Test creating an API key with an expiration."""
        response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={
                "name": "Expiring Key",
                "expires_at": "2030-12-31T23:59:59Z",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["expires_at"] is not None

    def test_created_api_key_is_usable(self, authed_client, client):
        """Test that a newly created API key can be used for auth."""
        response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Usable Key"},
        )
        assert response.status_code == 201
        raw_key = response.json()["raw_key"]

        # Use the new key to access the current org
        current = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert current.status_code == 200
        assert current.json()["id"] == str(DEFAULT_ORG_ID)


class TestListApiKeys:
    def test_list_api_keys(self, authed_client):
        """Test listing API keys for the current organization."""
        # The authed_client fixture already created one key
        response = authed_client.get("/v1/organizations/current/api_keys")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        key = data[0]
        assert "key_prefix" in key
        assert "name" in key
        assert "status" in key
        assert "id" in key
        # Should NOT include raw_key or organization_id
        assert "raw_key" not in key

    def test_list_api_keys_after_creation(self, authed_client):
        """Test that newly created keys appear in the list."""
        authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Listed Key 1"},
        )
        authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Listed Key 2"},
        )

        response = authed_client.get("/v1/organizations/current/api_keys")
        assert response.status_code == 200
        data = response.json()
        # 1 from authed_client fixture + 2 created above
        assert len(data) >= 3

    def test_list_api_keys_pagination(self, authed_client):
        """Test pagination for API key listing."""
        for i in range(5):
            authed_client.post(
                "/v1/organizations/current/api_keys",
                json={"name": f"Page Key {i}"},
            )

        response = authed_client.get(
            "/v1/organizations/current/api_keys?skip=1&limit=2",
        )
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_list_api_keys_isolation(self, authed_client, second_org_client):
        """Test that API keys are scoped to the organization."""
        authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Org1 Key"},
        )
        second_org_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Org2 Key"},
        )

        response1 = authed_client.get("/v1/organizations/current/api_keys")
        response2 = second_org_client.get("/v1/organizations/current/api_keys")

        org1_names = {k["name"] for k in response1.json()}
        org2_names = {k["name"] for k in response2.json()}

        assert "Org1 Key" in org1_names
        assert "Org2 Key" not in org1_names
        assert "Org2 Key" in org2_names
        assert "Org1 Key" not in org2_names


class TestRevokeApiKey:
    def test_revoke_api_key(self, authed_client):
        """Test revoking an API key."""
        # Create a key to revoke
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Revoke Me"},
        )
        assert create_response.status_code == 201
        api_key_id = create_response.json()["id"]

        # Revoke it
        response = authed_client.delete(
            f"/v1/organizations/current/api_keys/{api_key_id}",
        )
        assert response.status_code == 204

    def test_revoke_api_key_not_found(self, authed_client):
        """Test revoking a non-existent API key."""
        fake_id = str(uuid.uuid4())
        response = authed_client.delete(
            f"/v1/organizations/current/api_keys/{fake_id}",
        )
        assert response.status_code == 404

    def test_revoke_api_key_wrong_org(self, authed_client, second_org_client):
        """Test revoking an API key from another org returns 404."""
        # Create a key in the default org
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Cross Org Key"},
        )
        api_key_id = create_response.json()["id"]

        # Try to revoke it from the second org
        response = second_org_client.delete(
            f"/v1/organizations/current/api_keys/{api_key_id}",
        )
        assert response.status_code == 404

    def test_revoked_key_cannot_authenticate(self, authed_client, client, db_session):
        """Test that a revoked API key cannot be used for auth."""
        # Create a key
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Will Be Revoked"},
        )
        raw_key = create_response.json()["raw_key"]
        api_key_id = create_response.json()["id"]

        # Verify it works
        verify = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert verify.status_code == 200

        # Revoke it
        authed_client.delete(
            f"/v1/organizations/current/api_keys/{api_key_id}",
        )

        # Verify it no longer works
        verify_after = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
        assert verify_after.status_code == 401


class TestRotateApiKey:
    def test_rotate_api_key(self, authed_client):
        """Test rotating an API key returns a new key."""
        # Create a key to rotate
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Rotate Me", "expires_at": "2030-12-31T23:59:59Z"},
        )
        assert create_response.status_code == 201
        old_key = create_response.json()
        api_key_id = old_key["id"]

        # Rotate it
        response = authed_client.post(
            f"/v1/organizations/current/api_keys/{api_key_id}/rotate",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Rotate Me"
        assert data["expires_at"] is not None
        assert data["status"] == "active"
        assert "raw_key" in data
        assert data["raw_key"].startswith("bxb_")
        assert data["id"] != api_key_id

    def test_rotate_api_key_not_found(self, authed_client):
        """Test rotating a non-existent API key returns 404."""
        fake_id = str(uuid.uuid4())
        response = authed_client.post(
            f"/v1/organizations/current/api_keys/{fake_id}/rotate",
        )
        assert response.status_code == 404

    def test_rotate_already_revoked(self, authed_client):
        """Test rotating an already-revoked key returns 404."""
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Revoke Then Rotate"},
        )
        api_key_id = create_response.json()["id"]

        # Revoke
        authed_client.delete(f"/v1/organizations/current/api_keys/{api_key_id}")

        # Try to rotate
        response = authed_client.post(
            f"/v1/organizations/current/api_keys/{api_key_id}/rotate",
        )
        assert response.status_code == 404

    def test_rotate_wrong_org(self, authed_client, second_org_client):
        """Test rotating a key from another org returns 404."""
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Cross Org Rotate"},
        )
        api_key_id = create_response.json()["id"]

        response = second_org_client.post(
            f"/v1/organizations/current/api_keys/{api_key_id}/rotate",
        )
        assert response.status_code == 404

    def test_rotated_key_is_usable(self, authed_client, client):
        """Test that the new key from rotation can be used for auth."""
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Usable Rotated Key"},
        )
        api_key_id = create_response.json()["id"]

        rotate_response = authed_client.post(
            f"/v1/organizations/current/api_keys/{api_key_id}/rotate",
        )
        new_raw_key = rotate_response.json()["raw_key"]

        current = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {new_raw_key}"},
        )
        assert current.status_code == 200
        assert current.json()["id"] == str(DEFAULT_ORG_ID)

    def test_old_key_stops_working_after_rotation(self, authed_client, client):
        """Test that the old key is revoked after rotation."""
        create_response = authed_client.post(
            "/v1/organizations/current/api_keys",
            json={"name": "Old Key Revoked"},
        )
        old_raw_key = create_response.json()["raw_key"]
        api_key_id = create_response.json()["id"]

        authed_client.post(
            f"/v1/organizations/current/api_keys/{api_key_id}/rotate",
        )

        verify = client.get(
            "/v1/organizations/current",
            headers={"Authorization": f"Bearer {old_raw_key}"},
        )
        assert verify.status_code == 401


class TestXOrganizationIdHeader:
    def test_switch_org_via_header(self, client, second_org):
        """Test that X-Organization-Id header overrides the default org."""
        response = client.get(
            "/v1/organizations/current",
            headers={"X-Organization-Id": str(second_org.id)},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(second_org.id)
        assert response.json()["name"] == "Second Test Organization"

    def test_header_overrides_api_key(self, authed_client, second_org):
        """Test that X-Organization-Id header takes precedence over API key auth."""
        response = authed_client.get(
            "/v1/organizations/current",
            headers={"X-Organization-Id": str(second_org.id)},
        )
        assert response.status_code == 200
        assert response.json()["id"] == str(second_org.id)

    def test_invalid_header_returns_400(self, client):
        """Test that an invalid UUID in X-Organization-Id returns 400."""
        response = client.get(
            "/v1/organizations/current",
            headers={"X-Organization-Id": "not-a-uuid"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid X-Organization-Id header"


class TestOrganizationCreateResponseSchema:
    def test_schema_includes_api_key(self):
        """Test that OrganizationCreateResponse schema has api_key field."""
        schema = OrganizationCreateResponse.model_json_schema()
        assert "api_key" in schema["properties"]
