---
type: spec
title: "Subscription Lifecycle Specification"
created: 2026-02-11
tags:
  - spec
  - subscription
  - lifecycle
  - trials
  - P1
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[04-credit-notes]]"
  - "[[12-commitments-and-thresholds]]"
---

# Subscription Lifecycle Specification

## Overview

Enhanced subscription management including upgrade/downgrade flows, trial period tracking, billing time modes (calendar vs anniversary), termination options, grace periods, and pay-in-advance support. The current bxb subscription model supports basic states (pending, active, canceled, terminated) but lacks the advanced lifecycle features that Lago provides.

## Lago Reference

Source: `app/models/subscription.rb` in the Lago codebase. Includes PaperTrailTraceable. Supports billing_time enum (calendar, anniversary), next_subscription relationships for upgrade/downgrade, and trial period management.

## Enhanced Subscription Fields

### Additional Columns on `subscriptions` Table

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `billing_time` | String(20) | NOT NULL, default "calendar" | calendar or anniversary |
| `subscription_at` | DateTime | nullable | Custom billing anchor date |
| `trial_ended_at` | DateTime | nullable | When trial period ended |
| `next_plan_id` | UUID | FK -> plans, nullable | Plan for pending upgrade/downgrade |
| `previous_subscription_id` | UUID | FK -> subscriptions, nullable | Predecessor subscription (for upgrades) |
| `pay_in_advance` | Boolean | NOT NULL, default false | Bill at start of period |

## State Machine

```
                  ┌─────────┐
                  │ pending  │
                  └────┬─────┘
                       │ activate
                       v
               ┌───────────────┐
               │    active      │──── in_trial_period? ────┐
               └───┬───────┬───┘                           │
                   │       │                               │
          cancel   │       │ terminate             trial ends
                   v       v                               │
          ┌──────────┐  ┌─────────────┐                    │
          │ canceled  │  │ terminated  │ <─────────────────┘
          └──────────┘  └─────────────┘
                │
                │ end of billing period
                v
          ┌─────────────┐
          │ terminated  │
          └─────────────┘
```

### State Descriptions

- **pending**: Created but not yet activated (e.g., future start date)
- **active**: Currently billing. May be in trial period.
- **canceled**: Will terminate at end of current billing period
- **terminated**: No longer active. Final invoice generated.

## Calendar vs Anniversary Billing

### Calendar Billing (`billing_time = "calendar"`)
- Billing periods align to calendar months/quarters/years
- Monthly: 1st of each month
- Quarterly: Jan 1, Apr 1, Jul 1, Oct 1
- Yearly: Jan 1

### Anniversary Billing (`billing_time = "anniversary"`)
- Billing periods start from `subscription_at` date
- Monthly: same day each month (e.g., subscribed on 15th → bills on 15th)
- Handles end-of-month edge cases (e.g., Jan 31 → Feb 28)

## Trial Period Management

1. When a subscription activates on a plan with `trial_period_days > 0`:
   - `started_at` = activation date
   - Trial end date = `started_at + trial_period_days`
   - During trial: no charge fees generated, only subscription tracking
2. `in_trial_period` computed property: `trial_ended_at is None and now < started_at + plan.trial_period_days`
3. When trial ends: `trial_ended_at` is set, normal billing begins
4. If subscription is terminated during trial: no charges

## Upgrade/Downgrade Flows

### Immediate Upgrade
1. Current subscription is terminated immediately
2. New subscription is created with the new plan
3. `previous_subscription_id` links to the old subscription
4. Prorated credit note generated for unused portion of current period (see [[04-credit-notes]])
5. New invoice generated for the new plan

### Downgrade (End of Period)
1. `next_plan_id` is set on the current subscription
2. Current subscription continues until end of billing period
3. At period end: current subscription terminated, new subscription created with next_plan_id
4. `previous_subscription_id` links to the old subscription

## Termination Options

### `on_termination_invoice`
- When true: generate a final invoice for usage up to termination date
- When false: no final invoice (usage is forgiven)

### `on_termination_credit_note`
- When true: generate a credit note for the unused portion of a prepaid period
- When false: no credit note (prepaid amount is forfeited)

## Grace Periods

- `grace_period_days` on the plan or organization level
- After invoice generation, the invoice remains in `draft` status for the grace period
- During grace period: customer can dispute charges, add usage corrections
- After grace period: invoice is automatically finalized

## Pay-in-Advance

When `pay_in_advance = true`:
- Subscription fee is billed at the **start** of each billing period
- Usage fees are billed as they occur (per-event or per-threshold)
- Fees are created with `invoice_id = null` initially (pay-in-advance fees)
- A separate collection mechanism groups pay-in-advance fees into invoices

## API Endpoints (Enhanced)

### Existing endpoints enhanced:
- `POST /v1/subscriptions` — Add `billing_time`, `subscription_at`, `pay_in_advance` fields
- `PUT /v1/subscriptions/{id}` — Support plan changes (upgrade/downgrade)
- `POST /v1/subscriptions/{id}/terminate` — Add `on_termination_invoice`, `on_termination_credit_note` options

### New endpoints:
- `GET /v1/subscriptions/{id}/usage` — Get current period usage summary
