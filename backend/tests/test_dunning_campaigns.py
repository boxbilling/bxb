"""Tests for DunningCampaign models, schemas, and repository."""

import uuid
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.dunning_campaign_threshold import DunningCampaignThreshold
from app.models.payment_request import PaymentRequest
from app.repositories.dunning_campaign_repository import DunningCampaignRepository
from app.schemas.dunning_campaign import (
    DunningCampaignCreate,
    DunningCampaignPerformanceStats,
    DunningCampaignResponse,
    DunningCampaignThresholdCreate,
    DunningCampaignThresholdResponse,
    DunningCampaignUpdate,
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


class TestDunningCampaignModel:
    """Test DunningCampaign model defaults and fields."""

    def test_dunning_campaign_defaults(self, db_session: Session) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-001",
            name="Default Campaign",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        assert campaign.id is not None
        assert campaign.organization_id == DEFAULT_ORG_ID
        assert campaign.code == "dc-001"
        assert campaign.name == "Default Campaign"
        assert campaign.description is None
        assert campaign.max_attempts == 3
        assert campaign.days_between_attempts == 3
        assert campaign.bcc_emails == []
        assert campaign.status == "active"
        assert campaign.created_at is not None
        assert campaign.updated_at is not None

    def test_dunning_campaign_all_fields(self, db_session: Session) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-002",
            name="Premium Campaign",
            description="Campaign for premium customers",
            max_attempts=5,
            days_between_attempts=7,
            bcc_emails=["billing@example.com", "admin@example.com"],
            status="inactive",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        assert campaign.description == "Campaign for premium customers"
        assert campaign.max_attempts == 5
        assert campaign.days_between_attempts == 7
        assert campaign.bcc_emails == ["billing@example.com", "admin@example.com"]
        assert campaign.status == "inactive"


class TestDunningCampaignThresholdModel:
    """Test DunningCampaignThreshold model."""

    def test_threshold_creation(self, db_session: Session) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-thresh",
            name="Threshold Test",
        )
        db_session.add(campaign)
        db_session.commit()

        threshold = DunningCampaignThreshold(
            dunning_campaign_id=campaign.id,
            currency="USD",
            amount_cents=Decimal("1000.0000"),
        )
        db_session.add(threshold)
        db_session.commit()
        db_session.refresh(threshold)

        assert threshold.id is not None
        assert threshold.dunning_campaign_id == campaign.id
        assert threshold.currency == "USD"
        assert threshold.amount_cents == Decimal("1000.0000")
        assert threshold.created_at is not None
        assert threshold.updated_at is not None


