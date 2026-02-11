# bxb Development Plan

> **bxb** - An open-source billing and metering platform inspired by Lago

## 1. Project Goals and Scope

### Vision
Build a modern, open-source billing platform that handles usage-based, subscription-based, and hybrid pricing models. bxb aims to be the developer-friendly alternative to Chargebee, Recurly, and Stripe Billing.

### Core Goals
1. **Developer Experience**: OpenAPI-first design with auto-generated clients
2. **Flexibility**: Support any pricing model (usage-based, subscription, hybrid)
3. **Self-Hosted Friendly**: Easy Docker deployment
4. **Quality First**: 100% test coverage, always
5. **Real-Time**: Event-driven architecture for instant metering
6. **Extensible**: Clean architecture for adding payment providers
7. **UCP Native**: Payment abstraction via Universal Checkout Protocol (https://ucp.dev)

### What Makes bxb Different from Lago

| Aspect | Lago | bxb |
|--------|------|-----|
| Backend | Ruby on Rails | Python/FastAPI |
| Type Safety | Limited | Full (Pydantic + mypy) |
| Testing | ~70% coverage | 100% coverage (enforced) |
| API Design | REST + GraphQL | REST (OpenAPI 3.1) |
| Async Support | Limited | Native async/await |
| Learning Curve | Steep | Moderate |

---

## 2. Tech Stack

### Backend
- **Language**: Python 3.12+
- **Framework**: FastAPI (async, OpenAPI native)
- **ORM**: SQLAlchemy 2.0 (async support)
- **Main Database**: Postgres
- **Streamed Events**: ClickHouse
- **Validation**: Pydantic v2
- **Migrations**: Alembic
- **Background Jobs**: arq (Redis-based async)
- **Package Manager**: uv

### Database
- **Primary**: PostgreSQL 16 (ACID transactions, JSONB)
- **Queue/Cache**: Redis (for arq background jobs)

### Frontend
- **Framework**: React 18+ with TypeScript
- **Build Tool**: Vite
- **UI Library**: Radix UI + Tailwind CSS
- **API Client**: Auto-generated from OpenAPI

### Testing & Quality
- **Testing**: pytest + pytest-cov
- **Linting**: ruff (replaces black, isort, flake8)
- **Type Checking**: mypy (strict mode)
- **Coverage**: 100% enforced via CI

### Infrastructure
- **CI/CD**: GitHub Actions
- **Containerization**: Docker
- **Local Dev**: Docker Compose

---

## 3. Core Entities (Based on Lago)

### Entity Relationship

```
┌─────────────────┐       ┌──────────────────┐
│   Organization  │──────<│     Customer     │
└─────────────────┘       └──────────────────┘
                                   │
                                   │ 1:N
                                   ▼
┌─────────────────┐       ┌──────────────────┐
│      Plan       │──────<│   Subscription   │
└─────────────────┘       └──────────────────┘
        │                          │
        │ N:M                      │ 1:N
        ▼                          ▼
┌─────────────────┐       ┌──────────────────┐
│ BillableMetric  │       │      Invoice     │
└─────────────────┘       └──────────────────┘
        │                          │
        │ 1:N                      │ 1:N
        ▼                          ▼
┌─────────────────┐       ┌──────────────────┐
│      Event      │       │       Fee        │
└─────────────────┘       └──────────────────┘
```

### Models

#### Customer
```python
class Customer(Base):
    __tablename__ = "customers"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

#### BillableMetric
```python
class AggregationType(str, Enum):
    COUNT = "count"
    SUM = "sum"
    MAX = "max"
    UNIQUE_COUNT = "unique_count"

class BillableMetric(Base):
    __tablename__ = "billable_metrics"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    aggregation_type: Mapped[AggregationType]
    field_name: Mapped[str | None] = mapped_column(String(255))  # For SUM, MAX
```

#### Plan
```python
class PlanInterval(str, Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"

class Plan(Base):
    __tablename__ = "plans"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    interval: Mapped[PlanInterval]
    amount_cents: Mapped[int] = mapped_column(default=0)  # Base subscription fee
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    trial_period_days: Mapped[int] = mapped_column(default=0)
```

#### Charge (connects Plan to BillableMetric)
```python
class ChargeModel(str, Enum):
    STANDARD = "standard"      # Fixed price per unit
    GRADUATED = "graduated"    # Tiered pricing
    VOLUME = "volume"          # Volume discounts
    PACKAGE = "package"        # Price per X units
    PERCENTAGE = "percentage"  # % of transaction

class Charge(Base):
    __tablename__ = "charges"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"))
    billable_metric_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("billable_metrics.id"))
    charge_model: Mapped[ChargeModel]
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Properties vary by model: amount, graduated_ranges, volume_ranges, etc.
```

#### Subscription
```python
class SubscriptionStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CANCELED = "canceled"
    TERMINATED = "terminated"

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(String(255), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    plan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("plans.id"))
    status: Mapped[SubscriptionStatus] = mapped_column(default=SubscriptionStatus.ACTIVE)
    started_at: Mapped[datetime]
    ending_at: Mapped[datetime | None]
    canceled_at: Mapped[datetime | None]
    billing_time: Mapped[str] = mapped_column(default="calendar")  # calendar or anniversary
```

#### Event (usage data)
```python
class Event(Base):
    __tablename__ = "events"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True)  # Idempotency key
    external_customer_id: Mapped[str] = mapped_column(String(255), index=True)
    code: Mapped[str] = mapped_column(String(255), index=True)  # Billable metric code
    timestamp: Mapped[datetime] = mapped_column(index=True)
    properties: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

