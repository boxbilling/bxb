"""Tests for DataExport model, repository, service, and API endpoints."""

import csv
import io
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
from app.models.credit_note import CreditNoteReason, CreditNoteType
from app.models.data_export import DataExport, ExportStatus, ExportType, generate_uuid
from app.repositories.credit_note_repository import CreditNoteRepository
from app.repositories.customer_repository import CustomerRepository
from app.repositories.data_export_repository import DataExportRepository
from app.repositories.event_repository import EventRepository
from app.repositories.fee_repository import FeeRepository
from app.repositories.invoice_repository import InvoiceRepository
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.schemas.credit_note import CreditNoteCreate
from app.schemas.customer import CustomerCreate
from app.schemas.data_export import DataExportCreate, DataExportEstimate, DataExportResponse
from app.schemas.event import EventCreate
from app.schemas.fee import FeeCreate
from app.schemas.invoice import InvoiceCreate, InvoiceLineItem
from app.schemas.plan import PlanCreate
from app.schemas.subscription import SubscriptionCreate
from app.services.data_export_service import DataExportService, _fmt_dt
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def db_session():
    """Create a database session for direct testing."""
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
        CustomerCreate(
            external_id=f"export_test_cust_{uuid4()}",
            name="Export Test Customer",
            email="export@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def plan(db_session):
    """Create a test plan."""
    repo = PlanRepository(db_session)
    return repo.create(
        PlanCreate(
            code=f"export_test_plan_{uuid4()}",
            name="Export Test Plan",
            interval="monthly",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def subscription(db_session, customer, plan):
    """Create a test subscription."""
    repo = SubscriptionRepository(db_session)
    return repo.create(
        SubscriptionCreate(
            external_id=f"export_test_sub_{uuid4()}",
            customer_id=customer.id,
            plan_id=plan.id,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def invoice(db_session, customer, subscription):
    """Create a test invoice."""
    repo = InvoiceRepository(db_session)
    return repo.create(
        InvoiceCreate(
            customer_id=customer.id,
            subscription_id=subscription.id,
            billing_period_start=datetime.now(UTC),
            billing_period_end=datetime.now(UTC) + timedelta(days=30),
            due_date=datetime.now(UTC) + timedelta(days=14),
            line_items=[
                InvoiceLineItem(
                    description="Test Service",
                    quantity=Decimal("1"),
                    unit_price=Decimal("100.00"),
                    amount=Decimal("100.00"),
                )
            ],
        ),
    )


@pytest.fixture
def event(db_session, customer):
    """Create a test event."""
    repo = EventRepository(db_session)
    return repo.create(
        EventCreate(
            transaction_id=f"export_test_evt_{uuid4()}",
            external_customer_id=customer.external_id,
            code="api_calls",
            timestamp=datetime.now(UTC),
            properties={"count": 5},
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def fee(db_session, customer, invoice, subscription):
    """Create a test fee."""
    repo = FeeRepository(db_session)
    return repo.create(
        FeeCreate(
            invoice_id=invoice.id,
            subscription_id=subscription.id,
            customer_id=customer.id,
            fee_type="subscription",
            amount_cents=Decimal("100.00"),
            units=Decimal("1"),
        ),
    )


@pytest.fixture
def credit_note(db_session, customer, invoice):
    """Create a test credit note."""
    repo = CreditNoteRepository(db_session)
    return repo.create(
        CreditNoteCreate(
            number=f"CN-TEST-{uuid4()}",
            invoice_id=invoice.id,
            customer_id=customer.id,
            credit_note_type=CreditNoteType.CREDIT,
            reason=CreditNoteReason.OTHER,
            credit_amount_cents=Decimal("50.00"),
            total_amount_cents=Decimal("50.00"),
            currency="USD",
            items=[],
        ),
    )


class TestDataExportModel:
    """Tests for DataExport model helpers."""

    def test_generate_uuid(self):
        """Test UUID generation produces unique values."""
        uuid1 = generate_uuid()
        uuid2 = generate_uuid()
        assert uuid1 != uuid2
        assert str(uuid1)

    def test_export_type_enum(self):
        """Test ExportType enum values."""
        assert ExportType.INVOICES.value == "invoices"
        assert ExportType.CUSTOMERS.value == "customers"
        assert ExportType.SUBSCRIPTIONS.value == "subscriptions"
        assert ExportType.EVENTS.value == "events"
        assert ExportType.FEES.value == "fees"
        assert ExportType.CREDIT_NOTES.value == "credit_notes"

    def test_export_status_enum(self):
        """Test ExportStatus enum values."""
        assert ExportStatus.PENDING.value == "pending"
        assert ExportStatus.PROCESSING.value == "processing"
        assert ExportStatus.COMPLETED.value == "completed"
        assert ExportStatus.FAILED.value == "failed"

    def test_model_creation(self, db_session):
        """Test creating a DataExport model instance."""
        export = DataExport(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES.value,
            status=ExportStatus.PENDING.value,
        )
        db_session.add(export)
        db_session.commit()
        db_session.refresh(export)

        assert export.id is not None
        assert export.organization_id == DEFAULT_ORG_ID
        assert export.export_type == "invoices"
        assert export.status == "pending"
        assert export.created_at is not None
        assert export.file_path is None
        assert export.record_count is None
        assert export.error_message is None

    def test_model_with_filters(self, db_session):
        """Test DataExport with filters."""
        filters = {"status": "paid", "customer_id": str(uuid4())}
        export = DataExport(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES.value,
            filters=filters,
        )
        db_session.add(export)
        db_session.commit()
        db_session.refresh(export)

        assert export.filters == filters


class TestDataExportSchema:
    """Tests for DataExport schemas."""

    def test_create_schema(self):
        """Test DataExportCreate schema."""
        data = DataExportCreate(
            export_type=ExportType.INVOICES,
            filters={"status": "paid"},
        )
        assert data.export_type == ExportType.INVOICES
        assert data.filters == {"status": "paid"}

    def test_create_schema_no_filters(self):
        """Test DataExportCreate schema without filters."""
        data = DataExportCreate(export_type=ExportType.CUSTOMERS)
        assert data.export_type == ExportType.CUSTOMERS
        assert data.filters is None

    def test_estimate_schema(self):
        """Test DataExportEstimate schema."""
        estimate = DataExportEstimate(
            export_type="invoices",
            record_count=42,
        )
        assert estimate.export_type == "invoices"
        assert estimate.record_count == 42

    def test_response_schema(self):
        """Test DataExportResponse schema with from_attributes."""
        export = DataExport()
        export.id = uuid4()
        export.organization_id = DEFAULT_ORG_ID
        export.export_type = ExportType.INVOICES.value
        export.status = ExportStatus.COMPLETED.value
        export.filters = None
        export.file_path = "/tmp/test.csv"
        export.record_count = 10
        export.error_message = None
        export.started_at = datetime.now(UTC)
        export.completed_at = datetime.now(UTC)
        export.created_at = datetime.now(UTC)

        response = DataExportResponse.model_validate(export)
        assert response.export_type == "invoices"
        assert response.status == "completed"
        assert response.record_count == 10
        assert response.file_path == "/tmp/test.csv"


class TestDataExportRepository:
    """Tests for DataExportRepository."""

    def test_create(self, db_session):
        """Test creating a data export."""
        repo = DataExportRepository(db_session)
        data = DataExportCreate(
            export_type=ExportType.INVOICES,
            filters={"status": "paid"},
        )
        export = repo.create(data, DEFAULT_ORG_ID)

        assert export.id is not None
        assert export.organization_id == DEFAULT_ORG_ID
        assert export.export_type == "invoices"
        assert export.status == "pending"
        assert export.filters == {"status": "paid"}

    def test_get_by_id(self, db_session):
        """Test getting a data export by ID."""
        repo = DataExportRepository(db_session)
        data = DataExportCreate(export_type=ExportType.CUSTOMERS)
        created = repo.create(data, DEFAULT_ORG_ID)

        fetched = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting non-existent data export."""
        repo = DataExportRepository(db_session)
        result = repo.get_by_id(uuid4())
        assert result is None

    def test_get_by_id_wrong_org(self, db_session):
        """Test getting data export with wrong organization."""
        repo = DataExportRepository(db_session)
        data = DataExportCreate(export_type=ExportType.CUSTOMERS)
        created = repo.create(data, DEFAULT_ORG_ID)

        result = repo.get_by_id(created.id, uuid4())
        assert result is None

    def test_get_all(self, db_session):
        """Test listing data exports."""
        repo = DataExportRepository(db_session)
        repo.create(DataExportCreate(export_type=ExportType.INVOICES), DEFAULT_ORG_ID)
        repo.create(DataExportCreate(export_type=ExportType.CUSTOMERS), DEFAULT_ORG_ID)

        exports = repo.get_all(DEFAULT_ORG_ID)
        assert len(exports) == 2

    def test_get_all_pagination(self, db_session):
        """Test listing data exports with pagination."""
        repo = DataExportRepository(db_session)
        for _ in range(5):
            repo.create(DataExportCreate(export_type=ExportType.INVOICES), DEFAULT_ORG_ID)

        exports = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(exports) == 2

    def test_get_all_empty(self, db_session):
        """Test listing data exports when none exist."""
        repo = DataExportRepository(db_session)
        exports = repo.get_all(DEFAULT_ORG_ID)
        assert exports == []

    def test_update_status(self, db_session):
        """Test updating data export status."""
        repo = DataExportRepository(db_session)
        data = DataExportCreate(export_type=ExportType.INVOICES)
        created = repo.create(data, DEFAULT_ORG_ID)

        updated = repo.update_status(
            created.id,
            status=ExportStatus.COMPLETED.value,
            file_path="/tmp/test.csv",
            record_count=42,
        )

        assert updated is not None
        assert updated.status == "completed"
        assert updated.file_path == "/tmp/test.csv"
        assert updated.record_count == 42

    def test_update_status_not_found(self, db_session):
        """Test updating non-existent data export."""
        repo = DataExportRepository(db_session)
        result = repo.update_status(uuid4(), status="completed")
        assert result is None


class TestDataExportService:
    """Tests for DataExportService."""

    def test_create_export(self, db_session):
        """Test creating a data export via service."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES,
            filters={"status": "paid"},
        )
        assert export.id is not None
        assert export.export_type == "invoices"
        assert export.status == "pending"

    def test_process_export_invoices(self, db_session, invoice):
        """Test processing an invoice export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1
        assert result.file_path is not None
        assert result.started_at is not None
        assert result.completed_at is not None
        assert os.path.exists(str(result.file_path))

        # Verify CSV content
        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "number",
            "customer_id",
            "status",
            "subtotal",
            "tax_amount",
            "total",
            "currency",
            "issued_at",
            "due_date",
            "paid_at",
        ]
        assert len(rows) == 2  # header + 1 record
        assert rows[1][2] == "draft"  # status

    def test_process_export_invoices_with_status_filter(self, db_session, invoice):
        """Test invoice export with status filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES,
            filters={"status": "paid"},
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 0

    def test_process_export_invoices_with_customer_filter(self, db_session, invoice, customer):
        """Test invoice export with customer_id filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES,
            filters={"customer_id": str(customer.id)},
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1

    def test_process_export_customers(self, db_session, customer):
        """Test processing a customer export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.CUSTOMERS,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1
        assert result.file_path is not None

        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "external_id",
            "name",
            "email",
            "currency",
            "timezone",
            "created_at",
        ]
        assert len(rows) == 2
        assert rows[1][1] == "Export Test Customer"

    def test_process_export_subscriptions(self, db_session, subscription):
        """Test processing a subscription export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.SUBSCRIPTIONS,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1

        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "external_id",
            "customer_id",
            "plan_id",
            "status",
            "billing_time",
            "started_at",
            "canceled_at",
            "created_at",
        ]
        assert len(rows) == 2

    def test_process_export_subscriptions_with_status_filter(self, db_session, subscription):
        """Test subscription export with status filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.SUBSCRIPTIONS,
            filters={"status": "terminated"},
        )
        result = service.process_export(export.id)
        assert result.record_count == 0

    def test_process_export_subscriptions_with_customer_filter(
        self, db_session, subscription, customer
    ):
        """Test subscription export with customer_id filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.SUBSCRIPTIONS,
            filters={"customer_id": str(customer.id)},
        )
        result = service.process_export(export.id)
        assert result.record_count == 1

    def test_process_export_events(self, db_session, event):
        """Test processing an event export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.EVENTS,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1

        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "transaction_id",
            "external_customer_id",
            "code",
            "timestamp",
            "created_at",
        ]
        assert len(rows) == 2
        assert rows[1][2] == "api_calls"

    def test_process_export_events_with_customer_filter(self, db_session, event, customer):
        """Test event export with external_customer_id filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.EVENTS,
            filters={"external_customer_id": customer.external_id},
        )
        result = service.process_export(export.id)
        assert result.record_count == 1

    def test_process_export_events_with_code_filter(self, db_session, event):
        """Test event export with code filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.EVENTS,
            filters={"code": "nonexistent_code"},
        )
        result = service.process_export(export.id)
        assert result.record_count == 0

    def test_process_export_fees(self, db_session, fee):
        """Test processing a fee export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.FEES,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1

        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "id",
            "invoice_id",
            "fee_type",
            "amount_cents",
            "units",
            "events_count",
            "payment_status",
            "created_at",
        ]
        assert len(rows) == 2

    def test_process_export_fees_with_type_filter(self, db_session, fee):
        """Test fee export with fee_type filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.FEES,
            filters={"fee_type": "add_on"},
        )
        result = service.process_export(export.id)
        assert result.record_count == 0

    def test_process_export_fees_with_invoice_filter(self, db_session, fee, invoice):
        """Test fee export with invoice_id filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.FEES,
            filters={"invoice_id": str(invoice.id)},
        )
        result = service.process_export(export.id)
        assert result.record_count == 1

    def test_process_export_credit_notes(self, db_session, credit_note):
        """Test processing a credit note export."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.CREDIT_NOTES,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 1

        with open(str(result.file_path)) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == [
            "number",
            "invoice_id",
            "customer_id",
            "credit_note_type",
            "status",
            "total_amount_cents",
            "currency",
            "issued_at",
            "created_at",
        ]
        assert len(rows) == 2

    def test_process_export_credit_notes_with_status_filter(self, db_session, credit_note):
        """Test credit note export with status filter."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.CREDIT_NOTES,
            filters={"status": "finalized"},
        )
        result = service.process_export(export.id)
        assert result.record_count == 0

    def test_process_export_not_found(self, db_session):
        """Test processing a non-existent export."""
        service = DataExportService(db_session)
        with pytest.raises(ValueError, match="not found"):
            service.process_export(uuid4())

    def test_process_export_empty_data(self, db_session):
        """Test processing an export with no matching data."""
        service = DataExportService(db_session)
        export = service.create_export(
            organization_id=DEFAULT_ORG_ID,
            export_type=ExportType.INVOICES,
        )
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert result.record_count == 0

    def test_fmt_dt_with_value(self):
        """Test _fmt_dt with a datetime value."""
        dt = datetime(2026, 1, 15, 10, 30, 0)
        assert _fmt_dt(dt) == dt.isoformat()

    def test_fmt_dt_with_none(self):
        """Test _fmt_dt with None."""
        assert _fmt_dt(None) == ""


class TestDataExportEstimateService:
    """Tests for DataExportService.estimate_count."""

    def test_estimate_invoices(self, db_session, invoice):
        """Test estimate count for invoices."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.INVOICES)
        assert count == 1

    def test_estimate_invoices_with_status_filter(self, db_session, invoice):
        """Test estimate count for invoices with status filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.INVOICES, {"status": "paid"})
        assert count == 0

    def test_estimate_invoices_with_customer_filter(self, db_session, invoice, customer):
        """Test estimate count for invoices with customer filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.INVOICES, {"customer_id": str(customer.id)}
        )
        assert count == 1

    def test_estimate_customers(self, db_session, customer):
        """Test estimate count for customers."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.CUSTOMERS)
        assert count == 1

    def test_estimate_subscriptions(self, db_session, subscription):
        """Test estimate count for subscriptions."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.SUBSCRIPTIONS)
        assert count == 1

    def test_estimate_subscriptions_with_status_filter(self, db_session, subscription):
        """Test estimate count for subscriptions with status filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.SUBSCRIPTIONS, {"status": "terminated"}
        )
        assert count == 0

    def test_estimate_subscriptions_with_customer_filter(self, db_session, subscription, customer):
        """Test estimate count for subscriptions with customer filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.SUBSCRIPTIONS, {"customer_id": str(customer.id)}
        )
        assert count == 1

    def test_estimate_events(self, db_session, event):
        """Test estimate count for events."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.EVENTS)
        assert count == 1

    def test_estimate_events_with_customer_filter(self, db_session, event, customer):
        """Test estimate count for events with external_customer_id filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.EVENTS, {"external_customer_id": customer.external_id}
        )
        assert count == 1

    def test_estimate_events_with_code_filter(self, db_session, event):
        """Test estimate count for events with code filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.EVENTS, {"code": "nonexistent_code"}
        )
        assert count == 0

    def test_estimate_fees(self, db_session, fee):
        """Test estimate count for fees."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.FEES)
        assert count == 1

    def test_estimate_fees_with_type_filter(self, db_session, fee):
        """Test estimate count for fees with fee_type filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.FEES, {"fee_type": "add_on"}
        )
        assert count == 0

    def test_estimate_fees_with_invoice_filter(self, db_session, fee, invoice):
        """Test estimate count for fees with invoice_id filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.FEES, {"invoice_id": str(invoice.id)}
        )
        assert count == 1

    def test_estimate_credit_notes(self, db_session, credit_note):
        """Test estimate count for credit notes."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.CREDIT_NOTES)
        assert count == 1

    def test_estimate_credit_notes_with_status_filter(self, db_session, credit_note):
        """Test estimate count for credit notes with status filter."""
        service = DataExportService(db_session)
        count = service.estimate_count(
            DEFAULT_ORG_ID, ExportType.CREDIT_NOTES, {"status": "finalized"}
        )
        assert count == 0

    def test_estimate_empty_data(self, db_session):
        """Test estimate count with no matching data."""
        service = DataExportService(db_session)
        count = service.estimate_count(DEFAULT_ORG_ID, ExportType.INVOICES)
        assert count == 0

    def test_estimate_unknown_type(self, db_session):
        """Test estimate count with an unknown export type raises ValueError."""
        service = DataExportService(db_session)

        class FakeType:
            value = "nonexistent_type"

        with pytest.raises(ValueError, match="Unknown export type"):
            service.estimate_count(DEFAULT_ORG_ID, FakeType())  # type: ignore[arg-type]


class TestDataExportAPI:
    """Tests for data export API endpoints."""

    def test_create_export(self, client, customer):
        """Test POST /v1/data_exports."""
        response = client.post(
            "/v1/data_exports/",
            json={"export_type": "customers"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["export_type"] == "customers"
        assert data["status"] == "completed"
        assert data["record_count"] == 1

    def test_create_export_with_filters(self, client, invoice):
        """Test POST /v1/data_exports with filters."""
        response = client.post(
            "/v1/data_exports/",
            json={
                "export_type": "invoices",
                "filters": {"status": "draft"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "completed"
        assert data["record_count"] == 1

    def test_create_export_invalid_type(self, client):
        """Test POST /v1/data_exports with invalid export type."""
        response = client.post(
            "/v1/data_exports/",
            json={"export_type": "invalid_type"},
        )
        assert response.status_code == 422

    def test_list_exports(self, client, db_session):
        """Test GET /v1/data_exports."""
        # Create some exports first
        service = DataExportService(db_session)
        service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)
        service.create_export(DEFAULT_ORG_ID, ExportType.CUSTOMERS)

        response = client.get("/v1/data_exports/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_exports_empty(self, client):
        """Test GET /v1/data_exports when empty."""
        response = client.get("/v1/data_exports/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_exports_pagination(self, client, db_session):
        """Test GET /v1/data_exports with pagination."""
        service = DataExportService(db_session)
        for _ in range(5):
            service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)

        response = client.get("/v1/data_exports/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_export(self, client, db_session):
        """Test GET /v1/data_exports/{id}."""
        service = DataExportService(db_session)
        export = service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)

        response = client.get(f"/v1/data_exports/{export.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["export_type"] == "invoices"

    def test_get_export_not_found(self, client):
        """Test GET /v1/data_exports/{id} for non-existent export."""
        response = client.get(f"/v1/data_exports/{uuid4()}")
        assert response.status_code == 404

    def test_download_export(self, client, customer):
        """Test GET /v1/data_exports/{id}/download."""
        # Create and process an export
        response = client.post(
            "/v1/data_exports/",
            json={"export_type": "customers"},
        )
        assert response.status_code == 201
        export_id = response.json()["id"]

        # Download
        response = client.get(f"/v1/data_exports/{export_id}/download")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

        # Verify CSV content
        content = response.text
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)
        assert rows[0][0] == "external_id"
        assert len(rows) == 2

    def test_download_export_not_found(self, client):
        """Test download for non-existent export."""
        response = client.get(f"/v1/data_exports/{uuid4()}/download")
        assert response.status_code == 404

    def test_download_export_not_completed(self, client, db_session):
        """Test download for pending export."""
        service = DataExportService(db_session)
        export = service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)

        response = client.get(f"/v1/data_exports/{export.id}/download")
        assert response.status_code == 400
        assert "not completed" in response.json()["detail"]

    def test_download_export_missing_file(self, client, db_session):
        """Test download when file doesn't exist on disk."""
        repo = DataExportRepository(db_session)
        data = DataExportCreate(export_type=ExportType.INVOICES)
        export = repo.create(data, DEFAULT_ORG_ID)
        repo.update_status(
            export.id,
            status=ExportStatus.COMPLETED.value,
            file_path="/tmp/nonexistent_file.csv",
        )

        response = client.get(f"/v1/data_exports/{export.id}/download")
        assert response.status_code == 404
        assert "file not found" in response.json()["detail"].lower()


