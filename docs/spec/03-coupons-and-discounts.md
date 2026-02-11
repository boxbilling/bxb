---
type: spec
title: "Coupons and Discounts Specification"
created: 2026-02-11
tags:
  - spec
  - coupons
  - discounts
  - credits
  - P1
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[02-wallets-and-credits]]"
  - "[[04-credit-notes]]"
  - "[[06-tax-system]]"
---

# Coupons and Discounts Specification

## Overview

The coupon system enables organizations to create discount codes that can be applied to customer subscriptions. Coupons can be fixed-amount or percentage-based, applied once, recurring, or forever. They can be scoped to specific plans or billable metrics. When applied to a customer, a Credit record is created on the invoice representing the discount.

## Lago Reference

Sources: `app/models/coupon.rb`, `app/models/applied_coupon.rb`, `app/models/coupon_target.rb`, `app/models/credit.rb` in the Lago codebase.

## Entities

### Table: `coupons`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique coupon identifier |
| `code` | String(255) | NOT NULL, unique, indexed | Lookup code |
| `name` | String(255) | NOT NULL | Display name |
| `description` | String(500) | nullable | Description |
| `coupon_type` | String(20) | NOT NULL | fixed_amount or percentage |
| `amount_cents` | Numeric(12,4) | nullable | Discount amount (for fixed_amount) |
| `currency` | String(3) | nullable | Currency (for fixed_amount) |
| `percentage_rate` | Numeric(8,4) | nullable | Discount percentage (for percentage) |
| `frequency` | String(20) | NOT NULL | once, recurring, or forever |
| `frequency_duration` | Integer | nullable | Number of billing periods (for recurring) |
| `expiration` | String(20) | NOT NULL, default "no_expiration" | no_expiration or time_limit |
| `expiration_at` | DateTime | nullable | Expiration date (for time_limit) |
| `reusable` | Boolean | NOT NULL, default true | Whether multiple customers can use it |
| `limited_plans` | Boolean | NOT NULL, default false | Whether scoped to specific plans |
| `limited_billable_metrics` | Boolean | NOT NULL, default false | Whether scoped to specific metrics |
| `status` | String(20) | NOT NULL, default "active" | active or terminated |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `applied_coupons`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique applied coupon identifier |
| `coupon_id` | UUID | FK -> coupons, NOT NULL, indexed | Source coupon |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Applied-to customer |
| `status` | String(20) | NOT NULL, default "active" | active or terminated |
| `amount_cents` | Numeric(12,4) | nullable | Override amount (snapshot at apply time) |
| `currency` | String(3) | nullable | Currency |
| `percentage_rate` | Numeric(8,4) | nullable | Override percentage |
| `frequency` | String(20) | NOT NULL | Frequency at time of application |
| `frequency_duration` | Integer | nullable | Duration at time of application |
| `frequency_duration_remaining` | Integer | nullable | Remaining billing periods |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `coupon_targets`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique target identifier |
| `coupon_id` | UUID | FK -> coupons, NOT NULL, indexed | Parent coupon |
| `target_type` | String(50) | NOT NULL | "Plan" or "BillableMetric" |
| `target_id` | UUID | NOT NULL | Referenced plan or metric ID |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

### Table: `credits`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique credit identifier |
| `invoice_id` | UUID | FK -> invoices, NOT NULL, indexed | Invoice where credit is applied |
| `applied_coupon_id` | UUID | FK -> applied_coupons, nullable, indexed | Source applied coupon |
| `credit_note_id` | UUID | FK -> credit_notes, nullable, indexed | Source credit note |
| `amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Credit amount |
| `amount_currency` | String(3) | NOT NULL, default "USD" | Currency |
| `before_taxes` | Boolean | NOT NULL, default false | Whether discount applies before tax calculation |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

## Application Rules

### Invoice Calculation Order

When generating an invoice with coupons:

1. Calculate all fee amounts (charge fees, subscription fees)
2. Apply **before-tax coupons** (reduce subtotal before tax calculation)
3. Calculate taxes on the reduced subtotal
4. Apply **after-tax coupons** (reduce total after tax)
5. Apply wallet credits (see [[02-wallets-and-credits]])
6. Final total = subtotal + taxes - before_tax_credits - after_tax_credits - wallet_credits

### Coupon Eligibility

A coupon applies to an invoice if:
- The AppliedCoupon is `active`
- The coupon has not expired
- If `frequency=recurring`: `frequency_duration_remaining > 0`
- If `limited_plans=true`: the subscription's plan matches a CouponTarget
- If `limited_billable_metrics=true`: at least one charge's metric matches a CouponTarget

### Frequency Handling

- **once**: Applied to the first invoice only, then AppliedCoupon is terminated
- **recurring**: Applied for `frequency_duration` billing periods, decrementing `frequency_duration_remaining` each period
- **forever**: Applied to every invoice until manually terminated

### Fixed Amount vs Percentage

- **fixed_amount**: Deducts `amount_cents` from invoice (capped at invoice total — never negative)
- **percentage**: Deducts `percentage_rate`% of applicable fee amounts

## API Endpoints

### Coupons
- `POST /v1/coupons` — Create coupon
- `GET /v1/coupons` — List coupons (filter by status)
- `GET /v1/coupons/{id}` — Get coupon by ID
- `PUT /v1/coupons/{id}` — Update coupon
- `DELETE /v1/coupons/{id}` — Terminate coupon

### Applied Coupons
- `POST /v1/applied_coupons` — Apply coupon to customer
- `GET /v1/applied_coupons` — List applied coupons (filter by customer_id, status)
- `DELETE /v1/applied_coupons/{id}` — Remove applied coupon