#### Invoice
```python
class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    FINALIZED = "finalized"
    PAID = "paid"
    VOIDED = "voided"

class Invoice(Base):
    __tablename__ = "invoices"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    number: Mapped[str] = mapped_column(String(255), unique=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id"))
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id"))
    status: Mapped[InvoiceStatus] = mapped_column(default=InvoiceStatus.DRAFT)
    currency: Mapped[str] = mapped_column(String(3))
    amount_cents: Mapped[int] = mapped_column(default=0)
    taxes_amount_cents: Mapped[int] = mapped_column(default=0)
    total_amount_cents: Mapped[int] = mapped_column(default=0)
    issuing_date: Mapped[date]
    due_date: Mapped[date]
```

---

## 4. MVP Feature Set

### Must Have (Phase 1-2)
1. **Customer Management**
   - Create, read, update, delete customers
   - External ID for integration

2. **Billable Metrics**
   - Define what to meter (API calls, storage, users, etc.)
   - Aggregation types: COUNT, SUM, MAX, UNIQUE_COUNT

3. **Plans & Charges**
   - Create plans with base fees
   - Attach charges (usage-based pricing)
   - Standard charge model (price per unit)

4. **Subscriptions**
   - Subscribe customers to plans
   - Handle billing periods

5. **Event Ingestion**
   - Accept usage events via API
   - Idempotency via transaction_id
   - Timestamp support

6. **Usage Aggregation**
   - Aggregate events per billing period
   - Support all aggregation types

7. **Invoice Generation**
   - Calculate subscription fees
   - Calculate usage fees
   - Generate invoices

---

## 5. Development Phases

### Phase 1: Foundation (Week 1-2) ✅
- [x] Project setup with FastAPI + React
- [x] CI/CD with 100% coverage enforcement
- [x] Docker Compose for local dev
- [ ] Database schema (Customer, BillableMetric)
- [ ] Basic CRUD APIs for Customer

### Phase 2: Core Billing (Week 3-4) ✅
- [x] BillableMetric API
- [x] Plan & Charge models
- [x] Plan API
- [x] Subscription model and API

### Phase 3: Event Ingestion (Week 5-6) ✅
- [x] Event model and API
- [x] Batch event ingestion
- [x] Idempotency handling
- [x] Event validation

### Phase 4: Aggregation Engine (Week 7-8) ✅
- [x] Usage aggregation service
- [x] All aggregation types
- [x] Billing period calculations
- [x] Background job for aggregation

### Phase 5: Invoicing (Week 9-10) ✅
- [x] Invoice generation
- [x] Fee calculation
- [x] Invoice finalization
- [ ] PDF generation (optional)

### Phase 6: Payments (Week 11-12) ✅
- [x] Payment provider abstraction (Stripe + UCP + Manual, extensible for PayPal, Adyen, etc.)
- [x] Checkout session management
- [x] Payment webhook handling
- [x] Invoice status updates on payment
- [x] UCP (Universal Commerce Protocol) integration - https://ucp.dev

### Phase 7: Advanced Charges (Week 13-14)
- [ ] Graduated pricing
- [ ] Volume pricing
- [ ] Package pricing

