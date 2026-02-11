---
type: spec
title: "Webhooks Specification"
created: 2026-02-11
tags:
  - spec
  - webhooks
  - events
  - P1
related:
  - "[[00-overview]]"
  - "[[10-multi-tenancy]]"
---

# Webhooks Specification

## Overview

The webhook system delivers real-time notifications to external services when billing events occur. Organizations configure webhook endpoints with URLs and signature algorithms. Each event generates a webhook record that is delivered with retry logic and exponential backoff. Webhook payloads are signed for verification.

## Lago Reference

Sources: `app/models/webhook.rb`, `app/models/webhook_endpoint.rb` in the Lago codebase. Webhooks support JWT (RS256) and HMAC (SHA256) signature algorithms. Max 10 endpoints per organization.

## Entities

### Table: `webhook_endpoints`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique endpoint identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `url` | String(2048) | NOT NULL | Delivery URL |
| `signature_algo` | String(20) | NOT NULL, default "hmac" | hmac or jwt |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

**Constraints:**
- Unique: `(organization_id, url)` — no duplicate URLs per org
- Maximum 10 endpoints per organization

### Table: `webhooks`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique webhook identifier |
| `webhook_endpoint_id` | UUID | FK -> webhook_endpoints, NOT NULL, indexed | Target endpoint |
| `object_id` | UUID | nullable | Source object ID |
| `object_type` | String(50) | nullable | Source object type |
| `webhook_type` | String(100) | NOT NULL, indexed | Event type (e.g., "invoice.created") |
| `payload` | JSON | NOT NULL | Full event payload |
| `status` | String(20) | NOT NULL, default "pending" | pending, succeeded, or failed |
| `retries` | Integer | NOT NULL, default 0 | Number of delivery attempts |
| `http_status` | Integer | nullable | Last HTTP response status code |
| `response` | Text | nullable | Last HTTP response body (truncated) |
| `last_retried_at` | DateTime | nullable | Timestamp of last retry |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

## Signature Generation

### HMAC-SHA256

```
signature = HMAC-SHA256(organization.hmac_key, payload_json)
Header: X-Lago-Signature: <hex_encoded_signature>
```

### JWT-RS256

```
token = JWT.encode(payload_json, organization.rsa_private_key, "RS256")
Header: X-Lago-Signature: <jwt_token>
```

The receiving service verifies using the organization's public key.

## Retry Logic

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 30 seconds |
| 3 | 1 minute |
| 4 | 5 minutes |
| 5 | 30 minutes |
| 6 | 1 hour |
| 7 | 6 hours |
| 8+ | Exponential backoff (capped at 24 hours) |

- Max retries: configurable (default 3)
- After max retries: status set to `failed`
- Success: any 2xx HTTP response
- Failure: non-2xx response, timeout (30s), or connection error

## Retention

Webhook records are retained for 90 days, then automatically purged.

## Webhook Event Types

### Invoice Events
- `invoice.drafted` — Invoice created in draft status
- `invoice.created` — Invoice finalized
- `invoice.paid` — Invoice marked as paid
- `invoice.voided` — Invoice voided
- `invoice.payment_overdue` — Invoice past due date
- `invoice.generated` — Invoice PDF generated

### Payment Events
- `payment.created` — Payment initiated
- `payment.succeeded` — Payment succeeded
- `payment.failed` — Payment failed
- `payment.refunded` — Payment refunded

### Subscription Events
- `subscription.started` — Subscription activated
- `subscription.terminated` — Subscription terminated
- `subscription.canceled` — Subscription canceled

### Customer Events
- `customer.created` — Customer created
- `customer.updated` — Customer updated

### Credit Note Events
- `credit_note.created` — Credit note issued
- `credit_note.voided` — Credit note voided

### Wallet Events
- `wallet.created` — Wallet created
- `wallet.depleted` — Wallet balance reached zero
- `wallet.transaction.created` — Wallet top-up processed

### Event Events
- `event.error` — Event ingestion error

### Fee Events
- `fee.created` — Fee created (for pay-in-advance)

## API Endpoints

### Webhook Endpoints
- `POST /v1/webhook_endpoints` — Create endpoint
- `GET /v1/webhook_endpoints` — List endpoints
- `GET /v1/webhook_endpoints/{id}` — Get endpoint
- `PUT /v1/webhook_endpoints/{id}` — Update endpoint (URL, signature_algo)
- `DELETE /v1/webhook_endpoints/{id}` — Delete endpoint

### Webhooks
- `GET /v1/webhooks` — List webhooks (filter by status, webhook_type)
- `GET /v1/webhooks/{id}` — Get webhook details
- `POST /v1/webhooks/{id}/retry` — Manually retry a failed webhook
