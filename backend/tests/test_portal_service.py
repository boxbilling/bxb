"""Tests for portal token service, auth dependency, and portal_url endpoint."""

import time
import uuid
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_portal_customer
from app.core.config import settings
from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.services.portal_service import PortalService
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    gen = get_db()
    db = next(gen)
    try:
        yield db
    finally:
        for _ in gen:
            pass


@pytest.fixture
def customer(db_session):
    c = Customer(
        external_id=f"portal_cust_{uuid.uuid4()}",
        name="Portal Test Customer",
        email="portal@example.com",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


class TestPortalService:
    """Tests for PortalService methods."""

    def test_generate_token(self, db_session):
        """Test that generate_token returns a valid JWT string."""
        service = PortalService(db_session)
        customer_id = uuid.uuid4()
        org_id = DEFAULT_ORG_ID

        token = service.generate_token(customer_id, org_id)

        assert isinstance(token, str)
        payload = jwt.decode(token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"])
        assert payload["customer_id"] == str(customer_id)
        assert payload["organization_id"] == str(org_id)
        assert payload["type"] == "portal"
        assert "exp" in payload

    def test_generate_portal_url(self, db_session):
        """Test that generate_portal_url returns a valid URL with a JWT."""
        service = PortalService(db_session)
        customer_id = uuid.uuid4()
        org_id = DEFAULT_ORG_ID

        result = service.generate_portal_url(customer_id, org_id)

        assert result.portal_url.startswith(f"https://{settings.APP_DOMAIN}/portal?token=")
        token = result.portal_url.split("token=")[1]
        payload = jwt.decode(token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"])
        assert payload["customer_id"] == str(customer_id)
        assert payload["organization_id"] == str(org_id)
        assert payload["type"] == "portal"
        assert "exp" in payload

    def test_verify_portal_token_valid(self, db_session):
        """Test that verify_portal_token correctly decodes a valid token."""
        service = PortalService(db_session)
        customer_id = uuid.uuid4()
        org_id = DEFAULT_ORG_ID

        result = service.generate_portal_url(customer_id, org_id)
        token = result.portal_url.split("token=")[1]

        decoded_customer_id, decoded_org_id = PortalService.verify_portal_token(token)
        assert decoded_customer_id == customer_id
        assert decoded_org_id == org_id

    def test_verify_portal_token_expired(self):
        """Test that an expired token is rejected."""
        payload = {
            "customer_id": str(uuid.uuid4()),
            "organization_id": str(DEFAULT_ORG_ID),
            "type": "portal",
            "exp": time.time() - 3600,  # 1 hour in the past
        }
        token = jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")

        with pytest.raises(jwt.ExpiredSignatureError):
            PortalService.verify_portal_token(token)

    def test_verify_portal_token_invalid_signature(self):
        """Test that a token with wrong secret is rejected."""
        payload = {
            "customer_id": str(uuid.uuid4()),
            "organization_id": str(DEFAULT_ORG_ID),
            "type": "portal",
            "exp": time.time() + 3600,
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(jwt.InvalidTokenError):
            PortalService.verify_portal_token(token)

    def test_verify_portal_token_invalid_type(self):
        """Test that a token with wrong type claim is rejected."""
        payload = {
            "customer_id": str(uuid.uuid4()),
            "organization_id": str(DEFAULT_ORG_ID),
            "type": "not-portal",
            "exp": time.time() + 3600,
        }
        token = jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")

        with pytest.raises(jwt.InvalidTokenError, match="Invalid token type"):
            PortalService.verify_portal_token(token)

    def test_verify_portal_token_garbage(self):
        """Test that a completely invalid token is rejected."""
        with pytest.raises(jwt.InvalidTokenError):
            PortalService.verify_portal_token("not-a-valid-jwt-token")


class TestGetPortalCustomerDependency:
    """Tests for the get_portal_customer FastAPI dependency."""

    def test_valid_token(self, db_session):
        """Test dependency returns (customer_id, org_id) for a valid token."""
        service = PortalService(db_session)
        customer_id = uuid.uuid4()
        org_id = DEFAULT_ORG_ID

        result = service.generate_portal_url(customer_id, org_id)
        token = result.portal_url.split("token=")[1]

        cid, oid = get_portal_customer(token)
        assert cid == customer_id
        assert oid == org_id

    def test_expired_token_raises_401(self):
        """Test dependency raises HTTPException for expired token."""
        from fastapi import HTTPException

        payload = {
            "customer_id": str(uuid.uuid4()),
            "organization_id": str(DEFAULT_ORG_ID),
            "type": "portal",
            "exp": time.time() - 3600,
        }
        token = jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            get_portal_customer(token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Portal token has expired"

    def test_invalid_token_raises_401(self):
        """Test dependency raises HTTPException for invalid token."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_portal_customer("garbage-token")
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid portal token"

    def test_wrong_secret_raises_401(self):
        """Test dependency raises HTTPException for wrong-secret token."""
        from fastapi import HTTPException

        payload = {
            "customer_id": str(uuid.uuid4()),
            "organization_id": str(DEFAULT_ORG_ID),
            "type": "portal",
            "exp": time.time() + 3600,
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            get_portal_customer(token)
        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid portal token"


class TestPortalUrlEndpoint:
    """Tests for the GET /v1/customers/{external_id}/portal_url endpoint."""

    def test_generate_portal_url_success(self, client: TestClient, db_session, customer):
        """Test successfully generating a portal URL for a customer."""
        response = client.get(f"/v1/customers/{customer.external_id}/portal_url")
        assert response.status_code == 200
        data = response.json()
        assert "portal_url" in data
        assert data["portal_url"].startswith(f"https://{settings.APP_DOMAIN}/portal?token=")

        # Verify the embedded token contains correct claims
        token = data["portal_url"].split("token=")[1]
        payload = jwt.decode(token, settings.PORTAL_JWT_SECRET, algorithms=["HS256"])
        assert payload["customer_id"] == str(customer.id)
        assert payload["organization_id"] == str(DEFAULT_ORG_ID)
        assert payload["type"] == "portal"

    def test_generate_portal_url_customer_not_found(self, client: TestClient):
        """Test 404 when customer external_id does not exist."""
        response = client.get("/v1/customers/nonexistent-customer/portal_url")
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    def test_portal_url_uses_app_domain(self, client: TestClient, db_session, customer):
        """Test that the portal URL uses the configured APP_DOMAIN."""
        with patch.object(settings, "APP_DOMAIN", "billing.acme.com"):
            response = client.get(f"/v1/customers/{customer.external_id}/portal_url")
        assert response.status_code == 200
        assert "billing.acme.com" in response.json()["portal_url"]