class TestDataExportEstimateAPI:
    """Tests for data export estimate API endpoint."""

    def test_estimate_export(self, client, customer):
        """Test POST /v1/data_exports/estimate."""
        response = client.post(
            "/v1/data_exports/estimate",
            json={"export_type": "customers"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["export_type"] == "customers"
        assert data["record_count"] == 1

    def test_estimate_export_with_filters(self, client, invoice):
        """Test POST /v1/data_exports/estimate with filters."""
        response = client.post(
            "/v1/data_exports/estimate",
            json={
                "export_type": "invoices",
                "filters": {"status": "draft"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["record_count"] == 1

    def test_estimate_export_with_no_matches(self, client, invoice):
        """Test POST /v1/data_exports/estimate when no records match."""
        response = client.post(
            "/v1/data_exports/estimate",
            json={
                "export_type": "invoices",
                "filters": {"status": "paid"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["record_count"] == 0

    def test_estimate_export_invalid_type(self, client):
        """Test POST /v1/data_exports/estimate with invalid export type."""
        response = client.post(
            "/v1/data_exports/estimate",
            json={"export_type": "invalid_type"},
        )
        assert response.status_code == 422

    def test_estimate_export_empty_data(self, client):
        """Test POST /v1/data_exports/estimate with no data."""
        response = client.post(
            "/v1/data_exports/estimate",
            json={"export_type": "invoices"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["record_count"] == 0


class TestDataExportServiceErrorHandling:
    """Tests for error handling in DataExportService."""

    def test_process_export_creates_export_directory(self, db_session, tmp_path, monkeypatch):
        """Test that process_export creates export directory if it doesn't exist."""
        monkeypatch.setattr(
            "app.services.data_export_service.settings.APP_DATA_PATH", str(tmp_path)
        )

        service = DataExportService(db_session)
        export = service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)
        result = service.process_export(export.id)

        assert result.status == ExportStatus.COMPLETED.value
        assert os.path.exists(os.path.join(str(tmp_path), "exports"))

    def test_process_export_sets_processing_status(self, db_session, tmp_path, monkeypatch):
        """Test that process_export transitions through processing status."""
        monkeypatch.setattr(
            "app.services.data_export_service.settings.APP_DATA_PATH", str(tmp_path)
        )

        service = DataExportService(db_session)
        export = service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)
        result = service.process_export(export.id)

        # Should end as completed
        assert result.status == ExportStatus.COMPLETED.value
        assert result.started_at is not None
        assert result.completed_at is not None

    def test_process_export_handles_generation_error(self, db_session, monkeypatch):
        """Test that process_export handles errors during CSV generation gracefully."""
        service = DataExportService(db_session)
        export = service.create_export(DEFAULT_ORG_ID, ExportType.INVOICES)

        # Force an error during CSV generation
        def _raise(*args, **kwargs):
            raise RuntimeError("Simulated CSV generation error")

        monkeypatch.setattr(service, "_generate_csv", _raise)

        result = service.process_export(export.id)

        assert result.status == ExportStatus.FAILED.value
        assert "Simulated CSV generation error" in str(result.error_message)
        assert result.completed_at is not None

    def test_generate_csv_unknown_type(self, db_session):
        """Test _generate_csv with an unknown export type."""
        service = DataExportService(db_session)
        with pytest.raises(ValueError, match="Unknown export type"):
            service._generate_csv("nonexistent_type", DEFAULT_ORG_ID, {})
