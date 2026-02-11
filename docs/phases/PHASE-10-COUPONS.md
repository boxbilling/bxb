# Phase 10: Coupons & Discounts

> **Priority:** MEDIUM | **Complexity:** Medium | **Est. Time:** 1-2 weeks

## Overview

Coupons provide discounts on invoices — fixed amount, percentage, or recurring.

## Lago Reference

**Source:** `lago-api/app/models/coupon.rb`, `lago-api/app/models/applied_coupon.rb`

```ruby
# Coupon types
COUPON_TYPES = [:fixed_amount, :percentage].freeze
FREQUENCIES = [:once, :recurring, :forever].freeze
EXPIRATION_TYPES = [:no_expiration, :time_limit].freeze
```

---

## Implementation Plan

### Step 1: Models

```python
# app/models/coupon.py
class CouponType(str, Enum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"

class CouponFrequency(str, Enum):
    ONCE = "once"            # Apply once
    RECURRING = "recurring"  # Apply for N billing periods
    FOREVER = "forever"      # Apply indefinitely

class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(UUIDType, primary_key=True)
    code = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Type
    coupon_type = Column(String(20), nullable=False)  # fixed_amount, percentage
    
    # Value
    amount_cents = Column(BigInteger, nullable=True)  # For fixed_amount
    amount_currency = Column(String(3), nullable=True)
    percentage_rate = Column(Numeric(5, 2), nullable=True)  # For percentage (e.g., 20.00)
    
    # Frequency
    frequency = Column(String(20), default="once")
    frequency_duration = Column(Integer, nullable=True)  # For recurring
    
    # Limits
    limited_plans = Column(Boolean, default=False)  # Only apply to specific plans
    limited_billable_metrics = Column(Boolean, default=False)
    
    # Redemption limits
    reusable = Column(Boolean, default=True)  # Can be applied multiple times
    limited_redemptions = Column(Boolean, default=False)
    redemption_limit = Column(Integer, nullable=True)
    
    # Expiration
    expiration_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    status = Column(String(20), default="active")  # active, terminated
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# app/models/applied_coupon.py
class AppliedCoupon(Base):
    """Coupon applied to a customer."""
    __tablename__ = "applied_coupons"

    id = Column(UUIDType, primary_key=True)
    coupon_id = Column(UUIDType, ForeignKey("coupons.id"))
    customer_id = Column(UUIDType, ForeignKey("customers.id"))
    
    # Tracking
    amount_cents = Column(BigInteger)  # Remaining amount for fixed coupons
    amount_currency = Column(String(3))
    percentage_rate = Column(Numeric(5, 2))
    
    # Frequency tracking
    frequency = Column(String(20))
    frequency_duration = Column(Integer, nullable=True)
    frequency_duration_remaining = Column(Integer, nullable=True)
    
    # Status
    status = Column(String(20), default="active")  # active, terminated
    terminated_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# app/models/coupon_target.py  
class CouponTarget(Base):
    """Plans/metrics a coupon applies to."""
    __tablename__ = "coupon_targets"

    id = Column(UUIDType, primary_key=True)
    coupon_id = Column(UUIDType, ForeignKey("coupons.id"))
    
    target_type = Column(String(50))  # Plan, BillableMetric
    target_id = Column(UUIDType)
```

### Step 2: Coupon Service

```python
# app/services/coupon_service.py
class CouponService:
    def apply_to_customer(self, coupon_id: UUID, customer_id: UUID) -> AppliedCoupon:
        """Apply a coupon to a customer."""
        coupon = self.db.query(Coupon).get(coupon_id)
        
        # Validate
        if coupon.status != "active":
            raise ValueError("Coupon is not active")
        if coupon.expiration_at and coupon.expiration_at < datetime.utcnow():
            raise ValueError("Coupon has expired")
        
        # Check redemption limit
        if coupon.limited_redemptions:
            count = self.db.query(AppliedCoupon).filter(
                AppliedCoupon.coupon_id == coupon_id
            ).count()
            if count >= coupon.redemption_limit:
                raise ValueError("Coupon redemption limit reached")
        
        applied = AppliedCoupon(
            coupon_id=coupon_id,
            customer_id=customer_id,
            amount_cents=coupon.amount_cents,
            amount_currency=coupon.amount_currency,
            percentage_rate=coupon.percentage_rate,
            frequency=coupon.frequency,
            frequency_duration=coupon.frequency_duration,
            frequency_duration_remaining=coupon.frequency_duration,
        )
        self.db.add(applied)
        self.db.commit()
        return applied
    
    def calculate_discount(
        self,
        customer_id: UUID,
        subtotal_cents: int,
        plan_id: UUID | None = None
    ) -> int:
        """Calculate total discount for customer's active coupons."""
        applied_coupons = self.db.query(AppliedCoupon).filter(
            AppliedCoupon.customer_id == customer_id,
            AppliedCoupon.status == "active",
        ).all()
        
        total_discount = 0
        
        for ac in applied_coupons:
            coupon = self.db.query(Coupon).get(ac.coupon_id)
            
            # Check plan target
            if coupon.limited_plans and plan_id:
                targets = self.db.query(CouponTarget).filter(
                    CouponTarget.coupon_id == coupon.id,
                    CouponTarget.target_type == "Plan",
                    CouponTarget.target_id == plan_id,
                ).first()
                if not targets:
                    continue
            
            if ac.percentage_rate:
                discount = int(subtotal_cents * ac.percentage_rate / 100)
            else:
                discount = min(ac.amount_cents or 0, subtotal_cents - total_discount)
            
            total_discount += discount
            
            # Update remaining
            self._update_applied_coupon_usage(ac, discount)
        
        return total_discount
    
    def _update_applied_coupon_usage(self, ac: AppliedCoupon, discount_cents: int):
        """Update coupon after use."""
        if ac.frequency == CouponFrequency.ONCE.value:
            ac.status = "terminated"
            ac.terminated_at = datetime.utcnow()
        elif ac.frequency == CouponFrequency.RECURRING.value:
            if ac.frequency_duration_remaining:
                ac.frequency_duration_remaining -= 1
                if ac.frequency_duration_remaining <= 0:
                    ac.status = "terminated"
                    ac.terminated_at = datetime.utcnow()
        # forever = no action needed
        
        # For fixed amount, track remaining
        if ac.amount_cents:
            ac.amount_cents -= discount_cents
            if ac.amount_cents <= 0:
                ac.status = "terminated"
                ac.terminated_at = datetime.utcnow()
```

