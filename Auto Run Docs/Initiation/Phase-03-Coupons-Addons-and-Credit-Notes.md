# Phase 03: Coupons, Add-ons & Credit Notes

This phase implements three tightly related billing features that are completely missing from bxb: coupons/discounts, add-ons (one-time charges), and credit notes (refunds/credits). These are essential for real-world billing operations. Coupons enable promotional pricing and customer retention. Add-ons allow one-time charges outside the subscription cycle. Credit notes enable refunds, credits, and adjustments against existing invoices. Together they complete the financial instrument toolkit needed for production billing.

## Tasks

- [x] Create the Coupon and AppliedCoupon models, migrations, repositories, and schemas:
  <!-- Completed: Created Coupon model, AppliedCoupon model, CouponRepository, AppliedCouponRepository, schemas (CouponCreate/Update/Response, ApplyCouponRequest, AppliedCouponResponse), Alembic migrations (d4e5f6a7b9c0, e5f6a7b9c0d1), updated models/__init__.py. 59 tests added, 843 total pass with 100% coverage. -->
  - `backend/app/models/coupon.py` — Coupon model:
    - `id` (UUIDType PK), `code` (String(255), unique index), `name` (String(255))
    - `description` (Text, nullable)
    - `coupon_type` (String: "fixed_amount", "percentage")
    - `amount_cents` (Numeric(12,4) nullable) — for fixed_amount type
    - `amount_currency` (String(3) nullable) — for fixed_amount type
    - `percentage_rate` (Numeric(5,2) nullable) — for percentage type (e.g., 10.00 = 10%)
    - `frequency` (String: "once", "recurring", "forever")
    - `frequency_duration` (Integer nullable) — number of billing periods for "recurring"
    - `reusable` (Boolean default True) — can be applied to multiple customers
    - `expiration` (String: "no_expiration", "time_limit")
    - `expiration_at` (DateTime nullable)
    - `status` (String: "active", "terminated", default "active")
    - `created_at`, `updated_at` timestamps
  - `backend/app/models/applied_coupon.py` — AppliedCoupon model:
    - `id` (UUIDType PK), `coupon_id` (FK to coupons), `customer_id` (FK to customers)
    - `amount_cents` (Numeric(12,4) nullable) — override amount for this application
    - `amount_currency` (String(3) nullable)
    - `percentage_rate` (Numeric(5,2) nullable)
    - `frequency` (String), `frequency_duration` (Integer nullable)
    - `frequency_duration_remaining` (Integer nullable) — periods remaining
    - `status` (String: "active", "terminated")
    - `terminated_at` (DateTime nullable)
    - `created_at`, `updated_at` timestamps
    - Unique constraint: `(coupon_id, customer_id)` when coupon is not reusable
  - Schemas: `CouponCreate`, `CouponUpdate`, `CouponResponse`, `ApplyCouponRequest`, `AppliedCouponResponse`
  - Repositories: `CouponRepository` (CRUD + `get_by_code()`), `AppliedCouponRepository` (CRUD + `get_active_by_customer_id()`, `decrement_frequency()`, `terminate()`)
  - Alembic migrations for both tables

- [ ] Create the AddOn and AppliedAddOn models, migrations, repositories, and schemas:
  - `backend/app/models/add_on.py` — AddOn model:
    - `id` (UUIDType PK), `code` (String(255), unique index), `name` (String(255))
    - `description` (Text nullable)
    - `amount_cents` (Numeric(12,4) not null), `amount_currency` (String(3) default "USD")
    - `invoice_display_name` (String(255) nullable)
    - `created_at`, `updated_at` timestamps
  - `backend/app/models/applied_add_on.py` — AppliedAddOn model:
    - `id` (UUIDType PK), `add_on_id` (FK to add_ons), `customer_id` (FK to customers)
    - `amount_cents` (Numeric(12,4)) — final applied amount (may differ from add-on default)
    - `amount_currency` (String(3))
    - `created_at` timestamp
  - Schemas: `AddOnCreate`, `AddOnUpdate`, `AddOnResponse`, `ApplyAddOnRequest`, `AppliedAddOnResponse`
  - Repositories: `AddOnRepository` (CRUD + `get_by_code()`), `AppliedAddOnRepository` (CRUD + `get_by_customer_id()`)
  - Alembic migrations for both tables

- [ ] Create the CreditNote and CreditNoteItem models, migrations, repositories, and schemas:
  - `backend/app/models/credit_note.py` — CreditNote model:
    - `id` (UUIDType PK), `number` (String(50), unique index)
    - `invoice_id` (FK to invoices, not null), `customer_id` (FK to customers, not null)
    - `credit_note_type` (String: "credit", "refund", "offset")
    - `status` (String: "draft", "finalized", default "draft")
    - `credit_status` (String: "available", "consumed", "voided", nullable)
    - `refund_status` (String: "pending", "succeeded", "failed", nullable)
    - `reason` (String: "duplicated_charge", "product_unsatisfactory", "order_change", "order_cancellation", "fraudulent_charge", "other")
    - `description` (Text nullable)
    - `credit_amount_cents` (Numeric(12,4) default 0)
    - `refund_amount_cents` (Numeric(12,4) default 0)
    - `balance_amount_cents` (Numeric(12,4) default 0) — remaining credit available
    - `total_amount_cents` (Numeric(12,4) default 0)
    - `taxes_amount_cents` (Numeric(12,4) default 0)
    - `currency` (String(3))
    - `issued_at` (DateTime nullable), `voided_at` (DateTime nullable)
    - `created_at`, `updated_at` timestamps
  - `backend/app/models/credit_note_item.py` — CreditNoteItem model:
    - `id` (UUIDType PK), `credit_note_id` (FK to credit_notes), `fee_id` (FK to fees)
    - `amount_cents` (Numeric(12,4))
    - `created_at` timestamp
  - Schemas: `CreditNoteCreate`, `CreditNoteUpdate`, `CreditNoteResponse`, `CreditNoteItemResponse`
  - Repositories: `CreditNoteRepository` (CRUD + `get_by_invoice_id()`, `get_by_customer_id()`, `finalize()`, `void()`, `consume_credit(amount)`, `get_available_credit_by_customer_id()`), `CreditNoteItemRepository`
  - Alembic migrations for both tables

