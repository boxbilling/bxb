"""Tests for Invoice API and Repository."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.billable_metric import BillableMetric
from app.models.charge import Charge
from app.models.event import Event
from app.models.invoice import InvoiceStatus
from app.models.payment import Payment, PaymentStatus
from app.models.plan import Plan, PlanInterval
from app.models.subscription import Subscription, SubscriptionStatus
from app.repositories.audit_log_repository import AuditLogRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.payment_method_repository import PaymentMethodRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.customer import CustomerCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem, InvoiceUpdate
from app.schemas.payment_method import PaymentMethodCreate
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.payment_provider import ChargeResult
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
    """Create a test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(external_id="inv_test_cust", name="Invoice Test Customer"), DEFAULT_ORG_ID
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(code="inv_test_plan", name="Invoice Test Plan", interval="monthly"),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id="inv_test_sub",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def sample_line_items():
    """Sample line items for invoice creation."""
    return [
        InvoiceLineItem(
            description="Base subscription fee",
            quantity=Decimal("1"),
            unit_price=Decimal("29.99"),
            amount=Decimal("29.99"),
        ),
        InvoiceLineItem(
            description="API calls overage",
            quantity=Decimal("1000"),
            unit_price=Decimal("0.01"),
            amount=Decimal("10.00"),
            metric_code="api_calls",
        ),
    ]


