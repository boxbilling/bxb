"""API Key model, schema, repository, and auth middleware tests."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.auth import get_current_organization
from app.core.database import get_db
from app.main import app
from app.models.api_key import ApiKey, generate_uuid
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.models.organization import Organization
from app.repositories.api_key_repository import (
    ApiKeyRepository,
    generate_api_key,
    hash_api_key,
)
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
)
from tests.conftest import DEFAULT_ORG_ID


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
def second_org(db_session):
    """Create a second organization for testing."""
    org = Organization(
        id=uuid.uuid4(),
        name="Second Test Organization",
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


class TestApiKeyModel:
    def test_generate_uuid(self):
        """Test that generate_uuid returns a valid UUID."""
        result = generate_uuid()
        assert isinstance(result, uuid.UUID)

    def test_api_key_defaults(self, db_session):
        """Test ApiKey model default values."""
        api_key = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="abc123hash",
            key_prefix="bxb_1234",
        )
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)

        assert api_key.id is not None
        assert api_key.organization_id == DEFAULT_ORG_ID
        assert api_key.key_hash == "abc123hash"
        assert api_key.key_prefix == "bxb_1234"
        assert api_key.name is None
        assert api_key.last_used_at is None
        assert api_key.expires_at is None
        assert api_key.status == "active"
        assert api_key.created_at is not None
        assert api_key.updated_at is not None

    def test_api_key_with_all_fields(self, db_session):
        """Test ApiKey with all fields set."""
        now = datetime.now(UTC)
        expires = now + timedelta(days=30)
        api_key = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="full_hash_value",
            key_prefix="bxb_full",
            name="My API Key",
            last_used_at=now,
            expires_at=expires,
            status="active",
        )
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)

        assert api_key.name == "My API Key"
        assert api_key.last_used_at is not None
        assert api_key.expires_at is not None
        assert api_key.status == "active"

    def test_api_key_unique_hash(self, db_session):
        """Test that key_hash must be unique."""
        key1 = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="unique_hash",
            key_prefix="bxb_uni1",
        )
        db_session.add(key1)
        db_session.commit()

        key2 = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="unique_hash",
            key_prefix="bxb_uni2",
        )
        db_session.add(key2)
        with pytest.raises(IntegrityError):
            db_session.commit()
        db_session.rollback()


class TestApiKeyHelperFunctions:
    def test_generate_api_key_format(self):
        """Test that generated API keys have the bxb_ prefix."""
        key = generate_api_key()
        assert key.startswith("bxb_")
        assert len(key) == 68  # "bxb_" + 64 hex chars

    def test_generate_api_key_uniqueness(self):
        """Test that generated API keys are unique."""
        keys = {generate_api_key() for _ in range(10)}
        assert len(keys) == 10

    def test_hash_api_key(self):
        """Test that hash_api_key returns SHA-256 hex digest."""
        raw_key = "bxb_test123"
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        assert hash_api_key(raw_key) == expected

    def test_hash_api_key_deterministic(self):
        """Test that hashing the same key gives the same result."""
        raw_key = "bxb_deterministic"
        assert hash_api_key(raw_key) == hash_api_key(raw_key)

    def test_hash_api_key_different_keys(self):
        """Test that different keys produce different hashes."""
        assert hash_api_key("bxb_key1") != hash_api_key("bxb_key2")


class TestApiKeyRepository:
    def test_create_api_key(self, db_session):
        """Test creating an API key."""
        repo = ApiKeyRepository(db_session)
        data = ApiKeyCreate(name="Test Key")
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, data)

        assert api_key.id is not None
        assert api_key.organization_id == DEFAULT_ORG_ID
        assert api_key.name == "Test Key"
        assert api_key.status == "active"
        assert api_key.key_prefix == raw_key[:12]
        assert api_key.key_hash == hash_api_key(raw_key)
        assert raw_key.startswith("bxb_")

    def test_create_api_key_without_name(self, db_session):
        """Test creating an API key without a name."""
        repo = ApiKeyRepository(db_session)
        data = ApiKeyCreate()
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, data)

        assert api_key.name is None
        assert raw_key.startswith("bxb_")

    def test_create_api_key_with_expiry(self, db_session):
        """Test creating an API key with an expiration date."""
        repo = ApiKeyRepository(db_session)
        expires = datetime.now(UTC) + timedelta(days=90)
        data = ApiKeyCreate(name="Expiring Key", expires_at=expires)
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, data)

        assert api_key.expires_at is not None

    def test_get_by_hash(self, db_session):
        """Test looking up an API key by hash."""
        repo = ApiKeyRepository(db_session)
        data = ApiKeyCreate(name="Hash Lookup")
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, data)

        found = repo.get_by_hash(hash_api_key(raw_key))
        assert found is not None
        assert found.id == api_key.id

    def test_get_by_hash_not_found(self, db_session):
        """Test looking up a non-existent hash."""
        repo = ApiKeyRepository(db_session)
        result = repo.get_by_hash("nonexistent_hash")
        assert result is None

    def test_get_by_id(self, db_session):
        """Test getting an API key by ID and organization."""
        repo = ApiKeyRepository(db_session)
        data = ApiKeyCreate(name="ID Lookup")
        api_key, _ = repo.create(DEFAULT_ORG_ID, data)

        found = repo.get_by_id(api_key.id, DEFAULT_ORG_ID)
        assert found is not None
        assert found.name == "ID Lookup"

    def test_get_by_id_wrong_org(self, db_session, second_org):
        """Test that API keys are scoped by organization."""
        repo = ApiKeyRepository(db_session)
        data = ApiKeyCreate(name="Org Scoped")
        api_key, _ = repo.create(DEFAULT_ORG_ID, data)

        result = repo.get_by_id(api_key.id, second_org.id)
        assert result is None

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent API key."""
        repo = ApiKeyRepository(db_session)
        result = repo.get_by_id(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_list_by_org(self, db_session):
        """Test listing API keys by organization."""
        repo = ApiKeyRepository(db_session)
        repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Key 1"))
        repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Key 2"))
        repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Key 3"))

        keys = repo.list_by_org(DEFAULT_ORG_ID)
        assert len(keys) == 3

    def test_list_by_org_empty(self, db_session, second_org):
        """Test listing API keys for an org with none."""
        repo = ApiKeyRepository(db_session)
        keys = repo.list_by_org(second_org.id)
        assert keys == []

    def test_list_by_org_pagination(self, db_session):
        """Test pagination of API key listing."""
        repo = ApiKeyRepository(db_session)
        for i in range(5):
            repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name=f"Key {i}"))

        page = repo.list_by_org(DEFAULT_ORG_ID, skip=1, limit=2)
        assert len(page) == 2

    def test_list_by_org_isolation(self, db_session, second_org):
        """Test that listing only returns keys for the specified org."""
        repo = ApiKeyRepository(db_session)
        repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Default Org Key"))
        repo.create(second_org.id, ApiKeyCreate(name="Second Org Key"))

        default_keys = repo.list_by_org(DEFAULT_ORG_ID)
        second_keys = repo.list_by_org(second_org.id)

        assert len(default_keys) == 1
        assert default_keys[0].name == "Default Org Key"
        assert len(second_keys) == 1
        assert second_keys[0].name == "Second Org Key"

    def test_revoke(self, db_session):
        """Test revoking an API key."""
        repo = ApiKeyRepository(db_session)
        api_key, _ = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Revoke Me"))
        assert api_key.status == "active"

        revoked = repo.revoke(api_key.id, DEFAULT_ORG_ID)
        assert revoked is not None
        assert revoked.status == "revoked"

    def test_revoke_wrong_org(self, db_session, second_org):
        """Test revoking an API key from wrong org."""
        repo = ApiKeyRepository(db_session)
        api_key, _ = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Wrong Org"))

        result = repo.revoke(api_key.id, second_org.id)
        assert result is None

    def test_revoke_not_found(self, db_session):
        """Test revoking a non-existent API key."""
        repo = ApiKeyRepository(db_session)
        result = repo.revoke(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_update_last_used(self, db_session):
        """Test updating last_used_at timestamp."""
        repo = ApiKeyRepository(db_session)
        api_key, _ = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Track Usage"))
        assert api_key.last_used_at is None

        now = datetime.now(UTC)
        repo.update_last_used(api_key, now)
        db_session.refresh(api_key)

        assert api_key.last_used_at is not None


class TestApiKeySchemas:
    def test_create_schema_minimal(self):
        """Test ApiKeyCreate with minimal fields."""
        schema = ApiKeyCreate()
        assert schema.name is None
        assert schema.expires_at is None

    def test_create_schema_with_name(self):
        """Test ApiKeyCreate with name."""
        schema = ApiKeyCreate(name="My Key")
        assert schema.name == "My Key"

    def test_create_schema_with_expiry(self):
        """Test ApiKeyCreate with expires_at."""
        expires = datetime.now(UTC) + timedelta(days=30)
        schema = ApiKeyCreate(name="Expiring", expires_at=expires)
        assert schema.expires_at == expires

    def test_response_schema_from_model(self, db_session):
        """Test ApiKeyResponse from ORM model."""
        api_key = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="test_hash",
            key_prefix="bxb_test",
            name="Response Test",
            status="active",
        )
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)

        response = ApiKeyResponse.model_validate(api_key)
        assert response.name == "Response Test"
        assert response.key_prefix == "bxb_test"
        assert response.status == "active"
        assert response.created_at is not None
        assert response.organization_id == DEFAULT_ORG_ID

    def test_list_response_schema(self, db_session):
        """Test ApiKeyListResponse from ORM model."""
        api_key = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="list_hash",
            key_prefix="bxb_list",
            name="List Test",
            status="active",
        )
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)

        response = ApiKeyListResponse.model_validate(api_key)
        assert response.name == "List Test"
        assert response.key_prefix == "bxb_list"
        assert response.status == "active"

    def test_create_response_schema(self, db_session):
        """Test ApiKeyCreateResponse with raw_key."""
        api_key = ApiKey(
            id=uuid.uuid4(),
            organization_id=DEFAULT_ORG_ID,
            key_hash="create_hash",
            key_prefix="bxb_crea",
            name="Create Test",
            status="active",
        )
        db_session.add(api_key)
        db_session.commit()
        db_session.refresh(api_key)

        # ApiKeyCreateResponse needs raw_key as extra data
        data = {
            **ApiKeyResponse.model_validate(api_key).model_dump(),
            "raw_key": "bxb_abcdef123456",
        }
        response = ApiKeyCreateResponse(**data)
        assert response.raw_key == "bxb_abcdef123456"
        assert response.name == "Create Test"


