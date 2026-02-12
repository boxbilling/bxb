"""Tests for DunningService — dunning campaign evaluation and payment request lifecycle."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.customer import Customer
from app.models.dunning_campaign import DunningCampaign
from app.models.dunning_campaign_threshold import DunningCampaignThreshold
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment_request import PaymentRequest
from app.repositories.payment_request_repository import PaymentRequestRepository
from app.services.dunning_service import DunningService
from tests.conftest import DEFAULT_ORG_ID


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
def customer(db_session: Session) -> Customer:
    c = Customer(
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-dunning-001",
        name="Dunning Test Customer",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def customer2(db_session: Session) -> Customer:
    c = Customer(
        organization_id=DEFAULT_ORG_ID,
        external_id="cust-dunning-002",
        name="Dunning Test Customer 2",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def campaign(db_session: Session) -> DunningCampaign:
    c = DunningCampaign(
        organization_id=DEFAULT_ORG_ID,
        code="dc-test",
        name="Test Campaign",
        max_attempts=3,
        days_between_attempts=3,
        status="active",
    )
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def threshold(db_session: Session, campaign: DunningCampaign) -> DunningCampaignThreshold:
    t = DunningCampaignThreshold(
        dunning_campaign_id=campaign.id,
        currency="USD",
        amount_cents=Decimal("500"),
    )
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    return t


def _make_overdue_invoice(
    db_session: Session,
    customer: Customer,
    total: Decimal,
    currency: str = "USD",
    inv_num: str | None = None,
) -> Invoice:
    inv = Invoice(
        organization_id=DEFAULT_ORG_ID,
        invoice_number=inv_num or f"INV-D-{uuid.uuid4().hex[:8]}",
        customer_id=customer.id,
        status=InvoiceStatus.FINALIZED.value,
        billing_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        billing_period_end=datetime(2026, 1, 31, tzinfo=UTC),
        subtotal=total,
        tax_amount=Decimal("0"),
        total=total,
        currency=currency,
        due_date=datetime.now(UTC) - timedelta(days=1),
    )
    db_session.add(inv)
    db_session.commit()
    db_session.refresh(inv)
    return inv


class TestCheckAndCreatePaymentRequests:
    """Tests for DunningService.check_and_create_payment_requests."""

    def test_no_active_campaigns_returns_empty(self, db_session: Session) -> None:
        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_no_overdue_invoices_returns_empty(
        self, db_session: Session, campaign: DunningCampaign, threshold: DunningCampaignThreshold,
    ) -> None:
        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_creates_payment_request_when_threshold_exceeded(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        # Create overdue invoices totaling $600 (above $500 threshold)
        _make_overdue_invoice(db_session, customer, Decimal("300"))
        _make_overdue_invoice(db_session, customer, Decimal("300"))

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)

        assert len(result) == 1
        pr = result[0]
        assert pr.customer_id == customer.id
        assert pr.amount_cents == Decimal("600")
        assert pr.amount_currency == "USD"
        assert pr.dunning_campaign_id == campaign.id

    def test_does_not_create_when_below_threshold(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        # Create overdue invoices totaling $400 (below $500 threshold)
        _make_overdue_invoice(db_session, customer, Decimal("200"))
        _make_overdue_invoice(db_session, customer, Decimal("200"))

        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_skips_invoices_already_in_pending_request(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        inv1 = _make_overdue_invoice(db_session, customer, Decimal("600"))

        # Create existing payment request for inv1
        pr_repo = PaymentRequestRepository(db_session)
        pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("600"),
            amount_currency="USD",
            invoice_ids=[inv1.id],
        )

        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_inactive_campaign_ignored(
        self, db_session: Session, customer: Customer,
    ) -> None:
        # Create an inactive campaign
        c = DunningCampaign(
            organization_id=DEFAULT_ORG_ID,
            code="dc-inactive",
            name="Inactive",
            status="inactive",
        )
        db_session.add(c)
        db_session.commit()

        t = DunningCampaignThreshold(
            dunning_campaign_id=c.id,
            currency="USD",
            amount_cents=Decimal("100"),
        )
        db_session.add(t)
        db_session.commit()

        _make_overdue_invoice(db_session, customer, Decimal("500"))

        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_currency_mismatch_no_threshold_skipped(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        # threshold is for USD, invoice is EUR
        _make_overdue_invoice(db_session, customer, Decimal("1000"), currency="EUR")

        service = DunningService(db_session)
        result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_triggers_webhook_on_creation(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        _make_overdue_invoice(db_session, customer, Decimal("600"))

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook") as mock_wh:
            service.check_and_create_payment_requests(DEFAULT_ORG_ID)

        mock_wh.assert_called_once()
        call_kwargs = mock_wh.call_args
        assert call_kwargs.kwargs["webhook_type"] == "payment_request.created"

    def test_multiple_customers(
        self,
        db_session: Session,
        customer: Customer,
        customer2: Customer,
        campaign: DunningCampaign,
        threshold: DunningCampaignThreshold,
    ) -> None:
        _make_overdue_invoice(db_session, customer, Decimal("600"))
        _make_overdue_invoice(db_session, customer2, Decimal("700"))

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            result = service.check_and_create_payment_requests(DEFAULT_ORG_ID)

        assert len(result) == 2
        customer_ids = {pr.customer_id for pr in result}
        assert customer.id in customer_ids
        assert customer2.id in customer_ids


class TestProcessPaymentRequests:
    """Tests for DunningService.process_payment_requests."""

    def test_processes_pending_ready_requests(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )
        assert pr.ready_for_payment_processing is True

        service = DunningService(db_session)
        result = service.process_payment_requests(DEFAULT_ORG_ID)

        assert len(result) == 1
        assert result[0].id == pr.id
        assert result[0].payment_attempts == 1
        assert result[0].ready_for_payment_processing is False

    def test_skips_non_pending_requests(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )
        pr_repo.update_status(pr.id, DEFAULT_ORG_ID, "succeeded")

        service = DunningService(db_session)
        result = service.process_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_skips_not_ready_requests(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )
        pr.ready_for_payment_processing = False  # type: ignore[assignment]
        db_session.commit()

        service = DunningService(db_session)
        result = service.process_payment_requests(DEFAULT_ORG_ID)
        assert result == []

    def test_skips_ineligible_retry(
        self, db_session: Session, customer: Customer, campaign: DunningCampaign,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
            dunning_campaign_id=campaign.id,
        )
        # Simulate already at max attempts
        pr.payment_attempts = 3  # type: ignore[assignment]
        pr.ready_for_payment_processing = True  # type: ignore[assignment]
        db_session.commit()

        service = DunningService(db_session)
        result = service.process_payment_requests(DEFAULT_ORG_ID)
        assert result == []


class TestMarkPaymentRequestSucceeded:
    """Tests for DunningService.mark_payment_request_succeeded."""

    def test_marks_succeeded_and_pays_invoices(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        assert inv.status == InvoiceStatus.FINALIZED.value

        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            result = service.mark_payment_request_succeeded(pr.id, DEFAULT_ORG_ID)

        assert result is not None
        assert result.payment_status == "succeeded"

        db_session.refresh(inv)
        assert inv.status == InvoiceStatus.PAID.value
        assert inv.paid_at is not None

    def test_does_not_pay_already_paid_invoices(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        # Mark as paid before the payment request
        inv.status = InvoiceStatus.PAID.value  # type: ignore[assignment]
        db_session.commit()

        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            result = service.mark_payment_request_succeeded(pr.id, DEFAULT_ORG_ID)

        assert result is not None
        db_session.refresh(inv)
        # Should still be PAID, not re-paid
        assert inv.status == InvoiceStatus.PAID.value

    def test_not_found_returns_none(self, db_session: Session) -> None:
        service = DunningService(db_session)
        result = service.mark_payment_request_succeeded(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_triggers_webhook(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook") as mock_wh:
            service.mark_payment_request_succeeded(pr.id, DEFAULT_ORG_ID)

        mock_wh.assert_called_once()
        assert mock_wh.call_args.kwargs["webhook_type"] == "payment_request.payment_succeeded"


class TestMarkPaymentRequestFailed:
    """Tests for DunningService.mark_payment_request_failed."""

    def test_marks_failed(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook"):
            result = service.mark_payment_request_failed(pr.id, DEFAULT_ORG_ID)

        assert result is not None
        assert result.payment_status == "failed"

    def test_not_found_returns_none(self, db_session: Session) -> None:
        service = DunningService(db_session)
        result = service.mark_payment_request_failed(uuid.uuid4(), DEFAULT_ORG_ID)
        assert result is None

    def test_triggers_webhook(
        self, db_session: Session, customer: Customer,
    ) -> None:
        inv = _make_overdue_invoice(db_session, customer, Decimal("100"))
        pr_repo = PaymentRequestRepository(db_session)
        pr = pr_repo.create(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            invoice_ids=[inv.id],
        )

        service = DunningService(db_session)
        with patch.object(service.webhook_service, "send_webhook") as mock_wh:
            service.mark_payment_request_failed(pr.id, DEFAULT_ORG_ID)

        mock_wh.assert_called_once()
        assert mock_wh.call_args.kwargs["webhook_type"] == "payment_request.payment_failed"


class TestEvaluateRetryEligibility:
    """Tests for DunningService.evaluate_retry_eligibility."""

    def test_first_attempt_always_eligible(
        self, db_session: Session, customer: Customer,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=0,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is True

    def test_no_campaign_always_eligible(
        self, db_session: Session, customer: Customer,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=5,
            dunning_campaign_id=None,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is True

    def test_max_attempts_reached(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=3,
            dunning_campaign_id=campaign.id,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is False

    def test_too_soon_for_retry(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=1,
            dunning_campaign_id=campaign.id,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        # updated_at is "now", days_between_attempts is 3, so not eligible yet
        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is False

    def test_eligible_after_wait_period(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=1,
            dunning_campaign_id=campaign.id,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        # Manually set updated_at to 4 days ago (past the 3-day wait)
        pr.updated_at = datetime.now(UTC) - timedelta(days=4)  # type: ignore[assignment]
        db_session.commit()
        db_session.refresh(pr)

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is True

    def test_campaign_not_found_eligible(
        self, db_session: Session, customer: Customer,
    ) -> None:
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=1,
            dunning_campaign_id=uuid.uuid4(),  # nonexistent campaign
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is True

    def test_no_updated_at_eligible(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
    ) -> None:
        """When updated_at is None, should still be eligible."""
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=1,
            dunning_campaign_id=campaign.id,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        # Force updated_at to None
        pr.updated_at = None  # type: ignore[assignment]

        service = DunningService(db_session)
        assert service.evaluate_retry_eligibility(pr) is True

    def test_updated_at_with_tzinfo_not_eligible(
        self,
        db_session: Session,
        customer: Customer,
        campaign: DunningCampaign,
    ) -> None:
        """When updated_at already has tzinfo, skip replace and check."""
        pr = PaymentRequest(
            organization_id=DEFAULT_ORG_ID,
            customer_id=customer.id,
            amount_cents=Decimal("100"),
            amount_currency="USD",
            payment_attempts=1,
            dunning_campaign_id=campaign.id,
        )
        db_session.add(pr)
        db_session.commit()
        db_session.refresh(pr)

        # Set updated_at to a tz-aware datetime (recently)
        pr.updated_at = datetime.now(UTC)  # type: ignore[assignment]

        service = DunningService(db_session)
        # days_between_attempts=3, updated_at is "now" so not eligible
        assert service.evaluate_retry_eligibility(pr) is False
