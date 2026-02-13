# Phase 10: Admin UI, Analytics & Polish

This phase brings everything together with a comprehensive admin UI that exposes all the features built in previous phases, adds analytics dashboards, and polishes the platform for production readiness. The current frontend has 7 basic admin pages but none of them reflect the new capabilities (wallets, coupons, credit notes, taxes, webhooks, organizations, commitments, thresholds, integrations). This phase updates the frontend to be a full-featured billing administration interface, adds OpenAPI documentation, and ensures the platform is production-ready with proper error handling, performance optimization, and security hardening.

## Tasks

- [x] Update the frontend API client and types:
  - Run `make openapi` to regenerate the OpenAPI schema from the backend
  - Run `cd /Users/System/Documents/bxb/frontend && npx openapi-typescript ../backend/openapi.json -o src/lib/schema.d.ts` to generate TypeScript types
  - Update `frontend/src/types/billing.ts` with any custom type helpers needed for the new entities
  - Verify `frontend/src/lib/api.ts` client works with new endpoints
  - **Note:** Fixed FastAPI 0.121.x OpenAPI generation bug via `backend/scripts/generate_openapi.py` helper; updated Makefile `openapi` target accordingly. Added 15 new API client modules (wallets, coupons, add-ons, credit notes, taxes, webhooks, organizations, dunning campaigns, commitments, usage thresholds, integrations, data exports, events, fees, payment requests). Updated existing pages (Invoices, Customers, Metrics, Subscriptions) for compatibility with new generated schema types.

- [x] Build the Wallets management UI:
  - `frontend/src/pages/admin/WalletsPage.tsx`:
    - Wallet list table with columns: customer name, wallet name/code, balance (credits + currency), status, priority, expiration
    - Create wallet dialog: select customer, set name/code, rate_amount, currency, initial credits, priority, expiration
    - Wallet detail view: balance history chart (using recharts), transaction list, top-up action
    - Top-up dialog: amount of credits to grant
    - Terminate wallet action with confirmation
  - Add "Wallets" to AdminLayout sidebar navigation
  - **Note:** Implemented full WalletsPage with: stat cards (total/active/credits/consumed), search + status filter, list table with all columns, create/edit wallet dialog, top-up dialog with source selection, wallet detail dialog with transaction history table, terminate confirmation. Added route in App.tsx, sidebar nav item with Coins icon, page export in index.ts. Used recharts-free approach for transaction list display (transaction table instead of chart). All TypeScript types verified, frontend builds clean.

- [ ] Build the Coupons and Add-ons management UI:
  - `frontend/src/pages/admin/CouponsPage.tsx`:
    - Coupon list table: code, name, type (fixed/percentage), frequency, status, usage count
    - Create coupon form: code, name, type selector, amount/percentage, frequency, duration, expiration, reusable toggle
    - Apply coupon dialog: select customer, optional amount override
    - View applied coupons per customer
  - `frontend/src/pages/admin/AddOnsPage.tsx`:
    - Add-on list table: code, name, amount, currency
    - Create add-on form: code, name, description, amount, currency
    - Apply add-on dialog: select customer, amount override
  - Add both to sidebar navigation

- [ ] Build the Credit Notes management UI:
  - `frontend/src/pages/admin/CreditNotesPage.tsx`:
    - Credit note list table: number, customer, invoice, type, status, total amount
    - Create credit note from invoice: select fees to credit, set reason, amounts
    - Credit note detail view: items, amounts breakdown, status actions
    - Actions: finalize (draft→finalized), void (finalized→voided)
  - Link credit notes from InvoicesPage (button on invoice detail to create credit note)

- [ ] Build the Tax management UI:
  - `frontend/src/pages/admin/TaxesPage.tsx`:
    - Tax list table: code, name, rate, description, applied_to_organization flag
    - Create tax form: code, name, rate (percentage input), description
    - Toggle organization-wide default
    - Apply tax to entity dialog: select entity type + entity, apply tax
  - Show applied taxes on Invoice detail, Fee detail, and Customer detail pages

- [ ] Build the Webhooks management UI:
  - `frontend/src/pages/admin/WebhooksPage.tsx`:
    - Webhook endpoints list: URL, signature algorithm, status
    - Create endpoint form: URL, signature algorithm
    - Recent webhooks table: type, status, retries, timestamp, http_status
    - Webhook detail view: full payload (JSON viewer), response body, retry button for failed
    - Status indicators: green (succeeded), red (failed), yellow (pending)

- [ ] Build the Organization settings and API key management:
  - Update `frontend/src/pages/admin/SettingsPage.tsx`:
    - Organization details section: name, email, legal name, address, timezone, default currency
    - API key management section:
      - List API keys: prefix, name, last used, created, expires
      - Create new API key (show key ONCE in a modal, copy to clipboard)
      - Revoke API key with confirmation
    - Dunning campaigns section:
      - List campaigns, create/edit with thresholds
    - Integration settings section:
      - List active integrations, add new, configure settings, test connection

