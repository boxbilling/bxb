# Phase 16: Analytics & Reporting

> **Priority:** LOW | **Complexity:** Medium | **Est. Time:** 1-2 weeks

## Overview

Business analytics dashboards: MRR, ARR, churn, revenue trends.

## Lago Reference

**Source:** `lago-api/app/services/analytics/`, `lago-api/app/models/analytics/`

Key metrics Lago tracks:
- MRR (Monthly Recurring Revenue)
- Invoice collections
- Gross revenue
- Overdue balance

---

## Implementation Plan

### Analytics Service

```python
# app/services/analytics_service.py
class AnalyticsService:
    def get_mrr(self, as_of: date = None) -> Decimal:
        """
        Calculate Monthly Recurring Revenue.
        MRR = Sum of all active subscription monthly values.
        """
        as_of = as_of or date.today()
        
        subscriptions = self.db.query(Subscription).filter(
            Subscription.status == "active",
            Subscription.started_at <= as_of,
        ).all()
        
        mrr = Decimal("0")
        for sub in subscriptions:
            plan = sub.plan
            if plan.interval == "monthly":
                mrr += plan.amount_cents
            elif plan.interval == "yearly":
                mrr += plan.amount_cents / 12
            elif plan.interval == "weekly":
                mrr += plan.amount_cents * Decimal("4.33")
        
        return mrr
    
    def get_arr(self) -> Decimal:
        """Annual Recurring Revenue = MRR × 12"""
        return self.get_mrr() * 12
    
    def get_revenue_by_period(
        self,
        start_date: date,
        end_date: date,
        granularity: str = "month"  # day, week, month
    ) -> list[dict]:
        """Get revenue grouped by time period."""
        invoices = self.db.query(
            func.date_trunc(granularity, Invoice.issuing_date).label("period"),
            func.sum(Invoice.total_amount_cents).label("revenue_cents"),
            func.count(Invoice.id).label("invoice_count"),
        ).filter(
            Invoice.issuing_date >= start_date,
            Invoice.issuing_date <= end_date,
            Invoice.status == "finalized",
        ).group_by("period").order_by("period").all()
        
        return [
            {
                "period": str(inv.period),
                "revenue_cents": int(inv.revenue_cents or 0),
                "invoice_count": inv.invoice_count,
            }
            for inv in invoices
        ]
    
    def get_overdue_balance(self) -> int:
        """Total overdue invoice amount."""
        result = self.db.query(func.sum(Invoice.total_amount_cents)).filter(
            Invoice.payment_status == "pending",
            Invoice.payment_due_date < date.today(),
            Invoice.status == "finalized",
        ).scalar()
        return int(result or 0)
    
    def get_customer_count_by_status(self) -> dict:
        """Count customers by status."""
        results = self.db.query(
            Customer.status,
            func.count(Customer.id)
        ).group_by(Customer.status).all()
        
        return {r[0]: r[1] for r in results}
    
    def get_churn_rate(self, period_start: date, period_end: date) -> Decimal:
        """
        Churn rate = Lost customers / Starting customers.
        """
        # Customers at start of period
        starting = self.db.query(func.count(Subscription.id)).filter(
            Subscription.started_at < period_start,
            Subscription.status.in_(["active", "terminated"]),
        ).scalar() or 1
        
        # Customers churned during period
        churned = self.db.query(func.count(Subscription.id)).filter(
            Subscription.terminated_at >= period_start,
            Subscription.terminated_at <= period_end,
        ).scalar() or 0
        
        return Decimal(churned) / Decimal(starting) * 100
```

### API Endpoints

```python
# app/routers/analytics.py
@router.get("/mrr")
async def get_mrr():
    """Get current MRR."""
    return {"mrr_cents": service.get_mrr(), "currency": "USD"}

@router.get("/arr")
async def get_arr():
    """Get current ARR."""
    return {"arr_cents": service.get_arr(), "currency": "USD"}

@router.get("/revenue")
async def get_revenue(
    start_date: date,
    end_date: date,
    granularity: str = "month"
):
    """Get revenue by period."""
    return service.get_revenue_by_period(start_date, end_date, granularity)

@router.get("/overdue")
async def get_overdue():
    """Get overdue balance."""
    return {"overdue_cents": service.get_overdue_balance()}

@router.get("/churn")
async def get_churn(start_date: date, end_date: date):
    """Get churn rate for period."""
    return {"churn_rate_percent": service.get_churn_rate(start_date, end_date)}

@router.get("/dashboard")
async def get_dashboard():
    """Get all key metrics for dashboard."""
    return {
        "mrr_cents": service.get_mrr(),
        "arr_cents": service.get_arr(),
        "overdue_cents": service.get_overdue_balance(),
        "customer_counts": service.get_customer_count_by_status(),
    }
```

### Cached Aggregations (Performance)

For large datasets, pre-compute and cache metrics:

```python
# app/models/analytics_cache.py
class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"

    id = Column(UUIDType, primary_key=True)
    metric_name = Column(String(100), nullable=False)  # "mrr", "arr", etc.
    period = Column(Date, nullable=False)
    value_cents = Column(BigInteger)
    metadata = Column(JSON)
    
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

# Background job to refresh cache daily
async def refresh_analytics_cache():
    service = AnalyticsService(db)
    today = date.today()
    
    # Cache MRR
    mrr = service.get_mrr()
    db.merge(AnalyticsCache(
        metric_name="mrr",
        period=today,
        value_cents=int(mrr),
    ))
    # ... other metrics
```

---

## Files to Create

| File | Action |
|------|--------|
| `app/services/analytics_service.py` | Create |
| `app/routers/analytics.py` | Create |
| `app/models/analytics_cache.py` | Create (optional) |
| `app/tasks.py` | Add cache refresh |
| `tests/test_analytics.py` | Create |

---

## Acceptance Criteria

- [ ] MRR/ARR calculation
- [ ] Revenue by period (day/week/month)
- [ ] Overdue balance tracking
- [ ] Churn rate calculation
- [ ] Dashboard endpoint with all metrics
- [ ] Performance optimization (caching)
- [ ] 100% test coverage