class TestDunningCampaignSchemas:
    """Test DunningCampaign Pydantic schemas."""

    def test_create_schema_minimal(self) -> None:
        data = DunningCampaignCreate(code="dc-001", name="Test")
        assert data.code == "dc-001"
        assert data.name == "Test"
        assert data.max_attempts == 3
        assert data.days_between_attempts == 3
        assert data.bcc_emails == []
        assert data.status == "active"
        assert data.thresholds == []

    def test_create_schema_full(self) -> None:
        data = DunningCampaignCreate(
            code="dc-002",
            name="Full Campaign",
            description="Full description",
            max_attempts=5,
            days_between_attempts=7,
            bcc_emails=["a@b.com"],
            status="inactive",
            thresholds=[
                DunningCampaignThresholdCreate(currency="USD", amount_cents=Decimal("500")),
            ],
        )
        assert data.description == "Full description"
        assert data.max_attempts == 5
        assert len(data.thresholds) == 1
        assert data.thresholds[0].currency == "USD"

    def test_create_schema_invalid_status(self) -> None:
        with pytest.raises(ValidationError):
            DunningCampaignCreate(code="dc", name="Test", status="bogus")

    def test_create_schema_invalid_max_attempts(self) -> None:
        with pytest.raises(ValidationError):
            DunningCampaignCreate(code="dc", name="Test", max_attempts=0)

    def test_create_schema_invalid_days_between_attempts(self) -> None:
        with pytest.raises(ValidationError):
            DunningCampaignCreate(code="dc", name="Test", days_between_attempts=0)

    def test_update_schema_partial(self) -> None:
        data = DunningCampaignUpdate(name="Updated")
        dump = data.model_dump(exclude_unset=True)
        assert dump == {"name": "Updated"}

    def test_update_schema_with_thresholds(self) -> None:
        data = DunningCampaignUpdate(
            thresholds=[
                DunningCampaignThresholdCreate(currency="EUR", amount_cents=Decimal("200")),
            ],
        )
        assert data.thresholds is not None
        assert len(data.thresholds) == 1

    def test_threshold_create_schema(self) -> None:
        data = DunningCampaignThresholdCreate(currency="USD", amount_cents=Decimal("100"))
        assert data.currency == "USD"
        assert data.amount_cents == Decimal("100")

    def test_threshold_create_invalid_currency(self) -> None:
        with pytest.raises(ValidationError):
            DunningCampaignThresholdCreate(currency="US", amount_cents=Decimal("100"))

    def test_threshold_create_negative_amount(self) -> None:
        with pytest.raises(ValidationError):
            DunningCampaignThresholdCreate(currency="USD", amount_cents=Decimal("-1"))

    def test_response_schema(self, db_session: Session) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-resp",
            name="Response Test",
        )
        db_session.add(campaign)
        db_session.commit()
        db_session.refresh(campaign)

        resp = DunningCampaignResponse.model_validate(campaign)
        assert resp.id == campaign.id
        assert resp.code == "dc-resp"
        assert resp.thresholds == []

    def test_threshold_response_schema(self, db_session: Session) -> None:
        campaign = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-tr",
            name="Thresh Resp",
        )
        db_session.add(campaign)
        db_session.commit()

        threshold = DunningCampaignThreshold(
            dunning_campaign_id=campaign.id,
            currency="EUR",
            amount_cents=Decimal("500"),
        )
        db_session.add(threshold)
        db_session.commit()
        db_session.refresh(threshold)

        resp = DunningCampaignThresholdResponse.model_validate(threshold)
        assert resp.currency == "EUR"
        assert resp.amount_cents == Decimal("500")


