"""Tests for CouponApplicationService business logic."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.database import Base, engine, get_db
from app.models.applied_coupon import AppliedCouponStatus
from app.models.coupon import CouponExpiration, CouponFrequency, CouponType
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.coupon import CouponCreate
from app.schemas.customer import CustomerCreate
from app.services.coupon_service import CouponApplicationService, CouponDiscount


@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


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
        CustomerCreate(
            external_id=f"cs_test_cust_{uuid4()}",
            name="CouponService Test Customer",
            email="couponservice@test.com",
        )
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"cs_test_cust2_{uuid4()}",
            name="CouponService Test Customer 2",
        )
    )


@pytest.fixture
def coupon_service(db_session):
    """Create a CouponApplicationService instance."""
    return CouponApplicationService(db_session)


@pytest.fixture
def coupon_repo(db_session):
    """Create a CouponRepository instance."""
    return CouponRepository(db_session)


@pytest.fixture
def applied_coupon_repo(db_session):
    """Create an AppliedCouponRepository instance."""
    return AppliedCouponRepository(db_session)


@pytest.fixture
def fixed_coupon(coupon_repo):
    """Create a fixed amount coupon ($10 off, once, reusable)."""
    return coupon_repo.create(
        CouponCreate(
            code="SVC_FIXED10",
            name="$10 Off",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("1000.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
            reusable=True,
        )
    )


@pytest.fixture
def percentage_coupon(coupon_repo):
    """Create a percentage coupon (20% off, forever, reusable)."""
    return coupon_repo.create(
        CouponCreate(
            code="SVC_PERCENT20",
            name="20% Off",
            coupon_type=CouponType.PERCENTAGE,
            percentage_rate=Decimal("20.00"),
            frequency=CouponFrequency.FOREVER,
            reusable=True,
        )
    )


@pytest.fixture
def recurring_coupon(coupon_repo):
    """Create a recurring coupon ($5 off for 3 periods, non-reusable)."""
    return coupon_repo.create(
        CouponCreate(
            code="SVC_RECURRING5",
            name="$5 off for 3 periods",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.RECURRING,
            frequency_duration=3,
            reusable=False,
        )
    )


@pytest.fixture
def expired_coupon(coupon_repo):
    """Create an expired coupon."""
    return coupon_repo.create(
        CouponCreate(
            code="SVC_EXPIRED",
            name="Expired Coupon",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
            expiration=CouponExpiration.TIME_LIMIT,
            expiration_at=datetime.now(UTC) - timedelta(days=1),
        )
    )


@pytest.fixture
def future_expiration_coupon(coupon_repo):
    """Create a coupon with future expiration."""
    return coupon_repo.create(
        CouponCreate(
            code="SVC_FUTURE_EXP",
            name="Future Expiration Coupon",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
            expiration=CouponExpiration.TIME_LIMIT,
            expiration_at=datetime.now(UTC) + timedelta(days=30),
        )
    )


class TestApplyCouponToCustomer:
    """Tests for CouponApplicationService.apply_coupon_to_customer()."""

    def test_apply_fixed_coupon(self, coupon_service, fixed_coupon, customer):
        """Test applying a fixed amount coupon to a customer."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        assert applied.coupon_id == fixed_coupon.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents == Decimal("1000.0000")
        assert applied.amount_currency == "USD"
        assert applied.percentage_rate is None
        assert applied.frequency == "once"
        assert applied.status == AppliedCouponStatus.ACTIVE.value

    def test_apply_percentage_coupon(self, coupon_service, percentage_coupon, customer):
        """Test applying a percentage coupon to a customer."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
        )
        assert applied.coupon_id == percentage_coupon.id
        assert applied.percentage_rate == Decimal("20.00")
        assert applied.amount_currency is None
        assert applied.frequency == "forever"

    def test_apply_recurring_coupon(self, coupon_service, recurring_coupon, customer):
        """Test applying a recurring coupon to a customer."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_RECURRING5",
            customer_id=customer.id,
        )
        assert applied.frequency == "recurring"
        assert applied.frequency_duration == 3
        assert applied.frequency_duration_remaining == 3

    def test_apply_with_amount_override(self, coupon_service, fixed_coupon, customer):
        """Test applying a coupon with an amount override."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
            amount_override=Decimal("750.0000"),
        )
        assert applied.amount_cents == Decimal("750.0000")

    def test_apply_with_percentage_override(self, coupon_service, percentage_coupon, customer):
        """Test applying a coupon with a percentage override."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
            percentage_override=Decimal("30.00"),
        )
        assert applied.percentage_rate == Decimal("30.00")

    def test_apply_coupon_not_found(self, coupon_service, customer):
        """Test applying a non-existent coupon raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="NONEXISTENT",
                customer_id=customer.id,
            )

    def test_apply_terminated_coupon(self, coupon_service, fixed_coupon, customer, coupon_repo):
        """Test applying a terminated coupon raises ValueError."""
        coupon_repo.terminate("SVC_FIXED10")
        with pytest.raises(ValueError, match="not active"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="SVC_FIXED10",
                customer_id=customer.id,
            )

    def test_apply_expired_coupon(self, coupon_service, expired_coupon, customer):
        """Test applying an expired coupon raises ValueError."""
        with pytest.raises(ValueError, match="expired"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="SVC_EXPIRED",
                customer_id=customer.id,
            )

    def test_apply_coupon_with_future_expiration(
        self, coupon_service, future_expiration_coupon, customer
    ):
        """Test applying a coupon with future expiration succeeds."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FUTURE_EXP",
            customer_id=customer.id,
        )
        assert applied.status == AppliedCouponStatus.ACTIVE.value

    def test_apply_expired_coupon_timezone_aware(
        self, coupon_service, expired_coupon, customer, db_session
    ):
        """Test applying an expired coupon with timezone-aware expiration_at."""
        # Manually set expiration_at to a timezone-aware past datetime
        expired_coupon.expiration_at = datetime.now(UTC) - timedelta(hours=1)
        db_session.commit()
        db_session.refresh(expired_coupon)
        # Force tzinfo onto the attribute (SQLite strips it, so we patch it)
        expired_coupon.expiration_at = expired_coupon.expiration_at.replace(tzinfo=UTC)

        with pytest.raises(ValueError, match="expired"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="SVC_EXPIRED",
                customer_id=customer.id,
            )

    def test_apply_coupon_customer_not_found(self, coupon_service, fixed_coupon):
        """Test applying a coupon to a non-existent customer raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="SVC_FIXED10",
                customer_id=uuid4(),
            )

    def test_apply_non_reusable_coupon_duplicate(
        self, coupon_service, recurring_coupon, customer
    ):
        """Test applying a non-reusable coupon to the same customer twice raises ValueError."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_RECURRING5",
            customer_id=customer.id,
        )
        with pytest.raises(ValueError, match="already applied"):
            coupon_service.apply_coupon_to_customer(
                coupon_code="SVC_RECURRING5",
                customer_id=customer.id,
            )

    def test_apply_reusable_coupon_to_multiple_customers(
        self, coupon_service, fixed_coupon, customer, customer2
    ):
        """Test applying a reusable coupon to multiple customers succeeds."""
        applied1 = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        applied2 = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer2.id,
        )
        assert applied1.customer_id == customer.id
        assert applied2.customer_id == customer2.id


