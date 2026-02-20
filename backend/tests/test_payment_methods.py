"""Tests for payment methods API endpoints."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.shared import generate_uuid
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.schemas.payment_method import (
    PaymentMethodCreate,
    SetupSessionCreate,
    SetupSessionResponse,
)
from app.services.payment_provider import SetupSession, StripeProvider
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


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
def customer(db_session):
    """Create a customer for testing."""
    c = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-pm-api-001",
        name="PM API Customer",
        email="pm-api@example.com",
        currency="USD",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def second_customer(db_session):
    """Create a second customer for testing."""
    c = Customer(
        id=generate_uuid(),
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-pm-api-002",
        name="Second PM Customer",
        email="pm-api-2@example.com",
        currency="USD",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def payment_method(db_session, customer):
    """Create a payment method for testing."""
    repo = PaymentMethodRepository(db_session)
    return repo.create(
        PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_test_api_1",
            type="card",
            details={"last4": "4242", "brand": "visa"},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def default_payment_method(db_session, customer):
    """Create a default payment method for testing."""
    repo = PaymentMethodRepository(db_session)
    return repo.create(
        PaymentMethodCreate(
            customer_id=customer.id,
            provider="stripe",
            provider_payment_method_id="pm_default_api",
            type="card",
            is_default=True,
            details={"last4": "1234", "brand": "mastercard"},
        ),
        DEFAULT_ORG_ID,
    )


class TestListPaymentMethods:
    """Tests for GET /v1/payment_methods/."""

    def test_list_empty(self, client):
        """Test listing payment methods when none exist."""
        response = client.get("/v1/payment_methods/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_data(self, client, payment_method):
        """Test listing payment methods with data."""
        response = client.get("/v1/payment_methods/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["provider"] == "stripe"

    def test_list_filter_by_customer(self, client, customer, second_customer, db_session):
        """Test listing payment methods filtered by customer_id."""
        repo = PaymentMethodRepository(db_session)
        repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_filter_1",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )
        repo.create(
            PaymentMethodCreate(
                customer_id=second_customer.id,
                provider="stripe",
                provider_payment_method_id="pm_filter_2",
                type="card",
            ),
            DEFAULT_ORG_ID,
        )

        response = client.get(f"/v1/payment_methods/?customer_id={customer.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["customer_id"] == str(customer.id)

    def test_list_pagination(self, client, customer, db_session):
        """Test listing payment methods with pagination."""
        repo = PaymentMethodRepository(db_session)
        for i in range(3):
            repo.create(
                PaymentMethodCreate(
                    customer_id=customer.id,
                    provider="stripe",
                    provider_payment_method_id=f"pm_page_{i}",
                    type="card",
                ),
                DEFAULT_ORG_ID,
            )

        response = client.get("/v1/payment_methods/?skip=1&limit=1")
        assert response.status_code == 200
        assert len(response.json()) == 1


class TestGetPaymentMethod:
    """Tests for GET /v1/payment_methods/{id}."""

    def test_get_by_id(self, client, payment_method):
        """Test getting a payment method by ID."""
        response = client.get(f"/v1/payment_methods/{payment_method.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(payment_method.id)
        assert data["provider"] == "stripe"
        assert data["type"] == "card"
        assert data["details"]["last4"] == "4242"

    def test_get_not_found(self, client):
        """Test getting a non-existent payment method."""
        response = client.get(f"/v1/payment_methods/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"


class TestCreatePaymentMethod:
    """Tests for POST /v1/payment_methods/."""

    def test_create(self, client, customer):
        """Test creating a payment method."""
        response = client.post(
            "/v1/payment_methods/",
            json={
                "customer_id": str(customer.id),
                "provider": "stripe",
                "provider_payment_method_id": "pm_new_create",
                "type": "card",
                "details": {"last4": "5555", "brand": "mastercard"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "stripe"
        assert data["type"] == "card"
        assert data["is_default"] is False
        assert data["details"]["last4"] == "5555"

    def test_create_with_default(self, client, customer):
        """Test creating a default payment method."""
        response = client.post(
            "/v1/payment_methods/",
            json={
                "customer_id": str(customer.id),
                "provider": "stripe",
                "provider_payment_method_id": "pm_new_default",
                "type": "card",
                "is_default": True,
            },
        )
        assert response.status_code == 201
        assert response.json()["is_default"] is True

    def test_create_minimal(self, client, customer):
        """Test creating a payment method with minimal fields."""
        response = client.post(
            "/v1/payment_methods/",
            json={
                "customer_id": str(customer.id),
                "provider": "adyen",
                "provider_payment_method_id": "pm_adyen_min",
                "type": "bank_account",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "adyen"
        assert data["details"] == {}


class TestDeletePaymentMethod:
    """Tests for DELETE /v1/payment_methods/{id}."""

    def test_delete(self, client, payment_method):
        """Test deleting a non-default payment method."""
        response = client.delete(f"/v1/payment_methods/{payment_method.id}")
        assert response.status_code == 204

        # Verify it's gone
        response = client.get(f"/v1/payment_methods/{payment_method.id}")
        assert response.status_code == 404

    def test_delete_not_found(self, client):
        """Test deleting a non-existent payment method."""
        response = client.delete(f"/v1/payment_methods/{uuid4()}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"

    def test_delete_default_returns_400(self, client, default_payment_method):
        """Test deleting a default payment method returns 400."""
        response = client.delete(f"/v1/payment_methods/{default_payment_method.id}")
        assert response.status_code == 400
        assert "default" in response.json()["detail"].lower()


class TestSetDefaultPaymentMethod:
    """Tests for POST /v1/payment_methods/{id}/set_default."""

    def test_set_default(self, client, payment_method):
        """Test setting a payment method as default."""
        response = client.post(
            f"/v1/payment_methods/{payment_method.id}/set_default"
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is True

    def test_set_default_unsets_previous(
        self, client, payment_method, default_payment_method
    ):
        """Test that setting a new default unsets the previous one."""
        # payment_method is not default, default_payment_method is default
        response = client.post(
            f"/v1/payment_methods/{payment_method.id}/set_default"
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is True

        # Check that the old default was unset
        response = client.get(
            f"/v1/payment_methods/{default_payment_method.id}"
        )
        assert response.status_code == 200
        assert response.json()["is_default"] is False

    def test_set_default_not_found(self, client):
        """Test setting default for non-existent payment method."""
        response = client.post(
            f"/v1/payment_methods/{uuid4()}/set_default"
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Payment method not found"


class TestSetupSession:
    """Tests for POST /v1/payment_methods/setup."""

    @patch("app.routers.payment_methods.get_payment_provider")
    def test_create_setup_session(self, mock_get_provider, client, customer):
        """Test creating a setup session successfully."""
        mock_provider = MagicMock()
        mock_provider.create_checkout_setup_session.return_value = SetupSession(
            provider_setup_id="seti_mock_123",
            setup_url="https://checkout.stripe.com/seti_mock_123",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payment_methods/setup",
            json={
                "customer_id": str(customer.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["setup_id"] == "seti_mock_123"
        assert data["setup_url"] == "https://checkout.stripe.com/seti_mock_123"
        assert data["provider"] == "stripe"
        assert data["expires_at"] is not None

    def test_create_setup_session_customer_not_found(self, client):
        """Test creating a setup session with non-existent customer."""
        response = client.post(
            "/v1/payment_methods/setup",
            json={
                "customer_id": str(uuid4()),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Customer not found"

    @patch("app.routers.payment_methods.get_payment_provider")
    def test_create_setup_session_provider_not_supported(
        self, mock_get_provider, client, customer
    ):
        """Test creating setup session when provider doesn't support it."""
        mock_provider = MagicMock()
        mock_provider.create_checkout_setup_session.side_effect = NotImplementedError(
            "manual does not support setup sessions"
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payment_methods/setup",
            json={
                "customer_id": str(customer.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
                "provider": "manual",
            },
        )
        assert response.status_code == 501

    @patch("app.routers.payment_methods.get_payment_provider")
    def test_create_setup_session_provider_not_configured(
        self, mock_get_provider, client, customer
    ):
        """Test creating setup session when provider is not configured."""
        mock_provider = MagicMock()
        mock_provider.create_checkout_setup_session.side_effect = ImportError(
            "stripe not installed"
        )
        mock_get_provider.return_value = mock_provider

        response = client.post(
            "/v1/payment_methods/setup",
            json={
                "customer_id": str(customer.id),
                "success_url": "https://example.com/success",
                "cancel_url": "https://example.com/cancel",
            },
        )
        assert response.status_code == 503
        assert "not configured" in response.json()["detail"]


class TestStripeSetupSession:
    """Tests for StripeProvider.create_checkout_setup_session."""

    def test_stripe_setup_session(self):
        """Test Stripe setup session creation with mocked stripe module."""
        import stripe

        mock_session = MagicMock()
        mock_session.id = "cs_setup_mock"
        mock_session.url = "https://checkout.stripe.com/cs_setup_mock"
        mock_session.expires_at = 1234567890

        provider = StripeProvider(api_key="sk_test_key")
        _ = provider.stripe

        with patch.object(
            stripe.checkout.Session, "create", return_value=mock_session
        ) as mock_create:
            session = provider.create_checkout_setup_session(
                customer_id=uuid4(),
                customer_email="setup@test.com",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={"source": "test"},
            )

            assert session.provider_setup_id == "cs_setup_mock"
            assert session.setup_url == "https://checkout.stripe.com/cs_setup_mock"
            assert session.expires_at is not None
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args[1]
            assert call_kwargs["mode"] == "setup"
            assert call_kwargs["customer_email"] == "setup@test.com"

    def test_stripe_setup_session_without_email(self):
        """Test Stripe setup session without customer email."""
        import stripe

        mock_session = MagicMock()
        mock_session.id = "cs_setup_no_email"
        mock_session.url = "https://checkout.stripe.com/cs_setup_no_email"
        mock_session.expires_at = None

        provider = StripeProvider(api_key="sk_test_key")
        _ = provider.stripe

        with patch.object(
            stripe.checkout.Session, "create", return_value=mock_session
        ) as mock_create:
            session = provider.create_checkout_setup_session(
                customer_id=uuid4(),
                customer_email=None,
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

            assert session.provider_setup_id == "cs_setup_no_email"
            assert session.expires_at is None
            call_kwargs = mock_create.call_args[1]
            assert "customer_email" not in call_kwargs

    @patch("app.services.payment_provider.settings")
    def test_stripe_setup_session_with_mock_stripe(self, mock_settings):
        """Test Stripe setup session with fully mocked stripe module."""
        mock_settings.stripe_api_key = "sk_test_123"

        mock_stripe = MagicMock()
        mock_session = MagicMock()
        mock_session.id = "cs_setup_full_mock"
        mock_session.url = "https://checkout.stripe.com/cs_setup_full_mock"
        mock_session.expires_at = 1234567890
        mock_stripe.checkout.Session.create.return_value = mock_session

        provider = StripeProvider(api_key="sk_test_123")
        provider._stripe = mock_stripe

        session = provider.create_checkout_setup_session(
            customer_id=uuid4(),
            customer_email="mock@test.com",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )

        assert session.provider_setup_id == "cs_setup_full_mock"
        call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
        assert call_kwargs["mode"] == "setup"
        assert call_kwargs["customer_email"] == "mock@test.com"


class TestPaymentProviderBaseSetupSession:
    """Tests for the default create_checkout_setup_session on PaymentProviderBase."""

    def test_manual_provider_setup_session_not_supported(self):
        """Test that ManualProvider raises NotImplementedError for setup sessions."""
        from app.services.payment_provider import ManualProvider

        provider = ManualProvider()
        with pytest.raises(NotImplementedError, match="manual does not support setup sessions"):
            provider.create_checkout_setup_session(
                customer_id=uuid4(),
                customer_email="test@example.com",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )

    def test_ucp_provider_setup_session_not_supported(self):
        """Test that UCPProvider raises NotImplementedError for setup sessions."""
        from app.services.payment_provider import UCPProvider

        provider = UCPProvider()
        with pytest.raises(NotImplementedError, match="ucp does not support setup sessions"):
            provider.create_checkout_setup_session(
                customer_id=uuid4(),
                customer_email="test@example.com",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )


class TestSetupSessionSchemas:
    """Tests for setup session schemas."""

    def test_setup_session_create_defaults(self):
        """Test SetupSessionCreate with default provider."""
        schema = SetupSessionCreate(
            customer_id=uuid4(),
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert schema.provider.value == "stripe"

    def test_setup_session_create_custom_provider(self):
        """Test SetupSessionCreate with custom provider."""
        schema = SetupSessionCreate(
            customer_id=uuid4(),
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            provider="manual",
        )
        assert schema.provider.value == "manual"

    def test_setup_session_response(self):
        """Test SetupSessionResponse serialization."""
        resp = SetupSessionResponse(
            setup_id="seti_123",
            setup_url="https://example.com/setup",
            provider="stripe",
            expires_at=datetime.now(UTC),
        )
        assert resp.setup_id == "seti_123"
        assert resp.provider == "stripe"

    def test_setup_session_response_no_expiry(self):
        """Test SetupSessionResponse without expiry."""
        resp = SetupSessionResponse(
            setup_id="seti_456",
            setup_url="https://example.com/setup",
            provider="stripe",
        )
        assert resp.expires_at is None
