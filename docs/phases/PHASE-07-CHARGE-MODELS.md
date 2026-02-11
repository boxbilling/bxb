# Phase 7: Advanced Charge Models

> **Priority:** HIGH | **Complexity:** High | **Est. Time:** 2-3 weeks

## Overview

Lago supports 8 charge models. bxb currently has only `standard`. This phase implements the remaining 7.

## Lago Reference

**Source:** `lago-api/app/models/charge.rb`
```ruby
CHARGE_MODELS = %i[
  standard        # ✅ Done in bxb
  graduated       # Tiered pricing
  package         # Per-package pricing
  percentage      # % of amount
  volume          # Volume discounts
  graduated_percentage  # Tiered percentages
  custom          # Custom logic
  dynamic         # Real-time pricing
].freeze
```

**Services:** `lago-api/app/services/charge_models/`
- `standard_service.rb` (17 lines - simple)
- `graduated_service.rb` (65 lines)
- `package_service.rb` (70 lines)
- `percentage_service.rb` (240 lines)
- `volume_service.rb` (75 lines)
- `graduated_percentage_service.rb` (40 lines)

---

## Implementation Plan

### Step 1: Charge Model Enum & Schema

**File:** `app/models/charge.py`

```python
class ChargeModel(str, Enum):
    STANDARD = "standard"
    GRADUATED = "graduated"
    PACKAGE = "package"
    PERCENTAGE = "percentage"
    VOLUME = "volume"
    GRADUATED_PERCENTAGE = "graduated_percentage"
```

**Schema Update:** `app/schemas/charge.py`
```python
class ChargeProperties(BaseModel):
    """Properties vary by charge model."""
    # Standard
    amount: Decimal | None = None
    
    # Graduated/Volume
    graduated_ranges: list[GraduatedRange] | None = None
    
    # Package
    package_size: int | None = None
    free_units: int | None = None
    
    # Percentage
    rate: Decimal | None = None
    fixed_amount: Decimal | None = None
    free_units_per_events: int | None = None
    free_units_per_total_aggregation: Decimal | None = None
    per_transaction_min_amount: Decimal | None = None
    per_transaction_max_amount: Decimal | None = None

class GraduatedRange(BaseModel):
    from_value: int
    to_value: int | None  # None = infinity
    per_unit_amount: Decimal
    flat_amount: Decimal = Decimal("0")
```

### Step 2: Charge Model Services

Create `app/services/charge_models/` directory with:

#### 2.1 Standard Service (exists implicitly)
```python
# app/services/charge_models/standard.py
def calculate(units: Decimal, properties: dict) -> Decimal:
    """Standard: units × amount"""
    return units * Decimal(str(properties.get("amount", 0)))
```

#### 2.2 Graduated Service
**Lago ref:** `lago-api/app/services/charge_models/graduated_service.rb`

```python
# app/services/charge_models/graduated.py
def calculate(units: Decimal, properties: dict) -> Decimal:
    """
    Graduated: Different price per tier.
    
    Example: 
    - 0-10 units: $1/unit
    - 11-50 units: $0.80/unit
    - 51+: $0.50/unit
    
    100 units = (10 × $1) + (40 × $0.80) + (50 × $0.50) = $67
    """
    ranges = properties.get("graduated_ranges", [])
    total = Decimal("0")
    remaining = units
    
    for r in sorted(ranges, key=lambda x: x["from_value"]):
        if remaining <= 0:
            break
            
        from_val = r["from_value"]
        to_val = r.get("to_value")  # None = infinity
        per_unit = Decimal(str(r["per_unit_amount"]))
        flat = Decimal(str(r.get("flat_amount", 0)))
        
        if to_val is None:
            units_in_tier = remaining
        else:
            tier_size = to_val - from_val + 1
            units_in_tier = min(remaining, tier_size)
        
        total += (units_in_tier * per_unit) + flat
        remaining -= units_in_tier
    
    return total
```

#### 2.3 Package Service
**Lago ref:** `lago-api/app/services/charge_models/package_service.rb`