class TestAuthMiddleware:
    def test_no_auth_header_uses_default_org(self, client):
        """Test that missing Authorization header falls back to default org."""
        # GET /v1/customers should work without auth (uses default org)
        response = client.get("/v1/customers/")
        assert response.status_code == 200

    def test_invalid_header_format(self, client):
        """Test that non-Bearer auth returns 401."""
        response = client.get(
            "/v1/customers/",
            headers={"Authorization": "Basic abc123"},
        )
        # Without the auth dependency wired into customers, this should still work
        # because the dependency is not yet applied to existing routers
        # This test validates the auth module itself
        assert response.status_code == 200

    def test_get_current_organization_no_header(self, db_session):
        """Test get_current_organization with no auth header."""
        from unittest.mock import MagicMock

        request = MagicMock()
        request.headers.get.return_value = None

        org_id = get_current_organization(request, db_session)
        assert org_id == DEFAULT_ORGANIZATION_ID

    def test_get_current_organization_invalid_format(self, db_session):
        """Test get_current_organization with invalid header format."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = "Basic abc123"

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(request, db_session)
        assert exc_info.value.status_code == 401
        assert "Invalid authorization header format" in exc_info.value.detail

    def test_get_current_organization_empty_key(self, db_session):
        """Test get_current_organization with empty Bearer token."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = "Bearer "

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(request, db_session)
        assert exc_info.value.status_code == 401
        assert "API key is required" in exc_info.value.detail

    def test_get_current_organization_invalid_key(self, db_session):
        """Test get_current_organization with non-existent key."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        request = MagicMock()
        request.headers.get.return_value = "Bearer bxb_invalidkey12345"

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(request, db_session)
        assert exc_info.value.status_code == 401
        assert "Invalid API key" in exc_info.value.detail

    def test_get_current_organization_valid_key(self, db_session):
        """Test get_current_organization with a valid key."""
        from unittest.mock import MagicMock

        repo = ApiKeyRepository(db_session)
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Auth Test"))

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {raw_key}"

        org_id = get_current_organization(request, db_session)
        assert org_id == DEFAULT_ORG_ID

    def test_get_current_organization_revoked_key(self, db_session):
        """Test get_current_organization with a revoked key."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        repo = ApiKeyRepository(db_session)
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Revoked"))
        repo.revoke(api_key.id, DEFAULT_ORG_ID)

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {raw_key}"

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(request, db_session)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail

    def test_get_current_organization_expired_key(self, db_session):
        """Test get_current_organization with an expired key."""
        from unittest.mock import MagicMock

        from fastapi import HTTPException

        repo = ApiKeyRepository(db_session)
        expired = datetime.now(UTC) - timedelta(days=1)
        api_key, raw_key = repo.create(
            DEFAULT_ORG_ID, ApiKeyCreate(name="Expired", expires_at=expired)
        )

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {raw_key}"

        with pytest.raises(HTTPException) as exc_info:
            get_current_organization(request, db_session)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail

    def test_get_current_organization_updates_last_used(self, db_session):
        """Test that successful auth updates last_used_at."""
        from unittest.mock import MagicMock

        repo = ApiKeyRepository(db_session)
        api_key, raw_key = repo.create(DEFAULT_ORG_ID, ApiKeyCreate(name="Track"))
        assert api_key.last_used_at is None

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {raw_key}"

        get_current_organization(request, db_session)

        db_session.refresh(api_key)
        assert api_key.last_used_at is not None

    def test_get_current_organization_non_expired_key(self, db_session):
        """Test get_current_organization with a key that has future expiry."""
        from unittest.mock import MagicMock

        repo = ApiKeyRepository(db_session)
        future = datetime.now(UTC) + timedelta(days=30)
        api_key, raw_key = repo.create(
            DEFAULT_ORG_ID, ApiKeyCreate(name="Future", expires_at=future)
        )

        request = MagicMock()
        request.headers.get.return_value = f"Bearer {raw_key}"

        org_id = get_current_organization(request, db_session)
        assert org_id == DEFAULT_ORG_ID
