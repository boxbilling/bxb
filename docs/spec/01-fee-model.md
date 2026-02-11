---
type: spec
title: "Fee Model Specification"
created: 2026-02-11
tags:
  - spec
  - fee-model
  - P0
related:
  - "[[00-overview]]"
  - "[[06-tax-system]]"
  - "[[04-credit-notes]]"
  - "[[12-commitments-and-thresholds]]"
---

# Fee Model Specification

## Overview

The Fee model represents a first-class billing line item entity. Currently, bxb stores invoice line items as a JSON blob inside the Invoice model's `line_items` column. Lago treats fees as first-class entities with their own table, relationships, payment status, and tax tracking. The Fee model is the foundational data structure that nearly every subsequent feature depends on: wallets, coupons, credit notes, commitments, and progressive billing all operate on fees.

## Lago Reference

Source: `app/models/fee.rb` in the Lago codebase.

Lago's Fee model includes soft-delete (Discard), currency handling, and relationships to invoices, charges, subscriptions, add-ons, and organizations. It tracks both gross and precise amounts, applied taxes, and payment status.

## Entity Definition

### Table: `fees`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique fee identifier |
| `invoice_id` | UUID | FK -> invoices, nullable, indexed | Parent invoice (nullable for pay-in-advance fees) |
| `charge_id` | UUID | FK -> charges, nullable, indexed | Source charge definition |
| `subscription_id` | UUID | FK -> subscriptions, nullable, indexed | Source subscription |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Owning customer |
| `fee_type` | String(20) | NOT NULL, indexed | One of: charge, subscription, add_on, credit, commitment |
| `amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Pre-tax amount |
| `taxes_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Tax amount |
| `total_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Total (amount + taxes) |
| `units` | Numeric(12,4) | NOT NULL, default 0 | Quantity of units consumed |
| `events_count` | Integer | NOT NULL, default 0 | Number of events aggregated |
| `unit_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Price per unit |
| `payment_status` | String(20) | NOT NULL, default "pending" | One of: pending, succeeded, failed, refunded |
| `description` | String(500) | nullable | Human-readable description |
| `metric_code` | String(255) | nullable | Billable metric code for usage fees |
| `properties` | JSON | NOT NULL, default {} | Charge model properties snapshot |
| `created_at` | DateTime | NOT NULL, server_default now | Creation timestamp |
| `updated_at` | DateTime | NOT NULL, server_default now, onupdate now | Last update timestamp |

### Enums

```python
class FeeType(str, Enum):
    CHARGE = "charge"
    SUBSCRIPTION = "subscription"
    ADD_ON = "add_on"
    CREDIT = "credit"
    COMMITMENT = "commitment"

class FeePaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
```

### Indexes

| Index | Columns | Type |
|-------|---------|------|
| `ix_fees_invoice_id` | invoice_id | btree |
| `ix_fees_customer_id` | customer_id | btree |
| `ix_fees_subscription_id` | subscription_id | btree |
| `ix_fees_charge_id` | charge_id | btree |
| `ix_fees_fee_type` | fee_type | btree |

### Relationships

- **Invoice**: `Fee.invoice_id -> Invoice.id` (many-to-one). An invoice has many fees. A fee optionally belongs to one invoice (nullable for pay-in-advance).
- **Charge**: `Fee.charge_id -> Charge.id` (many-to-one). A fee optionally references the charge definition used for calculation.
- **Subscription**: `Fee.subscription_id -> Subscription.id` (many-to-one). A fee optionally references the subscription it was generated for.
- **Customer**: `Fee.customer_id -> Customer.id` (many-to-one, required). Every fee belongs to a customer.

Future relationships (to be added with their respective features):
- **AppliedTax**: One fee has many applied taxes (see [[06-tax-system]])
- **CreditNoteItem**: One fee has many credit note items (see [[04-credit-notes]])

## Pydantic Schemas

### FeeCreate

```python
class FeeCreate(BaseModel):
    invoice_id: UUID | None = None
    charge_id: UUID | None = None
    subscription_id: UUID | None = None
    customer_id: UUID
    fee_type: FeeType
    amount_cents: Decimal = Decimal(0)
    taxes_amount_cents: Decimal = Decimal(0)
    total_amount_cents: Decimal = Decimal(0)
    units: Decimal = Decimal(0)
    events_count: int = 0
    unit_amount_cents: Decimal = Decimal(0)
    payment_status: FeePaymentStatus = FeePaymentStatus.PENDING
    description: str | None = None
    metric_code: str | None = None
    properties: dict = {}
```

