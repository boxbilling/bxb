---
type: spec
title: "Credit Notes Specification"
created: 2026-02-11
tags:
  - spec
  - credit-notes
  - refunds
  - P1
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[03-coupons-and-discounts]]"
  - "[[06-tax-system]]"
  - "[[11-dunning-and-payments]]"
---

# Credit Notes Specification

## Overview

Credit notes are formal documents issued to adjust or reverse charges on finalized invoices. They support three modes: credit (store credit for future invoices), refund (return funds to customer), and offset (internal adjustment). Credit notes have their own sequential numbering, status tracking, and can be applied as credits on future invoices.

## Lago Reference

Sources: `app/models/credit_note.rb`, `app/models/credit_note_item.rb` in the Lago codebase. Uses the `Sequenced` concern for sequential numbering with advisory locks.

## Entities

### Table: `credit_notes`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique credit note identifier |
| `number` | String(50) | NOT NULL, unique, indexed | Sequential document number |
| `sequential_id` | Integer | NOT NULL | Sequential counter for numbering |
| `invoice_id` | UUID | FK -> invoices, NOT NULL, indexed | Source invoice being credited |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Customer |
| `credit_note_type` | String(20) | NOT NULL | credit, refund, or offset |
| `status` | String(20) | NOT NULL, default "draft" | draft or finalized |
| `credit_status` | String(20) | nullable | available, consumed, or voided |
| `refund_status` | String(20) | nullable | pending, succeeded, or failed |
| `reason` | String(50) | NOT NULL | duplicated_charge, product_unsatisfactory, order_change, order_cancellation, fraudulent_charge, other |
| `description` | String(500) | nullable | Additional details |
| `currency` | String(3) | NOT NULL | Currency code |
| `credit_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Amount available as store credit |
| `refund_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Amount to be refunded |
| `balance_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Remaining credit balance (decreases as consumed) |
| `total_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Total = credit + refund amounts |
| `taxes_amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Tax portion of the credit note |
| `taxes_rate` | Numeric(8,4) | NOT NULL, default 0 | Effective tax rate |
| `issuing_date` | Date | NOT NULL | Date credit note was issued |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `credit_note_items`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique item identifier |
| `credit_note_id` | UUID | FK -> credit_notes, NOT NULL, indexed | Parent credit note |
| `fee_id` | UUID | FK -> fees, NOT NULL, indexed | Original fee being credited |
| `amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Credit amount for this item |
| `precise_amount_cents` | Numeric(16,8) | NOT NULL, default 0 | High-precision amount |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

## Reason Enum

```python
class CreditNoteReason(str, Enum):
    DUPLICATED_CHARGE = "duplicated_charge"
    PRODUCT_UNSATISFACTORY = "product_unsatisfactory"
    ORDER_CHANGE = "order_change"
    ORDER_CANCELLATION = "order_cancellation"
    FRAUDULENT_CHARGE = "fraudulent_charge"
    OTHER = "other"
```

## Status Transitions

### Credit Note Status
```
draft -> finalized  (issued to customer)
```

### Credit Status
```
available -> consumed  (fully applied to invoices)
available -> voided    (manually voided)
```

### Refund Status
```
pending -> succeeded  (refund processed)
pending -> failed     (refund failed)
```

## Refund Flow

1. Create credit note with `credit_note_type=refund` against a finalized/paid invoice
2. Calculate refund amounts per fee (proportional to original fee amounts)
3. Set `refund_status=pending`
4. Initiate refund via payment provider
5. On success: `refund_status=succeeded`, update associated fee `payment_status=refunded`
6. On failure: `refund_status=failed`

## Void Flow

1. Credit note must have `credit_status=available`
2. Set `credit_status=voided`
3. Set `balance_amount_cents=0`
4. Credit is no longer available for future invoice application

## Invoice Settlement

When a credit note with `credit_status=available` exists:
1. During invoice generation, check for available credit notes for the customer
2. Apply credit (up to `balance_amount_cents`) to reduce invoice total
3. Create a Credit record linking the credit note to the invoice
4. Reduce `balance_amount_cents` by the applied amount
5. If `balance_amount_cents` reaches 0, set `credit_status=consumed`

## Sequential Numbering

Credit notes use sequential numbering similar to invoices:
- Format: `CN-YYYYMMDD-XXXX` (configurable per organization)
- Uses advisory locks to prevent race conditions in concurrent generation
- Sequential ID increments per organization/billing entity

## API Endpoints

- `POST /v1/credit_notes` — Create credit note for an invoice
- `GET /v1/credit_notes` — List credit notes (filter by customer_id, invoice_id, status)
- `GET /v1/credit_notes/{id}` — Get credit note by ID
- `PUT /v1/credit_notes/{id}` — Update credit note (draft only)
- `POST /v1/credit_notes/{id}/void` — Void a credit note
- `GET /v1/credit_notes/{id}/items` — List credit note items