class TestDunningCampaignRepository:
    """Test DunningCampaignRepository CRUD operations."""

    def test_create_campaign(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(code="dc-001", name="Test Campaign")
        campaign = repo.create(data, DEFAULT_ORG_ID)

        assert campaign.id is not None
        assert campaign.code == "dc-001"
        assert campaign.organization_id == DEFAULT_ORG_ID

    def test_create_campaign_with_thresholds(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(
            code="dc-002",
            name="Threshold Campaign",
            thresholds=[
                DunningCampaignThresholdCreate(currency="USD", amount_cents=Decimal("100")),
                DunningCampaignThresholdCreate(currency="EUR", amount_cents=Decimal("200")),
            ],
        )
        campaign = repo.create(data, DEFAULT_ORG_ID)
        thresholds = repo.get_thresholds(campaign.id)

        assert len(thresholds) == 2
        currencies = {t.currency for t in thresholds}
        assert currencies == {"USD", "EUR"}

    def test_get_by_id(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(code="dc-get", name="Get Test")
        created = repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_id(created.id, DEFAULT_ORG_ID)
        assert found is not None
        assert found.id == created.id

    def test_get_by_id_not_found(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        result = repo.get_by_id(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_get_by_code(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(code="dc-code", name="Code Test")
        repo.create(data, DEFAULT_ORG_ID)

        found = repo.get_by_code("dc-code", DEFAULT_ORG_ID)
        assert found is not None
        assert found.code == "dc-code"

    def test_get_by_code_not_found(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        result = repo.get_by_code("nonexistent", DEFAULT_ORG_ID)
        assert result is None

    def test_get_all(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        repo.create(DunningCampaignCreate(code="dc-a", name="A"), DEFAULT_ORG_ID)
        repo.create(DunningCampaignCreate(code="dc-b", name="B"), DEFAULT_ORG_ID)

        campaigns = repo.get_all(DEFAULT_ORG_ID)
        assert len(campaigns) == 2

    def test_get_all_with_status_filter(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        repo.create(DunningCampaignCreate(code="dc-act", name="Active"), DEFAULT_ORG_ID)
        repo.create(
            DunningCampaignCreate(code="dc-inact", name="Inactive", status="inactive"),
            DEFAULT_ORG_ID,
        )

        active = repo.get_all(DEFAULT_ORG_ID, status="active")
        assert len(active) == 1
        assert active[0].code == "dc-act"

    def test_get_all_pagination(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        for i in range(5):
            repo.create(DunningCampaignCreate(code=f"dc-{i}", name=f"C{i}"), DEFAULT_ORG_ID)

        page = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(page) == 2

    def test_update_campaign(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(code="dc-upd", name="Original")
        campaign = repo.create(data, DEFAULT_ORG_ID)

        updated = repo.update(
            campaign.id,
            DunningCampaignUpdate(name="Updated"),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.name == "Updated"

    def test_update_campaign_with_thresholds(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(
            code="dc-upd-t",
            name="With Thresh",
            thresholds=[
                DunningCampaignThresholdCreate(currency="USD", amount_cents=Decimal("100")),
            ],
        )
        campaign = repo.create(data, DEFAULT_ORG_ID)

        # Update with new thresholds (replaces old ones)
        updated = repo.update(
            campaign.id,
            DunningCampaignUpdate(
                thresholds=[
                    DunningCampaignThresholdCreate(currency="EUR", amount_cents=Decimal("200")),
                    DunningCampaignThresholdCreate(currency="GBP", amount_cents=Decimal("300")),
                ],
            ),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        thresholds = repo.get_thresholds(campaign.id)
        assert len(thresholds) == 2
        currencies = {t.currency for t in thresholds}
        assert currencies == {"EUR", "GBP"}

    def test_update_campaign_not_found(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        result = repo.update(uuid.uuid4(), DunningCampaignUpdate(name="X"), DEFAULT_ORG_ID)
        assert result is None

    def test_delete_campaign(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        data = DunningCampaignCreate(code="dc-del", name="Delete Me")
        campaign = repo.create(data, DEFAULT_ORG_ID)

        result = repo.delete(campaign.id, DEFAULT_ORG_ID)
        assert result is True
        assert repo.get_by_id(campaign.id, DEFAULT_ORG_ID) is None

    def test_delete_campaign_not_found(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        result = repo.delete(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is False

    def test_get_thresholds_empty(self, db_session: Session) -> None:
        repo = DunningCampaignRepository(db_session)
        thresholds = repo.get_thresholds(uuid.uuid4())
        assert thresholds == []

    def test_performance_stats_empty(self, db_session: Session) -> None:
        """Performance stats with no campaigns or payment requests."""
        repo = DunningCampaignRepository(db_session)
        stats = repo.performance_stats(DEFAULT_ORG_ID)
        assert stats.total_campaigns == 0
        assert stats.active_campaigns == 0
        assert stats.total_payment_requests == 0
        assert stats.succeeded_requests == 0
        assert stats.failed_requests == 0
        assert stats.pending_requests == 0
        assert stats.recovery_rate == 0.0
        assert stats.total_recovered_amount_cents == Decimal("0")
        assert stats.total_outstanding_amount_cents == Decimal("0")

    def test_performance_stats_with_campaigns_only(self, db_session: Session) -> None:
        """Performance stats with campaigns but no payment requests."""
        repo = DunningCampaignRepository(db_session)
        repo.create(DunningCampaignCreate(code="dc-ps1", name="Active"), DEFAULT_ORG_ID)
        repo.create(
            DunningCampaignCreate(code="dc-ps2", name="Inactive", status="inactive"),
            DEFAULT_ORG_ID,
        )

        stats = repo.performance_stats(DEFAULT_ORG_ID)
        assert stats.total_campaigns == 2
        assert stats.active_campaigns == 1
        assert stats.total_payment_requests == 0
        assert stats.recovery_rate == 0.0

    def test_performance_stats_with_payment_requests(self, db_session: Session) -> None:
        """Performance stats with campaigns and payment requests of various statuses."""
        repo = DunningCampaignRepository(db_session)
        campaign = repo.create(DunningCampaignCreate(code="dc-perf", name="Perf"), DEFAULT_ORG_ID)

        # Create a customer for payment requests
        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-perf-stats",
            name="Perf Stats Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Create payment requests with different statuses
        pr_succeeded = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("5000"),
            amount_currency="USD",
            payment_status="succeeded",
        )
        pr_failed = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("3000"),
            amount_currency="USD",
            payment_status="failed",
        )
        pr_pending = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=campaign.id,
            amount_cents=Decimal("2000"),
            amount_currency="USD",
            payment_status="pending",
        )
        db_session.add_all([pr_succeeded, pr_failed, pr_pending])
        db_session.commit()

        stats = repo.performance_stats(DEFAULT_ORG_ID)
        assert stats.total_campaigns == 1
        assert stats.active_campaigns == 1
        assert stats.total_payment_requests == 3
        assert stats.succeeded_requests == 1
        assert stats.failed_requests == 1
        assert stats.pending_requests == 1
        # Recovery rate: 1/3 = 33.3%
        assert stats.recovery_rate == 33.3
        assert stats.total_recovered_amount_cents == Decimal("5000")
        # Outstanding = failed + pending amounts
        assert stats.total_outstanding_amount_cents == Decimal("5000")

    def test_performance_stats_excludes_non_dunning_requests(self, db_session: Session) -> None:
        """Payment requests without dunning_campaign_id are excluded from stats."""
        repo = DunningCampaignRepository(db_session)
        repo.create(DunningCampaignCreate(code="dc-excl", name="Exclude"), DEFAULT_ORG_ID)

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-excl",
            name="Exclusion Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        # Payment request NOT linked to a dunning campaign
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            dunning_campaign_id=None,
            amount_cents=Decimal("9999"),
            amount_currency="USD",
            payment_status="succeeded",
        )
        db_session.add(pr)
        db_session.commit()

        stats = repo.performance_stats(DEFAULT_ORG_ID)
        assert stats.total_payment_requests == 0
        assert stats.total_recovered_amount_cents == Decimal("0")

    def test_performance_stats_100_recovery_rate(self, db_session: Session) -> None:
        """Performance stats with 100% recovery rate."""
        repo = DunningCampaignRepository(db_session)
        campaign = repo.create(DunningCampaignCreate(code="dc-100", name="Perfect"), DEFAULT_ORG_ID)

        customer = Customer(
            organization_id=DEFAULT_ORG_ID,
            external_id="cust-100",
            name="Perfect Customer",
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        for _i in range(3):
            pr = PaymentRequest(
                organization_id=DEFAULT_ORG_ID,
                customer_id=customer.id,
                dunning_campaign_id=campaign.id,
                amount_cents=Decimal("1000"),
                amount_currency="USD",
                payment_status="succeeded",
            )
            db_session.add(pr)
        db_session.commit()

        stats = repo.performance_stats(DEFAULT_ORG_ID)
        assert stats.recovery_rate == 100.0
        assert stats.total_recovered_amount_cents == Decimal("3000")
        assert stats.total_outstanding_amount_cents == Decimal("0")


class TestDunningCampaignPerformanceStatsSchema:
    """Test DunningCampaignPerformanceStats Pydantic schema."""

    def test_schema_construction(self) -> None:
        stats = DunningCampaignPerformanceStats(
            total_campaigns=2,
            active_campaigns=1,
            total_payment_requests=10,
            succeeded_requests=7,
            failed_requests=2,
            pending_requests=1,
            recovery_rate=70.0,
            total_recovered_amount_cents=Decimal("50000"),
            total_outstanding_amount_cents=Decimal("15000"),
        )
        assert stats.total_campaigns == 2
        assert stats.recovery_rate == 70.0
        assert stats.total_recovered_amount_cents == Decimal("50000")
