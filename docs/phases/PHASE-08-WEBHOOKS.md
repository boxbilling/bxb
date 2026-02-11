# Phase 8: Webhooks

> **Priority:** HIGH | **Complexity:** Medium | **Est. Time:** 1 week

## Overview

Webhooks notify external systems of billing events (invoice created, payment received, subscription changed, etc.).

## Lago Reference

**Models:**
- `lago-api/app/models/webhook_endpoint.rb` — Customer-defined endpoints
- `lago-api/app/models/webhook.rb` — Individual webhook delivery attempts

**Services:** `lago-api/app/services/webhooks/`
```
webhooks/
├── base_service.rb
├── send_http_service.rb      # HTTP delivery
├── retry_service.rb          # Retry failed webhooks
├── invoices/                 # Invoice events
├── subscriptions/            # Subscription events
├── customers/                # Customer events
├── payments/                 # Payment events
└── ...
```

**Lago Webhook Events:**
```ruby
# From lago-api/app/services/webhooks/
- invoice.created
- invoice.payment_status_updated
- invoice.paid_credit_added
- customer.created
- customer.updated
- subscription.started
- subscription.terminated
- payment.created
- payment.failed
- credit_note.created
- wallet_transaction.created
- event.error
```

---

## Implementation Plan

### Step 1: Models

#### WebhookEndpoint Model
```python
# app/models/webhook_endpoint.py
class WebhookEndpoint(Base):
    """Customer-defined webhook endpoint."""
    __tablename__ = "webhook_endpoints"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    organization_id = Column(UUIDType, ForeignKey("organizations.id"), nullable=True)
    
    webhook_url = Column(String(2048), nullable=False)
    signature_algo = Column(String(20), default="hmac-sha256")  # hmac-sha256, hmac-sha512
    
    # Events to receive (empty = all)
    subscribed_events = Column(JSON, default=list)  # ["invoice.created", "payment.received"]
    
    # Status
    status = Column(String(20), default="active")  # active, inactive
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

#### Webhook Model (delivery log)
```python
# app/models/webhook.py
class WebhookStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class Webhook(Base):
    """Webhook delivery attempt."""
    __tablename__ = "webhooks"

    id = Column(UUIDType, primary_key=True, default=generate_uuid)
    webhook_endpoint_id = Column(UUIDType, ForeignKey("webhook_endpoints.id"))
    
    # Event info
    event_type = Column(String(100), nullable=False)  # invoice.created
    object_id = Column(UUIDType, nullable=False)      # Invoice ID, etc.
    object_type = Column(String(50), nullable=False)  # invoice, payment, etc.
    
    # Payload
    payload = Column(JSON, nullable=False)
    
    # Delivery status
    status = Column(String(20), default=WebhookStatus.PENDING.value)
    http_status = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    
    # Retry tracking
    retries = Column(Integer, default=0)
    last_retried_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

### Step 2: Webhook Events Enum

```python
# app/models/webhook_event.py
class WebhookEvent(str, Enum):
    # Invoices
    INVOICE_CREATED = "invoice.created"
    INVOICE_FINALIZED = "invoice.finalized"
    INVOICE_PAID = "invoice.paid"
    INVOICE_VOIDED = "invoice.voided"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
    
    # Payments
    PAYMENT_CREATED = "payment.created"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"
    
    # Subscriptions
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_STARTED = "subscription.started"
    SUBSCRIPTION_TERMINATED = "subscription.terminated"
    SUBSCRIPTION_CANCELED = "subscription.canceled"
    
    # Customers
    CUSTOMER_CREATED = "customer.created"
    CUSTOMER_UPDATED = "customer.updated"
    
    # Events (usage)
    EVENT_ERROR = "event.error"
```

### Step 3: Webhook Service