```python
# app/services/charge_models/package.py
import math

def calculate(units: Decimal, properties: dict) -> Decimal:
    """
    Package: Price per X units.
    
    Example: $10 per 100 API calls
    - 250 calls = 3 packages = $30
    """
    amount = Decimal(str(properties.get("amount", 0)))
    package_size = int(properties.get("package_size", 1))
    free_units = int(properties.get("free_units", 0))
    
    billable_units = max(0, units - free_units)
    packages = math.ceil(billable_units / package_size)
    
    return packages * amount
```

#### 2.4 Percentage Service
**Lago ref:** `lago-api/app/services/charge_models/percentage_service.rb` (most complex)

```python
# app/services/charge_models/percentage.py
def calculate(
    units: Decimal, 
    total_amount: Decimal,  # Sum of transaction amounts
    event_count: int,
    properties: dict
) -> Decimal:
    """
    Percentage: % of transaction amount.
    
    Example: 2.9% + $0.30 per transaction (Stripe-like)
    
    Properties:
    - rate: Percentage (e.g., 2.9)
    - fixed_amount: Per-transaction fee
    - free_units_per_events: Free transactions
    - per_transaction_min_amount: Minimum fee per txn
    - per_transaction_max_amount: Maximum fee per txn
    """
    rate = Decimal(str(properties.get("rate", 0))) / 100
    fixed_amount = Decimal(str(properties.get("fixed_amount", 0)))
    free_events = int(properties.get("free_units_per_events", 0))
    min_per_txn = properties.get("per_transaction_min_amount")
    max_per_txn = properties.get("per_transaction_max_amount")
    
    billable_events = max(0, event_count - free_events)
    
    # Calculate percentage fee
    percentage_fee = total_amount * rate
    
    # Calculate fixed fees
    fixed_fees = billable_events * fixed_amount
    
    total = percentage_fee + fixed_fees
    
    # Apply min/max per transaction
    if min_per_txn and total < min_per_txn * billable_events:
        total = min_per_txn * billable_events
    if max_per_txn and total > max_per_txn * billable_events:
        total = max_per_txn * billable_events
    
    return total
```

#### 2.5 Volume Service
**Lago ref:** `lago-api/app/services/charge_models/volume_service.rb`

```python
# app/services/charge_models/volume.py
def calculate(units: Decimal, properties: dict) -> Decimal:
    """
    Volume: ALL units priced at the tier they land in.
    
    Example:
    - 0-100 units: $1/unit
    - 101-500 units: $0.80/unit
    - 501+: $0.50/unit
    
    100 units = 100 × $1 = $100
    150 units = 150 × $0.80 = $120  (NOT graduated!)
    """
    ranges = properties.get("volume_ranges", [])
    
    for r in sorted(ranges, key=lambda x: x["from_value"], reverse=True):
        from_val = r["from_value"]
        if units >= from_val:
            per_unit = Decimal(str(r["per_unit_amount"]))
            flat = Decimal(str(r.get("flat_amount", 0)))
            return (units * per_unit) + flat
    
    return Decimal("0")
```

#### 2.6 Graduated Percentage Service
```python
# app/services/charge_models/graduated_percentage.py
def calculate(total_amount: Decimal, properties: dict) -> Decimal:
    """
    Graduated Percentage: Different % per tier of amount.
    
    Example:
    - $0-$1000: 3%
    - $1001-$10000: 2%
    - $10001+: 1%
    """
    ranges = properties.get("graduated_percentage_ranges", [])
    total_fee = Decimal("0")
    remaining = total_amount
    
    for r in sorted(ranges, key=lambda x: x["from_value"]):
        if remaining <= 0:
            break
            
        from_val = Decimal(str(r["from_value"]))
        to_val = r.get("to_value")
        rate = Decimal(str(r["rate"])) / 100
        flat = Decimal(str(r.get("flat_amount", 0)))
        
        if to_val is None:
            amount_in_tier = remaining
        else:
            tier_size = Decimal(str(to_val)) - from_val
            amount_in_tier = min(remaining, tier_size)
        
        total_fee += (amount_in_tier * rate) + flat
        remaining -= amount_in_tier
    
    return total_fee
```

