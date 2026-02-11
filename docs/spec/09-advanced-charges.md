---
type: spec
title: "Advanced Charges Specification"
created: 2026-02-11
tags:
  - spec
  - charges
  - billable-metrics
  - filters
  - P2
related:
  - "[[00-overview]]"
  - "[[01-fee-model]]"
  - "[[08-subscription-lifecycle]]"
---

# Advanced Charges Specification

## Overview

This specification covers additional charge models, enhanced billable metric aggregation types, and the charge/metric filter system for conditional pricing. The current bxb implementation supports 5 charge models (standard, graduated, volume, package, percentage) and 4 aggregation types (count, sum, max, unique_count). Lago provides additional models and a powerful filtering system.

## Lago Reference

Sources: `app/models/charge.rb`, `app/models/billable_metric.rb` in the Lago codebase. Charge includes ChargePropertiesValidation concern. BillableMetric includes expression parsing and custom aggregation support.

## Additional Charge Models

### Graduated Percentage

Tiered percentage rates where each tier applies a different percentage to the usage amount within that tier's range.

```json
{
  "charge_model": "graduated_percentage",
  "properties": {
    "graduated_percentage_ranges": [
      {"from_value": 0, "to_value": 1000, "rate": "1.5", "flat_amount": "0.50"},
      {"from_value": 1001, "to_value": 10000, "rate": "1.0", "flat_amount": "0"},
      {"from_value": 10001, "to_value": null, "rate": "0.5", "flat_amount": "0"}
    ]
  }
}
```

**Calculation:**
For each tier, charge = `(usage_in_tier * rate / 100) + flat_amount`
Total = sum of all tier charges

### Custom Charge Model

Uses a custom aggregation expression to compute the charge amount. The expression can reference event properties and perform arithmetic operations.

```json
{
  "charge_model": "custom",
  "properties": {
    "custom_properties": {}
  }
}
```

Relies on the billable metric's `expression` field for aggregation logic.

### Dynamic Charge Model

Pricing is determined from event properties at ingestion time rather than pre-configured rates.

```json
{
  "charge_model": "dynamic",
  "properties": {}
}
```

The `unit_amount_cents` is extracted from each event's properties, allowing real-time pricing.

## Enhanced Billable Metrics

### Additional Aggregation Types

| Type | Code | Description |
|------|------|-------------|
| Weighted Sum | `weighted_sum_agg` | Sum weighted by time duration within the billing period |
| Latest | `latest_agg` | Most recent value of the field |
| Custom | `custom_agg` | Custom expression-based aggregation |

### Additional Fields on `billable_metrics` Table

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `recurring` | Boolean | NOT NULL, default false | Whether metric persists across billing periods |
| `rounding_function` | String(20) | nullable | round, ceil, or floor |
| `rounding_precision` | Integer | nullable | Decimal places for rounding |
| `expression` | Text | nullable | Custom aggregation expression |

### Weighted Sum Aggregation

Computes a time-weighted sum: each event's value is weighted by the duration it was active within the billing period. Useful for metrics like "average concurrent connections" or "storage GB-hours".

```
weighted_sum = Σ (value_i × duration_i / total_period_duration)
```

### Latest Aggregation

Returns the most recent value of the tracked field. Useful for metrics like "current storage usage" or "number of seats".

### Custom Aggregation

Uses the `expression` field to define arbitrary aggregation logic. The expression can reference event properties and use built-in functions.

### Rounding

After aggregation, the result can be rounded:
- `round`: Standard rounding to `rounding_precision` decimal places
- `ceil`: Round up
- `floor`: Round down

## Charge Filters

Charge filters enable conditional pricing based on event properties. For example, charge different rates for API calls by region or storage by tier.

### Table: `charge_filters`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique filter identifier |
| `charge_id` | UUID | FK -> charges, NOT NULL, indexed | Parent charge |
| `properties` | JSON | NOT NULL | Charge properties for matching events |
| `invoice_display_name` | String(255) | nullable | Custom display name on invoices |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Table: `charge_filter_values`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique value identifier |
| `charge_filter_id` | UUID | FK -> charge_filters, NOT NULL, indexed | Parent filter |
| `billable_metric_filter_id` | UUID | FK -> billable_metric_filters, NOT NULL | Filter definition |
| `values` | JSON | NOT NULL | Array of matching values |
| `created_at` | DateTime | NOT NULL | Creation timestamp |

### Table: `billable_metric_filters`

| Column | Type | Constraints | Description |
|--------|------|------------|-------------|
| `id` | UUID | PK | Unique filter identifier |
| `billable_metric_id` | UUID | FK -> billable_metrics, NOT NULL, indexed | Parent metric |
| `key` | String(255) | NOT NULL | Event property key to filter on |
| `values` | JSON | NOT NULL | Allowed values for this key |
| `created_at` | DateTime | NOT NULL | Creation timestamp |
| `updated_at` | DateTime | NOT NULL | Last update timestamp |

### Filter Evaluation

During invoice generation for a charge with filters:

1. Fetch all events for the billing period
2. For each charge filter:
   a. Match events where properties match all filter values
   b. Aggregate matched events using the billable metric
   c. Calculate fee using the filter's charge properties
   d. Create a separate Fee record for each filter
3. Unmatched events fall through to the default charge properties (if any)

## API Endpoints

### Enhanced Charge Creation
```json
{
  "plan_id": "uuid",
  "billable_metric_id": "uuid",
  "charge_model": "graduated_percentage",
  "properties": { ... },
  "filters": [
    {
      "invoice_display_name": "US Region API Calls",
      "properties": { "unit_price": "0.02" },
      "values": {
        "region": ["us-east-1", "us-west-2"]
      }
    }
  ]
}
```

### Enhanced Billable Metric Creation
```json
{
  "code": "storage_gb_hours",
  "name": "Storage GB-Hours",
  "aggregation_type": "weighted_sum_agg",
  "field_name": "gb_used",
  "recurring": true,
  "rounding_function": "ceil",
  "rounding_precision": 2,
  "filters": [
    { "key": "storage_tier", "values": ["standard", "premium", "archive"] }
  ]
}
```
