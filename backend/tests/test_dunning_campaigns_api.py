"""Tests for DunningCampaign API router endpoints."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.models.payment_request_invoice import PaymentRequestInvoice
from app.repositories.dunning_campaign_repository import DunningCampaignRepository
from app.schemas.dunning_campaign import (
    DunningCampaignCreate,
    DunningCampaignThresholdCreate,
)
from tests.conftest import DEFAULT_ORG_ID


@pytest.fixture
def db_session():
    """Get a database session."""
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
def campaign(db_session: Session) -> DunningCampaign:
    """Create a test dunning campaign with thresholds."""
    repo = DunningCampaignRepository(db_session)
    return repo.create(
        DunningCampaignCreate(
            code="test-dc",
            name="Test Campaign",
            description="A test campaign",
            max_attempts=5,
            days_between_attempts=7,
            bcc_emails=["test@example.com"],
            thresholds=[
                DunningCampaignThresholdCreate(
                    currency="USD",
                    amount_cents=Decimal("1000"),
                ),
            ],
        ),
        DEFAULT_ORG_ID,
    )


class TestCreateDunningCampaign:
    def test_create_campaign_minimal(self, client: TestClient) -> None:
        """Test creating a campaign with minimal fields."""
        response = client.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc-min", "name": "Minimal"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "dc-min"
        assert data["name"] == "Minimal"
        assert data["max_attempts"] == 3
        assert data["days_between_attempts"] == 3
        assert data["bcc_emails"] == []
        assert data["status"] == "active"
        assert data["thresholds"] == []
        assert data["description"] is None
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data
        assert data["organization_id"] == str(DEFAULT_ORG_ID)

    def test_create_campaign_full(self, client: TestClient) -> None:
        """Test creating a campaign with all fields and thresholds."""
        response = client.post(
            "/v1/dunning_campaigns/",
            json={
                "code": "dc-full",
                "name": "Full Campaign",
                "description": "Full description",
                "max_attempts": 5,
                "days_between_attempts": 7,
                "bcc_emails": ["a@b.com", "c@d.com"],
                "status": "inactive",
                "thresholds": [
                    {"currency": "USD", "amount_cents": "500"},
                    {"currency": "EUR", "amount_cents": "400"},
                ],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "dc-full"
        assert data["description"] == "Full description"
        assert data["max_attempts"] == 5
        assert data["days_between_attempts"] == 7
        assert data["bcc_emails"] == ["a@b.com", "c@d.com"]
        assert data["status"] == "inactive"
        assert len(data["thresholds"]) == 2
        currencies = {t["currency"] for t in data["thresholds"]}
        assert currencies == {"USD", "EUR"}

    def test_create_campaign_duplicate_code(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test creating a campaign with a duplicate code returns 409."""
        response = client.post(
            "/v1/dunning_campaigns/",
            json={"code": "test-dc", "name": "Duplicate"},
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_campaign_validation_error(self, client: TestClient) -> None:
        """Test creating a campaign with missing required fields returns 422."""
        response = client.post(
            "/v1/dunning_campaigns/",
            json={"code": "dc"},
        )
        assert response.status_code == 422


class TestListDunningCampaigns:
    def test_list_campaigns_empty(self, client: TestClient) -> None:
        """Test listing campaigns when none exist."""
        response = client.get("/v1/dunning_campaigns/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_campaigns(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test listing campaigns returns existing campaigns."""
        response = client.get("/v1/dunning_campaigns/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "test-dc"
        assert len(data[0]["thresholds"]) == 1

    def test_list_campaigns_with_status_filter(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test listing campaigns with status filter."""
        # Create an inactive campaign
        repo = DunningCampaignRepository(db_session)
        repo.create(
            DunningCampaignCreate(
                code="dc-inactive",
                name="Inactive",
                status="inactive",
            ),
            DEFAULT_ORG_ID,
        )

        active = client.get("/v1/dunning_campaigns/?status=active")
        assert active.status_code == 200
        assert len(active.json()) == 1
        assert active.json()[0]["code"] == "test-dc"

        inactive = client.get("/v1/dunning_campaigns/?status=inactive")
        assert inactive.status_code == 200
        assert len(inactive.json()) == 1
        assert inactive.json()[0]["code"] == "dc-inactive"

    def test_list_campaigns_pagination(
        self,
        client: TestClient,
        db_session: Session,
    ) -> None:
        """Test listing campaigns with pagination."""
        repo = DunningCampaignRepository(db_session)
        for i in range(5):
            repo.create(
                DunningCampaignCreate(code=f"dc-{i}", name=f"Camp {i}"),
                DEFAULT_ORG_ID,
            )

        response = client.get("/v1/dunning_campaigns/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetDunningCampaign:
    def test_get_campaign(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test getting a campaign by ID."""
        response = client.get(f"/v1/dunning_campaigns/{campaign.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "test-dc"
        assert data["name"] == "Test Campaign"
        assert data["description"] == "A test campaign"
        assert len(data["thresholds"]) == 1
        assert data["thresholds"][0]["currency"] == "USD"

    def test_get_campaign_not_found(self, client: TestClient) -> None:
        """Test getting a non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(f"/v1/dunning_campaigns/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Dunning campaign not found"


class TestUpdateDunningCampaign:
    def test_update_campaign(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test updating a campaign."""
        response = client.put(
            f"/v1/dunning_campaigns/{campaign.id}",
            json={"name": "Updated Campaign"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Campaign"
        assert data["code"] == "test-dc"  # unchanged

    def test_update_campaign_with_thresholds(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test updating a campaign's thresholds."""
        response = client.put(
            f"/v1/dunning_campaigns/{campaign.id}",
            json={
                "thresholds": [
                    {"currency": "GBP", "amount_cents": "300"},
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["thresholds"]) == 1
        assert data["thresholds"][0]["currency"] == "GBP"

    def test_update_campaign_not_found(self, client: TestClient) -> None:
        """Test updating a non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"/v1/dunning_campaigns/{fake_id}",
            json={"name": "Ghost"},
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Dunning campaign not found"


class TestDeleteDunningCampaign:
    def test_delete_campaign(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test deleting a campaign."""
        response = client.delete(f"/v1/dunning_campaigns/{campaign.id}")
        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get(f"/v1/dunning_campaigns/{campaign.id}")
        assert get_response.status_code == 404

    def test_delete_campaign_not_found(self, client: TestClient) -> None:
        """Test deleting a non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.delete(f"/v1/dunning_campaigns/{fake_id}")
        assert response.status_code == 404
        assert response.json()["detail"] == "Dunning campaign not found"


class TestPerformanceStats:
    def test_performance_stats_empty(self, client: TestClient) -> None:
        """Test performance stats with no data."""
        response = client.get("/v1/dunning_campaigns/performance_stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_campaigns"] == 0
        assert data["active_campaigns"] == 0
        assert data["total_payment_requests"] == 0
        assert data["recovery_rate"] == 0.0
        assert data["total_recovered_amount_cents"] == "0"
        assert data["total_outstanding_amount_cents"] == "0"

    def test_performance_stats_with_data(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test performance stats with campaigns and payment requests."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-api-perf",
            name="API Perf Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Add payment requests linked to the campaign
        for status, amount in [
            ("succeeded", Decimal("5000")),
            ("succeeded", Decimal("3000")),
            ("failed", Decimal("2000")),
        ]:
            pr = PaymentRequest(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                dunning_campaign_id=campaign.id,
                amount_cents=amount,
                amount_currency="USD",
                payment_status=status,
            )
            db_session.add(pr)
        db_session.commit()

        response = client.get("/v1/dunning_campaigns/performance_stats")
        assert response.status_code == 200
        data = response.json()
        assert data["total_campaigns"] == 1
        assert data["active_campaigns"] == 1
        assert data["total_payment_requests"] == 3
        assert data["succeeded_requests"] == 2
        assert data["failed_requests"] == 1
        assert data["pending_requests"] == 0
        assert data["recovery_rate"] == 66.7
        assert Decimal(data["total_recovered_amount_cents"]) == Decimal("8000")
        assert Decimal(data["total_outstanding_amount_cents"]) == Decimal("2000")


def _create_overdue_invoice(
    db_session: Session,
    customer_id: uuid.UUID,
    total: Decimal = Decimal("5000"),
    currency: str = "USD",
    inv_num: str | None = None,
) -> Invoice:
    """Helper to create an overdue finalized invoice."""
    inv = Invoice(
        organization_id=DEFAULT_ORG_ID,
        invoice_number=inv_num or f"INV-D-{uuid.uuid4().hex[:8]}",
        customer_id=customer_id,
        status=InvoiceStatus.FINALIZED.value,
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
        subtotal=total,
        tax_amount=Decimal("0"),
        total=total,
        currency=currency,
        due_date=datetime.now(UTC) - timedelta(days=10),
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


class TestExecutionHistory:
    def test_execution_history_empty(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test execution history with no payment requests."""
        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/execution_history"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_execution_history_with_data(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test execution history returns payment requests with customer and invoice info."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-hist",
            name="History Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        inv = _create_overdue_invoice(db_session, customer.id, inv_num="INV-HIST-001")

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("5000"),
            amount_currency="USD",
            payment_status="pending",
            payment_attempts=1,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        # Link invoice to payment request
        pri = PaymentRequestInvoice(
            payment_request_id=pr.id,
            invoice_id=inv.id,
        )
        db_session.add(pri)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/execution_history"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        entry = data[0]
        assert entry["customer_name"] == "History Customer"
        assert entry["payment_status"] == "pending"
        assert entry["payment_attempts"] == 1
        assert len(entry["invoices"]) == 1
        assert entry["invoices"][0]["invoice_number"] == "INV-HIST-001"

    def test_execution_history_not_found(self, client: TestClient) -> None:
        """Test execution history for non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/v1/dunning_campaigns/{fake_id}/execution_history"
        )
        assert response.status_code == 404

    def test_execution_history_multiple_statuses(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test execution history with mixed payment statuses."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-multi",
            name="Multi Status Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        for status, amount in [
            ("succeeded", Decimal("3000")),
            ("failed", Decimal("2000")),
            ("pending", Decimal("4000")),
        ]:
            pr = PaymentRequest(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                dunning_campaign_id=campaign.id,
                amount_cents=amount,
                amount_currency="USD",
                payment_status=status,
            )
            db_session.add(pr)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/execution_history"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        statuses = {d["payment_status"] for d in data}
        assert statuses == {"succeeded", "failed", "pending"}

    def test_execution_history_no_invoices(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test execution history with PR that has no linked invoices."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-noinv",
            name="No Invoice Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            payment_status="pending",
        )
        db_session.add(pr)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/execution_history"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["customer_name"] == "No Invoice Customer"
        assert data[0]["invoices"] == []


class TestCampaignTimeline:
    def test_timeline_campaign_only(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test timeline with just a campaign (no payment requests)."""
        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/timeline"
        )
        assert response.status_code == 200
        data = response.json()
        events = data["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "campaign_created"
        assert "Test Campaign" in events[0]["description"]

    def test_timeline_with_payment_requests(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test timeline includes payment request events."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-tl",
            name="Timeline Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("5000"),
            amount_currency="USD",
            payment_status="succeeded",
            payment_attempts=2,
        )
        db_session.add(pr)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/timeline"
        )
        assert response.status_code == 200
        data = response.json()
        events = data["events"]
        event_types = [e["event_type"] for e in events]
        assert "campaign_created" in event_types
        assert "payment_request_created" in event_types
        assert "payment_succeeded" in event_types

    def test_timeline_not_found(self, client: TestClient) -> None:
        """Test timeline for non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.get(
            f"/v1/dunning_campaigns/{fake_id}/timeline"
        )
        assert response.status_code == 404

    def test_timeline_failed_payment(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test timeline includes failed payment events."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-tl-fail",
            name="Failed Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("3000"),
            amount_currency="EUR",
            payment_status="failed",
            payment_attempts=3,
        )
        db_session.add(pr)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/timeline"
        )
        assert response.status_code == 200
        data = response.json()
        events = data["events"]
        failed_events = [e for e in events if e["event_type"] == "payment_failed"]
        assert len(failed_events) == 1
        assert failed_events[0]["attempt_number"] == 3
        assert "Failed Customer" in failed_events[0]["description"]
        assert failed_events[0]["amount_currency"] == "EUR"

    def test_timeline_pending_no_outcome(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test timeline with pending PR shows only creation, no outcome."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-tl-pending",
            name="Pending Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("2000"),
            amount_currency="USD",
            payment_status="pending",
            payment_attempts=0,
        )
        db_session.add(pr)
        db_session.commit()

        response = client.get(
            f"/v1/dunning_campaigns/{campaign.id}/timeline"
        )
        assert response.status_code == 200
        data = response.json()
        events = data["events"]
        event_types = [e["event_type"] for e in events]
        assert "payment_request_created" in event_types
        # No outcome event for pending with 0 attempts
        assert "payment_succeeded" not in event_types
        assert "payment_failed" not in event_types


class TestCampaignPreview:
    def test_preview_no_overdue_invoices(
        self,
        client: TestClient,
        campaign: DunningCampaign,
    ) -> None:
        """Test preview with no overdue invoices."""
        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["campaign_name"] == "Test Campaign"
        assert data["total_overdue_invoices"] == 0
        assert data["payment_requests_to_create"] == 0
        assert data["groups"] == []

    def test_preview_with_matching_threshold(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test preview creates groups when invoices exceed threshold."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prev",
            name="Preview Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Campaign has USD threshold at 1000 cents
        _create_overdue_invoice(
            db_session, customer.id, total=Decimal("2000"), inv_num="INV-PREV-001"
        )

        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_overdue_invoices"] == 1
        assert data["payment_requests_to_create"] == 1
        assert len(data["groups"]) == 1
        group = data["groups"][0]
        assert group["customer_name"] == "Preview Customer"
        assert group["currency"] == "USD"
        assert Decimal(group["total_outstanding_cents"]) == Decimal("2000")
        assert len(group["invoices"]) == 1
        assert group["invoices"][0]["invoice_number"] == "INV-PREV-001"

    def test_preview_below_threshold(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test preview shows no groups when below threshold."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prev-low",
            name="Low Amount Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Campaign has USD threshold at 1000 cents, invoice is only 500
        _create_overdue_invoice(
            db_session, customer.id, total=Decimal("500"), inv_num="INV-PREV-LOW"
        )

        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_overdue_invoices"] == 1
        assert data["payment_requests_to_create"] == 0
        assert data["groups"] == []

    def test_preview_not_found(self, client: TestClient) -> None:
        """Test preview for non-existent campaign returns 404."""
        fake_id = str(uuid.uuid4())
        response = client.post(
            f"/v1/dunning_campaigns/{fake_id}/preview"
        )
        assert response.status_code == 404

    def test_preview_excludes_invoices_in_pending_prs(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test preview excludes invoices already in pending payment requests."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prev-exc",
            name="Excluded Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        inv = _create_overdue_invoice(
            db_session, customer.id, total=Decimal("5000"), inv_num="INV-PREV-EXC"
        )

        # Create a pending PR that already covers this invoice
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("5000"),
            amount_currency="USD",
            payment_status="pending",
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        pri = PaymentRequestInvoice(
            payment_request_id=pr.id,
            invoice_id=inv.id,
        )
        db_session.add(pri)
        db_session.commit()

        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_overdue_invoices"] == 1
        assert data["payment_requests_to_create"] == 0

    def test_preview_wrong_currency(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test preview doesn't match invoices with currencies not in thresholds."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prev-eur",
            name="EUR Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Campaign only has USD threshold; invoice is in EUR
        _create_overdue_invoice(
            db_session, customer.id, total=Decimal("5000"), currency="EUR", inv_num="INV-PREV-EUR"
        )

        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_overdue_invoices"] == 1
        assert data["payment_requests_to_create"] == 0

    def test_preview_existing_pending_count(
        self,
        client: TestClient,
        campaign: DunningCampaign,
        db_session: Session,
    ) -> None:
        """Test preview reports existing pending requests for this campaign."""
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-prev-cnt",
            name="Count Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Add 2 pending PRs linked to this campaign
        for _i in range(2):
            pr = PaymentRequest(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                dunning_campaign_id=campaign.id,
                amount_cents=Decimal("1000"),
                amount_currency="USD",
                payment_status="pending",
            )
            db_session.add(pr)
        db_session.commit()

        response = client.post(
            f"/v1/dunning_campaigns/{campaign.id}/preview"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["existing_pending_requests"] == 2
