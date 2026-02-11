---
type: reference
title: "bxb Lago Parity: Feature Gap Analysis Overview"
created: 2026-02-11
tags:
  - spec
  - overview
  - lago-parity
related:
  - "[[01-fee-model]]"
  - "[[02-wallets-and-credits]]"
  - "[[03-coupons-and-discounts]]"
  - "[[04-credit-notes]]"
  - "[[05-add-ons]]"
  - "[[06-tax-system]]"
  - "[[07-webhooks]]"
  - "[[08-subscription-lifecycle]]"
  - "[[09-advanced-charges]]"
  - "[[10-multi-tenancy]]"
  - "[[11-dunning-and-payments]]"
  - "[[12-commitments-and-thresholds]]"
  - "[[13-integrations]]"
  - "[[14-data-export-and-analytics]]"
---

# bxb Lago Parity: Feature Gap Analysis

## Executive Summary

This document provides a comprehensive analysis of the 33 feature areas identified as gaps between the current bxb billing platform and the Lago open-source billing engine. bxb currently implements core billing primitives (customers, plans, charges, subscriptions, events, invoices, payments) but lacks many of the advanced features that Lago provides for enterprise billing workflows.

The analysis covers entity models, API endpoints, business logic, and integration points. Each feature area is assessed for current status, priority, and estimated complexity.

## Current bxb Capabilities

bxb currently supports:
- Customer management with external IDs
- Plan and charge configuration (5 charge models: standard, graduated, volume, package, percentage)
- Subscription lifecycle (pending, active, canceled, terminated)
- Event ingestion with deduplication (single and batch)
- Usage aggregation (count, sum, max, unique_count)
- Invoice generation from subscriptions with JSON line_items
- Payment processing (Stripe, Manual, UCP providers)
- 100% test coverage enforcement

## Feature Gap Matrix

| # | Feature Area | Status | Priority | Complexity | Spec |
|---|-------------|--------|----------|------------|------|
| 1 | Fee Model (first-class line items) | complete-gap | P0 | M | [[01-fee-model]] |
| 2 | Wallet System | complete-gap | P1 | L |  [[02-wallets-and-credits]] |
| 3 | Wallet Transactions | complete-gap | P1 | M | [[02-wallets-and-credits]] |
| 4 | Recurring Transaction Rules | complete-gap | P2 | M | [[02-wallets-and-credits]] |
| 5 | Wallet Targets | complete-gap | P2 | S | [[02-wallets-and-credits]] |
| 6 | Coupons | complete-gap | P1 | L | [[03-coupons-and-discounts]] |
| 7 | Applied Coupons | complete-gap | P1 | M | [[03-coupons-and-discounts]] |
| 8 | Coupon Targets (plan/metric scoping) | complete-gap | P2 | S | [[03-coupons-and-discounts]] |
| 9 | Credits (invoice application) | complete-gap | P1 | M | [[03-coupons-and-discounts]] |
| 10 | Credit Notes | complete-gap | P1 | XL | [[04-credit-notes]] |
| 11 | Credit Note Items | complete-gap | P1 | M | [[04-credit-notes]] |
| 12 | Add-Ons | complete-gap | P1 | M | [[05-add-ons]] |
| 13 | Applied Add-Ons | complete-gap | P1 | S | [[05-add-ons]] |
| 14 | Tax Entity | complete-gap | P0 | L | [[06-tax-system]] |
| 15 | Applied Tax (polymorphic) | complete-gap | P0 | L | [[06-tax-system]] |
| 16 | Webhook Endpoints | complete-gap | P1 | M | [[07-webhooks]] |
| 17 | Webhook Delivery & Retry | complete-gap | P1 | L | [[07-webhooks]] |
| 18 | Subscription Upgrades/Downgrades | complete-gap | P1 | L | [[08-subscription-lifecycle]] |
| 19 | Trial Period Management | partial | P1 | M | [[08-subscription-lifecycle]] |
| 20 | Pay-in-Advance Billing | complete-gap | P1 | L | [[08-subscription-lifecycle]] |
| 21 | Calendar vs Anniversary Billing | complete-gap | P1 | M | [[08-subscription-lifecycle]] |
| 22 | Graduated Percentage Charges | complete-gap | P2 | M | [[09-advanced-charges]] |
| 23 | Custom/Dynamic Charges | complete-gap | P2 | L | [[09-advanced-charges]] |
| 24 | Advanced Aggregation Types | complete-gap | P2 | M | [[09-advanced-charges]] |
| 25 | Charge Filters | complete-gap | P2 | L | [[09-advanced-charges]] |
| 26 | Organization (multi-tenant) | complete-gap | P1 | XL | [[10-multi-tenancy]] |
| 27 | Billing Entity (sub-tenant) | complete-gap | P2 | L | [[10-multi-tenancy]] |
| 28 | Dunning Campaigns | complete-gap | P2 | L | [[11-dunning-and-payments]] |
| 29 | Payment Requests | complete-gap | P2 | M | [[11-dunning-and-payments]] |
| 30 | Commitments (minimum spend) | complete-gap | P2 | M | [[12-commitments-and-thresholds]] |
| 31 | Usage Thresholds / Progressive Billing | complete-gap | P2 | L | [[12-commitments-and-thresholds]] |
| 32 | External Integrations | complete-gap | P3 | XL | [[13-integrations]] |
| 33 | Data Export & Analytics | complete-gap | P3 | L | [[14-data-export-and-analytics]] |