```python
# app/services/webhook_service.py
import hashlib
import hmac
import httpx
from datetime import datetime, timedelta

class WebhookService:
    RETRY_DELAYS = [60, 300, 900, 3600, 7200]  # 1m, 5m, 15m, 1h, 2h
    MAX_RETRIES = 5
    TIMEOUT = 30
    
    def __init__(self, db: Session):
        self.db = db
    
    def dispatch(
        self,
        event_type: WebhookEvent,
        object_id: UUID,
        object_type: str,
        payload: dict
    ):
        """Dispatch webhook to all subscribed endpoints."""
        endpoints = self._get_subscribed_endpoints(event_type)
        
        for endpoint in endpoints:
            webhook = Webhook(
                webhook_endpoint_id=endpoint.id,
                event_type=event_type.value,
                object_id=object_id,
                object_type=object_type,
                payload=self._build_payload(event_type, payload),
                status=WebhookStatus.PENDING.value,
            )
            self.db.add(webhook)
            self.db.commit()
            
            # Send async (in production, use background job)
            self._send_webhook(webhook, endpoint)
    
    def _build_payload(self, event_type: WebhookEvent, data: dict) -> dict:
        """Build webhook payload."""
        return {
            "webhook_type": event_type.value,
            "object_type": event_type.value.split(".")[0],
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def _sign_payload(self, payload: str, secret: str, algo: str = "hmac-sha256") -> str:
        """Generate webhook signature."""
        if algo == "hmac-sha256":
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha256
            ).hexdigest()
        elif algo == "hmac-sha512":
            return hmac.new(
                secret.encode(),
                payload.encode(),
                hashlib.sha512
            ).hexdigest()
        return ""
    
    def _send_webhook(self, webhook: Webhook, endpoint: WebhookEndpoint):
        """Send webhook HTTP request."""
        import json
        
        payload_str = json.dumps(webhook.payload)
        signature = self._sign_payload(payload_str, endpoint.secret or "")
        
        headers = {
            "Content-Type": "application/json",
            "X-Lago-Signature": signature,
            "X-Webhook-ID": str(webhook.id),
        }
        
        try:
            response = httpx.post(
                endpoint.webhook_url,
                content=payload_str,
                headers=headers,
                timeout=self.TIMEOUT,
            )
            
            webhook.http_status = response.status_code
            webhook.response_body = response.text[:1000]  # Truncate
            
            if 200 <= response.status_code < 300:
                webhook.status = WebhookStatus.SUCCEEDED.value
            else:
                self._schedule_retry(webhook)
                
        except Exception as e:
            webhook.response_body = str(e)
            self._schedule_retry(webhook)
        
        self.db.commit()
    
    def _schedule_retry(self, webhook: Webhook):
        """Schedule webhook retry with exponential backoff."""
        if webhook.retries >= self.MAX_RETRIES:
            webhook.status = WebhookStatus.FAILED.value
            return
        
        delay = self.RETRY_DELAYS[min(webhook.retries, len(self.RETRY_DELAYS) - 1)]
        webhook.retries += 1
        webhook.last_retried_at = datetime.utcnow()
        webhook.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
    
    def retry_pending(self):
        """Retry webhooks that are due."""
        due_webhooks = self.db.query(Webhook).filter(
            Webhook.status == WebhookStatus.PENDING.value,
            Webhook.next_retry_at <= datetime.utcnow(),
            Webhook.retries < self.MAX_RETRIES,
        ).all()
        
        for webhook in due_webhooks:
            endpoint = self.db.query(WebhookEndpoint).get(webhook.webhook_endpoint_id)
            if endpoint and endpoint.status == "active":
                self._send_webhook(webhook, endpoint)
```

### Step 4: Integration Points

Add webhook dispatch to existing services:

```python
# app/services/invoice_generation.py
def generate_invoice(...):
    invoice = ...  # Create invoice
    
    # Dispatch webhook
    webhook_service.dispatch(
        event_type=WebhookEvent.INVOICE_CREATED,
        object_id=invoice.id,
        object_type="invoice",
        payload=InvoiceResponse.model_validate(invoice).model_dump()
    )
    
    return invoice

# app/routers/payments.py - in webhook handler
def handle_webhook(...):
    ...
    if result.status == "succeeded":
        payment_repo.mark_succeeded(payment.id)
        
        # Dispatch webhook
        webhook_service.dispatch(
            event_type=WebhookEvent.PAYMENT_SUCCEEDED,
            object_id=payment.id,
            object_type="payment",
            payload=PaymentResponse.model_validate(payment).model_dump()
        )
```

### Step 5: API Endpoints