### FeeUpdate

```python
class FeeUpdate(BaseModel):
    payment_status: FeePaymentStatus | None = None
    description: str | None = None
```

### FeeResponse

```python
class FeeResponse(BaseModel):
    id: UUID
    invoice_id: UUID | None
    charge_id: UUID | None
    subscription_id: UUID | None
    customer_id: UUID
    fee_type: str
    amount_cents: Decimal
    taxes_amount_cents: Decimal
    total_amount_cents: Decimal
    units: Decimal
    events_count: int
    unit_amount_cents: Decimal
    payment_status: str
    description: str | None
    metric_code: str | None
    properties: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
```

## Repository: FeeRepository

### Methods

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(data: FeeCreate) -> Fee` | Create a single fee |
| `create_bulk` | `(fees: list[FeeCreate]) -> list[Fee]` | Create multiple fees in one transaction |
| `get_by_id` | `(fee_id: UUID) -> Fee \| None` | Get fee by primary key |
| `get_by_invoice_id` | `(invoice_id: UUID) -> list[Fee]` | Get all fees for an invoice |
| `get_by_customer_id` | `(customer_id: UUID, skip, limit) -> list[Fee]` | Get all fees for a customer |
| `get_by_subscription_id` | `(subscription_id: UUID) -> list[Fee]` | Get all fees for a subscription |
| `update` | `(fee_id: UUID, data: FeeUpdate) -> Fee \| None` | Update a fee |
| `delete` | `(fee_id: UUID) -> bool` | Delete a fee |
| `mark_succeeded` | `(fee_id: UUID) -> Fee \| None` | Set payment_status to succeeded |
| `mark_failed` | `(fee_id: UUID) -> Fee \| None` | Set payment_status to failed |

## API Endpoints

### `GET /v1/fees`

List fees with optional filters.

**Query Parameters:**
- `invoice_id` (UUID, optional) — Filter by invoice
- `customer_id` (UUID, optional) — Filter by customer
- `subscription_id` (UUID, optional) — Filter by subscription
- `fee_type` (string, optional) — Filter by fee type
- `payment_status` (string, optional) — Filter by payment status
- `skip` (int, default 0) — Pagination offset
- `limit` (int, default 100) — Page size

**Response:** `list[FeeResponse]`

### `GET /v1/fees/{id}`

Get a single fee by ID.

**Response:** `FeeResponse` or 404

### `PUT /v1/fees/{id}`

Update a fee (primarily for payment status changes).

**Request Body:** `FeeUpdate`
**Response:** `FeeResponse` or 404

## Invoice Generation Integration

When generating an invoice, the `InvoiceGenerationService` should:

1. For each charge, create a `Fee` record with:
   - `fee_type = "charge"`
   - `invoice_id` = the generated invoice ID
   - `charge_id` = the charge definition ID
   - `subscription_id` = the subscription ID
   - `customer_id` = the customer ID
   - `amount_cents` = calculated charge amount
   - `units` = aggregated usage quantity
   - `unit_amount_cents` = effective per-unit price
   - `events_count` = number of events in the period
   - `description` = human-readable line description
   - `metric_code` = billable metric code

2. For the subscription base fee, create a `Fee` with:
   - `fee_type = "subscription"`
   - Amount from the plan's `amount_cents`

3. Compute invoice `subtotal` and `total` from the sum of all fee `total_amount_cents`.

4. Populate the legacy `line_items` JSON from the fee records for backward compatibility.

## Payment Status Transitions

```
pending -> succeeded  (payment confirmed)
pending -> failed     (payment failed)
succeeded -> refunded (refund processed)
```

## Future Extensions

- `invoiceable_type` / `invoiceable_id` polymorphic fields for linking to add-ons, commitments, etc.
- `precise_amount_cents` for higher-precision intermediate calculations
- `pay_in_advance` flag for prepaid charge fees
- Soft delete via `deleted_at` column
- Applied taxes relationship (see [[06-tax-system]])