- [ ] Create API routers for Coupons, Add-ons, and Credit Notes:
  - `backend/app/routers/coupons.py`:
    - `POST /v1/coupons` — Create coupon
    - `GET /v1/coupons` — List coupons (filter by status)
    - `GET /v1/coupons/{code}` — Get coupon by code
    - `PUT /v1/coupons/{code}` — Update coupon
    - `DELETE /v1/coupons/{code}` — Terminate coupon
    - `POST /v1/coupons/apply` — Apply coupon to customer (body: coupon_code, customer_id, optional amount override)
    - `GET /v1/customers/{customer_id}/applied_coupons` — List applied coupons for customer
  - `backend/app/routers/add_ons.py`:
    - `POST /v1/add_ons` — Create add-on
    - `GET /v1/add_ons` — List add-ons
    - `GET /v1/add_ons/{code}` — Get add-on by code
    - `PUT /v1/add_ons/{code}` — Update add-on
    - `DELETE /v1/add_ons/{code}` — Delete add-on
    - `POST /v1/add_ons/apply` — Apply add-on to customer (creates one-off invoice with Fee of type "add_on")
  - `backend/app/routers/credit_notes.py`:
    - `POST /v1/credit_notes` — Create credit note (linked to invoice, with items referencing fees)
    - `GET /v1/credit_notes` — List credit notes (filter by customer_id, invoice_id, status)
    - `GET /v1/credit_notes/{id}` — Get credit note
    - `PUT /v1/credit_notes/{id}` — Update credit note (only in draft)
    - `POST /v1/credit_notes/{id}/finalize` — Finalize credit note
    - `POST /v1/credit_notes/{id}/void` — Void credit note (sets credit_status=voided)
  - Register all routers in `backend/app/main.py`

- [ ] Create CouponApplicationService for invoice calculation integration:
  - `backend/app/services/coupon_service.py`:
    - `apply_coupon_to_customer(coupon_code, customer_id, amount_override, percentage_override)` — Validate coupon (active, not expired, reusable check), create AppliedCoupon
    - `calculate_coupon_discount(customer_id, subtotal_cents)` — Get active applied coupons for customer, calculate total discount:
      - Fixed amount: deduct `amount_cents` (cap at subtotal)
      - Percentage: calculate `subtotal * percentage_rate / 100`
      - Return total discount and list of applied coupon IDs consumed
    - `consume_applied_coupon(applied_coupon_id)` — For "once" frequency: terminate. For "recurring": decrement frequency_duration_remaining, terminate if 0.

- [ ] Create AddOnService and CreditNoteService:
  - `backend/app/services/add_on_service.py`:
    - `apply_add_on(add_on_code, customer_id, amount_override)` — Create AppliedAddOn, generate one-off Invoice with a single Fee of type "add_on"
  - `backend/app/services/credit_note_service.py`:
    - `create_credit_note(invoice_id, items, reason, description)` — Validate invoice is finalized, create CreditNote with CreditNoteItems referencing fees, calculate amounts
    - `finalize_credit_note(credit_note_id)` — Set status=finalized, issued_at=now, set balance_amount_cents=credit_amount_cents
    - `void_credit_note(credit_note_id)` — Set credit_status=voided, voided_at=now
    - `apply_credit_to_invoice(credit_note_id, invoice_id, amount)` — Deduct from balance_amount_cents, create Credit record linking credit note to invoice

- [ ] Integrate coupon discounts into invoice generation:
  - Modify `backend/app/services/invoice_generation.py`:
    - After calculating all fees, call `CouponApplicationService.calculate_coupon_discount(customer_id, subtotal)`
    - Subtract discount from invoice total
    - Add `coupons_amount_cents` field to Invoice model (Numeric(12,4) default 0) via migration
    - Store discount breakdown in invoice metadata or as a Credit record
  - Update `backend/app/schemas/invoice.py` to include `coupons_amount_cents`

- [ ] Write comprehensive tests for all three feature areas:
  - `backend/tests/test_coupons.py` — Coupon CRUD, apply to customer, fixed/percentage types, once/recurring/forever frequencies, expiration, reusable vs single-use, discount calculation
  - `backend/tests/test_add_ons.py` — Add-on CRUD, apply to customer, one-off invoice generation, fee creation
  - `backend/tests/test_credit_notes.py` — Credit note CRUD, finalize, void, items linked to fees, credit application, reason codes, balance tracking
  - Update `backend/tests/test_invoices.py` to verify coupon discount integration

- [ ] Run the full test suite and fix any failures:
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ -v --tb=short`
  - Fix any test failures or coverage gaps
  - Execute `cd /Users/System/Documents/bxb/backend && python -m pytest tests/ --cov=app --cov-report=term-missing --cov-fail-under=100` to verify 100% coverage
