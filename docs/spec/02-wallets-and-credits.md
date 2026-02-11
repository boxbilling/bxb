---
type: spec
title: "Wallets and Credits Specification"
created: 2026-02-11
tags:
  - spec
  - wallets
  - credits
  - P1
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[03-coupons-and-discounts]]"
  - "[[11-dunning-and-payments]]"
---

# Wallets and Credits Specification

## Overview

The wallet system provides prepaid credit management for customers. Customers can hold credit balances that are consumed during invoice generation, reducing the amount owed. Lago's wallet system supports manual and automated top-ups, priority-based consumption across multiple wallets, expiration policies, and recurring transaction rules.

## Lago Reference

Sources: `app/models/wallet.rb`, `app/models/wallet_transaction.rb`, `app/models/recurring_transaction_rule.rb` in the Lago codebase.

## Entities

### Table: `wallets`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique wallet identifier |
| `customer_id` | UUID | FK -> customers, NOT NULL, indexed | Owning customer |
| `name` | String(255) | nullable | Display name |
| `code` | String(255) | nullable | Lookup code |
| `balance_cents` | Numeric(12,4) | NOT NULL, default 0 | Current monetary balance |
| `credits_balance` | Numeric(12,4) | NOT NULL, default 0 | Current credit units balance |
| `consumed_credits` | Numeric(12,4) | NOT NULL, default 0 | Total credits consumed |
| `rate_amount` | Numeric(12,4) | NOT NULL, default 1 | Exchange rate: 1 credit = rate_amount currency |
| `currency` | String(3) | NOT NULL, default "USD" | Wallet currency |
| `status` | String(20) | NOT NULL, default "active" | active or terminated |
| `expiration_at` | DateTime | nullable | When wallet expires |
| `priority` | Integer | NOT NULL, default 0 | Consumption priority (lower = consumed first) |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `wallet_transactions`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique transaction identifier |
| `wallet_id` | UUID | FK -> wallets, NOT NULL, indexed | Parent wallet |
| `transaction_type` | String(20) | NOT NULL | inbound or outbound |
| `transaction_status` | String(20) | NOT NULL, default "purchased" | purchased, granted, voided, invoiced |
| `status` | String(20) | NOT NULL, default "settled" | pending, settled, failed |
| `source` | String(20) | NOT NULL, default "manual" | manual, interval, threshold |
| `amount` | Numeric(12,4) | NOT NULL, default 0 | Monetary amount |
| `credit_amount` | Numeric(12,4) | NOT NULL, default 0 | Credit units amount |
| `invoice_id` | UUID | FK -> invoices, nullable | Invoice for purchased credits |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `recurring_transaction_rules`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique rule identifier |
| `wallet_id` | UUID | FK -> wallets, NOT NULL, indexed | Parent wallet |
| `interval` | String(20) | nullable | weekly, monthly, quarterly, yearly |
| `method` | String(20) | NOT NULL, default "fixed" | fixed or target |
| `trigger` | String(20) | NOT NULL, default "interval" | interval or threshold |
| `paid_credits` | Numeric(12,4) | NOT NULL, default 0 | Credits to purchase |
| `granted_credits` | Numeric(12,4) | NOT NULL, default 0 | Free credits to grant |
| `threshold_credits` | Numeric(12,4) | NOT NULL, default 0 | Threshold for trigger |
| `target_ongoing_balance` | Numeric(12,4) | nullable | Target balance for "target" method |
| `status` | String(20) | NOT NULL, default "active" | active or terminated |
| `started_at` | DateTime | nullable | When rule begins |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `wallet_targets`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique target identifier |
| `wallet_id` | UUID | FK -> wallets, NOT NULL, indexed | Parent wallet |
| `target_type` | String(20) | NOT NULL | Type of target entity |
| `target_id` | UUID | NOT NULL | Referenced entity ID |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

## Consumption Priority Algorithm

When consuming wallet credits during invoice generation:

1. Retrieve all **active, non-expired** wallets for the customer, ordered by `priority ASC` (lowest first)
2. For each wallet (in priority order):
   a. Calculate available balance: `min(balance_cents, remaining_invoice_amount)`
   b. Deduct from wallet balance
   c. Create an **outbound** WalletTransaction
   d. Reduce remaining invoice amount
   e. If remaining amount is zero, stop
3. Create a Credit record on the invoice for the total wallet consumption

## Top-Up Triggers

### Manual Top-Up
- API call to add credits to a wallet
- Creates an inbound WalletTransaction with `source=manual`
- Optionally generates a purchase invoice for paid credits

### Interval Top-Up (RecurringTransactionRule)
- Scheduled at configured interval (weekly/monthly/quarterly/yearly)
- Adds `paid_credits` + `granted_credits` to wallet
- Creates inbound WalletTransactions for each

### Threshold Top-Up (RecurringTransactionRule)
- Triggered when wallet balance drops below `threshold_credits`
- **Fixed method**: adds fixed amount of credits
- **Target method**: tops up to `target_ongoing_balance`

## API Endpoints

### Wallets
- `POST /v1/wallets` — Create wallet for a customer
- `GET /v1/wallets` — List wallets (filter by customer_id, status)
- `GET /v1/wallets/{id}` — Get wallet by ID
- `PUT /v1/wallets/{id}` — Update wallet (name, expiration, priority)
- `DELETE /v1/wallets/{id}` — Terminate wallet

### Wallet Transactions
- `POST /v1/wallets/{wallet_id}/transactions` — Create top-up transaction
- `GET /v1/wallets/{wallet_id}/transactions` — List transactions (filter by type, status)

### Recurring Transaction Rules
- Managed as nested resources on the wallet (created/updated via wallet endpoints)
