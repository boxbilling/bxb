"""Tests for DunningCampaign API router endpoints."""

import uuid
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.main import app
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.payment_request import PaymentRequest
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