class TestInvoiceRepository:
    def test_create_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            currency="USD",
            line_items=sample_line_items,
            due_date=datetime.now(UTC) + timedelta(days=14),
        )

        invoice = repo.create(data, DEFAULT_ORG_ID)

        assert invoice.id is not None
        assert invoice.invoice_number.startswith("INV-")
        assert invoice.customer_id == customer.id
        assert invoice.subscription_id == subscription.id
        assert invoice.status == InvoiceStatus.DRAFT.value
        assert invoice.subtotal == Decimal("39.99")
        assert invoice.total == Decimal("39.99")
        assert len(invoice.line_items) == 2

    def test_generate_invoice_number_sequence(
        self, db_session, customer, subscription, sample_line_items
    ):
        """Test that invoice numbers are sequential."""
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )

        invoice1 = repo.create(data, DEFAULT_ORG_ID)
        invoice2 = repo.create(data, DEFAULT_ORG_ID)

        # Extract sequence numbers
        seq1 = int(invoice1.invoice_number.split("-")[-1])
        seq2 = int(invoice2.invoice_number.split("-")[-1])

        assert seq2 == seq1 + 1

    def test_get_by_id(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        fetched = repo.get_by_id(invoice.id)
        assert fetched is not None
        assert fetched.id == invoice.id

    def test_get_by_id_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_invoice_number(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        fetched = repo.get_by_invoice_number(invoice.invoice_number)
        assert fetched is not None
        assert fetched.id == invoice.id

    def test_get_by_invoice_number_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.get_by_invoice_number("INV-NOTEXIST-0001") is None

    def test_get_all(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        # Create multiple invoices
        invoices_created = []
        for i in range(3):
            data = InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=i),
                billing_period_end=datetime.now(UTC) + timedelta(days=30 + i),
                line_items=sample_line_items,
            )
            invoices_created.append(repo.create(data, DEFAULT_ORG_ID))

        invoices = repo.get_all(DEFAULT_ORG_ID)
        assert len(invoices) >= 3

    def test_get_all_with_filters(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        # Create an invoice
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        repo.create(data, DEFAULT_ORG_ID)

        # Test customer_id filter
        invoices = repo.get_all(DEFAULT_ORG_ID, customer_id=customer.id)
        assert len(invoices) == 1

        # Test subscription_id filter
        invoices = repo.get_all(DEFAULT_ORG_ID, subscription_id=subscription.id)
        assert len(invoices) == 1

        # Test status filter
        invoices = repo.get_all(DEFAULT_ORG_ID, status=InvoiceStatus.DRAFT)
        assert len(invoices) == 1

        # Test no match
        invoices = repo.get_all(DEFAULT_ORG_ID, customer_id=uuid4())
        assert len(invoices) == 0

    def test_get_all_pagination(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        # Create 5 invoices
        for i in range(5):
            data = InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=i * 10),
                billing_period_end=datetime.now(UTC) + timedelta(days=30 + i * 10),
                line_items=sample_line_items,
            )
            repo.create(data, DEFAULT_ORG_ID)

        # Test pagination
        invoices = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(invoices) == 2

    def test_generate_invoice_number_with_invalid_format(
        self, db_session, customer, subscription, sample_line_items
    ):
        """Test that invalid invoice number format in DB falls back to sequence 1."""
        repo = InvoiceRepository(db_session)

        # First create a valid invoice
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        # Manually corrupt the invoice number to have today's prefix but invalid suffix
        today = datetime.now().strftime("%Y%m%d")
        invoice.invoice_number = f"INV-{today}-INVALID"  # type: ignore[assignment]
        db_session.commit()

        # Create another invoice - should handle invalid format gracefully
        data2 = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC) + timedelta(days=31),
            billing_period_end=datetime.now(UTC) + timedelta(days=60),
            line_items=sample_line_items,
        )
        invoice2 = repo.create(data2, DEFAULT_ORG_ID)

        # Should still generate a valid invoice number with sequence 1
        assert invoice2.invoice_number.startswith("INV-")
        assert invoice2.invoice_number.endswith("-0001")

    def test_update_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        # Update due date
        new_due_date = datetime.now(UTC) + timedelta(days=30)
        updated = repo.update(invoice.id, InvoiceUpdate(due_date=new_due_date))

        assert updated is not None
        assert updated.due_date is not None

    def test_update_invoice_status(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        # Update status via update method
        updated = repo.update(invoice.id, InvoiceUpdate(status=InvoiceStatus.FINALIZED))
        assert updated is not None
        assert updated.status == InvoiceStatus.FINALIZED.value

    def test_update_invoice_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.update(uuid4(), InvoiceUpdate(due_date=datetime.now(UTC))) is None

    def test_finalize_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        finalized = repo.finalize(invoice.id)

        assert finalized is not None
        assert finalized.status == InvoiceStatus.FINALIZED.value
        assert finalized.issued_at is not None

    def test_finalize_invoice_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.finalize(uuid4()) is None

    def test_finalize_non_draft_invoice(
        self, db_session, customer, subscription, sample_line_items
    ):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        # Try to finalize again
        with pytest.raises(ValueError, match="Only draft invoices can be finalized"):
            repo.finalize(invoice.id)

    def test_mark_paid(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        paid = repo.mark_paid(invoice.id)

        assert paid is not None
        assert paid.status == InvoiceStatus.PAID.value
        assert paid.paid_at is not None

    def test_mark_paid_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.mark_paid(uuid4()) is None

    def test_mark_paid_draft_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        with pytest.raises(ValueError, match="Only finalized invoices can be marked as paid"):
            repo.mark_paid(invoice.id)

    def test_void_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        voided = repo.void(invoice.id)

        assert voided is not None
        assert voided.status == InvoiceStatus.VOIDED.value

    def test_void_invoice_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.void(uuid4()) is None

    def test_void_paid_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        with pytest.raises(ValueError, match="Paid invoices cannot be voided"):
            repo.void(invoice.id)

    def test_delete_draft_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        result = repo.delete(invoice.id, DEFAULT_ORG_ID)

        assert result is True
        assert repo.get_by_id(invoice.id) is None

    def test_delete_invoice_not_found(self, db_session):
        repo = InvoiceRepository(db_session)
        assert repo.delete(uuid4(), DEFAULT_ORG_ID) is False

    def test_delete_finalized_invoice(self, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)

        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with pytest.raises(ValueError, match="Only draft invoices can be deleted"):
            repo.delete(invoice.id, DEFAULT_ORG_ID)


class TestInvoicesAPI:
    def test_list_invoices_empty(self, client):
        response = client.get("/v1/invoices/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_invoices(self, client, db_session, customer, subscription, sample_line_items):
        # Create invoice directly
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        repo.create(data, DEFAULT_ORG_ID)

        response = client.get("/v1/invoices/")
        assert response.status_code == 200
        invoices = response.json()
        assert len(invoices) == 1

    def test_list_invoices_with_filters(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        repo.create(data, DEFAULT_ORG_ID)

        # Filter by customer_id
        response = client.get(f"/v1/invoices/?customer_id={customer.id}")
        assert response.status_code == 200
        assert len(response.json()) == 1

        # Filter by status
        response = client.get("/v1/invoices/?status=draft")
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_get_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.get(f"/v1/invoices/{invoice.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(invoice.id)
        assert data["status"] == "draft"

    def test_get_invoice_not_found(self, client):
        response = client.get(f"/v1/invoices/{uuid4()}")
        assert response.status_code == 404

    def test_update_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.put(
            f"/v1/invoices/{invoice.id}",
            json={"due_date": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
        )
        assert response.status_code == 200

    def test_update_invoice_not_found(self, client):
        response = client.put(
            f"/v1/invoices/{uuid4()}",
            json={"due_date": datetime.now(UTC).isoformat()},
        )
        assert response.status_code == 404

    def test_finalize_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200
        assert response.json()["status"] == "finalized"

        # Verify audit log was created
        audit_repo = AuditLogRepository(db_session)
        logs = audit_repo.get_by_resource("invoice", invoice.id)
        assert any(log.action == "status_changed" for log in logs)

    def test_finalize_invoice_not_found(self, client):
        response = client.post(f"/v1/invoices/{uuid4()}/finalize")
        assert response.status_code == 404

    def test_finalize_non_draft(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 400

    def test_pay_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        response = client.post(f"/v1/invoices/{invoice.id}/pay")
        assert response.status_code == 200
        assert response.json()["status"] == "paid"

        # Verify audit log was created
        audit_repo = AuditLogRepository(db_session)
        logs = audit_repo.get_by_resource("invoice", invoice.id)
        status_logs = [log for log in logs if log.action == "status_changed"]
        assert any(
            log.changes.get("status", {}).get("new") == "paid" for log in status_logs
        )

    def test_pay_invoice_not_found(self, client):
        response = client.post(f"/v1/invoices/{uuid4()}/pay")
        assert response.status_code == 404

    def test_pay_draft_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/pay")
        assert response.status_code == 400

    def test_void_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/void")
        assert response.status_code == 200
        assert response.json()["status"] == "voided"

        # Verify audit log was created
        audit_repo = AuditLogRepository(db_session)
        logs = audit_repo.get_by_resource("invoice", invoice.id)
        status_logs = [log for log in logs if log.action == "status_changed"]
        assert any(
            log.changes.get("status", {}).get("new") == "voided" for log in status_logs
        )

    def test_void_invoice_not_found(self, client):
        response = client.post(f"/v1/invoices/{uuid4()}/void")
        assert response.status_code == 404

    def test_void_paid_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        response = client.post(f"/v1/invoices/{invoice.id}/void")
        assert response.status_code == 400

    def test_delete_invoice(self, client, db_session, customer, subscription, sample_line_items):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.delete(f"/v1/invoices/{invoice.id}")
        assert response.status_code == 204

    def test_delete_invoice_not_found(self, client):
        response = client.delete(f"/v1/invoices/{uuid4()}")
        assert response.status_code == 404

    def test_delete_finalized_invoice(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        response = client.delete(f"/v1/invoices/{invoice.id}")
        assert response.status_code == 400


class TestInvoiceWalletIntegration:
    """Tests for wallet credit consumption during invoice finalization."""

    def test_finalize_with_wallet_full_coverage(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that wallet credits fully cover invoice and mark it as paid."""
        from app.services.wallet_service import WalletService

        # Create a wallet with enough credits to cover invoice total
        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Full Coverage",
            code="full-cov",
            initial_granted_credits=Decimal("100"),  # rate=1, balance=100 cents
        )

        # Create invoice with total = 39.99 (from sample_line_items)
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200
        data = response.json()

        # Invoice should be marked as paid since wallet fully covers it
        assert data["status"] == "paid"
        assert Decimal(data["prepaid_credit_amount"]) == Decimal(str(invoice.total))
        assert data["paid_at"] is not None

    def test_finalize_with_wallet_partial_coverage(
        self, client, db_session, customer, subscription
    ):
        """Test that wallet credits partially cover invoice, recording prepaid amount."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Partial Coverage",
            code="partial-cov",
            initial_granted_credits=Decimal("10"),  # Only 10 cents
        )

        # Create invoice with higher total
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=[
                InvoiceLineItem(
                    description="Big charge",
                    quantity=Decimal("1"),
                    unit_price=Decimal("500.00"),
                    amount=Decimal("500.00"),
                ),
            ],
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200
        data = response.json()

        # Invoice should be finalized (not paid, since only partially covered)
        assert data["status"] == "finalized"
        assert Decimal(data["prepaid_credit_amount"]) == Decimal("10")

    def test_finalize_without_wallet(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that finalization works normally without any wallets."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "finalized"
        assert Decimal(data["prepaid_credit_amount"]) == Decimal("0")

    def test_finalize_creates_wallet_transactions(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that finalizing an invoice creates outbound wallet transactions."""
        from app.repositories.wallet_transaction_repository import WalletTransactionRepository
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Txn Check",
            code="txn-check",
            initial_granted_credits=Decimal("100"),
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        client.post(f"/v1/invoices/{invoice.id}/finalize")

        # Verify outbound transaction was created
        txn_repo = WalletTransactionRepository(db_session)
        outbound = txn_repo.get_outbound_by_wallet_id(wallet.id)
        assert len(outbound) == 1
        assert outbound[0].transaction_type == "outbound"
        assert outbound[0].invoice_id == invoice.id

    def test_finalize_with_multiple_wallets_priority(
        self, client, db_session, customer, subscription
    ):
        """Test that finalization uses wallets in priority order."""
        from app.repositories.wallet_repository import WalletRepository
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        w1 = wallet_service.create_wallet(
            customer_id=customer.id,
            name="P2",
            code="p2",
            priority=2,
            initial_granted_credits=Decimal("50"),
        )
        w2 = wallet_service.create_wallet(
            customer_id=customer.id,
            name="P1",
            code="p1",
            priority=1,
            initial_granted_credits=Decimal("50"),
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=[
                InvoiceLineItem(
                    description="Priority test",
                    quantity=Decimal("1"),
                    unit_price=Decimal("60.00"),
                    amount=Decimal("60.00"),
                ),
            ],
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"

        # P1 (priority=1) should be drained first, then P2 used for remainder
        wallet_repo = WalletRepository(db_session)
        w2_updated = wallet_repo.get_by_id(w2.id)
        w1_updated = wallet_repo.get_by_id(w1.id)
        assert Decimal(str(w2_updated.balance_cents)) == Decimal("0")  # P1 drained
        assert Decimal(str(w1_updated.balance_cents)) == Decimal("40.0000")  # P2 partially used

    def test_finalize_zero_total_invoice_no_wallet_consumption(
        self, client, db_session, customer, subscription
    ):
        """Test that zero-total invoice doesn't trigger wallet consumption."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet = wallet_service.create_wallet(
            customer_id=customer.id,
            name="Untouched",
            code="untouched",
            initial_granted_credits=Decimal("100"),
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=[
                InvoiceLineItem(
                    description="Free",
                    quantity=Decimal("1"),
                    unit_price=Decimal("0"),
                    amount=Decimal("0"),
                ),
            ],
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")
        assert response.status_code == 200

        # Wallet balance should be untouched
        from app.repositories.wallet_repository import WalletRepository

        wallet_repo = WalletRepository(db_session)
        updated = wallet_repo.get_by_id(wallet.id)
        assert Decimal(str(updated.balance_cents)) == Decimal("100.0000")

    def test_prepaid_credit_amount_in_response(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that prepaid_credit_amount field is present in invoice responses."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        # Check GET endpoint includes prepaid_credit_amount
        response = client.get(f"/v1/invoices/{invoice.id}")
        assert response.status_code == 200
        data = response.json()
        assert "prepaid_credit_amount" in data
        assert Decimal(data["prepaid_credit_amount"]) == Decimal("0")

    def test_coupons_amount_cents_in_response(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that coupons_amount_cents field is present in invoice responses."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.get(f"/v1/invoices/{invoice.id}")
        assert response.status_code == 200
        data = response.json()
        assert "coupons_amount_cents" in data
        assert Decimal(data["coupons_amount_cents"]) == Decimal("0")


class TestInvoiceRouterEdgeCases:
    """Tests for defensive checks in invoice router actions."""

    def test_finalize_returns_none_race_condition(
        self,
        client,
        db_session,
        customer,
        subscription,
        sample_line_items,
    ):
        """Test finalize endpoint when repo.finalize returns None (race condition)."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        with patch.object(InvoiceRepository, "finalize", return_value=None):
            response = client.post(f"/v1/invoices/{invoice.id}/finalize")
            assert response.status_code == 404

    def test_mark_paid_returns_none_race_condition(
        self,
        client,
        db_session,
        customer,
        subscription,
        sample_line_items,
    ):
        """Test mark_paid endpoint when repo.mark_paid returns None (race condition)."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with patch.object(InvoiceRepository, "mark_paid", return_value=None):
            response = client.post(f"/v1/invoices/{invoice.id}/pay")
            assert response.status_code == 404

    def test_void_returns_none_race_condition(
        self,
        client,
        db_session,
        customer,
        subscription,
        sample_line_items,
    ):
        """Test void endpoint when repo.void returns None (race condition)."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with patch.object(InvoiceRepository, "void", return_value=None):
            response = client.post(f"/v1/invoices/{invoice.id}/void")
            assert response.status_code == 404


class TestDownloadInvoicePdf:
    """Tests for POST /v1/invoices/{invoice_id}/download_pdf endpoint."""

    def test_download_pdf_finalized(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful PDF download for a finalized invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with patch(
            "app.routers.invoices.PdfService.generate_invoice_pdf",
            return_value=b"%PDF-test",
        ):
            response = client.post(f"/v1/invoices/{invoice.id}/download_pdf")

        assert response.status_code == 200
        assert response.content == b"%PDF-test"
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers["content-disposition"]
        assert invoice.invoice_number in response.headers["content-disposition"]

    def test_download_pdf_paid(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful PDF download for a paid invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        with patch(
            "app.routers.invoices.PdfService.generate_invoice_pdf",
            return_value=b"%PDF-test",
        ):
            response = client.post(f"/v1/invoices/{invoice.id}/download_pdf")

        assert response.status_code == 200
        assert response.content == b"%PDF-test"

    def test_download_pdf_draft_returns_400(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that downloading PDF for a draft invoice returns 400."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/download_pdf")
        assert response.status_code == 400

    def test_download_pdf_not_found(self, client):
        """Test that downloading PDF for a non-existent invoice returns 404."""
        response = client.post(f"/v1/invoices/{uuid4()}/download_pdf")
        assert response.status_code == 404


class TestInvoiceRepositoryCount:
    """Tests for InvoiceRepository.count branch coverage."""

    def test_count_without_organization_id(self, db_session):
        """Test count() without org_id returns total count across all orgs."""
        repo = InvoiceRepository(db_session)
        result = repo.count()
        assert isinstance(result, int)
        assert result >= 0


class TestInvoicePreviewAPI:
    """Tests for POST /v1/invoices/preview endpoint."""

    @pytest.fixture
    def preview_metric(self, db_session):
        """Create a billable metric for preview tests."""
        m = BillableMetric(
            code="preview_api_calls",
            name="API Calls",
            aggregation_type="count",
        )
        db_session.add(m)
        db_session.commit()
        db_session.refresh(m)
        return m

    @pytest.fixture
    def preview_plan(self, db_session):
        """Create a plan for preview tests."""
        p = Plan(
            code="preview_plan",
            name="Preview Plan",
            interval=PlanInterval.MONTHLY.value,
        )
        db_session.add(p)
        db_session.commit()
        db_session.refresh(p)
        return p

    @pytest.fixture
    def preview_charge(self, db_session, preview_plan, preview_metric):
        """Create a charge linking plan to metric."""
        c = Charge(
            plan_id=preview_plan.id,
            billable_metric_id=preview_metric.id,
            charge_model="standard",
            properties={"unit_price": "100"},
        )
        db_session.add(c)
        db_session.commit()
        db_session.refresh(c)
        return c

    @pytest.fixture
    def preview_subscription(self, db_session, customer, preview_plan):
        """Create an active subscription for preview tests."""
        sub = Subscription(
            external_id="preview_test_sub",
            customer_id=customer.id,
            plan_id=preview_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)
        return sub

    def test_preview_invoice_success(
        self,
        client,
        db_session,
        customer,
        preview_metric,
        preview_charge,
        preview_subscription,
    ):
        """Test successful invoice preview."""
        # Create some events for the customer
        now = datetime.now(UTC)
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        for i in range(5):
            event = Event(
                transaction_id=f"prev-tx-{i}",
                external_customer_id=customer.external_id,
                code="preview_api_calls",
                timestamp=start + timedelta(hours=i),
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(
            "/v1/invoices/preview",
            json={"subscription_id": str(preview_subscription.id)},
        )
        assert response.status_code == 200
        data = response.json()
        assert "subtotal" in data
        assert "tax_amount" in data
        assert "coupons_amount" in data
        assert "prepaid_credit_amount" in data
        assert "total" in data
        assert "currency" in data
        assert "fees" in data
        assert len(data["fees"]) >= 1
        # 5 events * 100 cents unit_price = 500
        assert Decimal(data["subtotal"]) == Decimal("500")

    def test_preview_invoice_with_billing_period(
        self,
        client,
        db_session,
        customer,
        preview_metric,
        preview_charge,
        preview_subscription,
    ):
        """Test invoice preview with explicit billing period."""
        start = datetime(2024, 6, 1, tzinfo=UTC)
        end = datetime(2024, 7, 1, tzinfo=UTC)

        # Create events in the billing period
        for i in range(3):
            event = Event(
                transaction_id=f"prev-period-tx-{i}",
                external_customer_id=customer.external_id,
                code="preview_api_calls",
                timestamp=start + timedelta(days=i),
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(
            "/v1/invoices/preview",
            json={
                "subscription_id": str(preview_subscription.id),
                "billing_period_start": start.isoformat(),
                "billing_period_end": end.isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["subtotal"]) == Decimal("300")
        assert len(data["fees"]) == 1

    def test_preview_invoice_subscription_not_found(self, client):
        """Test preview with non-existent subscription."""
        response = client.post(
            "/v1/invoices/preview",
            json={"subscription_id": str(uuid4())},
        )
        assert response.status_code == 404
        assert "Subscription not found" in response.json()["detail"]

    def test_preview_invoice_inactive_subscription(
        self,
        client,
        db_session,
        customer,
        preview_plan,
        preview_metric,
        preview_charge,
    ):
        """Test preview with a non-active subscription returns 400."""
        sub = Subscription(
            external_id="preview_canceled_sub",
            customer_id=customer.id,
            plan_id=preview_plan.id,
            status=SubscriptionStatus.CANCELED.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.post(
            "/v1/invoices/preview",
            json={"subscription_id": str(sub.id)},
        )
        assert response.status_code == 400

    def test_preview_invoice_customer_not_found(
        self,
        client,
        db_session,
        preview_plan,
        preview_metric,
        preview_charge,
    ):
        """Test preview when subscription has orphaned customer_id."""
        sub = Subscription(
            external_id="preview_orphan_sub",
            customer_id=uuid4(),
            plan_id=preview_plan.id,
            status=SubscriptionStatus.ACTIVE.value,
            started_at=datetime.now(UTC) - timedelta(days=30),
        )
        db_session.add(sub)
        db_session.commit()
        db_session.refresh(sub)

        response = client.post(
            "/v1/invoices/preview",
            json={"subscription_id": str(sub.id)},
        )
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_preview_invoice_zero_usage(
        self,
        client,
        db_session,
        customer,
        preview_metric,
        preview_charge,
        preview_subscription,
    ):
        """Test preview with zero usage returns zero amounts."""
        # Use a billing period with no events
        start = datetime(2020, 1, 1, tzinfo=UTC)
        end = datetime(2020, 2, 1, tzinfo=UTC)

        response = client.post(
            "/v1/invoices/preview",
            json={
                "subscription_id": str(preview_subscription.id),
                "billing_period_start": start.isoformat(),
                "billing_period_end": end.isoformat(),
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["subtotal"]) == Decimal("0")
        assert Decimal(data["total"]) == Decimal("0")
        # No fees generated since usage is zero
        assert len(data["fees"]) == 0

    def test_preview_does_not_persist_records(
        self,
        client,
        db_session,
        customer,
        preview_metric,
        preview_charge,
        preview_subscription,
    ):
        """Test that preview does not create any Invoice or Fee records."""
        from app.models.fee import Fee
        from app.models.invoice import Invoice

        invoice_count_before = db_session.query(Invoice).count()
        fee_count_before = db_session.query(Fee).count()

        # Create events
        now = datetime.now(UTC)
        start = datetime(now.year, now.month, 1, tzinfo=UTC)
        for i in range(3):
            event = Event(
                transaction_id=f"prev-nopersist-{i}",
                external_customer_id=customer.external_id,
                code="preview_api_calls",
                timestamp=start + timedelta(hours=i),
            )
            db_session.add(event)
        db_session.commit()

        response = client.post(
            "/v1/invoices/preview",
            json={"subscription_id": str(preview_subscription.id)},
        )
        assert response.status_code == 200

        invoice_count_after = db_session.query(Invoice).count()
        fee_count_after = db_session.query(Fee).count()

        assert invoice_count_after == invoice_count_before
        assert fee_count_after == fee_count_before


class TestInvoicePaymentMethodIntegration:
    """Tests for auto-charge with default payment method during invoice finalization."""

    @pytest.fixture
    def payment_method(self, db_session, customer):
        """Create a default payment method for the customer."""
        pm_repo = PaymentMethodRepository(db_session)
        return pm_repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_test_123",
                type="card",
                is_default=True,
                details={"last4": "4242", "brand": "visa"},
            ),
            DEFAULT_ORG_ID,
        )

    def test_finalize_auto_charges_default_payment_method(
        self, client, db_session, customer, subscription, sample_line_items, payment_method
    ):
        """Test that finalize auto-charges when customer has a default payment method."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        mock_result = ChargeResult(
            provider_payment_id="pi_test_success",
            status="succeeded",
        )

        with patch(
            "app.routers.invoices.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.charge_payment_method.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert data["paid_at"] is not None

        # Verify a payment record was created
        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.SUCCEEDED.value
        assert payments[0].provider_payment_id == "pi_test_success"

    def test_finalize_no_auto_charge_without_default_method(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that finalize does NOT auto-charge when no default payment method exists."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"

        # No payment records should be created
        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 0

    def test_finalize_failed_charge_leaves_invoice_finalized(
        self, client, db_session, customer, subscription, sample_line_items, payment_method
    ):
        """Test that a failed charge leaves the invoice as finalized with a failed payment."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        mock_result = ChargeResult(
            provider_payment_id="pi_test_failed",
            status="failed",
            failure_reason="Your card was declined.",
        )

        with patch(
            "app.routers.invoices.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.charge_payment_method.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"
        assert data["paid_at"] is None

        # Verify a failed payment record was created
        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.FAILED.value
        assert payments[0].failure_reason == "Your card was declined."
        assert payments[0].provider_payment_id == "pi_test_failed"

    def test_finalize_no_auto_charge_when_wallet_covers_full_amount(
        self, client, db_session, customer, subscription, sample_line_items, payment_method
    ):
        """Test that no auto-charge happens when wallet credits fully cover the invoice."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Full Cover",
            code="full-cover-pm",
            initial_granted_credits=Decimal("100"),
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"

        # No payment records should be created since wallet covers everything
        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 0

    def test_finalize_auto_charges_remaining_after_partial_wallet(
        self, client, db_session, customer, subscription, payment_method
    ):
        """Test auto-charge for the remaining amount after partial wallet coverage."""
        from app.services.wallet_service import WalletService

        wallet_service = WalletService(db_session)
        wallet_service.create_wallet(
            customer_id=customer.id,
            name="Partial",
            code="partial-pm",
            initial_granted_credits=Decimal("10"),
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=[
                InvoiceLineItem(
                    description="Test charge",
                    quantity=Decimal("1"),
                    unit_price=Decimal("50.00"),
                    amount=Decimal("50.00"),
                ),
            ],
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        mock_result = ChargeResult(
            provider_payment_id="pi_test_partial",
            status="succeeded",
        )

        with patch(
            "app.routers.invoices.get_payment_provider"
        ) as mock_get_provider:
            mock_provider = MagicMock()
            mock_provider.charge_payment_method.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "paid"
        assert Decimal(data["prepaid_credit_amount"]) == Decimal("10")

        # Verify a payment record for the remaining 40.00 was created
        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 1
        assert payments[0].status == PaymentStatus.SUCCEEDED.value
        assert Decimal(str(payments[0].amount)) == Decimal("40")

    def test_finalize_no_auto_charge_non_default_payment_method(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that non-default payment methods don't trigger auto-charge."""
        pm_repo = PaymentMethodRepository(db_session)
        pm_repo.create(
            PaymentMethodCreate(
                customer_id=customer.id,
                provider="stripe",
                provider_payment_method_id="pm_test_nondefault",
                type="card",
                is_default=False,
                details={"last4": "1234"},
            ),
            DEFAULT_ORG_ID,
        )

        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "finalized"

        payments = db_session.query(Payment).filter(Payment.invoice_id == invoice.id).all()
        assert len(payments) == 0

    def test_finalize_auto_charge_mark_paid_returns_none(
        self, client, db_session, customer, subscription, sample_line_items, payment_method
    ):
        """Test auto-charge when mark_paid returns None (race condition)."""
        repo = InvoiceRepository(db_session)
        invoice_data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(invoice_data, DEFAULT_ORG_ID)

        mock_result = ChargeResult(
            provider_payment_id="pi_test_race",
            status="succeeded",
        )

        with (
            patch(
                "app.routers.invoices.get_payment_provider"
            ) as mock_get_provider,
            patch.object(
                InvoiceRepository, "mark_paid", return_value=None
            ),
        ):
            mock_provider = MagicMock()
            mock_provider.charge_payment_method.return_value = mock_result
            mock_get_provider.return_value = mock_provider

            response = client.post(f"/v1/invoices/{invoice.id}/finalize")

        assert response.status_code == 200
        data = response.json()
        # Invoice stays finalized since mark_paid returned None
        assert data["status"] == "finalized"


class TestSendInvoiceEmailAPI:
    """Tests for POST /v1/invoices/{invoice_id}/send_email endpoint."""

    def test_send_email_finalized(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful email send for a finalized invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with (
            patch(
                "app.routers.invoices.PdfService.generate_invoice_pdf",
                return_value=b"%PDF-test",
            ),
            patch(
                "app.routers.invoices.EmailService.send_invoice_email",
                new_callable=AsyncMock,
                return_value=True,
            ) as mock_send,
        ):
            response = client.post(f"/v1/invoices/{invoice.id}/send_email")

        assert response.status_code == 200
        assert response.json() == {"sent": True}
        mock_send.assert_called_once()

    def test_send_email_paid(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful email send for a paid invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        with (
            patch(
                "app.routers.invoices.PdfService.generate_invoice_pdf",
                return_value=b"%PDF-test",
            ),
            patch(
                "app.routers.invoices.EmailService.send_invoice_email",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            response = client.post(f"/v1/invoices/{invoice.id}/send_email")

        assert response.status_code == 200
        assert response.json() == {"sent": True}

    def test_send_email_draft_returns_400(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that sending email for a draft invoice returns 400."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/send_email")
        assert response.status_code == 400
        assert "finalized or paid" in response.json()["detail"]

    def test_send_email_not_found(self, client):
        """Test that sending email for a non-existent invoice returns 404."""
        response = client.post(f"/v1/invoices/{uuid4()}/send_email")
        assert response.status_code == 404

    def test_send_email_service_returns_false(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test email service failure handling (returns False)."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with (
            patch(
                "app.routers.invoices.PdfService.generate_invoice_pdf",
                return_value=b"%PDF-test",
            ),
            patch(
                "app.routers.invoices.EmailService.send_invoice_email",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            response = client.post(f"/v1/invoices/{invoice.id}/send_email")

        assert response.status_code == 200
        assert response.json() == {"sent": False}


class TestCreateOneOffInvoiceAPI:
    """Tests for POST /v1/invoices/one_off endpoint."""

    def test_create_one_off_invoice(self, client, db_session, customer):
        """Test successful creation of a one-off invoice."""
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(customer.id),
                "currency": "USD",
                "line_items": [
                    {
                        "description": "Consulting fee",
                        "quantity": "2",
                        "unit_price": "150.00",
                        "amount": "300.00",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "draft"
        assert data["invoice_type"] == "one_off"
        assert data["customer_id"] == str(customer.id)
        assert data["subtotal"] == "300.0000"

    def test_create_one_off_invoice_with_due_date(self, client, db_session, customer):
        """Test one-off invoice creation with due date."""
        due_date = (datetime.now(UTC) + timedelta(days=30)).isoformat()
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(customer.id),
                "currency": "EUR",
                "due_date": due_date,
                "line_items": [
                    {
                        "description": "Service fee",
                        "quantity": "1",
                        "unit_price": "99.99",
                        "amount": "99.99",
                    }
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["currency"] == "EUR"
        assert data["due_date"] is not None

    def test_create_one_off_invoice_multiple_line_items(self, client, db_session, customer):
        """Test one-off invoice with multiple line items."""
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(customer.id),
                "line_items": [
                    {
                        "description": "Item A",
                        "quantity": "1",
                        "unit_price": "10.00",
                        "amount": "10.00",
                    },
                    {
                        "description": "Item B",
                        "quantity": "3",
                        "unit_price": "5.00",
                        "amount": "15.00",
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["subtotal"] == "25.0000"

    def test_create_one_off_invoice_customer_not_found(self, client):
        """Test one-off invoice creation with non-existent customer."""
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(uuid4()),
                "line_items": [
                    {
                        "description": "Test",
                        "quantity": "1",
                        "unit_price": "10.00",
                        "amount": "10.00",
                    }
                ],
            },
        )
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_create_one_off_invoice_no_line_items(self, client, db_session, customer):
        """Test one-off invoice creation with empty line items fails validation."""
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(customer.id),
                "line_items": [],
            },
        )
        assert response.status_code == 422

    def test_create_one_off_invoice_creates_audit_log(self, client, db_session, customer):
        """Test that one-off invoice creation creates an audit log."""
        response = client.post(
            "/v1/invoices/one_off",
            json={
                "customer_id": str(customer.id),
                "line_items": [
                    {
                        "description": "Audit test",
                        "quantity": "1",
                        "unit_price": "50.00",
                        "amount": "50.00",
                    }
                ],
            },
        )
        assert response.status_code == 200
        invoice_id = response.json()["id"]

        audit_repo = AuditLogRepository(db_session)
        logs = audit_repo.get_by_resource("invoice", invoice_id)
        assert len(logs) >= 1


class TestBulkFinalizeAPI:
    """Tests for POST /v1/invoices/bulk_finalize endpoint."""

    def test_bulk_finalize_success(self, client, db_session, customer, subscription, sample_line_items):
        """Test successful bulk finalization of multiple draft invoices."""
        repo = InvoiceRepository(db_session)
        invoices = []
        for i in range(3):
            data = InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=i * 30),
                billing_period_end=datetime.now(UTC) + timedelta(days=(i + 1) * 30),
                line_items=sample_line_items,
            )
            invoices.append(repo.create(data, DEFAULT_ORG_ID))

        response = client.post(
            "/v1/invoices/bulk_finalize",
            json={"invoice_ids": [str(inv.id) for inv in invoices]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["finalized_count"] == 3
        assert data["failed_count"] == 0
        assert len(data["results"]) == 3
        assert all(r["success"] for r in data["results"])

    def test_bulk_finalize_mixed_results(self, client, db_session, customer, subscription, sample_line_items):
        """Test bulk finalize with mix of valid and already-finalized invoices."""
        repo = InvoiceRepository(db_session)
        draft = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC),
                billing_period_end=datetime.now(UTC) + timedelta(days=30),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )
        already_finalized = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=30),
                billing_period_end=datetime.now(UTC) + timedelta(days=60),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )
        repo.finalize(already_finalized.id)

        response = client.post(
            "/v1/invoices/bulk_finalize",
            json={"invoice_ids": [str(draft.id), str(already_finalized.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["finalized_count"] == 1
        assert data["failed_count"] == 1

    def test_bulk_finalize_not_found(self, client):
        """Test bulk finalize with non-existent invoice IDs."""
        response = client.post(
            "/v1/invoices/bulk_finalize",
            json={"invoice_ids": [str(uuid4())]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["finalized_count"] == 0
        assert data["failed_count"] == 1
        assert data["results"][0]["error"] == "Invoice not found"

    def test_bulk_finalize_empty_list(self, client):
        """Test bulk finalize with empty list fails validation."""
        response = client.post(
            "/v1/invoices/bulk_finalize",
            json={"invoice_ids": []},
        )
        assert response.status_code == 422

    def test_bulk_finalize_repo_returns_none(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test bulk finalize when repo.finalize returns None (defensive branch)."""
        repo = InvoiceRepository(db_session)
        invoice = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC),
                billing_period_end=datetime.now(UTC) + timedelta(days=30),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )

        with patch.object(InvoiceRepository, "finalize", return_value=None):
            response = client.post(
                "/v1/invoices/bulk_finalize",
                json={"invoice_ids": [str(invoice.id)]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["finalized_count"] == 0
        assert data["failed_count"] == 1
        assert data["results"][0]["error"] == "Failed to finalize"


class TestSendInvoiceReminderAPI:
    """Tests for POST /v1/invoices/{invoice_id}/send_reminder endpoint."""

    def test_send_reminder_finalized(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful reminder send for a finalized invoice."""
        # Ensure customer has email
        customer.email = "test@example.com"
        db_session.commit()

        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with patch(
            "app.routers.invoices.EmailService.send_email",
            new_callable=AsyncMock,
            return_value=True,
        ) as mock_send:
            response = client.post(f"/v1/invoices/{invoice.id}/send_reminder")

        assert response.status_code == 200
        data = response.json()
        assert data["sent"] is True
        assert data["invoice_id"] == str(invoice.id)
        mock_send.assert_called_once()

    def test_send_reminder_draft_returns_400(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that sending reminder for a draft invoice returns 400."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.post(f"/v1/invoices/{invoice.id}/send_reminder")
        assert response.status_code == 400
        assert "finalized" in response.json()["detail"]

    def test_send_reminder_paid_returns_400(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that sending reminder for a paid invoice returns 400."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        response = client.post(f"/v1/invoices/{invoice.id}/send_reminder")
        assert response.status_code == 400

    def test_send_reminder_not_found(self, client):
        """Test that sending reminder for a non-existent invoice returns 404."""
        response = client.post(f"/v1/invoices/{uuid4()}/send_reminder")
        assert response.status_code == 404

    def test_send_reminder_no_customer_email(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test reminder when customer has no email returns 400."""
        customer.email = None
        db_session.commit()

        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        response = client.post(f"/v1/invoices/{invoice.id}/send_reminder")
        assert response.status_code == 400
        assert "email" in response.json()["detail"]


class TestPdfPreviewAPI:
    """Tests for GET /v1/invoices/{invoice_id}/pdf_preview endpoint."""

    def test_pdf_preview_finalized(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful PDF preview for a finalized invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)

        with patch(
            "app.routers.invoices.PdfService.generate_invoice_pdf",
            return_value=b"%PDF-preview-test",
        ):
            response = client.get(f"/v1/invoices/{invoice.id}/pdf_preview")

        assert response.status_code == 200
        assert response.content == b"%PDF-preview-test"
        assert response.headers["content-type"] == "application/pdf"
        assert "inline" in response.headers["content-disposition"]

    def test_pdf_preview_draft_returns_400(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test that PDF preview for a draft invoice returns 400."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)

        response = client.get(f"/v1/invoices/{invoice.id}/pdf_preview")
        assert response.status_code == 400

    def test_pdf_preview_not_found(self, client):
        """Test that PDF preview for a non-existent invoice returns 404."""
        response = client.get(f"/v1/invoices/{uuid4()}/pdf_preview")
        assert response.status_code == 404

    def test_pdf_preview_paid(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test successful PDF preview for a paid invoice."""
        repo = InvoiceRepository(db_session)
        data = InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            line_items=sample_line_items,
        )
        invoice = repo.create(data, DEFAULT_ORG_ID)
        repo.finalize(invoice.id)
        repo.mark_paid(invoice.id)

        with patch(
            "app.routers.invoices.PdfService.generate_invoice_pdf",
            return_value=b"%PDF-paid",
        ):
            response = client.get(f"/v1/invoices/{invoice.id}/pdf_preview")

        assert response.status_code == 200
        assert response.content == b"%PDF-paid"


class TestBulkVoidInvoicesAPI:
    """Tests for POST /v1/invoices/bulk_void endpoint."""

    def test_bulk_void_success(self, client, db_session, customer, subscription, sample_line_items):
        """Test successful bulk voiding of multiple finalized invoices."""
        repo = InvoiceRepository(db_session)
        invoices = []
        for i in range(3):
            data = InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=i * 30),
                billing_period_end=datetime.now(UTC) + timedelta(days=(i + 1) * 30),
                line_items=sample_line_items,
            )
            inv = repo.create(data, DEFAULT_ORG_ID)
            repo.finalize(inv.id)
            invoices.append(inv)

        response = client.post(
            "/v1/invoices/bulk_void",
            json={"invoice_ids": [str(inv.id) for inv in invoices]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["voided_count"] == 3
        assert data["failed_count"] == 0
        assert len(data["results"]) == 3
        assert all(r["success"] for r in data["results"])

    def test_bulk_void_mixed_results(self, client, db_session, customer, subscription, sample_line_items):
        """Test bulk void with mix of valid and paid invoices."""
        repo = InvoiceRepository(db_session)
        finalized = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC),
                billing_period_end=datetime.now(UTC) + timedelta(days=30),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )
        repo.finalize(finalized.id)

        paid = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC) + timedelta(days=30),
                billing_period_end=datetime.now(UTC) + timedelta(days=60),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )
        repo.finalize(paid.id)
        repo.mark_paid(paid.id)

        response = client.post(
            "/v1/invoices/bulk_void",
            json={"invoice_ids": [str(finalized.id), str(paid.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["voided_count"] == 1
        assert data["failed_count"] == 1

    def test_bulk_void_not_found(self, client):
        """Test bulk void with non-existent invoice IDs."""
        response = client.post(
            "/v1/invoices/bulk_void",
            json={"invoice_ids": [str(uuid4())]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["voided_count"] == 0
        assert data["failed_count"] == 1
        assert data["results"][0]["error"] == "Invoice not found"

    def test_bulk_void_empty_list(self, client):
        """Test bulk void with empty list fails validation."""
        response = client.post(
            "/v1/invoices/bulk_void",
            json={"invoice_ids": []},
        )
        assert response.status_code == 422

    def test_bulk_void_repo_returns_none(
        self, client, db_session, customer, subscription, sample_line_items
    ):
        """Test bulk void when repo.void returns None (defensive branch)."""
        repo = InvoiceRepository(db_session)
        invoice = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC),
                billing_period_end=datetime.now(UTC) + timedelta(days=30),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )
        repo.finalize(invoice.id)

        with patch.object(InvoiceRepository, "void", return_value=None):
            response = client.post(
                "/v1/invoices/bulk_void",
                json={"invoice_ids": [str(invoice.id)]},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["voided_count"] == 0
        assert data["failed_count"] == 1
        assert data["results"][0]["error"] == "Failed to void"

    def test_bulk_void_draft_invoices(self, client, db_session, customer, subscription, sample_line_items):
        """Test bulk void of draft invoices (should succeed since void allows non-paid)."""
        repo = InvoiceRepository(db_session)
        draft = repo.create(
            InvoiceCreate(
                customer_id=customer.id,
                subscription_id=subscription.id,
                billing_period_start=datetime.now(UTC),
                billing_period_end=datetime.now(UTC) + timedelta(days=30),
                line_items=sample_line_items,
            ),
            DEFAULT_ORG_ID,
        )

        response = client.post(
            "/v1/invoices/bulk_void",
            json={"invoice_ids": [str(draft.id)]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["voided_count"] == 1
        assert data["failed_count"] == 0
