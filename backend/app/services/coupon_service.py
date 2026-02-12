"""Coupon application service for managing coupon discounts."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.applied_coupon import AppliedCoupon
from app.models.coupon import CouponExpiration, CouponFrequency, CouponStatus, CouponType
from app.models.customer import DEFAULT_ORGANIZATION_ID
from app.repositories.applied_coupon_repository import AppliedCouponRepository
from app.repositories.coupon_repository import CouponRepository
from app.repositories.customer_repository import CustomerRepository


@dataclass
class CouponDiscount:
    """Result of a coupon discount calculation."""

    total_discount_cents: Decimal
    applied_coupon_ids: list[UUID]


class CouponApplicationService:
    """Service for coupon application and discount calculation."""

    def __init__(self, db: Session):
        self.db = db
        self.coupon_repo = CouponRepository(db)
        self.applied_coupon_repo = AppliedCouponRepository(db)
        self.customer_repo = CustomerRepository(db)

    def apply_coupon_to_customer(
        self,
        coupon_code: str,
        customer_id: UUID,
        amount_override: Decimal | None = None,
        percentage_override: Decimal | None = None,
        organization_id: UUID = DEFAULT_ORGANIZATION_ID,
    ) -> AppliedCoupon:
        """Validate and apply a coupon to a customer.

        Args:
            coupon_code: The coupon code to apply.
            customer_id: The customer to apply the coupon to.
            amount_override: Optional override for the fixed amount.
            percentage_override: Optional override for the percentage rate.

        Returns:
            The created AppliedCoupon.

        Raises:
            ValueError: If validation fails.
        """
        # Fetch and validate coupon
        coupon = self.coupon_repo.get_by_code(coupon_code, organization_id)
        if not coupon:
            raise ValueError(f"Coupon '{coupon_code}' not found")

        if coupon.status != CouponStatus.ACTIVE.value:
            raise ValueError("Coupon is not active")

        # Check expiration
        if coupon.expiration == CouponExpiration.TIME_LIMIT.value and coupon.expiration_at:
            expiration_at = coupon.expiration_at
            if expiration_at.tzinfo is None:
                expiration_at = expiration_at.replace(tzinfo=UTC)
            if datetime.now(UTC) >= expiration_at:
                raise ValueError("Coupon has expired")

        # Validate customer exists
        customer = self.customer_repo.get_by_id(customer_id)
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        # Check reusable constraint
        if not coupon.reusable:
            existing = self.applied_coupon_repo.get_by_coupon_and_customer(
                coupon.id,  # type: ignore[arg-type]
                customer_id,
            )
            if existing:
                raise ValueError("Coupon already applied to this customer")

        # Determine amount/rate values (override or coupon defaults)
        amount_cents = amount_override if amount_override is not None else coupon.amount_cents
        amount_currency = (
            coupon.amount_currency if coupon.coupon_type == CouponType.FIXED_AMOUNT.value else None
        )
        percentage_rate = (
            percentage_override if percentage_override is not None else coupon.percentage_rate
        )

        return self.applied_coupon_repo.create(
            coupon_id=coupon.id,  # type: ignore[arg-type]
            customer_id=customer_id,
            amount_cents=amount_cents,  # type: ignore[arg-type]
            amount_currency=amount_currency,  # type: ignore[arg-type]
            percentage_rate=percentage_rate,  # type: ignore[arg-type]
            frequency=str(coupon.frequency),
            frequency_duration=coupon.frequency_duration,  # type: ignore[arg-type]
        )

    def calculate_coupon_discount(
        self,
        customer_id: UUID,
        subtotal_cents: Decimal,
    ) -> CouponDiscount:
        """Calculate total coupon discount for a customer's invoice.

        Gets all active applied coupons for the customer, calculates the discount
        for each, and returns the total discount capped at the subtotal.

        Args:
            customer_id: The customer to calculate discounts for.
            subtotal_cents: The invoice subtotal in cents.

        Returns:
            CouponDiscount with total discount and list of applied coupon IDs consumed.
        """
        applied_coupons = self.applied_coupon_repo.get_active_by_customer_id(customer_id)

        total_discount = Decimal("0")
        consumed_ids: list[UUID] = []
        remaining_subtotal = Decimal(str(subtotal_cents))

        for applied_coupon in applied_coupons:
            if remaining_subtotal <= 0:
                break

            discount = self._calculate_single_discount(applied_coupon, remaining_subtotal)
            if discount > 0:
                total_discount += discount
                remaining_subtotal -= discount
                consumed_ids.append(applied_coupon.id)  # type: ignore[arg-type]

        return CouponDiscount(
            total_discount_cents=total_discount,
            applied_coupon_ids=consumed_ids,
        )

    def consume_applied_coupon(self, applied_coupon_id: UUID) -> AppliedCoupon | None:
        """Consume an applied coupon after it has been used in an invoice.

        For "once" frequency: terminate immediately.
        For "recurring": decrement frequency_duration_remaining, terminate if 0.
        For "forever": no action needed (coupon remains active).

        Args:
            applied_coupon_id: The applied coupon to consume.

        Returns:
            The updated AppliedCoupon, or None if not found.
        """
        applied_coupon = self.applied_coupon_repo.get_by_id(applied_coupon_id)
        if not applied_coupon:
            return None

        frequency = str(applied_coupon.frequency)

        if frequency == CouponFrequency.ONCE.value:
            return self.applied_coupon_repo.terminate(applied_coupon_id)

        if frequency == CouponFrequency.RECURRING.value:
            return self.applied_coupon_repo.decrement_frequency(applied_coupon_id)

        # For "forever" frequency, no consumption needed — return as-is
        return applied_coupon

    def _calculate_single_discount(
        self,
        applied_coupon: AppliedCoupon,
        remaining_subtotal: Decimal,
    ) -> Decimal:
        """Calculate discount for a single applied coupon.

        Args:
            applied_coupon: The applied coupon to calculate.
            remaining_subtotal: The remaining subtotal to apply discount against.

        Returns:
            The discount amount in cents.
        """
        # Determine coupon type from the applied coupon fields
        if applied_coupon.percentage_rate and applied_coupon.percentage_rate > 0:
            # Percentage discount
            rate = Decimal(str(applied_coupon.percentage_rate))
            discount = remaining_subtotal * rate / Decimal("100")
        elif applied_coupon.amount_cents and applied_coupon.amount_cents > 0:
            # Fixed amount discount — cap at remaining subtotal
            discount = min(Decimal(str(applied_coupon.amount_cents)), remaining_subtotal)
        else:
            discount = Decimal("0")

        return discount
