# Phase 01: Specification Document & Fee Model Foundation

This phase creates the comprehensive specification document for all missing Lago features and implements the Fee model — the most critical missing data structure in bxb. Currently, bxb stores invoice line items as a JSON blob inside the Invoice model. Lago treats fees as first-class entities with their own table, relationships, payment status, and tax tracking. The Fee model is the foundation that nearly every subsequent feature (wallets, coupons, credit notes, commitments, progressive billing) depends on. By the end of this phase, you will have a detailed spec document and a working Fee model with full API, tests, and invoice generation integration.

## Tasks

- [x] Analyze the Lago codebase at `/Users/System/Documents/lago-api` and the current bxb codebase at `/Users/System/Documents/bxb` to produce a comprehensive specification document. Create the following structured markdown files under `docs/spec/`:
  > **Completed 2026-02-11**: Created all 15 specification documents (00-overview through 14-data-export-and-analytics) under `docs/spec/`. Each file has YAML front matter with appropriate `type`, `created`, `tags`, and `related` fields. The overview document covers all 33 feature gaps with status, priority (P0-P3), and complexity (S/M/L/XL) ratings. All specs cross-reference each other via `[[wiki-links]]` (127 total cross-references). Content derived from analysis of both the Lago codebase (`app/models/*.rb`, concerns, and schema) and the current bxb codebase.
  - `docs/spec/00-overview.md` — Executive summary of all 33 feature areas identified as gaps between bxb and Lago. Include YAML front matter with `type: reference`, `tags: [spec, overview, lago-parity]`. List each feature area with status (complete-gap, partial, or integration), priority (P0-P3), and estimated complexity (S/M/L/XL). Link to each feature spec via `[[Feature-Name]]` wiki-links.
  - `docs/spec/01-fee-model.md` — Fee entity specification: fields (`fee_type` enum [charge, subscription, add_on, credit, commitment], `amount_cents`, `taxes_amount_cents`, `total_amount_cents`, `units`, `events_count`, `unit_amount_cents`, `payment_status`, `invoiceable_type`/`invoiceable_id` polymorphic), relationships (invoice, charge, subscription, add_on), indexes, and API endpoints. Reference Lago's `app/models/fee.rb` for field definitions.
  - `docs/spec/02-wallets-and-credits.md` — Wallet entity (`customer_id`, `name`, `code`, `balance_cents`, `credits_balance`, `rate_amount`, `status`, `expiration_at`, `priority`), WalletTransaction entity (`transaction_type` [inbound/outbound], `transaction_status`, `source`, `amount`, `credit_amount`), RecurringTransactionRule, WalletTarget. Include consumption priority algorithm, top-up triggers (manual/interval/threshold), and API endpoints.
  - `docs/spec/03-coupons-and-discounts.md` — Coupon entity (`code`, `name`, `coupon_type` [fixed_amount/percentage], `frequency` [once/recurring/forever], `amount_cents`/`percentage_rate`, `expiration`, `reusable`, scoping to plans/metrics), AppliedCoupon entity, CouponTarget entity, Credit entity (`amount_cents`, `before_taxes`, polymorphic source). Include application rules and invoice calculation order.
  - `docs/spec/04-credit-notes.md` — CreditNote entity (`number`, `credit_note_type` [credit/refund/offset], `status` [draft/finalized], `credit_status` [available/consumed/voided], `refund_status`, `reason` enum, amounts [credit/refund/offset/balance/total], tax amounts), CreditNoteItem entity, refund flow, void flow, invoice settlement.
  - `docs/spec/05-add-ons.md` — AddOn entity (`code`, `name`, `amount_cents`, `amount_currency`, `invoice_display_name`), AppliedAddOn entity, one-off invoice generation from add-ons.
  - `docs/spec/06-tax-system.md` — Tax entity (`code`, `name`, `rate`, `description`), AppliedTax polymorphic entity (applicable to Customer, Invoice, Fee, CreditNote, Plan, Charge, AddOn, Commitment), tax calculation pipeline, organization-level default taxes. Note: external tax providers (Anrok, Avalara) deferred to integrations phase.
  - `docs/spec/07-webhooks.md` — Webhook entity (`webhook_endpoint_id`, `webhook_type`, `payload`, `status` [pending/succeeded/failed], `retries`, `http_status`, `response`), WebhookEndpoint entity (`url`, `signature_algo` [hmac/jwt]), signature generation (HMAC-SHA256, JWT-RS256), retry logic with exponential backoff, 90-day retention. List all webhook event types (invoice.created, payment.succeeded, etc.).
  - `docs/spec/08-subscription-lifecycle.md` — Enhanced subscription states: pending→active→terminated/canceled. Upgrade/downgrade flows, trial period management (`trial_ended_at`, `in_trial_period`), billing_time (calendar vs anniversary), termination options (`on_termination_invoice`, `on_termination_credit_note`), grace periods, pay_in_advance support.
  - `docs/spec/09-advanced-charges.md` — Additional charge models: `graduated_percentage` (tiered percentage rates), `custom` (custom aggregation expression), `dynamic` (pricing from event properties). Enhanced billable metrics: `weighted_sum_agg`, `latest_agg`, `custom_agg`, `recurring` flag, `rounding_function`/`rounding_precision`, `expression` field. ChargeFilter and BillableMetricFilter entities for conditional pricing.
  - `docs/spec/10-multi-tenancy.md` — Organization entity (top-level tenant: `default_currency`, `timezone`, `hmac_key`, `document_number_prefix`), BillingEntity (sub-tenant: own invoices, taxes, dunning), API key scoping, sequential ID generation per org/billing-entity for invoice/credit-note numbering.
  - `docs/spec/11-dunning-and-payments.md` — DunningCampaign entity (`max_attempts`, `days_between_attempts`, `bcc_emails`), DunningCampaignThreshold, PaymentRequest entity (`amount_cents`, `payment_status`, `payment_attempts`), PaymentReceipt, InvoiceSettlement (links payments/credit-notes to invoices), enhanced payment methods per customer.
  - `docs/spec/12-commitments-and-thresholds.md` — Commitment entity (`plan_id`, `commitment_type` [minimum_commitment], `amount_cents`), UsageThreshold entity (`amount_cents`, `recurring`, `threshold_display_name`), progressive billing flow (threshold crossing → credit note + new invoice), AppliedUsageThreshold.
  - `docs/spec/13-integrations.md` — Integration architecture: BaseProvider pattern, IntegrationMapping, IntegrationCollectionMapping, IntegrationCustomer. Planned providers: accounting (Netsuite, Xero), CRM (HubSpot, Salesforce), tax (Anrok, Avalara), SSO (Okta). Each as pluggable adapter.
  - `docs/spec/14-data-export-and-analytics.md` — DataExport entity (CSV exports with status tracking), ClickHouse integration for event analytics, activity/API logging, daily usage pre-aggregation.
  - All spec files should use YAML front matter: `type: spec`, `created: 2026-02-11`, `tags: [spec, {feature-name}]`, and cross-reference related specs with `[[Spec-Name]]` wiki-links.