class TestCalculateCouponDiscount:
    """Tests for CouponApplicationService.calculate_coupon_discount()."""

    def test_fixed_discount(self, coupon_service, fixed_coupon, customer):
        """Test fixed amount discount calculation."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("5000.0000"),
        )
        assert result.total_discount_cents == Decimal("1000.0000")
        assert len(result.applied_coupon_ids) == 1

    def test_percentage_discount(self, coupon_service, percentage_coupon, customer):
        """Test percentage discount calculation."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("10000.0000"),
        )
        assert result.total_discount_cents == Decimal("2000.0000")
        assert len(result.applied_coupon_ids) == 1

    def test_fixed_discount_capped_at_subtotal(self, coupon_service, fixed_coupon, customer):
        """Test fixed discount is capped at the subtotal amount."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("500.0000"),
        )
        # $10 coupon capped at $5 subtotal
        assert result.total_discount_cents == Decimal("500.0000")
        assert len(result.applied_coupon_ids) == 1

    def test_multiple_coupons(
        self, coupon_service, fixed_coupon, percentage_coupon, customer
    ):
        """Test multiple coupons applied to same customer."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("10000.0000"),
        )
        # Fixed $10 + 20% of remaining $90 = $10 + $18 = $28
        assert result.total_discount_cents == Decimal("2800.0000")
        assert len(result.applied_coupon_ids) == 2

    def test_no_coupons(self, coupon_service, customer):
        """Test discount calculation with no applied coupons."""
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("5000.0000"),
        )
        assert result.total_discount_cents == Decimal("0")
        assert result.applied_coupon_ids == []

    def test_zero_subtotal(self, coupon_service, fixed_coupon, customer):
        """Test discount calculation with zero subtotal."""
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("0"),
        )
        assert result.total_discount_cents == Decimal("0")
        assert result.applied_coupon_ids == []

    def test_discount_does_not_exceed_subtotal(
        self, coupon_service, customer, coupon_repo
    ):
        """Test total discount from multiple coupons doesn't exceed subtotal."""
        # Create two large fixed coupons
        coupon_repo.create(
            CouponCreate(
                code="SVC_BIG1",
                name="Big Coupon 1",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("5000.0000"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
                reusable=True,
            )
        )
        coupon_repo.create(
            CouponCreate(
                code="SVC_BIG2",
                name="Big Coupon 2",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("5000.0000"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
                reusable=True,
            )
        )
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_BIG1", customer_id=customer.id
        )
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_BIG2", customer_id=customer.id
        )

        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("6000.0000"),
        )
        # First coupon takes $50, second can only take remaining $10
        assert result.total_discount_cents == Decimal("6000.0000")
        assert len(result.applied_coupon_ids) == 2

    def test_terminated_coupons_excluded(
        self, coupon_service, fixed_coupon, customer, applied_coupon_repo
    ):
        """Test that terminated applied coupons are not included in discount."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        applied_coupon_repo.terminate(applied.id)

        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("5000.0000"),
        )
        assert result.total_discount_cents == Decimal("0")
        assert result.applied_coupon_ids == []

    def test_zero_discount_coupon_excluded_from_consumed(
        self, coupon_service, customer, coupon_repo
    ):
        """Test that a coupon yielding zero discount is not included in consumed IDs."""
        coupon_repo.create(
            CouponCreate(
                code="SVC_ZERO_DISC",
                name="Zero Discount",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("0"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
                reusable=True,
            )
        )
        coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_ZERO_DISC",
            customer_id=customer.id,
        )
        result = coupon_service.calculate_coupon_discount(
            customer_id=customer.id,
            subtotal_cents=Decimal("5000.0000"),
        )
        assert result.total_discount_cents == Decimal("0")
        assert result.applied_coupon_ids == []

    def test_coupon_discount_dataclass(self):
        """Test CouponDiscount dataclass creation."""
        discount = CouponDiscount(
            total_discount_cents=Decimal("1000"),
            applied_coupon_ids=[uuid4(), uuid4()],
        )
        assert discount.total_discount_cents == Decimal("1000")
        assert len(discount.applied_coupon_ids) == 2


class TestConsumeAppliedCoupon:
    """Tests for CouponApplicationService.consume_applied_coupon()."""

    def test_consume_once_coupon(self, coupon_service, fixed_coupon, customer):
        """Test consuming a 'once' frequency coupon terminates it."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        result = coupon_service.consume_applied_coupon(applied.id)
        assert result is not None
        assert result.status == AppliedCouponStatus.TERMINATED.value
        assert result.terminated_at is not None

    def test_consume_recurring_coupon_decrements(
        self, coupon_service, recurring_coupon, customer
    ):
        """Test consuming a 'recurring' coupon decrements remaining count."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_RECURRING5",
            customer_id=customer.id,
        )
        assert applied.frequency_duration_remaining == 3

        result = coupon_service.consume_applied_coupon(applied.id)
        assert result is not None
        assert result.frequency_duration_remaining == 2
        assert result.status == AppliedCouponStatus.ACTIVE.value

    def test_consume_recurring_coupon_terminates_at_zero(
        self, coupon_service, recurring_coupon, customer
    ):
        """Test consuming a 'recurring' coupon terminates when remaining reaches 0."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_RECURRING5",
            customer_id=customer.id,
        )
        # Consume 3 times
        coupon_service.consume_applied_coupon(applied.id)
        coupon_service.consume_applied_coupon(applied.id)
        result = coupon_service.consume_applied_coupon(applied.id)

        assert result is not None
        assert result.frequency_duration_remaining == 0
        assert result.status == AppliedCouponStatus.TERMINATED.value
        assert result.terminated_at is not None

    def test_consume_forever_coupon(self, coupon_service, percentage_coupon, customer):
        """Test consuming a 'forever' coupon does not change its state."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
        )
        result = coupon_service.consume_applied_coupon(applied.id)
        assert result is not None
        assert result.status == AppliedCouponStatus.ACTIVE.value
        assert result.terminated_at is None

    def test_consume_not_found(self, coupon_service):
        """Test consuming a non-existent applied coupon returns None."""
        result = coupon_service.consume_applied_coupon(uuid4())
        assert result is None


class TestCalculateSingleDiscount:
    """Tests for CouponApplicationService._calculate_single_discount()."""

    def test_percentage_discount_calculation(
        self, coupon_service, percentage_coupon, customer
    ):
        """Test _calculate_single_discount for percentage type."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_PERCENT20",
            customer_id=customer.id,
        )
        discount = coupon_service._calculate_single_discount(
            applied, Decimal("10000.0000")
        )
        assert discount == Decimal("2000.000000")

    def test_fixed_discount_calculation(self, coupon_service, fixed_coupon, customer):
        """Test _calculate_single_discount for fixed amount type."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        discount = coupon_service._calculate_single_discount(
            applied, Decimal("5000.0000")
        )
        assert discount == Decimal("1000.0000")

    def test_fixed_discount_capped(self, coupon_service, fixed_coupon, customer):
        """Test _calculate_single_discount caps fixed amount at subtotal."""
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_FIXED10",
            customer_id=customer.id,
        )
        discount = coupon_service._calculate_single_discount(
            applied, Decimal("300.0000")
        )
        assert discount == Decimal("300.0000")

    def test_zero_amount_coupon(
        self, coupon_service, customer, coupon_repo
    ):
        """Test _calculate_single_discount with zero amount coupon."""
        coupon_repo.create(
            CouponCreate(
                code="SVC_ZERO",
                name="Zero Coupon",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("0"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
                reusable=True,
            )
        )
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_ZERO",
            customer_id=customer.id,
        )
        discount = coupon_service._calculate_single_discount(
            applied, Decimal("5000.0000")
        )
        assert discount == Decimal("0")

    def test_no_amount_no_percentage_coupon(
        self, coupon_service, customer, coupon_repo
    ):
        """Test _calculate_single_discount with neither amount nor percentage."""
        coupon_repo.create(
            CouponCreate(
                code="SVC_EMPTY",
                name="Empty Coupon",
                coupon_type=CouponType.FIXED_AMOUNT,
                frequency=CouponFrequency.ONCE,
                reusable=True,
            )
        )
        applied = coupon_service.apply_coupon_to_customer(
            coupon_code="SVC_EMPTY",
            customer_id=customer.id,
        )
        discount = coupon_service._calculate_single_discount(
            applied, Decimal("5000.0000")
        )
        assert discount == Decimal("0")