### Step 3: Invoice Integration

```python
# app/services/invoice_generation.py (modification)
def generate_invoice(...):
    # Calculate subtotal
    subtotal = calculate_fees(...)
    
    # Apply coupons
    coupon_service = CouponService(db)
    coupon_discount = coupon_service.calculate_discount(
        customer_id=customer.id,
        subtotal_cents=subtotal,
        plan_id=subscription.plan_id
    )
    
    invoice.coupons_amount_cents = coupon_discount
    invoice.total_amount_cents = subtotal - coupon_discount
```

### Step 4: API Endpoints

```python
# app/routers/coupons.py
@router.post("/", response_model=CouponResponse)
async def create_coupon(data: CouponCreate):
    """Create a coupon."""

@router.get("/", response_model=list[CouponResponse])
async def list_coupons():
    """List all coupons."""

@router.get("/{coupon_id}")
async def get_coupon(coupon_id: UUID):
    """Get a coupon."""

@router.put("/{coupon_id}")
async def update_coupon(coupon_id: UUID, data: CouponUpdate):
    """Update a coupon."""

@router.delete("/{coupon_id}")
async def terminate_coupon(coupon_id: UUID):
    """Terminate a coupon."""

# Applied coupons
@router.post("/applied_coupons", response_model=AppliedCouponResponse)
async def apply_coupon(data: ApplyCouponRequest):
    """Apply coupon to customer."""

@router.get("/applied_coupons", response_model=list[AppliedCouponResponse])
async def list_applied_coupons(customer_id: UUID = None):
    """List applied coupons."""

@router.delete("/applied_coupons/{id}")
async def remove_applied_coupon(id: UUID):
    """Remove coupon from customer."""
```

---

## Database Migrations

```sql
CREATE TABLE coupons (
    id UUID PRIMARY KEY,
    code VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    coupon_type VARCHAR(20) NOT NULL,
    amount_cents BIGINT,
    amount_currency VARCHAR(3),
    percentage_rate NUMERIC(5, 2),
    frequency VARCHAR(20) DEFAULT 'once',
    frequency_duration INTEGER,
    limited_plans BOOLEAN DEFAULT FALSE,
    limited_billable_metrics BOOLEAN DEFAULT FALSE,
    reusable BOOLEAN DEFAULT TRUE,
    limited_redemptions BOOLEAN DEFAULT FALSE,
    redemption_limit INTEGER,
    expiration_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE applied_coupons (
    id UUID PRIMARY KEY,
    coupon_id UUID REFERENCES coupons(id),
    customer_id UUID REFERENCES customers(id),
    amount_cents BIGINT,
    amount_currency VARCHAR(3),
    percentage_rate NUMERIC(5, 2),
    frequency VARCHAR(20),
    frequency_duration INTEGER,
    frequency_duration_remaining INTEGER,
    status VARCHAR(20) DEFAULT 'active',
    terminated_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE coupon_targets (
    id UUID PRIMARY KEY,
    coupon_id UUID REFERENCES coupons(id),
    target_type VARCHAR(50) NOT NULL,
    target_id UUID NOT NULL
);
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/coupon.py` | Create |
| `app/models/applied_coupon.py` | Create |
| `app/models/coupon_target.py` | Create |
| `app/services/coupon_service.py` | Create |
| `app/routers/coupons.py` | Create |
| `app/schemas/coupon.py` | Create |
| `app/services/invoice_generation.py` | Modify |
| `tests/test_coupons.py` | Create |

---

## Acceptance Criteria

- [ ] Coupon CRUD API (code, fixed amount, percentage)
- [ ] Apply coupon to customer
- [ ] Frequency: once, recurring, forever
- [ ] Plan/metric targeting
- [ ] Redemption limits
- [ ] Expiration dates
- [ ] Invoice discount calculation
- [ ] 100% test coverage
