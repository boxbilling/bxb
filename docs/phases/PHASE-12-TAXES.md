# Phase 12: Taxes

> **Priority:** MEDIUM | **Complexity:** Medium | **Est. Time:** 1 week

## Overview

Tax rates applied to invoices based on customer location, plan, or custom rules.

## Lago Reference

**Source:** `lago-api/app/models/tax.rb`

```ruby
# Tax can be applied at:
# - Organization level (default)
# - Customer level (override)
# - Plan level
# - Charge level
```

---

## Implementation Plan

### Models

```python
# app/models/tax.py
class Tax(Base):
    __tablename__ = "taxes"

    id = Column(UUIDType, primary_key=True)
    organization_id = Column(UUIDType)
    
    name = Column(String(255), nullable=False)  # "VAT", "Sales Tax"
    code = Column(String(50), unique=True)      # "vat_20", "sales_ca"
    description = Column(Text)
    
    rate = Column(Numeric(8, 5), nullable=False)  # 20.00000 = 20%
    
    # Auto-apply to all invoices?
    applied_to_organization = Column(Boolean, default=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

# app/models/applied_tax.py
class AppliedTax(Base):
    """Tax applied to customer, plan, or charge."""
    __tablename__ = "applied_taxes"

    id = Column(UUIDType, primary_key=True)
    tax_id = Column(UUIDType, ForeignKey("taxes.id"))
    
    # Polymorphic association
    taxable_type = Column(String(50))  # Customer, Plan, Charge
    taxable_id = Column(UUIDType)
```

### Tax Service

```python
# app/services/tax_service.py
class TaxService:
    def calculate_taxes(
        self,
        customer_id: UUID,
        plan_id: UUID,
        subtotal_cents: int
    ) -> tuple[int, list[dict]]:
        """
        Calculate taxes for an invoice.
        Returns: (total_tax_cents, tax_breakdown)
        
        Priority:
        1. Customer-specific taxes
        2. Plan-specific taxes
        3. Organization default taxes
        """
        taxes = self._get_applicable_taxes(customer_id, plan_id)
        
        total_tax = 0
        breakdown = []
        
        for tax in taxes:
            tax_amount = int(subtotal_cents * tax.rate / 100)
            total_tax += tax_amount
            breakdown.append({
                "tax_id": str(tax.id),
                "tax_name": tax.name,
                "tax_code": tax.code,
                "tax_rate": float(tax.rate),
                "amount_cents": tax_amount,
            })
        
        return total_tax, breakdown
    
    def _get_applicable_taxes(self, customer_id: UUID, plan_id: UUID) -> list[Tax]:
        """Get taxes in priority order."""
        # Check customer-specific taxes
        customer_taxes = self.db.query(Tax).join(AppliedTax).filter(
            AppliedTax.taxable_type == "Customer",
            AppliedTax.taxable_id == customer_id,
        ).all()
        if customer_taxes:
            return customer_taxes
        
        # Check plan-specific taxes
        plan_taxes = self.db.query(Tax).join(AppliedTax).filter(
            AppliedTax.taxable_type == "Plan",
            AppliedTax.taxable_id == plan_id,
        ).all()
        if plan_taxes:
            return plan_taxes
        
        # Fall back to organization default
        return self.db.query(Tax).filter(
            Tax.applied_to_organization == True
        ).all()
```

### API Endpoints

```python
# app/routers/taxes.py
@router.post("/")
async def create_tax(data: TaxCreate):
    """Create a tax rate."""

@router.get("/")
async def list_taxes():
    """List all tax rates."""

@router.put("/{tax_id}")
async def update_tax(tax_id: UUID, data: TaxUpdate):
    """Update a tax rate."""

@router.delete("/{tax_id}")
async def delete_tax(tax_id: UUID):
    """Delete a tax rate."""
```

### Invoice Integration

```python
# In invoice generation
tax_service = TaxService(db)
taxes_cents, tax_breakdown = tax_service.calculate_taxes(
    customer_id=customer.id,
    plan_id=plan.id,
    subtotal_cents=subtotal
)

invoice.taxes_amount_cents = taxes_cents
invoice.applied_taxes = tax_breakdown  # Store breakdown
invoice.total_amount_cents = subtotal + taxes_cents
```

---

## Files to Create

| File | Action |
|------|--------|
| `app/models/tax.py` | Create |
| `app/models/applied_tax.py` | Create |
| `app/services/tax_service.py` | Create |
| `app/routers/taxes.py` | Create |
| `app/schemas/tax.py` | Create |
| `tests/test_taxes.py` | Create |

---

## Acceptance Criteria

- [ ] Tax CRUD API
- [ ] Apply taxes at org/customer/plan/charge level
- [ ] Tax calculation with priority
- [ ] Tax breakdown on invoices
- [ ] 100% test coverage
