# Phase 14: Multi-Currency Support

> **Priority:** LOW | **Complexity:** Medium | **Est. Time:** 1 week

## Overview

Support billing in multiple currencies with proper conversion and display.

## Lago Reference

**Source:** `lago-api/app/models/concerns/currencies.rb`

Lago supports 150+ currencies and handles:
- Plan pricing in different currencies
- Invoice currency based on customer
- Wallet currencies
- Exchange rate display (not conversion)

---

## Implementation Plan

### Key Changes

#### 1. Currency on Customer
```python
# app/models/customer.py (add)
currency = Column(String(3), default="USD")
```

#### 2. Currency on Plans
```python
# Plans already have amount_currency
# Ensure charges inherit plan currency
```

#### 3. Invoice Currency
```python
# Invoice uses customer's currency
# If plan currency differs, show original + converted
```

### Currency Validation

```python
# app/core/currencies.py
SUPPORTED_CURRENCIES = [
    "USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY",
    "INR", "MXN", "BRL", "KRW", "SGD", "HKD", "NOK", "SEK",
    "DKK", "NZD", "ZAR", "RUB", "PLN", "THB", "MYR", "IDR",
    # ... more
]

def validate_currency(currency: str) -> bool:
    return currency.upper() in SUPPORTED_CURRENCIES
```

### Display Formatting

```python
# app/core/currencies.py
CURRENCY_FORMATS = {
    "USD": {"symbol": "$", "decimal_places": 2, "symbol_first": True},
    "EUR": {"symbol": "€", "decimal_places": 2, "symbol_first": False},
    "JPY": {"symbol": "¥", "decimal_places": 0, "symbol_first": True},
    "GBP": {"symbol": "£", "decimal_places": 2, "symbol_first": True},
    # ...
}

def format_amount(cents: int, currency: str) -> str:
    fmt = CURRENCY_FORMATS.get(currency, {"symbol": currency, "decimal_places": 2})
    amount = cents / (10 ** fmt["decimal_places"])
    
    if fmt.get("symbol_first"):
        return f"{fmt['symbol']}{amount:,.{fmt['decimal_places']}f}"
    return f"{amount:,.{fmt['decimal_places']}f} {fmt['symbol']}"
```

---

## Files to Modify

| File | Action |
|------|--------|
| `app/core/currencies.py` | Create |
| `app/models/customer.py` | Add currency field |
| `app/schemas/customer.py` | Add currency |
| `app/schemas/invoice.py` | Add formatted amounts |
| `tests/test_currencies.py` | Create |

---

## Acceptance Criteria

- [ ] Currency field on customers
- [ ] Currency validation (ISO 4217)
- [ ] Proper decimal handling per currency
- [ ] Display formatting (symbol, position)
- [ ] 100% test coverage