- [x] Create the Fee model, migration, repository, and schema in the bxb backend:
  > **Completed 2026-02-11**: Created all four components:
  > - `backend/app/models/fee.py` — Fee SQLAlchemy model with UUIDType PK, FKs to invoices/charges/subscriptions/customers, FeeType and FeePaymentStatus enums, all specified numeric/string/JSON fields, and 5 indexes
  > - `backend/app/schemas/fee.py` — Pydantic schemas: FeeCreate, FeeUpdate, FeeResponse with all fields, enums imported from model
  > - `backend/app/repositories/fee_repository.py` — FeeRepository with all 10 methods: create(), create_bulk(), get_by_id(), get_by_invoice_id(), get_by_customer_id(), get_by_subscription_id(), get_all() with filters, update(), delete(), mark_succeeded(), mark_failed()
  > - `backend/app/alembic/versions/20260211_c572a3f1d896_create_fees_table.py` — Migration for fees table with all columns, FKs, and indexes
  > - Registered Fee in models/__init__.py, schemas/__init__.py, repositories/__init__.py
  > - All 545 existing tests continue to pass.
  - `backend/app/models/fee.py` — Fee SQLAlchemy model with fields:
    - `id` (UUIDType PK), `invoice_id` (FK to invoices, nullable for pay-in-advance), `charge_id` (FK to charges, nullable), `subscription_id` (FK to subscriptions, nullable), `customer_id` (FK to customers, not null)
    - `fee_type` (String: "charge", "subscription", "add_on", "credit", "commitment")
    - `amount_cents` (Numeric(12,4)), `taxes_amount_cents` (Numeric(12,4) default 0), `total_amount_cents` (Numeric(12,4))
    - `units` (Numeric(12,4) default 0), `events_count` (Integer default 0), `unit_amount_cents` (Numeric(12,4) default 0)
    - `payment_status` (String: "pending", "succeeded", "failed", "refunded", default "pending")
    - `description` (String(500)), `metric_code` (String(255) nullable)
    - `properties` (JSON, default dict) — charge model properties snapshot
    - `created_at`, `updated_at` timestamps
    - Indexes: `(invoice_id)`, `(customer_id)`, `(subscription_id)`, `(charge_id)`, `(fee_type)`
  - `backend/app/schemas/fee.py` — Pydantic schemas: `FeeCreate`, `FeeUpdate`, `FeeResponse` with all fields, `FeeType` and `FeePaymentStatus` enums
  - `backend/app/repositories/fee_repository.py` — FeeRepository with methods: `create()`, `create_bulk()`, `get_by_id()`, `get_by_invoice_id()`, `get_by_customer_id()`, `get_by_subscription_id()`, `update()`, `delete()`, `mark_succeeded()`, `mark_failed()`
  - Alembic migration for the `fees` table with all columns and indexes