### Step 3: Charge Model Factory

```python
# app/services/charge_models/factory.py
from app.models.charge import ChargeModel
from app.services.charge_models import (
    standard, graduated, package, percentage, volume, graduated_percentage
)

def get_charge_calculator(model: ChargeModel):
    """Factory to get the appropriate charge calculator."""
    calculators = {
        ChargeModel.STANDARD: standard.calculate,
        ChargeModel.GRADUATED: graduated.calculate,
        ChargeModel.PACKAGE: package.calculate,
        ChargeModel.PERCENTAGE: percentage.calculate,
        ChargeModel.VOLUME: volume.calculate,
        ChargeModel.GRADUATED_PERCENTAGE: graduated_percentage.calculate,
    }
    return calculators.get(model)
```

### Step 4: Update Invoice Generation

Modify `app/services/invoice_generation.py` to use charge model factory:

```python
from app.services.charge_models.factory import get_charge_calculator

def calculate_usage_fee(charge: Charge, usage: UsageData) -> Decimal:
    calculator = get_charge_calculator(charge.charge_model)
    
    if charge.charge_model == ChargeModel.PERCENTAGE:
        return calculator(
            units=usage.units,
            total_amount=usage.total_amount,
            event_count=usage.event_count,
            properties=charge.properties
        )
    else:
        return calculator(
            units=usage.units,
            properties=charge.properties
        )
```

### Step 5: API Updates

Update charge creation/update endpoints to validate properties based on model:

```python
# app/routers/plans.py - charge validation
def validate_charge_properties(charge_model: ChargeModel, properties: dict):
    """Validate properties match the charge model."""
    required = {
        ChargeModel.STANDARD: ["amount"],
        ChargeModel.GRADUATED: ["graduated_ranges"],
        ChargeModel.PACKAGE: ["amount", "package_size"],
        ChargeModel.PERCENTAGE: ["rate"],
        ChargeModel.VOLUME: ["volume_ranges"],
        ChargeModel.GRADUATED_PERCENTAGE: ["graduated_percentage_ranges"],
    }
    
    for field in required.get(charge_model, []):
        if field not in properties:
            raise ValueError(f"Missing required property: {field}")
```

---

## Database Changes

```sql
-- Add charge_model column if not exists
ALTER TABLE charges ADD COLUMN IF NOT EXISTS charge_model VARCHAR(30) DEFAULT 'standard';

-- Properties stored as JSONB (already exists)
-- No schema change needed, just validation
```

---

## Test Plan

### Unit Tests (per charge model)
```python
class TestGraduatedChargeModel:
    def test_single_tier(self):
        """Test with usage in first tier only."""
    
    def test_multiple_tiers(self):
        """Test with usage spanning multiple tiers."""
    
    def test_flat_fees(self):
        """Test flat fee per tier."""
    
    def test_infinity_tier(self):
        """Test open-ended final tier."""

# Similar for each charge model...
```

### Integration Tests
- Create plan with graduated charges
- Subscribe customer
- Send events
- Generate invoice
- Verify fee calculation

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/charge.py` | Update ChargeModel enum |
| `app/schemas/charge.py` | Add ChargeProperties schema |
| `app/services/charge_models/__init__.py` | Create |
| `app/services/charge_models/standard.py` | Create |
| `app/services/charge_models/graduated.py` | Create |
| `app/services/charge_models/package.py` | Create |
| `app/services/charge_models/percentage.py` | Create |
| `app/services/charge_models/volume.py` | Create |
| `app/services/charge_models/graduated_percentage.py` | Create |
| `app/services/charge_models/factory.py` | Create |
| `app/services/invoice_generation.py` | Modify |
| `app/routers/plans.py` | Add validation |
| `tests/test_charge_models.py` | Create (comprehensive) |

---

## Acceptance Criteria

- [ ] All 6 new charge models implemented
- [ ] Property validation per model
- [ ] Invoice generation uses correct calculator
- [ ] 100% test coverage
- [ ] API documentation updated