### Phase 8: Polish (Week 15-16)
- [ ] Admin UI improvements
- [ ] API documentation
- [ ] Performance optimization
- [ ] Security audit

---

## 6. API Design

Following Lago's API patterns for familiarity.

### Customers
```
POST   /v1/customers           Create customer
GET    /v1/customers           List customers
GET    /v1/customers/:id       Get customer
PUT    /v1/customers/:id       Update customer
DELETE /v1/customers/:id       Delete customer
```

### Billable Metrics
```
POST   /v1/billable_metrics    Create metric
GET    /v1/billable_metrics    List metrics
GET    /v1/billable_metrics/:code  Get metric
PUT    /v1/billable_metrics/:code  Update metric
DELETE /v1/billable_metrics/:code  Delete metric
```

### Plans
```
POST   /v1/plans               Create plan
GET    /v1/plans               List plans
GET    /v1/plans/:code         Get plan
PUT    /v1/plans/:code         Update plan
DELETE /v1/plans/:code         Delete plan
```

### Subscriptions
```
POST   /v1/subscriptions       Create subscription
GET    /v1/subscriptions       List subscriptions
GET    /v1/subscriptions/:id   Get subscription
DELETE /v1/subscriptions/:id   Terminate subscription
```

### Events
```
POST   /v1/events              Send event
POST   /v1/events/batch        Send batch events
GET    /v1/events              List events (for debugging)
```

### Invoices
```
GET    /v1/invoices            List invoices
GET    /v1/invoices/:id        Get invoice
POST   /v1/invoices/:id/finalize  Finalize invoice
```

---

## 7. Testing Strategy

### 100% Coverage Requirement

Every line of code must be tested. No exceptions.

```bash
# Run locally before pushing
make test-cov
```

### Test Structure
```
tests/
├── conftest.py           # Fixtures (db, client)
├── test_api.py           # Basic health checks
├── test_customers.py     # Customer API tests
├── test_billable_metrics.py
├── test_plans.py
├── test_subscriptions.py
├── test_events.py
├── test_invoices.py
└── test_services/
    ├── test_aggregation.py
    └── test_billing.py
```

### Test Categories
1. **Unit Tests**: Services, utilities, pure functions
2. **Integration Tests**: API endpoints with database
3. **Edge Cases**: Error handling, validation

---

## 8. Directory Structure

```
bxb/
├── backend/
│   ├── app/
│   │   ├── alembic/          # Database migrations
│   │   │   └── versions/
│   │   ├── core/
│   │   │   ├── config.py     # Settings
│   │   │   ├── database.py   # DB connection
│   │   │   └── deps.py       # Dependencies
│   │   ├── models/           # SQLAlchemy models
│   │   │   ├── customer.py
│   │   │   ├── billable_metric.py
│   │   │   ├── plan.py
│   │   │   ├── subscription.py
│   │   │   ├── event.py
│   │   │   └── invoice.py
│   │   ├── repositories/     # Data access
│   │   ├── routers/          # API endpoints
│   │   │   ├── customers.py
│   │   │   ├── billable_metrics.py
│   │   │   ├── plans.py
│   │   │   ├── subscriptions.py
│   │   │   ├── events.py
│   │   │   └── invoices.py
│   │   ├── schemas/          # Pydantic models
│   │   ├── services/         # Business logic
│   │   │   ├── aggregation.py
│   │   │   ├── billing.py
│   │   │   └── invoice.py
│   │   └── main.py
│   ├── tests/
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── lib/
│   │   │   └── schema.d.ts   # Generated from OpenAPI
│   │   └── App.tsx
│   └── package.json
├── docker-compose.yml
├── Makefile
└── README.md
```

---

## 9. Commit Strategy

**Commit after each logical unit of work.** Each commit should:

1. Pass all tests (100% coverage)
2. Pass linting
3. Be deployable

### Commit Message Format
```
feat(customers): add customer CRUD API

- Add Customer model with migrations
- Add CustomerRepository
- Add /v1/customers endpoints
- Add tests (100% coverage)
```

### Phase Commits
- End of each phase = git tag (e.g., `v0.1.0-phase1`)
- Squash merge to main

---

## 10. Next Steps

1. **Create Customer model** with migrations
2. **Implement Customer API** with full CRUD
3. **Write tests** to 100% coverage
4. **Commit and push**

Let's build this! 🚀
