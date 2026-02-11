---
type: spec
title: "Add-Ons Specification"
created: 2026-02-11
tags:
  - spec
  - add-ons
  - one-off-charges
  - P1
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[06-tax-system]]"
---

# Add-Ons Specification

## Overview

Add-ons represent one-time charges that can be applied to customers outside of the regular subscription billing cycle. When an add-on is applied to a customer, it generates a one-off invoice with a single fee. Add-ons support tax configuration and integration mappings (for external accounting systems).

## Lago Reference

Sources: `app/models/add_on.rb`, `app/models/applied_add_on.rb` in the Lago codebase. AddOn includes PaperTrailTraceable, Currencies, IntegrationMappable, and Discard::Model (soft delete).

## Entities

### Table: `add_ons`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique add-on identifier |
| `code` | String(255) | NOT NULL, unique, indexed | Lookup code |
| `name` | String(255) | NOT NULL | Display name |
| `description` | String(500) | nullable | Description |
| `amount_cents` | Numeric(12,4) | NOT NULL | Default charge amount |
| `amount_currency` | String(3) | NOT NULL, default "USD" | Currency |
| `invoice_display_name` | String(255) | nullable | Custom name shown on invoices |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `applied_add_ons`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique applied add-on identifier |
| `add_on_id` | UUID | FK -> add_ons, NOT NULL, indexed | Source add-on |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Target customer |
| `amount_cents` | Numeric(12,4) | NOT NULL | Actual charge amount (can override add-on default) |
| `amount_currency` | String(3) | NOT NULL | Currency |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

## One-Off Invoice Generation

When an add-on is applied to a customer:

1. Create an `AppliedAddOn` record with the amount (using add-on default or custom override)
2. Generate a one-off invoice:
   - `status = "finalized"` (immediately finalized, no draft stage)
   - `billing_period_start` = `billing_period_end` = now
3. Create a Fee record:
   - `fee_type = "add_on"`
   - `amount_cents` = applied add-on amount
   - `invoice_id` = generated invoice ID
   - `customer_id` = target customer
   - `description` = add-on `invoice_display_name` or `name`
4. Apply applicable taxes (see [[06-tax-system]])
5. Compute invoice totals from fees

## API Endpoints

### Add-Ons
- `POST /v1/add_ons` — Create add-on
- `GET /v1/add_ons` — List add-ons
- `GET /v1/add_ons/{id}` — Get add-on by ID
- `PUT /v1/add_ons/{id}` — Update add-on
- `DELETE /v1/add_ons/{id}` — Delete add-on

### Applied Add-Ons
- `POST /v1/applied_add_ons` — Apply add-on to customer (triggers one-off invoice)

**Apply Add-On Request:**
```json
{
  "add_on_id": "uuid",
  "customer_id": "uuid",
  "amount_cents": 5000,       // optional override
  "amount_currency": "USD"    // optional override
}
```
