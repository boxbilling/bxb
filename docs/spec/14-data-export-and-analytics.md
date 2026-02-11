---
type: spec
title: "Data Export and Analytics Specification"
created: 2026-02-11
tags:
  - spec
  - data-export
  - analytics
  - P3
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[10-multi-tenancy]]"
---

# Data Export and Analytics Specification

## Overview

The data export and analytics system provides CSV export capabilities with status tracking, analytics integration for event data, API/activity logging, and daily usage pre-aggregation. Lago uses ClickHouse for high-performance event analytics alongside PostgreSQL for transactional data.

## Lago Reference

Source: `app/models/data_export.rb` in the Lago codebase. DataExport supports csv format, status tracking (pending, processing, completed, failed), Active Storage file attachments, and 7-day expiration.

## Entities

### Table: `data_exports`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique export identifier |
| `organization_id` | UUID | FK -> organizations, NOT NULL, indexed | Owning organization |
| `resource_type` | String(50) | NOT NULL | invoices, credit_notes, fees, or events |
| `format` | String(10) | NOT NULL, default "csv" | Export format |
| `status` | String(20) | NOT NULL, default "pending" | pending, processing, completed, failed |
| `filters` | JSON | NOT NULL, default {} | Export filter criteria |
| `record_count` | Integer | nullable | Total records exported |
| `file_url` | String(2048) | nullable | Download URL (after completion) |
| `expires_at` | DateTime | nullable | File expiration (7 days after completion) |
| `started_at` | DateTime | nullable | Processing start time |
| `completed_at` | DateTime | nullable | Processing completion time |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

## Export Flow

1. **Request export**: API call specifying resource_type and filters
2. **Queue processing**: Export job queued as background task
3. **Status: processing**: Job begins, `started_at` set
4. **Data extraction**: Query database with filters, stream results to CSV
5. **File storage**: Upload CSV to object storage (S3/local)
6. **Status: completed**: Set `file_url`, `completed_at`, `expires_at` (now + 7 days)
7. **On failure**: Status set to `failed`
8. **Expiration**: Files automatically purged after 7 days

## Export Filter Examples

### Invoice Export
```json
{
  "customer_id": "uuid",
  "status": "finalized",
  "issuing_date_from": "2026-01-01",
  "issuing_date_to": "2026-01-31",
  "currency": "USD"
}
```

### Fee Export
```json
{
  "fee_type": "charge",
  "payment_status": "succeeded",
  "created_at_from": "2026-01-01",
  "created_at_to": "2026-01-31"
}
```

## Analytics (ClickHouse Integration)

For high-volume event analytics, a ClickHouse integration provides:

### Event Analytics
- Real-time event counts by metric code, customer, time window
- Usage trend analysis over configurable time ranges
- Top customers by usage volume
- Event ingestion rate monitoring

### Pre-Aggregation

Daily usage pre-aggregation improves query performance for billing calculations:

### Table: `daily_usages` (analytics store)

| Column | Type | Description |
|--------|------|-------------|
| `organization_id` | UUID | Organization |
| `customer_id` | UUID | Customer |
| `subscription_id` | UUID | Subscription |
| `billable_metric_id` | UUID | Metric |
| `date` | Date | Aggregation date |
| `usage_value` | Numeric | Pre-aggregated value |
| `events_count` | Integer | Event count for the day |
| `updated_at` | DateTime | Last aggregation time |

**Primary Key:** `(organization_id, customer_id, subscription_id, billable_metric_id, date)`

Pre-aggregation runs as a scheduled background job (daily or more frequently for near-real-time billing).

## Activity / API Logging

Track API requests for auditing and debugging:

### Table: `api_logs` (optional)

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID | Log entry ID |
| `organization_id` | UUID | Organization |
| `api_key_id` | UUID | API key used |
| `method` | String(10) | HTTP method |
| `path` | String(2048) | Request path |
| `status_code` | Integer | Response status |
| `request_body` | JSON | Request payload (redacted) |
| `response_body` | JSON | Response payload (truncated) |
| `ip_address` | String(45) | Client IP |
| `duration_ms` | Integer | Request duration |
| `created_at` | DateTime | Request timestamp |

API logs should have a configurable retention period (default 30 days).

## API Endpoints

### Data Exports
- `POST /v1/data_exports` — Create export request
- `GET /v1/data_exports` — List exports (filter by status, resource_type)
- `GET /v1/data_exports/{id}` — Get export status and download URL
- `GET /v1/data_exports/{id}/download` — Download export file (redirect to file_url)

### Analytics (future)
- `GET /v1/analytics/usage` — Usage analytics (aggregated by metric, customer, time)
- `GET /v1/analytics/revenue` — Revenue analytics (invoiced amounts over time)
- `GET /v1/analytics/events` — Event ingestion analytics