- [ ] Enhance the Dashboard with analytics:
  - Update `frontend/src/pages/admin/DashboardPage.tsx`:
    - Revenue metrics cards: MRR (monthly recurring revenue), total revenue this month, outstanding invoices, overdue amount
    - Revenue chart (recharts Line): monthly revenue trend (last 12 months)
    - Customer metrics: total customers, new this month, churned this month
    - Subscription metrics: active subscriptions, new, canceled, by plan breakdown (Bar chart)
    - Usage overview: top 5 billable metrics by volume (Bar chart)
    - Recent activity feed: last 10 invoices, payments, subscription changes
    - Wallet balance summary: total prepaid credits across all customers
  - Add API endpoints to `backend/app/routers/dashboard.py` for analytics queries:
    - `GET /v1/dashboard/revenue` — MRR, total revenue, outstanding, overdue
    - `GET /v1/dashboard/customers` — Customer counts and trends
    - `GET /v1/dashboard/subscriptions` — Subscription counts by status and plan
    - `GET /v1/dashboard/usage` — Top metrics by usage volume

- [ ] Update existing admin pages to reflect new features:
  - `CustomersPage.tsx`:
    - Show customer wallets, applied coupons, credit notes, applied taxes in detail view
    - Add grace period and payment term fields to customer edit form
    - Show outstanding balance
  - `PlansPage.tsx`:
    - Show commitments on plan detail
    - Show usage thresholds on plan detail
    - Allow adding commitments and thresholds when editing plan
    - Show charge filters configuration
  - `SubscriptionsPage.tsx`:
    - Add upgrade/downgrade plan action
    - Show trial status and trial end date
    - Add billing_time and pay_in_advance options to create form
    - Show usage thresholds (subscription-level)
    - Termination dialog with action selection (generate invoice/credit note/skip)
  - `InvoicesPage.tsx`:
    - Show fees breakdown (from Fee model) instead of JSON line items
    - Show applied taxes per fee and total
    - Show coupon discounts
    - Show wallet credit applied
    - Show invoice settlements (how the invoice was paid)
    - Show credit notes linked to this invoice
    - Show invoice type (subscription/add_on/progressive_billing/etc.)

- [ ] Add comprehensive OpenAPI documentation:
  - Review all FastAPI router endpoints and ensure they have:
    - Descriptive `summary` and `description` parameters
    - Proper `response_model` return types
    - `tags` for grouping (Customers, Plans, Subscriptions, Events, Invoices, Payments, Wallets, Coupons, Add-ons, Credit Notes, Taxes, Webhooks, Organizations, Dunning, Commitments, Thresholds, Integrations, Exports, Dashboard)
    - Error response documentation (400, 401, 404, 422)
  - Run `make openapi` to regenerate the final OpenAPI spec
  - Verify the auto-generated Swagger UI at `/docs` is comprehensive and well-organized

- [ ] Performance and security hardening:
  - Add rate limiting to event ingestion endpoint (use a simple in-memory or Redis-based rate limiter):
    - Default: 1000 events/minute per API key
    - Configurable via settings
  - Add pagination to all list endpoints that don't already have it:
    - Standard pattern: `?page=1&per_page=20` with `X-Total-Count` response header
    - Verify: customers, plans, subscriptions, events, invoices, fees, wallets, coupons, credit notes, taxes, webhooks
  - Add database query optimization:
    - Review all repositories for N+1 query issues
    - Add SQLAlchemy `selectinload` or `joinedload` where relationships are frequently accessed
    - Add database indexes for common query patterns identified during development
  - Security review:
    - Ensure all user inputs are validated via Pydantic schemas (no raw query parameters)
    - Verify API key hashing uses SHA-256 (never store plaintext)
    - Verify webhook signatures use timing-safe comparison (`hmac.compare_digest`)
    - Ensure no SQL injection possible (SQLAlchemy parameterized queries)
    - Add CORS configuration to FastAPI app for frontend domain

- [ ] Write frontend tests and backend integration tests:
  - `backend/tests/test_dashboard.py` — Test all dashboard analytics endpoints return correct aggregated data
  - `backend/tests/test_pagination.py` — Test pagination across all list endpoints (page, per_page, total count)
  - `backend/tests/test_rate_limiting.py` — Test rate limiter on event ingestion (allow under limit, reject over limit)
  - Verify all existing tests still pass with the changes

- [ ] Run the full test suite one final time:
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ -v --tb=short`
  - Fix any test failures or coverage gaps
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=100` to verify 100% coverage
  - Run `cd /Users/System/Documents/bxb/frontend && npm run build` to verify frontend builds without errors
  - Run `cd /Users/System/Documents/bxb/frontend && npx tsc --noEmit` to verify TypeScript types
