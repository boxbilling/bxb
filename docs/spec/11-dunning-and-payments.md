---
type: spec
title: "Dunning and Payments Specification"
created: 2026-02-11
tags:
  - spec
  - dunning
  - payment-request
  - payment-receipt
  - P2
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[04-credit-notes]]"
  - "[[10-multi-tenancy]]"
---

# Dunning and Payments Specification

## Overview

The dunning system automates payment recovery for failed or overdue invoices. Dunning campaigns define retry strategies with configurable attempts, intervals, and escalation thresholds. Payment requests represent collection attempts against customers. Invoice settlements track the relationship between payments/credit-notes and the invoices they settle.

## Lago Reference

Sources: `app/models/dunning_campaign.rb`, `app/models/payment_request.rb` in the Lago codebase. DunningCampaign includes PaperTrailTraceable and Discard::Model. PaymentRequest includes PaperTrailTraceable.

## Entities

### Table: `dunning_campaigns`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique campaign identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `name` | String(255) | NOT NULL | Campaign name |
| `code` | String(255) | NOT NULL | Lookup code |
| `max_attempts` | Integer | NOT NULL, default 3 | Maximum collection attempts |
| `days_between_attempts` | Integer | NOT NULL, default 7 | Days between retry attempts |
| `description` | String(500) | nullable | Description |
| `applied_to_organization` | Boolean | NOT NULL, default false | Organization-wide default |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `dunning_campaign_thresholds`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique threshold identifier |
| `dunning_campaign_id` | UUID | FK -> dunning_campaigns, NOT NULL, indexed | Parent campaign |
| `amount_cents` | Numeric(12,4) | NOT NULL | Minimum overdue amount to trigger |
| `currency` | String(3) | NOT NULL | Currency for the threshold |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

### Table: `payment_requests`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique request identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Target customer |
| `amount_cents` | Numeric(12,4) | NOT NULL, default 0 | Total requested amount |
| `amount_currency` | String(3) | NOT NULL, default "USD" | Currency |
| `payment_status` | String(20) | NOT NULL, default "pending" | pending, succeeded, failed |
| `payment_attempts` | Integer | NOT NULL, default 0 | Number of payment attempts |
| `dunning_campaign_id` | UUID | FK -> dunning_campaigns, nullable | Source campaign |
| `email` | String(255) | nullable | Customer email used |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `payment_request_applied_invoices`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique identifier |
| `payment_request_id` | UUID | FK -> payment_requests, NOT NULL, indexed | Parent request |
| `invoice_id` | UUID | FK -> invoices, NOT NULL, indexed | Applied invoice |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

### Table: `payment_receipts`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique receipt identifier |
| `payment_id` | UUID | FK -> payments, NOT NULL, indexed | Source payment |
| `number` | String(50) | NOT NULL, unique | Sequential receipt number |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

### Table: `invoice_settlements`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique settlement identifier |
| `invoice_id` | UUID | FK -> invoices, NOT NULL, indexed | Settled invoice |
| `payment_id` | UUID | FK -> payments, nullable | Payment that settled the invoice |
| `credit_note_id` | UUID | FK -> credit_notes, nullable | Credit note applied |
| `amount_cents` | Numeric(12,4) | NOT NULL | Amount settled |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

## Dunning Flow

1. **Invoice becomes overdue**: Invoice due_date passes without payment
2. **Campaign evaluation**: Check if customer has an assigned dunning campaign (or org default)
3. **Threshold check**: Total overdue amount >= campaign threshold for the invoice currency
4. **Payment request creation**: Create PaymentRequest linking all overdue invoices for the customer
5. **Collection attempt**: Attempt payment via customer's payment method
6. **On success**: Mark payment request as succeeded, mark invoices as paid, create invoice settlements
7. **On failure**: Increment payment_attempts, schedule next attempt after `days_between_attempts`
8. **Max attempts reached**: Mark payment request as failed, emit `payment_request.failed` webhook

## Enhanced Payment Methods

Additional fields on Customer for payment configuration:

| Column | Type | Description |
|--------|------|-------------|
| `payment_provider` | String(20) | Preferred payment provider |
| `payment_provider_code` | String(255) | External customer ID in payment system |

## API Endpoints

### Dunning Campaigns
- `POST /v1/dunning_campaigns` — Create campaign
- `GET /v1/dunning_campaigns` — List campaigns
- `GET /v1/dunning_campaigns/{id}` — Get campaign
- `PUT /v1/dunning_campaigns/{id}` — Update campaign
- `DELETE /v1/dunning_campaigns/{id}` — Delete campaign

### Payment Requests
- `POST /v1/payment_requests` — Create manual payment request
- `GET /v1/payment_requests` — List requests (filter by customer_id, status)
- `GET /v1/payment_requests/{id}` — Get request details