- [x] Create the Fee API router:
  > **Completed 2026-02-11**: Created all components:
  > - `backend/app/routers/fees.py` — Three endpoints: `GET /` (list with pagination and 5 filters), `GET /{fee_id}` (get by ID), `PUT /{fee_id}` (update payment_status/description/taxes). Follows project conventions (Query-validated pagination, HTTPException 404s, FeeRepository pattern).
  > - Registered router in `backend/app/main.py` at `/v1/fees` with `["fees"]` tags
  > - `backend/tests/test_fees.py` — 35 tests covering: FeeRepository CRUD (19 tests: create, create_bulk, get_by_id, get_by_invoice/customer/subscription_id, get_all with filters/pagination, update, delete, mark_succeeded, mark_failed, payment_status_filter) + Fee API endpoints (16 tests: list empty/populated, all 5 filters, pagination, get by ID, get not found, update payment_status/description/taxes, update not found, response format, combined filters)
  > - All 580 tests pass (545 existing + 35 new).
  - `backend/app/routers/fees.py` — Endpoints:
    - `GET /v1/fees` — List fees with filters (invoice_id, customer_id, subscription_id, fee_type, payment_status)
    - `GET /v1/fees/{id}` — Get fee by ID
    - `PUT /v1/fees/{id}` — Update fee (payment_status changes)
  - Register the router in `backend/app/main.py`

- [x] Refactor InvoiceGenerationService to create Fee records instead of JSON line items:
  > **Completed 2026-02-11**: Refactored InvoiceGenerationService with:
  > - `_calculate_charge_fee()` — New method that returns `FeeCreate` objects with all fields (fee_type, customer_id, subscription_id, charge_id, amount_cents, units, events_count, unit_amount_cents, description, metric_code, properties)
  > - `generate_invoice()` — Now creates Fee records via `FeeRepository.create_bulk()` linked to the invoice. Invoice line_items JSON still populated from fees for backward compatibility.
  > - `_calculate_charge()` — Kept for backward compatibility (tests use it directly)
  > - `UsageAggregationService.aggregate_usage_with_count()` — New method returning `UsageResult` dataclass with both `value` and `events_count`. Original `aggregate_usage()` delegates to it.
  > - All 608 tests pass with 100% coverage.
  - Modify `backend/app/services/invoice_generation.py`:
    - `generate_invoice()` should create Fee records in the database for each charge
    - Each Fee gets: `fee_type="charge"`, `invoice_id`, `charge_id`, `subscription_id`, `customer_id`, the calculated `amount_cents`, `units`, `unit_amount_cents`, `events_count`, `description`, `metric_code`
    - Invoice `subtotal` and `total` should be computed from the sum of Fee `total_amount_cents`
    - Keep `line_items` JSON on Invoice for backward compatibility (populate from fees), but fees are now the source of truth
  - Modify `backend/app/services/usage_aggregation.py` to also return `events_count` alongside the aggregated value, so it can be stored on the Fee

- [x] Write comprehensive tests for the Fee model and API:
  > **Completed 2026-02-11**: Added 28 new tests across 3 files:
  > - `test_invoice_generation.py` — 19 new tests: `TestGenerateInvoiceFeeRecords` (7 tests: single/multiple fee creation, no-charge/none-charge scenarios, line_items backward compatibility, events_count verification, properties snapshot) + `TestCalculateChargeFee` (12 tests: standard/graduated/percentage/graduated_percentage fee calc, no-metric, metric-not-found, calculator-none, zero amounts, unknown model, empty properties, min/max price)
  > - `test_usage_aggregation.py` — 7 new tests: `TestAggregateUsageWithCount` covering count/sum/max/unique_count with events_count, no-events, unknown metric
  > - `test_fees.py` — 2 new tests: `test_get_all_with_subscription_filter` and `test_get_all_with_charge_filter` for full repository coverage
  - `backend/tests/test_fees.py` — Test all Fee CRUD operations, filtering, payment status transitions
  - Update `backend/tests/test_invoices.py` — Test that invoice generation now creates Fee records, verify Fee-Invoice relationship, verify backward compatibility of `line_items` JSON
  - Ensure 100% test coverage is maintained across all new and modified code

- [x] Run the full test suite and fix any failures:
  > **Completed 2026-02-11**: 608 tests pass, 100% coverage achieved.
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ -v --tb=short`
  - Fix any test failures or coverage gaps
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=100` to verify 100% coverage