## Priority Definitions

- **P0** — Foundation: Must be implemented first; other features depend on it
- **P1** — Core: Essential for production billing workflows
- **P2** — Advanced: Needed for enterprise customers and complex billing scenarios
- **P3** — Integration: External service connectors and analytics

## Complexity Definitions

- **S** (Small) — Single model, straightforward CRUD, <1 day
- **M** (Medium) — 1-2 models with business logic, 1-3 days
- **L** (Large) — Multiple models with complex interactions, 3-7 days
- **XL** (Extra Large) — Cross-cutting concern affecting many existing models, 1-2 weeks

## Implementation Order (Recommended)

### Phase 1: Foundation (P0)
1. [[01-fee-model]] — Fee model is the foundation for all subsequent features
2. [[06-tax-system]] — Tax system is required for correct invoice calculations

### Phase 2: Core Billing (P1)
3. [[08-subscription-lifecycle]] — Enhanced subscription management
4. [[05-add-ons]] — One-off charges
5. [[02-wallets-and-credits]] — Prepaid credit system
6. [[03-coupons-and-discounts]] — Discount application
7. [[04-credit-notes]] — Refunds and credit management
8. [[07-webhooks]] — Event notification system

### Phase 3: Advanced Features (P2)
9. [[09-advanced-charges]] — Additional charge models and filters
10. [[10-multi-tenancy]] — Organization and billing entity isolation
11. [[11-dunning-and-payments]] — Payment retry and recovery
12. [[12-commitments-and-thresholds]] — Minimum commitments and progressive billing

### Phase 4: Integrations (P3)
13. [[13-integrations]] — External service adapters
14. [[14-data-export-and-analytics]] — Reporting and data export

## Key Architectural Decisions

1. **Fee Model as Source of Truth**: Invoice line_items JSON will be replaced by first-class Fee records. The JSON field will be retained for backward compatibility but populated from fees.

2. **Polymorphic Associations**: Applied taxes, credits, and integration mappings use polymorphic relationships to attach to multiple entity types.

3. **Soft Delete**: Following Lago's pattern with Discard, entities that need audit trails should implement soft delete via `deleted_at` columns.

4. **Sequential Numbering**: Invoices and credit notes require sequential numbering per organization/billing entity, using advisory locks to prevent race conditions.

5. **Multi-Currency**: All monetary fields use `_cents` suffix with Numeric(12,4) precision. Currency codes stored alongside amounts.
