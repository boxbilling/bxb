---
type: spec
title: "Commitments and Usage Thresholds Specification"
created: 2026-02-11
tags:
  - spec
  - commitments
  - usage-thresholds
  - progressive-billing
  - P2
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[04-credit-notes]]"
  - "[[08-subscription-lifecycle]]"
---

# Commitments and Usage Thresholds Specification

## Overview

Commitments represent minimum spend requirements on plans. If a customer's actual usage is below the committed amount, they are charged the commitment minimum. Usage thresholds enable progressive billing: when cumulative usage crosses a threshold during a billing period, an interim invoice is generated immediately rather than waiting for period end.

## Lago Reference

Sources: `app/models/commitment.rb`, `app/models/usage_threshold.rb` in the Lago codebase. Commitment has applied taxes. UsageThreshold includes PaperTrailTraceable, Currencies, and Discard::Model. Thresholds can be at plan or subscription level.

## Entities

### Table: `commitments`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique commitment identifier |
| `plan_id` | UUID | FK -> plans, NOT NULL, indexed | Associated plan |
| `commitment_type` | String(30) | NOT NULL | minimum_commitment |
| `amount_cents` | Numeric(12,4) | NOT NULL | Minimum spend amount |
| `invoice_display_name` | String(255) | nullable | Custom name on invoices |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `usage_thresholds`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique threshold identifier |
| `plan_id` | UUID | FK -> plans, nullable, indexed | Plan-level threshold |
| `subscription_id` | UUID | FK -> subscriptions, nullable, indexed | Subscription-level threshold |
| `amount_cents` | Numeric(12,4) | NOT NULL | Threshold amount |
| `currency` | String(3) | NOT NULL, default "USD" | Currency |
| `recurring` | Boolean | NOT NULL, default false | Resets each billing period |
| `threshold_display_name` | String(255) | nullable | Custom display name |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

**Validation:** Exactly one of `plan_id` or `subscription_id` must be set.

### Table: `applied_usage_thresholds`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `usage_threshold_id` | UUID | FK -> usage_thresholds, NOT NULL, indexed | Threshold that was crossed |
| `invoice_id` | UUID | FK -> invoices, NOT NULL, indexed | Generated invoice |
| `lifetime_usage_amount_cents` | Numeric(12,4) | NOT NULL | Cumulative usage at crossing |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

## Commitment (Minimum Spend) Flow

At the end of a billing period:

1. Calculate total usage fees for the subscription
2. If total usage fees < commitment `amount_cents`:
   - Create a Fee with `fee_type = "commitment"`
   - `amount_cents` = `commitment.amount_cents - total_usage_fees`
   - This "true-up" fee brings the total to the minimum commitment
3. Apply commitment taxes (see [[06-tax-system]])
4. Add to the invoice

## Progressive Billing (Usage Thresholds) Flow

During a billing period, usage is tracked in real-time:

1. **Event ingestion**: New events are ingested and usage is aggregated
2. **Threshold evaluation**: After aggregation, check if cumulative usage crosses any uncrossed threshold
3. **Threshold crossed**:
   a. Generate a credit note for any previous progressive billing invoice in this period (see [[04-credit-notes]])
   b. Generate a new invoice with all usage up to the current point
   c. Create `AppliedUsageThreshold` record
   d. Emit `invoice.created` webhook
4. **Recurring thresholds**: If `recurring = true`, the threshold resets after each crossing (e.g., every $1000 of usage triggers an invoice)
5. **Period end**: Final invoice accounts for all remaining usage, minus previously billed amounts

### Example

Plan with thresholds at $500 and $1000:
- Usage reaches $500 → Invoice #1 for $500
- Usage reaches $1000 → Credit note for Invoice #1, Invoice #2 for $1000
- Period ends at $1200 → Credit note for Invoice #2, Final Invoice for $1200

## API Endpoints

### Commitments
Managed as nested resources on plans:
- `POST /v1/plans` with `commitments` array
- `PUT /v1/plans/{id}` to update commitments

### Usage Thresholds
Managed as nested resources:
- On plans: `POST /v1/plans` with `usage_thresholds` array
- On subscriptions: `PUT /v1/subscriptions/{id}` with `usage_thresholds` array

### Applied Usage Thresholds
- `GET /v1/subscriptions/{id}/applied_usage_thresholds` — List threshold crossings
