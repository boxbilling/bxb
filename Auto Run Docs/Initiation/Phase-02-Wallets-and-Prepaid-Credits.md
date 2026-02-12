# Phase 02: Wallets & Prepaid Credits System

This phase implements the wallet and prepaid credits system, one of Lago's most powerful features with zero presence in bxb today. Wallets allow customers to pre-purchase credits that are consumed against invoices, enabling prepaid billing models. The system supports multiple wallets per customer with priority-based consumption, automatic top-ups via recurring rules or threshold triggers, wallet expiration, and scoping wallets to specific billable metrics. This is a high-value feature for SaaS platforms offering credit-based pricing.

## Tasks

- [x] Create the Wallet model, migration, repository, and schema:
  - `backend/app/models/wallet.py` — Wallet SQLAlchemy model:
    - `id` (UUIDType PK), `customer_id` (FK to customers, not null)
    - `name` (String(255)), `code` (String(255), unique per customer — composite unique index on [customer_id, code])
    - `status` (String: "active", "terminated", default "active")
    - `balance_cents` (Numeric(12,4) default 0) — current balance in currency
    - `credits_balance` (Numeric(12,4) default 0) — current balance in credit units
    - `consumed_amount_cents` (Numeric(12,4) default 0) — total consumed
    - `consumed_credits` (Numeric(12,4) default 0) — total credits consumed
    - `rate_amount` (Numeric(12,4) default 1) — conversion rate: 1 credit = X currency cents
    - `currency` (String(3) default "USD")
    - `expiration_at` (DateTime nullable) — when wallet expires
    - `priority` (Integer default 1, range 1-50) — consumption order (lower = first)
    - `created_at`, `updated_at` timestamps
    - Indexes: `(customer_id)`, `(customer_id, code)` unique, `(status)`
  - `backend/app/schemas/wallet.py` — Pydantic schemas: `WalletCreate` (customer_id, name, code, rate_amount, currency, expiration_at, priority, initial_granted_credits optional), `WalletUpdate`, `WalletResponse`, `WalletStatus` enum
  - `backend/app/repositories/wallet_repository.py` — WalletRepository: `create()`, `get_by_id()`, `get_by_customer_id()`, `get_active_by_customer_id()` (ordered by priority ASC, created_at ASC), `update()`, `terminate()`, `update_balance()`, `deduct_balance()`
  - Alembic migration for `wallets` table

- [x] Create the WalletTransaction model, migration, repository, and schema:
  - `backend/app/models/wallet_transaction.py` — WalletTransaction model:
    - `id` (UUIDType PK), `wallet_id` (FK to wallets, not null), `customer_id` (FK to customers, not null)
    - `transaction_type` (String: "inbound", "outbound")
    - `transaction_status` (String: "purchased", "granted", "voided", "invoiced")
    - `source` (String: "manual", "interval", "threshold")
    - `status` (String: "pending", "settled", "failed")
    - `amount` (Numeric(12,4)) — credit units amount
    - `credit_amount` (Numeric(12,4)) — currency amount
    - `invoice_id` (FK to invoices, nullable) — for outbound consumption
    - `created_at`, `updated_at` timestamps
    - Indexes: `(wallet_id)`, `(customer_id)`, `(invoice_id)`
  - `backend/app/schemas/wallet_transaction.py` — Pydantic schemas: `WalletTransactionCreate`, `WalletTransactionResponse`, enums for type/status/source
  - `backend/app/repositories/wallet_transaction_repository.py` — WalletTransactionRepository: `create()`, `get_by_id()`, `get_by_wallet_id()`, `get_by_customer_id()`, `get_inbound_by_wallet_id()`, `get_outbound_by_wallet_id()`
  - Alembic migration for `wallet_transactions` table

- [ ] Create the WalletService with core business logic:
  - `backend/app/services/wallet_service.py`:
    - `create_wallet(customer_id, name, code, rate_amount, currency, expiration_at, priority, initial_granted_credits)` — Create wallet, optionally grant initial credits via inbound transaction
    - `terminate_wallet(wallet_id)` — Set status to "terminated", prevent further transactions
    - `top_up_wallet(wallet_id, credits, source="manual")` — Create inbound transaction, update balance
    - `consume_credits(customer_id, amount_cents, invoice_id)` — Priority-based consumption algorithm:
      1. Get all active, non-expired wallets for customer ordered by priority ASC, created_at ASC
      2. For each wallet: calculate max consumable = min(wallet.balance_cents, remaining_amount)
      3. Deduct from wallet, create outbound transaction
      4. Continue until amount fully consumed or no wallets remain
      5. Return total consumed and remaining uncovered amount
    - `get_customer_balance(customer_id)` — Total balance across all active wallets
    - `check_expired_wallets()` — Background job helper: find and terminate expired wallets

- [ ] Create Wallet API routers:
  - `backend/app/routers/wallets.py`:
    - `POST /v1/wallets` — Create wallet for customer
    - `GET /v1/wallets` — List wallets (filter by customer_id, status)
    - `GET /v1/wallets/{id}` — Get wallet details
    - `PUT /v1/wallets/{id}` — Update wallet (name, expiration_at, priority)
    - `DELETE /v1/wallets/{id}` — Terminate wallet (soft delete: sets status=terminated)
    - `POST /v1/wallets/{id}/top_up` — Top up wallet with credits
    - `GET /v1/wallets/{id}/transactions` — List wallet transactions
  - Register router in `backend/app/main.py`

- [ ] Integrate wallet consumption into the invoice payment flow:
  - Modify `backend/app/routers/invoices.py` — When an invoice is finalized or paid:
    - Before processing payment provider, check if customer has active wallets
    - Call `WalletService.consume_credits(customer_id, invoice_total, invoice_id)`
    - If wallet covers full amount: mark invoice as paid, create `prepaid_credit_amount` field on invoice
    - If wallet covers partial amount: reduce payment amount by consumed credits, proceed to payment provider for remainder
    - Add `prepaid_credit_amount` field to Invoice model (Numeric(12,4) default 0) via migration
  - Update `backend/app/schemas/invoice.py` to include `prepaid_credit_amount` in response

- [ ] Write comprehensive tests for the wallet system:
  - `backend/tests/test_wallets.py` — Test wallet CRUD, top-up, termination, expiration, priority ordering
  - `backend/tests/test_wallet_transactions.py` — Test transaction creation, filtering, balance calculations
  - `backend/tests/test_wallet_consumption.py` — Test priority-based consumption algorithm: single wallet, multiple wallets with priorities, partial consumption, expired wallet skipping, terminated wallet skipping, zero-balance wallet skipping
  - Update invoice tests to verify wallet integration

- [ ] Run the full test suite and fix any failures:
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ -v --tb=short`
  - Fix any test failures or coverage gaps
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=100` to verify 100% coverage