```python
# app/routers/webhook_endpoints.py
router = APIRouter()

@router.post("/", response_model=WebhookEndpointResponse)
async def create_webhook_endpoint(data: WebhookEndpointCreate, db: Session = Depends(get_db)):
    """Create a webhook endpoint."""
    ...

@router.get("/", response_model=list[WebhookEndpointResponse])
async def list_webhook_endpoints(db: Session = Depends(get_db)):
    """List all webhook endpoints."""
    ...

@router.get("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def get_webhook_endpoint(endpoint_id: UUID, db: Session = Depends(get_db)):
    """Get a webhook endpoint."""
    ...

@router.put("/{endpoint_id}", response_model=WebhookEndpointResponse)
async def update_webhook_endpoint(endpoint_id: UUID, data: WebhookEndpointUpdate, db: Session = Depends(get_db)):
    """Update a webhook endpoint."""
    ...

@router.delete("/{endpoint_id}", status_code=204)
async def delete_webhook_endpoint(endpoint_id: UUID, db: Session = Depends(get_db)):
    """Delete a webhook endpoint."""
    ...

# Webhook logs
@router.get("/{endpoint_id}/webhooks", response_model=list[WebhookResponse])
async def list_webhooks(endpoint_id: UUID, db: Session = Depends(get_db)):
    """List webhook delivery attempts for an endpoint."""
    ...

@router.post("/{endpoint_id}/webhooks/{webhook_id}/retry")
async def retry_webhook(endpoint_id: UUID, webhook_id: UUID, db: Session = Depends(get_db)):
    """Manually retry a failed webhook."""
    ...
```

### Step 6: Background Job for Retries

```python
# app/tasks.py (add to existing)
async def process_webhook_retries():
    """Background task to process webhook retries."""
    db = SessionLocal()
    try:
        service = WebhookService(db)
        service.retry_pending()
    finally:
        db.close()
```

---

## Database Migrations

```sql
CREATE TABLE webhook_endpoints (
    id UUID PRIMARY KEY,
    organization_id UUID,
    webhook_url VARCHAR(2048) NOT NULL,
    secret VARCHAR(255),
    signature_algo VARCHAR(20) DEFAULT 'hmac-sha256',
    subscribed_events JSONB DEFAULT '[]',
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE webhooks (
    id UUID PRIMARY KEY,
    webhook_endpoint_id UUID REFERENCES webhook_endpoints(id),
    event_type VARCHAR(100) NOT NULL,
    object_id UUID NOT NULL,
    object_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    http_status INTEGER,
    response_body TEXT,
    retries INTEGER DEFAULT 0,
    last_retried_at TIMESTAMP WITH TIME ZONE,
    next_retry_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_webhooks_status_retry ON webhooks(status, next_retry_at) 
    WHERE status = 'pending';
```

---

## Test Plan

```python
class TestWebhookService:
    def test_dispatch_to_subscribed_endpoints(self):
        """Webhook sent to endpoints subscribed to event."""
    
    def test_signature_generation(self):
        """Verify HMAC signature is correct."""
    
    def test_retry_on_failure(self):
        """Failed webhooks are scheduled for retry."""
    
    def test_max_retries(self):
        """Webhook marked failed after max retries."""
    
    def test_filter_by_subscribed_events(self):
        """Only send to endpoints subscribed to specific event."""

class TestWebhookEndpointsAPI:
    def test_create_endpoint(self):
        ...
    def test_list_endpoints(self):
        ...
    def test_update_endpoint(self):
        ...
    def test_delete_endpoint(self):
        ...
    def test_list_webhook_logs(self):
        ...
    def test_manual_retry(self):
        ...
```

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `app/models/webhook_endpoint.py` | Create |
| `app/models/webhook.py` | Create |
| `app/models/webhook_event.py` | Create |
| `app/services/webhook_service.py` | Create |
| `app/routers/webhook_endpoints.py` | Create |
| `app/schemas/webhook.py` | Create |
| `app/main.py` | Add router |
| `app/tasks.py` | Add retry task |
| `tests/test_webhooks.py` | Create |

---

## Acceptance Criteria

- [ ] Webhook endpoint CRUD API
- [ ] Webhook dispatch on billing events
- [ ] HMAC signature verification
- [ ] Retry logic with exponential backoff
- [ ] Webhook delivery logs
- [ ] Manual retry endpoint
- [ ] 100% test coverage
