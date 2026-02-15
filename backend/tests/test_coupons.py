"""Tests for Coupon and AppliedCoupon models, schemas, repositories, and CRUD operations."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.database import get_db
from app.main import app
from app.models.applied_coupon import AppliedCoupon, AppliedCouponStatus
from app.models.coupon import (
    Coupon,
    CouponExpiration,
    CouponFrequency,
    CouponStatus,
    CouponType,
)
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository
from app.schemas.coupon import (
    AppliedCouponResponse,
    ApplyCouponRequest,
    CouponCreate,
    CouponResponse,
    CouponUpdate,
)
from app.schemas.customer import CustomerCreate
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
        CustomerCreate(
            external_id=f"coupon_test_cust_{uuid4()}",
            name="Coupon Test Customer",
            email="coupon@test.com",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def customer2(db_session):
    """Create a second test customer."""
    repo = CustomerRepository(db_session)
    return repo.create(
        CustomerCreate(
            external_id=f"coupon_test_cust2_{uuid4()}",
            name="Coupon Test Customer 2",
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def fixed_coupon(db_session):
    """Create a fixed amount coupon."""
    repo = CouponRepository(db_session)
    return repo.create(
        CouponCreate(
            code="FIXED10",
            name="$10 Off",
            description="Get $10 off",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("1000.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
            reusable=True,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def percentage_coupon(db_session):
    """Create a percentage coupon."""
    repo = CouponRepository(db_session)
    return repo.create(
        CouponCreate(
            code="PERCENT20",
            name="20% Off",
            coupon_type=CouponType.PERCENTAGE,
            percentage_rate=Decimal("20.00"),
            frequency=CouponFrequency.FOREVER,
            reusable=True,
        ),
        DEFAULT_ORG_ID,
    )


@pytest.fixture
def recurring_coupon(db_session):
    """Create a recurring coupon."""
    repo = CouponRepository(db_session)
    return repo.create(
        CouponCreate(
            code="RECURRING5",
            name="$5 off for 3 periods",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            frequency=CouponFrequency.RECURRING,
            frequency_duration=3,
            reusable=False,
        ),
        DEFAULT_ORG_ID,
    )


class TestCouponModel:
    """Tests for Coupon SQLAlchemy model."""

    def test_coupon_defaults(self, db_session):
        """Test Coupon model default values."""
        coupon = Coupon(
            code="TEST1",
            name="Test Coupon",
            coupon_type=CouponType.FIXED_AMOUNT.value,
            frequency=CouponFrequency.ONCE.value,
        )
        db_session.add(coupon)
        db_session.commit()
        db_session.refresh(coupon)

        assert coupon.id is not None
        assert coupon.code == "TEST1"
        assert coupon.name == "Test Coupon"
        assert coupon.description is None
        assert coupon.coupon_type == "fixed_amount"
        assert coupon.amount_cents is None
        assert coupon.amount_currency is None
        assert coupon.percentage_rate is None
        assert coupon.frequency == "once"
        assert coupon.frequency_duration is None
        assert coupon.reusable is True
        assert coupon.expiration == CouponExpiration.NO_EXPIRATION.value
        assert coupon.expiration_at is None
        assert coupon.status == CouponStatus.ACTIVE.value
        assert coupon.created_at is not None
        assert coupon.updated_at is not None

    def test_coupon_with_all_fields(self, db_session):
        """Test Coupon model with all fields populated."""
        expiry = datetime.now(UTC) + timedelta(days=30)
        coupon = Coupon(
            code="FULL",
            name="Full Coupon",
            description="A fully populated coupon",
            coupon_type=CouponType.PERCENTAGE.value,
            percentage_rate=Decimal("15.50"),
            frequency=CouponFrequency.RECURRING.value,
            frequency_duration=6,
            reusable=False,
            expiration=CouponExpiration.TIME_LIMIT.value,
            expiration_at=expiry,
            status=CouponStatus.ACTIVE.value,
        )
        db_session.add(coupon)
        db_session.commit()
        db_session.refresh(coupon)

        assert coupon.code == "FULL"
        assert coupon.description == "A fully populated coupon"
        assert coupon.coupon_type == "percentage"
        assert coupon.percentage_rate == Decimal("15.50")
        assert coupon.frequency == "recurring"
        assert coupon.frequency_duration == 6
        assert coupon.reusable is False
        assert coupon.expiration == "time_limit"
        assert coupon.expiration_at is not None

    def test_coupon_type_enum(self):
        """Test CouponType enum values."""
        assert CouponType.FIXED_AMOUNT.value == "fixed_amount"
        assert CouponType.PERCENTAGE.value == "percentage"

    def test_coupon_frequency_enum(self):
        """Test CouponFrequency enum values."""
        assert CouponFrequency.ONCE.value == "once"
        assert CouponFrequency.RECURRING.value == "recurring"
        assert CouponFrequency.FOREVER.value == "forever"

    def test_coupon_expiration_enum(self):
        """Test CouponExpiration enum values."""
        assert CouponExpiration.NO_EXPIRATION.value == "no_expiration"
        assert CouponExpiration.TIME_LIMIT.value == "time_limit"

    def test_coupon_status_enum(self):
        """Test CouponStatus enum values."""
        assert CouponStatus.ACTIVE.value == "active"
        assert CouponStatus.TERMINATED.value == "terminated"


class TestAppliedCouponModel:
    """Tests for AppliedCoupon SQLAlchemy model."""

    def test_applied_coupon_defaults(self, db_session, customer, fixed_coupon):
        """Test AppliedCoupon model default values."""
        applied = AppliedCoupon(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            frequency="once",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.id is not None
        assert applied.coupon_id == fixed_coupon.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents is None
        assert applied.amount_currency is None
        assert applied.percentage_rate is None
        assert applied.frequency == "once"
        assert applied.frequency_duration is None
        assert applied.frequency_duration_remaining is None
        assert applied.status == AppliedCouponStatus.ACTIVE.value
        assert applied.terminated_at is None
        assert applied.created_at is not None
        assert applied.updated_at is not None

    def test_applied_coupon_with_all_fields(self, db_session, customer, fixed_coupon):
        """Test AppliedCoupon model with all fields populated."""
        applied = AppliedCoupon(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            percentage_rate=Decimal("10.00"),
            frequency="recurring",
            frequency_duration=5,
            frequency_duration_remaining=3,
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        assert applied.amount_cents == Decimal("500.0000")
        assert applied.amount_currency == "USD"
        assert applied.percentage_rate == Decimal("10.00")
        assert applied.frequency_duration == 5
        assert applied.frequency_duration_remaining == 3

    def test_applied_coupon_status_enum(self):
        """Test AppliedCouponStatus enum values."""
        assert AppliedCouponStatus.ACTIVE.value == "active"
        assert AppliedCouponStatus.TERMINATED.value == "terminated"


class TestCouponRepository:
    """Tests for CouponRepository CRUD and query methods."""

    def test_create_fixed_coupon(self, db_session):
        """Test creating a fixed amount coupon."""
        repo = CouponRepository(db_session)
        coupon = repo.create(
            CouponCreate(
                code="NEW10",
                name="New $10 Off",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("1000.0000"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
            ),
            DEFAULT_ORG_ID,
        )
        assert coupon.id is not None
        assert coupon.code == "NEW10"
        assert coupon.name == "New $10 Off"
        assert coupon.coupon_type == "fixed_amount"
        assert coupon.amount_cents == Decimal("1000.0000")
        assert coupon.amount_currency == "USD"
        assert coupon.frequency == "once"
        assert coupon.status == "active"

    def test_create_percentage_coupon(self, db_session):
        """Test creating a percentage coupon."""
        repo = CouponRepository(db_session)
        coupon = repo.create(
            CouponCreate(
                code="PCT15",
                name="15% Off",
                coupon_type=CouponType.PERCENTAGE,
                percentage_rate=Decimal("15.00"),
                frequency=CouponFrequency.FOREVER,
            ),
            DEFAULT_ORG_ID,
        )
        assert coupon.coupon_type == "percentage"
        assert coupon.percentage_rate == Decimal("15.00")
        assert coupon.frequency == "forever"

    def test_create_recurring_coupon(self, db_session):
        """Test creating a recurring coupon."""
        repo = CouponRepository(db_session)
        coupon = repo.create(
            CouponCreate(
                code="REC3",
                name="Recurring",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("500.0000"),
                amount_currency="USD",
                frequency=CouponFrequency.RECURRING,
                frequency_duration=3,
                reusable=False,
            ),
            DEFAULT_ORG_ID,
        )
        assert coupon.frequency == "recurring"
        assert coupon.frequency_duration == 3
        assert coupon.reusable is False

    def test_create_coupon_with_expiration(self, db_session):
        """Test creating a coupon with time-based expiration."""
        repo = CouponRepository(db_session)
        expiry = datetime.now(UTC) + timedelta(days=30)
        coupon = repo.create(
            CouponCreate(
                code="EXPIRING",
                name="Expiring Coupon",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("500.0000"),
                amount_currency="USD",
                frequency=CouponFrequency.ONCE,
                expiration=CouponExpiration.TIME_LIMIT,
                expiration_at=expiry,
            ),
            DEFAULT_ORG_ID,
        )
        assert coupon.expiration == "time_limit"
        assert coupon.expiration_at is not None

    def test_get_by_id(self, db_session, fixed_coupon):
        """Test getting a coupon by ID."""
        repo = CouponRepository(db_session)
        fetched = repo.get_by_id(fixed_coupon.id)
        assert fetched is not None
        assert fetched.id == fixed_coupon.id
        assert fetched.code == "FIXED10"

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent coupon."""
        repo = CouponRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_by_code(self, db_session, fixed_coupon):
        """Test getting a coupon by code."""
        repo = CouponRepository(db_session)
        fetched = repo.get_by_code("FIXED10", DEFAULT_ORG_ID)
        assert fetched is not None
        assert fetched.code == "FIXED10"
        assert fetched.id == fixed_coupon.id

    def test_get_by_code_not_found(self, db_session):
        """Test getting a non-existent coupon by code."""
        repo = CouponRepository(db_session)
        assert repo.get_by_code("NONEXISTENT", DEFAULT_ORG_ID) is None

    def test_get_all(self, db_session, fixed_coupon, percentage_coupon):
        """Test getting all coupons."""
        repo = CouponRepository(db_session)
        coupons = repo.get_all(DEFAULT_ORG_ID)
        assert len(coupons) == 2

    def test_get_all_filter_by_status(self, db_session, fixed_coupon, percentage_coupon):
        """Test getting coupons filtered by status."""
        repo = CouponRepository(db_session)
        repo.terminate("FIXED10", DEFAULT_ORG_ID)

        active = repo.get_all(DEFAULT_ORG_ID, status=CouponStatus.ACTIVE)
        assert len(active) == 1
        assert active[0].code == "PERCENT20"

        terminated = repo.get_all(DEFAULT_ORG_ID, status=CouponStatus.TERMINATED)
        assert len(terminated) == 1
        assert terminated[0].code == "FIXED10"

    def test_get_all_pagination(self, db_session):
        """Test pagination for get_all."""
        repo = CouponRepository(db_session)
        for i in range(5):
            repo.create(
                CouponCreate(
                    code=f"PAGE{i}",
                    name=f"Page {i}",
                    coupon_type=CouponType.FIXED_AMOUNT,
                    amount_cents=Decimal("100"),
                    amount_currency="USD",
                    frequency=CouponFrequency.ONCE,
                ),
                DEFAULT_ORG_ID,
            )
        result = repo.get_all(DEFAULT_ORG_ID, skip=2, limit=2)
        assert len(result) == 2

    def test_update(self, db_session, fixed_coupon):
        """Test updating a coupon."""
        repo = CouponRepository(db_session)
        updated = repo.update("FIXED10", CouponUpdate(name="Updated Name"), DEFAULT_ORG_ID)
        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.code == "FIXED10"  # unchanged

    def test_update_expiration(self, db_session, fixed_coupon):
        """Test updating coupon expiration."""
        repo = CouponRepository(db_session)
        expiry = datetime.now(UTC) + timedelta(days=90)
        updated = repo.update(
            "FIXED10",
            CouponUpdate(
                expiration=CouponExpiration.TIME_LIMIT,
                expiration_at=expiry,
            ),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.expiration == "time_limit"
        assert updated.expiration_at is not None

    def test_update_with_status(self, db_session, fixed_coupon):
        """Test updating a coupon with status change."""
        repo = CouponRepository(db_session)
        updated = repo.update(
            "FIXED10",
            CouponUpdate(status=CouponStatus.TERMINATED),
            DEFAULT_ORG_ID,
        )
        assert updated is not None
        assert updated.status == CouponStatus.TERMINATED.value

    def test_update_not_found(self, db_session):
        """Test updating a non-existent coupon."""
        repo = CouponRepository(db_session)
        assert repo.update("NONEXISTENT", CouponUpdate(name="nope"), DEFAULT_ORG_ID) is None

    def test_terminate(self, db_session, fixed_coupon):
        """Test terminating a coupon."""
        repo = CouponRepository(db_session)
        terminated = repo.terminate("FIXED10", DEFAULT_ORG_ID)
        assert terminated is not None
        assert terminated.status == CouponStatus.TERMINATED.value

    def test_terminate_not_found(self, db_session):
        """Test terminating a non-existent coupon."""
        repo = CouponRepository(db_session)
        assert repo.terminate("NONEXISTENT", DEFAULT_ORG_ID) is None

    def test_delete(self, db_session, fixed_coupon):
        """Test deleting a coupon."""
        repo = CouponRepository(db_session)
        assert repo.delete("FIXED10", DEFAULT_ORG_ID) is True
        assert repo.get_by_code("FIXED10", DEFAULT_ORG_ID) is None

    def test_delete_not_found(self, db_session):
        """Test deleting a non-existent coupon."""
        repo = CouponRepository(db_session)
        assert repo.delete("NONEXISTENT", DEFAULT_ORG_ID) is False


class TestAppliedCouponRepository:
    """Tests for AppliedCouponRepository CRUD and query methods."""

    def test_create_applied_coupon(self, db_session, customer, fixed_coupon):
        """Test creating an applied coupon."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000.0000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        assert applied.id is not None
        assert applied.coupon_id == fixed_coupon.id
        assert applied.customer_id == customer.id
        assert applied.amount_cents == Decimal("1000.0000")
        assert applied.frequency == "once"
        assert applied.status == "active"
        assert applied.frequency_duration_remaining is None

    def test_create_recurring_applied_coupon(self, db_session, customer, recurring_coupon):
        """Test creating a recurring applied coupon sets frequency_duration_remaining."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=recurring_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("500.0000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="recurring",
            frequency_duration=3,
        )
        assert applied.frequency == "recurring"
        assert applied.frequency_duration == 3
        assert applied.frequency_duration_remaining == 3

    def test_create_forever_applied_coupon(self, db_session, customer, percentage_coupon):
        """Test creating a forever applied coupon has no remaining count."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )
        assert applied.frequency == "forever"
        assert applied.frequency_duration_remaining is None

    def test_get_by_id(self, db_session, customer, fixed_coupon):
        """Test getting an applied coupon by ID."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        fetched = repo.get_by_id(applied.id)
        assert fetched is not None
        assert fetched.id == applied.id

    def test_get_by_id_not_found(self, db_session):
        """Test getting a non-existent applied coupon."""
        repo = AppliedCouponRepository(db_session)
        assert repo.get_by_id(uuid4()) is None

    def test_get_active_by_customer_id(self, db_session, customer, fixed_coupon, percentage_coupon):
        """Test getting active applied coupons for a customer."""
        repo = AppliedCouponRepository(db_session)
        active1 = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        active2 = repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )
        repo.terminate(active1.id)

        active = repo.get_active_by_customer_id(customer.id)
        assert len(active) == 1
        assert active[0].id == active2.id

    def test_get_active_by_customer_id_empty(self, db_session, customer):
        """Test getting active applied coupons for a customer with none."""
        repo = AppliedCouponRepository(db_session)
        assert repo.get_active_by_customer_id(customer.id) == []

    def test_get_by_coupon_and_customer(self, db_session, customer, fixed_coupon):
        """Test getting an applied coupon by coupon and customer."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        fetched = repo.get_by_coupon_and_customer(fixed_coupon.id, customer.id)
        assert fetched is not None
        assert fetched.id == applied.id

    def test_get_by_coupon_and_customer_not_found(self, db_session, customer, fixed_coupon):
        """Test getting non-existent coupon-customer pair."""
        repo = AppliedCouponRepository(db_session)
        assert repo.get_by_coupon_and_customer(fixed_coupon.id, customer.id) is None

    def test_get_all(self, db_session, customer, customer2, fixed_coupon, percentage_coupon):
        """Test getting all applied coupons with filters."""
        repo = AppliedCouponRepository(db_session)
        repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer2.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )

        all_applied = repo.get_all()
        assert len(all_applied) == 2

        c1_applied = repo.get_all(customer_id=customer.id)
        assert len(c1_applied) == 1

        c2_applied = repo.get_all(customer_id=customer2.id)
        assert len(c2_applied) == 1

    def test_get_all_filter_by_status(self, db_session, customer, fixed_coupon, percentage_coupon):
        """Test getting applied coupons filtered by status."""
        repo = AppliedCouponRepository(db_session)
        a1 = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )
        repo.terminate(a1.id)

        active = repo.get_all(status=AppliedCouponStatus.ACTIVE)
        assert len(active) == 1

        terminated = repo.get_all(status=AppliedCouponStatus.TERMINATED)
        assert len(terminated) == 1

    def test_get_all_pagination(self, db_session, customer, fixed_coupon):
        """Test pagination for get_all applied coupons."""
        repo = AppliedCouponRepository(db_session)
        coupon_repo = CouponRepository(db_session)
        for i in range(5):
            c = coupon_repo.create(
                CouponCreate(
                    code=f"PAG{i}",
                    name=f"Pag {i}",
                    coupon_type=CouponType.FIXED_AMOUNT,
                    amount_cents=Decimal("100"),
                    amount_currency="USD",
                    frequency=CouponFrequency.ONCE,
                ),
                DEFAULT_ORG_ID,
            )
            repo.create(
                coupon_id=c.id,
                customer_id=customer.id,
                amount_cents=Decimal("100"),
                amount_currency="USD",
                percentage_rate=None,
                frequency="once",
                frequency_duration=None,
            )
        result = repo.get_all(skip=2, limit=2)
        assert len(result) == 2

    def test_decrement_frequency(self, db_session, customer, recurring_coupon):
        """Test decrementing frequency_duration_remaining."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=recurring_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("500"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="recurring",
            frequency_duration=3,
        )
        assert applied.frequency_duration_remaining == 3

        # Decrement 1
        updated = repo.decrement_frequency(applied.id)
        assert updated is not None
        assert updated.frequency_duration_remaining == 2
        assert updated.status == "active"

        # Decrement 2
        updated = repo.decrement_frequency(applied.id)
        assert updated.frequency_duration_remaining == 1
        assert updated.status == "active"

        # Decrement 3 - should terminate
        updated = repo.decrement_frequency(applied.id)
        assert updated.frequency_duration_remaining == 0
        assert updated.status == "terminated"
        assert updated.terminated_at is not None

    def test_decrement_frequency_not_found(self, db_session):
        """Test decrementing frequency for non-existent applied coupon."""
        repo = AppliedCouponRepository(db_session)
        assert repo.decrement_frequency(uuid4()) is None

    def test_decrement_frequency_no_remaining(self, db_session, customer, percentage_coupon):
        """Test decrementing a forever coupon (no remaining count)."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )
        # Should not error, just return unchanged
        updated = repo.decrement_frequency(applied.id)
        assert updated is not None
        assert updated.status == "active"
        assert updated.frequency_duration_remaining is None

    def test_terminate(self, db_session, customer, fixed_coupon):
        """Test terminating an applied coupon."""
        repo = AppliedCouponRepository(db_session)
        applied = repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        terminated = repo.terminate(applied.id)
        assert terminated is not None
        assert terminated.status == "terminated"
        assert terminated.terminated_at is not None

    def test_terminate_not_found(self, db_session):
        """Test terminating a non-existent applied coupon."""
        repo = AppliedCouponRepository(db_session)
        assert repo.terminate(uuid4()) is None


class TestCouponSchema:
    """Tests for Coupon Pydantic schemas."""

    def test_coupon_create_fixed(self):
        """Test CouponCreate for fixed amount coupon."""
        schema = CouponCreate(
            code="FIX1",
            name="Fix",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
        )
        assert schema.code == "FIX1"
        assert schema.coupon_type == CouponType.FIXED_AMOUNT
        assert schema.reusable is True
        assert schema.expiration == CouponExpiration.NO_EXPIRATION

    def test_coupon_create_percentage(self):
        """Test CouponCreate for percentage coupon."""
        schema = CouponCreate(
            code="PCT1",
            name="Pct",
            coupon_type=CouponType.PERCENTAGE,
            percentage_rate=Decimal("25.50"),
            frequency=CouponFrequency.FOREVER,
        )
        assert schema.coupon_type == CouponType.PERCENTAGE
        assert schema.percentage_rate == Decimal("25.50")

    def test_coupon_create_with_expiration(self):
        """Test CouponCreate with time limit."""
        expiry = datetime.now(UTC) + timedelta(days=30)
        schema = CouponCreate(
            code="EXP1",
            name="Exp",
            coupon_type=CouponType.FIXED_AMOUNT,
            amount_cents=Decimal("500"),
            amount_currency="USD",
            frequency=CouponFrequency.ONCE,
            expiration=CouponExpiration.TIME_LIMIT,
            expiration_at=expiry,
        )
        assert schema.expiration == CouponExpiration.TIME_LIMIT
        assert schema.expiration_at is not None

    def test_coupon_create_code_max_length(self):
        """Test CouponCreate code max length."""
        with pytest.raises(ValidationError):
            CouponCreate(
                code="A" * 256,
                name="Too long",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("100"),
                frequency=CouponFrequency.ONCE,
            )

    def test_coupon_create_name_max_length(self):
        """Test CouponCreate name max length."""
        with pytest.raises(ValidationError):
            CouponCreate(
                code="OK",
                name="A" * 256,
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("100"),
                frequency=CouponFrequency.ONCE,
            )

    def test_coupon_create_invalid_currency_length(self):
        """Test CouponCreate with invalid currency."""
        with pytest.raises(ValidationError):
            CouponCreate(
                code="BAD",
                name="Bad",
                coupon_type=CouponType.FIXED_AMOUNT,
                amount_cents=Decimal("100"),
                amount_currency="US",
                frequency=CouponFrequency.ONCE,
            )

    def test_coupon_update_partial(self):
        """Test CouponUpdate partial update."""
        schema = CouponUpdate(name="New Name")
        dumped = schema.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "description" not in dumped
        assert "expiration" not in dumped
        assert "status" not in dumped

    def test_coupon_response_from_attributes(self, db_session):
        """Test CouponResponse can serialize from ORM object."""
        coupon = Coupon(
            code="RESP",
            name="Response Test",
            coupon_type="fixed_amount",
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            frequency="once",
        )
        db_session.add(coupon)
        db_session.commit()
        db_session.refresh(coupon)

        response = CouponResponse.model_validate(coupon)
        assert response.code == "RESP"
        assert response.name == "Response Test"
        assert response.coupon_type == "fixed_amount"
        assert response.status == "active"
        assert response.reusable is True

    def test_apply_coupon_request(self):
        """Test ApplyCouponRequest schema."""
        cid = uuid4()
        schema = ApplyCouponRequest(
            coupon_code="FIXED10",
            customer_id=cid,
        )
        assert schema.coupon_code == "FIXED10"
        assert schema.customer_id == cid
        assert schema.amount_cents is None
        assert schema.percentage_rate is None

    def test_apply_coupon_request_with_overrides(self):
        """Test ApplyCouponRequest with amount override."""
        cid = uuid4()
        schema = ApplyCouponRequest(
            coupon_code="FIXED10",
            customer_id=cid,
            amount_cents=Decimal("500"),
            amount_currency="EUR",
        )
        assert schema.amount_cents == Decimal("500")
        assert schema.amount_currency == "EUR"

    def test_apply_coupon_request_invalid_currency(self):
        """Test ApplyCouponRequest with invalid currency."""
        with pytest.raises(ValidationError):
            ApplyCouponRequest(
                coupon_code="X",
                customer_id=uuid4(),
                amount_currency="ABCD",
            )

    def test_applied_coupon_response_from_attributes(self, db_session, customer, fixed_coupon):
        """Test AppliedCouponResponse can serialize from ORM object."""
        applied = AppliedCoupon(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            frequency="once",
        )
        db_session.add(applied)
        db_session.commit()
        db_session.refresh(applied)

        response = AppliedCouponResponse.model_validate(applied)
        assert response.coupon_id == fixed_coupon.id
        assert response.customer_id == customer.id
        assert response.amount_cents == Decimal("1000")
        assert response.status == "active"

    def test_coupon_update_with_status(self):
        """Test CouponUpdate with status field."""
        schema = CouponUpdate(status=CouponStatus.TERMINATED)
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped["status"] == CouponStatus.TERMINATED

    def test_coupon_update_description(self):
        """Test CouponUpdate description field."""
        schema = CouponUpdate(description="New description")
        dumped = schema.model_dump(exclude_unset=True)
        assert dumped["description"] == "New description"


class TestCouponAPI:
    """Tests for Coupon API endpoints."""

    def test_create_coupon(self, client):
        """Test POST /v1/coupons/ creates a coupon."""
        response = client.post(
            "/v1/coupons/",
            json={
                "code": "API_FIXED",
                "name": "API Fixed Coupon",
                "description": "Test coupon from API",
                "coupon_type": "fixed_amount",
                "amount_cents": "1000.0000",
                "amount_currency": "USD",
                "frequency": "once",
                "reusable": True,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "API_FIXED"
        assert data["name"] == "API Fixed Coupon"
        assert data["coupon_type"] == "fixed_amount"
        assert data["status"] == "active"

    def test_create_coupon_percentage(self, client):
        """Test POST /v1/coupons/ creates a percentage coupon."""
        response = client.post(
            "/v1/coupons/",
            json={
                "code": "API_PCT",
                "name": "API Percentage Coupon",
                "coupon_type": "percentage",
                "percentage_rate": "15.00",
                "frequency": "forever",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["coupon_type"] == "percentage"
        assert data["percentage_rate"] == "15.00"
        assert data["frequency"] == "forever"

    def test_create_coupon_duplicate_code(self, client):
        """Test POST /v1/coupons/ returns 409 for duplicate code."""
        client.post(
            "/v1/coupons/",
            json={
                "code": "DUP_CODE",
                "name": "First",
                "coupon_type": "fixed_amount",
                "amount_cents": "100",
                "amount_currency": "USD",
                "frequency": "once",
            },
        )
        response = client.post(
            "/v1/coupons/",
            json={
                "code": "DUP_CODE",
                "name": "Second",
                "coupon_type": "fixed_amount",
                "amount_cents": "200",
                "amount_currency": "USD",
                "frequency": "once",
            },
        )
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_list_coupons(self, client, db_session, fixed_coupon, percentage_coupon):
        """Test GET /v1/coupons/ lists coupons."""
        response = client.get("/v1/coupons/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_coupons_empty(self, client):
        """Test GET /v1/coupons/ returns empty list."""
        response = client.get("/v1/coupons/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_coupons_filter_by_status(
        self, client, db_session, fixed_coupon, percentage_coupon
    ):
        """Test GET /v1/coupons/ filtered by status."""
        repo = CouponRepository(db_session)
        repo.terminate("FIXED10", DEFAULT_ORG_ID)

        response = client.get("/v1/coupons/?status=active")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["code"] == "PERCENT20"

    def test_list_coupons_pagination(self, client, db_session):
        """Test GET /v1/coupons/ with pagination."""
        repo = CouponRepository(db_session)
        for i in range(5):
            repo.create(
                CouponCreate(
                    code=f"APAG{i}",
                    name=f"Page {i}",
                    coupon_type=CouponType.FIXED_AMOUNT,
                    amount_cents=Decimal("100"),
                    amount_currency="USD",
                    frequency=CouponFrequency.ONCE,
                ),
                DEFAULT_ORG_ID,
            )
        response = client.get("/v1/coupons/?skip=2&limit=2")
        assert response.status_code == 200
        assert len(response.json()) == 2

    def test_get_coupon_by_code(self, client, db_session, fixed_coupon):
        """Test GET /v1/coupons/{code} returns coupon."""
        response = client.get("/v1/coupons/FIXED10")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "FIXED10"
        assert data["name"] == "$10 Off"

    def test_get_coupon_not_found(self, client):
        """Test GET /v1/coupons/{code} returns 404."""
        response = client.get("/v1/coupons/NONEXISTENT")
        assert response.status_code == 404

    def test_update_coupon(self, client, db_session, fixed_coupon):
        """Test PUT /v1/coupons/{code} updates coupon."""
        response = client.put(
            "/v1/coupons/FIXED10",
            json={
                "name": "Updated $10 Off",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated $10 Off"
        assert data["code"] == "FIXED10"

    def test_update_coupon_not_found(self, client):
        """Test PUT /v1/coupons/{code} returns 404."""
        response = client.put(
            "/v1/coupons/NONEXISTENT",
            json={
                "name": "Nope",
            },
        )
        assert response.status_code == 404

    def test_terminate_coupon(self, client, db_session, fixed_coupon):
        """Test DELETE /v1/coupons/{code} terminates coupon."""
        response = client.delete("/v1/coupons/FIXED10")
        assert response.status_code == 204

        # Verify terminated
        get_response = client.get("/v1/coupons/FIXED10")
        assert get_response.status_code == 200
        assert get_response.json()["status"] == "terminated"

    def test_terminate_coupon_not_found(self, client):
        """Test DELETE /v1/coupons/{code} returns 404."""
        response = client.delete("/v1/coupons/NONEXISTENT")
        assert response.status_code == 404

    def test_apply_coupon(self, client, db_session, fixed_coupon, customer):
        """Test POST /v1/coupons/apply applies coupon to customer."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(customer.id),
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["coupon_id"] == str(fixed_coupon.id)
        assert data["customer_id"] == str(customer.id)
        assert data["status"] == "active"
        assert data["amount_cents"] == "1000.0000"

    def test_apply_coupon_with_override(self, client, db_session, fixed_coupon, customer):
        """Test POST /v1/coupons/apply with amount override."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(customer.id),
                "amount_cents": "500.0000",
                "amount_currency": "EUR",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["amount_cents"] == "500.0000"
        assert data["amount_currency"] == "EUR"

    def test_apply_coupon_not_found(self, client, db_session, customer):
        """Test POST /v1/coupons/apply with non-existent coupon."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "NONEXISTENT",
                "customer_id": str(customer.id),
            },
        )
        assert response.status_code == 404
        assert "Coupon not found" in response.json()["detail"]

    def test_apply_coupon_customer_not_found(self, client, db_session, fixed_coupon):
        """Test POST /v1/coupons/apply with non-existent customer."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(uuid4()),
            },
        )
        assert response.status_code == 404
        assert "Customer not found" in response.json()["detail"]

    def test_apply_coupon_terminated(self, client, db_session, fixed_coupon, customer):
        """Test POST /v1/coupons/apply with terminated coupon."""
        repo = CouponRepository(db_session)
        repo.terminate("FIXED10", DEFAULT_ORG_ID)

        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(customer.id),
            },
        )
        assert response.status_code == 400
        assert "not active" in response.json()["detail"]

    def test_apply_non_reusable_coupon_duplicate(
        self, client, db_session, recurring_coupon, customer
    ):
        """Test POST /v1/coupons/apply with non-reusable coupon applied twice."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "RECURRING5",
                "customer_id": str(customer.id),
            },
        )
        assert response.status_code == 201

        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "RECURRING5",
                "customer_id": str(customer.id),
            },
        )
        assert response.status_code == 409
        assert "already applied" in response.json()["detail"]

    def test_apply_reusable_coupon_multiple_times(
        self, client, db_session, fixed_coupon, customer, customer2
    ):
        """Test POST /v1/coupons/apply reusable coupon to multiple customers."""
        response1 = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(customer.id),
            },
        )
        assert response1.status_code == 201

        response2 = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "FIXED10",
                "customer_id": str(customer2.id),
            },
        )
        assert response2.status_code == 201

    def test_list_applied_coupons(
        self, client, db_session, fixed_coupon, percentage_coupon, customer
    ):
        """Test GET /v1/customers/{customer_id}/applied_coupons."""
        applied_repo = AppliedCouponRepository(db_session)
        applied_repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        applied_repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )

        response = client.get(f"/v1/customers/{customer.id}/applied_coupons")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_list_applied_coupons_empty(self, client, db_session, customer):
        """Test GET /v1/customers/{customer_id}/applied_coupons returns empty list."""
        response = client.get(f"/v1/customers/{customer.id}/applied_coupons")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_applied_coupons_customer_not_found(self, client):
        """Test GET /v1/customers/{customer_id}/applied_coupons returns 404."""
        response = client.get(f"/v1/customers/{uuid4()}/applied_coupons")
        assert response.status_code == 404

    def test_apply_percentage_coupon_with_override(
        self, client, db_session, percentage_coupon, customer
    ):
        """Test POST /v1/coupons/apply with percentage rate override."""
        response = client.post(
            "/v1/coupons/apply",
            json={
                "coupon_code": "PERCENT20",
                "customer_id": str(customer.id),
                "percentage_rate": "30.00",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["percentage_rate"] == "30.00"


class TestRemoveAppliedCoupon:
    """Tests for DELETE /v1/coupons/applied/{applied_coupon_id} endpoint."""

    def test_remove_applied_coupon_success(
        self, client, db_session, fixed_coupon, customer
    ):
        """Test removing an applied coupon terminates it."""
        applied_repo = AppliedCouponRepository(db_session)
        applied = applied_repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )

        response = client.delete(f"/v1/coupons/applied/{applied.id}")
        assert response.status_code == 204

        # Verify it was terminated
        db_session.refresh(applied)
        assert applied.status == AppliedCouponStatus.TERMINATED.value
        assert applied.terminated_at is not None

    def test_remove_applied_coupon_not_found(self, client):
        """Test removing non-existent applied coupon returns 404."""
        response = client.delete(f"/v1/coupons/applied/{uuid4()}")
        assert response.status_code == 404

    def test_remove_applied_coupon_invalid_uuid(self, client):
        """Test removing with invalid UUID returns 422."""
        response = client.delete("/v1/coupons/applied/not-a-uuid")
        assert response.status_code == 422


class TestCouponAnalytics:
    """Tests for GET /v1/coupons/{code}/analytics endpoint."""

    def test_analytics_no_applications(self, client, db_session, fixed_coupon):
        """Test analytics for coupon with no applications."""
        response = client.get(f"/v1/coupons/{fixed_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["times_applied"] == 0
        assert data["active_applications"] == 0
        assert data["terminated_applications"] == 0
        assert Decimal(data["total_discount_cents"]) == Decimal("0")
        assert data["remaining_uses"] is None

    def test_analytics_with_active_applications(
        self, client, db_session, fixed_coupon, customer, customer2
    ):
        """Test analytics with active coupon applications."""
        applied_repo = AppliedCouponRepository(db_session)
        applied_repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        applied_repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer2.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )

        response = client.get(f"/v1/coupons/{fixed_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["times_applied"] == 2
        assert data["active_applications"] == 2
        assert data["terminated_applications"] == 0

    def test_analytics_with_terminated_once_coupon(
        self, client, db_session, fixed_coupon, customer
    ):
        """Test analytics with terminated once-frequency coupon (discount tracked)."""
        applied_repo = AppliedCouponRepository(db_session)
        applied = applied_repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        applied_repo.terminate(applied.id)

        response = client.get(f"/v1/coupons/{fixed_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["times_applied"] == 1
        assert data["active_applications"] == 0
        assert data["terminated_applications"] == 1
        assert Decimal(data["total_discount_cents"]) == Decimal("1000")

    def test_analytics_with_recurring_coupon(
        self, client, db_session, recurring_coupon, customer
    ):
        """Test analytics with recurring coupon showing remaining uses."""
        applied_repo = AppliedCouponRepository(db_session)
        applied_repo.create(
            coupon_id=recurring_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("500"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="recurring",
            frequency_duration=3,
        )

        response = client.get(f"/v1/coupons/{recurring_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["times_applied"] == 1
        assert data["active_applications"] == 1
        assert data["remaining_uses"] == 3

    def test_analytics_recurring_partially_consumed(
        self, client, db_session, recurring_coupon, customer
    ):
        """Test analytics with recurring coupon partially consumed."""
        applied_repo = AppliedCouponRepository(db_session)
        applied = applied_repo.create(
            coupon_id=recurring_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("500"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="recurring",
            frequency_duration=3,
        )
        # Decrement once (simulating one billing cycle consumed)
        applied_repo.decrement_frequency(applied.id)

        response = client.get(f"/v1/coupons/{recurring_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["remaining_uses"] == 2
        # 1 time used * 500 cents = 500
        assert Decimal(data["total_discount_cents"]) == Decimal("500")

    def test_analytics_coupon_not_found(self, client):
        """Test analytics for non-existent coupon returns 404."""
        response = client.get("/v1/coupons/NONEXISTENT/analytics")
        assert response.status_code == 404

    def test_analytics_percentage_coupon_no_discount_tracking(
        self, client, db_session, percentage_coupon, customer
    ):
        """Test analytics for percentage coupon (no discount amount tracking for forever)."""
        applied_repo = AppliedCouponRepository(db_session)
        applied_repo.create(
            coupon_id=percentage_coupon.id,
            customer_id=customer.id,
            amount_cents=None,
            amount_currency=None,
            percentage_rate=Decimal("20.00"),
            frequency="forever",
            frequency_duration=None,
        )

        response = client.get(f"/v1/coupons/{percentage_coupon.code}/analytics")
        assert response.status_code == 200
        data = response.json()
        assert data["times_applied"] == 1
        assert data["active_applications"] == 1
        assert data["remaining_uses"] is None


class TestDuplicateCoupon:
    """Tests for POST /v1/coupons/{code}/duplicate endpoint."""

    def test_duplicate_fixed_coupon(self, client, db_session, fixed_coupon):
        """Test duplicating a fixed amount coupon."""
        response = client.post(f"/v1/coupons/{fixed_coupon.code}/duplicate")
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "FIXED10_copy"
        assert data["name"] == "$10 Off (Copy)"
        assert data["coupon_type"] == "fixed_amount"
        assert Decimal(data["amount_cents"]) == Decimal("1000.0000")
        assert data["amount_currency"] == "USD"
        assert data["frequency"] == "once"
        assert data["status"] == "active"

    def test_duplicate_percentage_coupon(
        self, client, db_session, percentage_coupon
    ):
        """Test duplicating a percentage coupon."""
        response = client.post(f"/v1/coupons/{percentage_coupon.code}/duplicate")
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "PERCENT20_copy"
        assert data["name"] == "20% Off (Copy)"
        assert data["coupon_type"] == "percentage"
        assert Decimal(data["percentage_rate"]) == Decimal("20.00")

    def test_duplicate_recurring_coupon(
        self, client, db_session, recurring_coupon
    ):
        """Test duplicating a recurring coupon preserves frequency_duration."""
        response = client.post(
            f"/v1/coupons/{recurring_coupon.code}/duplicate"
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "RECURRING5_copy"
        assert data["frequency"] == "recurring"
        assert data["frequency_duration"] == 3
        assert data["reusable"] is False

    def test_duplicate_coupon_not_found(self, client):
        """Test duplicating non-existent coupon returns 404."""
        response = client.post("/v1/coupons/NONEXISTENT/duplicate")
        assert response.status_code == 404

    def test_duplicate_coupon_code_conflict(
        self, client, db_session, fixed_coupon
    ):
        """Test duplicating when _copy code already exists returns 409."""
        # First duplicate
        response = client.post(f"/v1/coupons/{fixed_coupon.code}/duplicate")
        assert response.status_code == 201

        # Second duplicate should fail
        response = client.post(f"/v1/coupons/{fixed_coupon.code}/duplicate")
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestAppliedCouponRepositoryExtensions:
    """Tests for new AppliedCouponRepository methods."""

    def test_get_all_by_coupon_id(
        self, db_session, fixed_coupon, customer, customer2
    ):
        """Test get_all_by_coupon_id returns all applications for a coupon."""
        repo = AppliedCouponRepository(db_session)
        repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )
        repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer2.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )

        results = repo.get_all_by_coupon_id(fixed_coupon.id)
        assert len(results) == 2

    def test_get_all_by_coupon_id_empty(self, db_session, fixed_coupon):
        """Test get_all_by_coupon_id returns empty for unused coupon."""
        repo = AppliedCouponRepository(db_session)
        results = repo.get_all_by_coupon_id(fixed_coupon.id)
        assert len(results) == 0

    def test_count_by_coupon_id(
        self, db_session, fixed_coupon, customer, customer2
    ):
        """Test count_by_coupon_id returns correct count."""
        repo = AppliedCouponRepository(db_session)
        repo.create(
            coupon_id=fixed_coupon.id,
            customer_id=customer.id,
            amount_cents=Decimal("1000"),
            amount_currency="USD",
            percentage_rate=None,
            frequency="once",
            frequency_duration=None,
        )

        assert repo.count_by_coupon_id(fixed_coupon.id) == 1
        assert repo.count_by_coupon_id(uuid4()) == 0


class TestCouponAnalyticsSchema:
    """Tests for CouponAnalyticsResponse schema."""

    def test_schema_validation(self):
        """Test CouponAnalyticsResponse schema with valid data."""
        from app.schemas.coupon import CouponAnalyticsResponse

        data = CouponAnalyticsResponse(
            times_applied=5,
            active_applications=3,
            terminated_applications=2,
            total_discount_cents=Decimal("5000"),
            remaining_uses=10,
        )
        assert data.times_applied == 5
        assert data.total_discount_cents == Decimal("5000")
        assert data.remaining_uses == 10

    def test_schema_remaining_uses_none(self):
        """Test CouponAnalyticsResponse with remaining_uses=None."""
        from app.schemas.coupon import CouponAnalyticsResponse

        data = CouponAnalyticsResponse(
            times_applied=1,
            active_applications=1,
            terminated_applications=0,
            total_discount_cents=Decimal("0"),
            remaining_uses=None,
        )
        assert data.remaining_uses is None
