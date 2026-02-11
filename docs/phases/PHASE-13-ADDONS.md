# Phase 13: Add-ons (One-time Charges)

> **Priority:** LOW | **Complexity:** Low | **Est. Time:** 3-5 days

## Overview

Add-ons are one-time charges applied to customers outside of subscriptions — setup fees, professional services, hardware, etc.

## Lago Reference

**Source:** `lago-api/app/models/add_on.rb`, `lago-api/app/models/applied_add_on.rb`

---

## Implementation Plan

### Models

```python
# app/models/add_on.py
class AddOn(Base):
    __tablename__ = "add_ons"

    id = Column(UUIDType, primary_key=True)
    
    code = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    
    amount_cents = Column(BigInteger, nullable=False)
    amount_currency = Column(String(3), default="USD")
    
    # Invoice display
    invoice_display_name = Column(String(255))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# app/models/applied_add_on.py
class AppliedAddOn(Base):
    """Add-on applied to a customer (becomes an invoice)."""
    __tablename__ = "applied_add_ons"

    id = Column(UUIDType, primary_key=True)
    add_on_id = Column(UUIDType, ForeignKey("add_ons.id"))
    customer_id = Column(UUIDType, ForeignKey("customers.id"))
    invoice_id = Column(UUIDType, ForeignKey("invoices.id"), nullable=True)
    
    # Can override amount
    amount_cents = Column(BigInteger, nullable=False)
    amount_currency = Column(String(3))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### API Endpoints

```python
# app/routers/add_ons.py
@router.post("/")
async def create_add_on(data: AddOnCreate):
    """Create an add-on."""

@router.get("/")
async def list_add_ons():
    """List all add-ons."""

@router.put("/{add_on_id}")
async def update_add_on(add_on_id: UUID, data: AddOnUpdate):
    """Update an add-on."""

@router.delete("/{add_on_id}")
async def delete_add_on(add_on_id: UUID):
    """Delete an add-on."""

# Apply add-on (creates one-time invoice)
@router.post("/applied_add_ons")
async def apply_add_on(data: ApplyAddOnRequest):
    """Apply add-on to customer. Creates a one-time invoice."""
```

### Invoice Generation

When an add-on is applied:
1. Create `AppliedAddOn` record
2. Generate one-time invoice with `invoice_type = "add_on"`
3. Mark as finalized immediately

---

## Files to Create

| File | Action |
|------|--------|
| `app/models/add_on.py` | Create |
| `app/models/applied_add_on.py` | Create |
| `app/routers/add_ons.py` | Create |
| `app/schemas/add_on.py` | Create |
| `tests/test_add_ons.py` | Create |

---

## Acceptance Criteria

- [ ] Add-on CRUD API
- [ ] Apply add-on to customer
- [ ] One-time invoice generation
- [ ] Amount override on application
- [ ] 100% test coverage
