---
type: spec
title: "Tax System Specification"
created: 2026-02-11
tags:
  - spec
  - tax
  - applied-tax
  - P0
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[03-coupons-and-discounts]]"
  - "[[04-credit-notes]]"
  - "[[05-add-ons]]"
  - "[[10-multi-tenancy]]"
  - "[[13-integrations]]"
---

# Tax System Specification

## Overview

The tax system manages tax rates and their application across multiple entity types. Taxes can be configured at the organization level (as defaults), then overridden at the customer, plan, charge, add-on, fee, invoice, or commitment level. The system uses a polymorphic `applied_taxes` table that can attach to any taxable entity.

External tax providers (Anrok, Avalara) are deferred to the integrations phase — see [[13-integrations]].

## Lago Reference

Source: `app/models/tax.rb` in the Lago codebase. Tax includes Discard::Model (soft delete). AppliedTax uses polymorphic associations.

## Entities

### Table: `taxes`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique tax identifier |
| `code` | String(255) | NOT NULL, unique, indexed | Lookup code |
| `name` | String(255) | NOT NULL | Display name (e.g., "VAT", "Sales Tax") |
| `rate` | Numeric(8,4) | NOT NULL | Tax rate as percentage (e.g., 20.0000 for 20%) |
| `description` | String(500) | nullable | Description |
| `applied_to_organization` | Boolean | NOT NULL, default false | Whether this is an org-level default tax |
| `auto_generated` | Boolean | NOT NULL, default false | System-generated (e.g., from external provider) |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `applied_taxes`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique applied tax identifier |
| `tax_id` | UUID | FK -> taxes, NOT NULL, indexed | Tax being applied |
| `taxable_type` | String(50) | NOT NULL, indexed | Polymorphic type: Customer, Invoice, Fee, CreditNote, Plan, Charge, AddOn, Commitment |
| `taxable_id` | UUID | NOT NULL, indexed | Polymorphic ID of the taxable entity |
| `tax_rate` | Numeric(8,4) | NOT NULL | Snapshot of rate at time of application |
| `tax_name` | String(255) | NOT NULL | Snapshot of name at time of application |
| `tax_code` | String(255) | NOT NULL | Snapshot of code at time of application |
| `amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Calculated tax amount (for fees/invoices) |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

**Unique Constraint:** `(tax_id, taxable_type, taxable_id)` — a tax can only be applied once per entity.

**Composite Index:** `(taxable_type, taxable_id)` — efficient lookup of all taxes for an entity.

## Tax Calculation Pipeline

### 1. Determine Applicable Taxes

For a given fee, resolve which taxes apply using this priority chain:

1. **Customer-level taxes**: If the customer has applied taxes, use those
2. **Charge-level taxes**: If the charge has applied taxes, use those (for charge fees)
3. **Plan-level taxes**: If the plan has applied taxes, use those (for subscription fees)
4. **Add-on-level taxes**: If the add-on has applied taxes, use those (for add-on fees)
5. **Organization-level defaults**: Fall back to taxes where `applied_to_organization=true`

### 2. Calculate Tax Amounts

For each fee:
1. Collect all applicable taxes (may be multiple, e.g., federal + state)
2. For each tax: `tax_amount = fee.amount_cents * (tax.rate / 100)`
3. `fee.taxes_amount_cents = sum of all tax amounts`
4. `fee.total_amount_cents = fee.amount_cents + fee.taxes_amount_cents`
5. Create AppliedTax records on the fee with calculated amounts

### 3. Aggregate to Invoice

1. `invoice.subtotal = sum of fee.amount_cents`
2. `invoice.tax_amount = sum of fee.taxes_amount_cents`
3. `invoice.total = invoice.subtotal + invoice.tax_amount`
4. Create AppliedTax records on the invoice (aggregated by tax code)

## Organization-Level Default Taxes

Taxes with `applied_to_organization=true` serve as defaults for all customers and fees unless overridden. Multiple organization-level taxes can coexist (e.g., VAT 20% + Environmental Tax 2%).

## API Endpoints

### Taxes
- `POST /v1/taxes` — Create tax
- `GET /v1/taxes` — List taxes
- `GET /v1/taxes/{id}` — Get tax by ID
- `PUT /v1/taxes/{id}` — Update tax
- `DELETE /v1/taxes/{id}` — Delete tax (soft delete)

### Applied Taxes
Applied taxes are managed through their parent entities:
- `PUT /v1/customers/{id}` with `tax_codes: ["vat", "state_tax"]`
- `PUT /v1/plans/{id}` with `tax_codes: ["vat"]`
- `PUT /v1/add_ons/{id}` with `tax_codes: ["vat"]`

## Future Extensions

- External tax provider integration (Anrok, Avalara) — see [[13-integrations]]
- EU VAT validation and reverse-charge logic
- Tax exemption per customer
- Tax-inclusive pricing (amount_cents includes tax)
