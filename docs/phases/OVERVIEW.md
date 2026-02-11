# bxb Development Phases — Lago Feature Parity

> Based on analysis of [lago-api](https://github.com/getlago/lago-api) codebase

## Current Status

**Completed (Phases 1-6):**
- ✅ Customers API
- ✅ Billable Metrics API
- ✅ Plans & Charges API (standard model only)
- ✅ Subscriptions API
- ✅ Events API (batch ingestion, idempotency)
- ✅ Usage Aggregation (count, sum, max, unique_count)
- ✅ Invoice Generation
- ✅ Payments (Stripe, UCP, Manual)

**Tests:** 431 passing, 100% coverage

---

## Remaining Phases

| Phase | Feature | Priority | Complexity | Est. Time |
|-------|---------|----------|------------|-----------|
| 7 | Advanced Charge Models | HIGH | High | 2-3 weeks |
| 8 | Webhooks | HIGH | Medium | 1 week |
| 9 | Wallets & Prepaid Credits | MEDIUM | High | 2 weeks |
| 10 | Coupons & Discounts | MEDIUM | Medium | 1-2 weeks |
| 11 | Credit Notes | MEDIUM | Medium | 1 week |
| 12 | Taxes | MEDIUM | Medium | 1 week |
| 13 | Add-ons | LOW | Low | 3-5 days |
| 14 | Multi-currency | LOW | Medium | 1 week |
| 15 | Customer Portal | LOW | High | 2 weeks |
| 16 | Analytics & Reporting | LOW | Medium | 1-2 weeks |

---

## Phase Files

Each phase has a detailed implementation plan:

- [`PHASE-07-CHARGE-MODELS.md`](./PHASE-07-CHARGE-MODELS.md) — Graduated, Volume, Package, Percentage pricing
- [`PHASE-08-WEBHOOKS.md`](./PHASE-08-WEBHOOKS.md) — Event notifications & retry logic
- [`PHASE-09-WALLETS.md`](./PHASE-09-WALLETS.md) — Prepaid credits & balance management
- [`PHASE-10-COUPONS.md`](./PHASE-10-COUPONS.md) — Discounts & promotions
- [`PHASE-11-CREDIT-NOTES.md`](./PHASE-11-CREDIT-NOTES.md) — Refunds & credits
- [`PHASE-12-TAXES.md`](./PHASE-12-TAXES.md) — Tax rates & calculations
- [`PHASE-13-ADDONS.md`](./PHASE-13-ADDONS.md) — One-time charges
- [`PHASE-14-MULTI-CURRENCY.md`](./PHASE-14-MULTI-CURRENCY.md) — Currency conversion
- [`PHASE-15-CUSTOMER-PORTAL.md`](./PHASE-15-CUSTOMER-PORTAL.md) — Self-service portal
- [`PHASE-16-ANALYTICS.md`](./PHASE-16-ANALYTICS.md) — Reporting & dashboards

---

## Lago Architecture Reference

```
lago-api/app/
├── models/           # 114 models
│   ├── customer.rb
│   ├── billable_metric.rb
│   ├── plan.rb
│   ├── charge.rb           # 8 charge models!
│   ├── subscription.rb
│   ├── event.rb
│   ├── invoice.rb
│   ├── fee.rb
│   ├── wallet.rb
│   ├── coupon.rb
│   ├── credit_note.rb
│   └── ...
├── services/         # 76 service directories
│   ├── charge_models/      # Pricing calculation services
│   ├── invoices/           # Invoice generation
│   ├── events/             # Event processing
│   ├── webhooks/           # Webhook dispatch
│   ├── payment_providers/  # Stripe, Adyen, GoCardless...
│   └── ...
└── controllers/api/v1/
    ├── customers_controller.rb
    ├── plans_controller.rb
    ├── subscriptions_controller.rb
    ├── events_controller.rb
    ├── invoices_controller.rb
    └── ...
```

---

## Implementation Principles

1. **100% Test Coverage** — Non-negotiable
2. **API Compatibility** — Match Lago's REST API patterns
3. **Incremental** — Each phase delivers working features
4. **Clean Code** — Type hints, docstrings, consistent style
5. **Performance** — Optimize hot paths (event ingestion, aggregation)
