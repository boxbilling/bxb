# Plan: ClickHouse Integration for Events Engine

## Overview

Adapt Lago's ClickHouse-based events engine pattern for bxb. The core idea: **dual-write** events to both SQL (for API listing/get-by-ID) and ClickHouse (for high-performance aggregation), with ClickHouse as an **optional** backend toggled via `CLICKHOUSE_URL` env var. When unset, the current SQLite/PostgreSQL behavior is preserved — tests continue using SQLite with no ClickHouse dependency.

## Architecture (Adapted from Lago)

```
POST /v1/events/
    ↓
EventRepository.create()
    ├→ SQL (existing) — for API list/get/idempotency
    └→ ClickHouseEventStore.insert() — for aggregation (when configured)

UsageAggregationService
    ├→ CLICKHOUSE_URL set? → ClickHouseAggregationService (new)
    └→ CLICKHOUSE_URL unset? → current SQL-based aggregation (unchanged)
```

**Key Lago patterns we're adopting:**
- **Store factory** pattern (Lago's `StoreFactory`) → our `UsageAggregationService` delegates based on config
- **events_enriched table** schema with `decimal_value` column for pre-computed numeric values
- **ReplacingMergeTree** engine for automatic deduplication by `transaction_id`
- **Query-time deduplication** via `argMax(value, enriched_at)` as a safety net
- **Direct write** instead of Kafka (we don't have Kafka infrastructure)

## Implementation Steps

### Step 1: Add `clickhouse-connect` dependency and ClickHouse config

**Files:** `backend/pyproject.toml`, `backend/app/core/config.py`

- Add `clickhouse-connect>=0.8.0` to dependencies
- Add `CLICKHOUSE_URL: str = ""` to `Settings` (empty = disabled)
- Add helper `@property clickhouse_enabled` that returns `bool(self.CLICKHOUSE_URL)`

### Step 2: Create ClickHouse client module

**New file:** `backend/app/core/clickhouse.py`

- Singleton `get_clickhouse_client()` function that creates/caches a `clickhouse_connect.Client`
- Parses `CLICKHOUSE_URL` (format: `clickhouse://user:pass@host:port/database`)
- Returns `None` when `CLICKHOUSE_URL` is empty
- Table creation on first connection (events_raw table)

### Step 3: Create ClickHouse events table schema

**Table: `events_raw`** (adapted from Lago's `events_enriched`)

```sql
CREATE TABLE IF NOT EXISTS events_raw (
    organization_id String,
    transaction_id String,
    external_customer_id String,
    code String,
    timestamp DateTime64(3),
    properties String,          -- JSON string (ClickHouse JSON type)
    value Nullable(String),     -- extracted field_name value
    decimal_value Nullable(Decimal(38, 26)),  -- numeric conversion
    created_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(created_at)
PRIMARY KEY (organization_id, code, external_customer_id, toDate(timestamp))
ORDER BY (organization_id, code, external_customer_id, toDate(timestamp), timestamp, transaction_id)
```

Key design choices (from Lago):
- `ReplacingMergeTree` deduplicates by `transaction_id` within the ORDER BY automatically
- PRIMARY KEY prefix enables fast aggregation queries by `(org, code, customer, date)`
- `decimal_value` pre-computes the numeric field for SUM/MAX aggregations
- `properties` stored as JSON string for UNIQUE_COUNT and CUSTOM aggregations

### Step 4: Create ClickHouse event store

**New file:** `backend/app/services/clickhouse_event_store.py`

```python
class ClickHouseEventStore:
    """Write and query events in ClickHouse."""

    def insert(self, event_data: EventCreate, organization_id: UUID, field_name: str | None = None) -> None:
        """Insert a single event into ClickHouse."""

    def insert_batch(self, events: list[EventCreate], organization_id: UUID) -> None:
        """Insert a batch of events into ClickHouse."""

    def ensure_table(self) -> None:
        """Create events_raw table if it doesn't exist."""
```

- Uses `clickhouse_connect` client for inserts
- Extracts `value`/`decimal_value` from properties based on the billable metric's `field_name` at write time
- Batch insert uses `client.insert()` with column-oriented data for efficiency

### Step 5: Create ClickHouse aggregation service

**New file:** `backend/app/services/clickhouse_aggregation.py`

```python
class ClickHouseAggregationService:
    """Aggregation queries against ClickHouse (adapted from Lago's ClickhouseStore)."""

    def aggregate(self, external_customer_id, code, from_ts, to_ts,
                  aggregation_type, field_name, filters, org_id) -> UsageResult:
        """Run aggregation query and return UsageResult."""

    def get_events(self, external_customer_id, code, from_ts, to_ts, org_id) -> list[dict]:
        """Get raw events for DYNAMIC charge model."""
```

Aggregation queries (from Lago's `clickhouse_store.rb`):

| Type | ClickHouse SQL |
|------|---------------|
| **COUNT** | `SELECT count() FROM events_raw WHERE ...` |
| **SUM** | `SELECT sum(decimal_value) FROM events_raw WHERE ...` |
| **MAX** | `SELECT max(decimal_value) FROM events_raw WHERE ...` |
| **UNIQUE_COUNT** | `SELECT uniq(JSONExtractString(properties, :field)) FROM events_raw WHERE ...` |
| **LATEST** | `SELECT decimal_value FROM events_raw WHERE ... ORDER BY timestamp DESC LIMIT 1` |
| **WEIGHTED_SUM** | Window function query with cumulative sums and duration ratios (adapted from Lago's `WeightedSumQuery`) |
| **CUSTOM** | Fetch events, evaluate expression in Python (same as current) |

Property-based filters: `JSONExtractString(properties, :key) = :value`

### Step 6: Modify `UsageAggregationService` to delegate

**File:** `backend/app/services/usage_aggregation.py`

- Add a check at the top of `aggregate_usage_with_count()`:
  - If `settings.clickhouse_enabled`, delegate to `ClickHouseAggregationService`
  - Otherwise, use current SQL-based logic (unchanged)
- Same delegation in `get_customer_usage_summary()`

### Step 7: Modify `EventRepository` for dual-write

**File:** `backend/app/repositories/event_repository.py`

- In `create()` and `create_batch()`, after SQL commit, fire-and-forget insert to ClickHouse
- Only when `settings.clickhouse_enabled`
- ClickHouse insert failures are logged but don't fail the API request (eventual consistency)

### Step 8: Modify raw event queries for DYNAMIC charges

**Files:** `backend/app/services/invoice_generation.py`, `backend/app/services/usage_threshold_service.py`

- Where these services query `Event` model directly for raw event properties (DYNAMIC charge model), add ClickHouse-aware path
- When ClickHouse is enabled, query `events_raw` for properties instead of SQL

### Step 9: Tests

**New file:** `backend/tests/test_clickhouse.py`

All ClickHouse code will be tested by **mocking the clickhouse_connect client**. This means:
- No actual ClickHouse server needed for tests
- Mock `client.query()` and `client.insert()` to verify correct SQL and parameters
- Test the aggregation service returns correct `UsageResult` from mocked query results
- Test dual-write: verify ClickHouse insert is called after SQL commit
- Test fallback: verify ClickHouse code is skipped when `CLICKHOUSE_URL` is empty
- Test each aggregation type produces correct ClickHouse SQL

**Modified file:** `backend/tests/test_events.py`

- Add tests verifying dual-write behavior (mock ClickHouse client)
- Verify existing behavior unchanged when `CLICKHOUSE_URL` is empty

### Step 10: Update existing test files for coverage

Any services modified (invoice_generation, usage_threshold_service) need test updates to cover the new ClickHouse branches.

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add `clickhouse-connect` dependency |
| `backend/app/core/config.py` | Add `CLICKHOUSE_URL` setting |
| `backend/app/core/clickhouse.py` | **NEW** — Client singleton, table setup |
| `backend/app/services/clickhouse_event_store.py` | **NEW** — Write events to ClickHouse |
| `backend/app/services/clickhouse_aggregation.py` | **NEW** — Aggregation queries |
| `backend/app/services/usage_aggregation.py` | Delegate to ClickHouse when enabled |
| `backend/app/repositories/event_repository.py` | Dual-write to ClickHouse |
| `backend/app/services/invoice_generation.py` | ClickHouse path for DYNAMIC charges |
| `backend/app/services/usage_threshold_service.py` | ClickHouse path for DYNAMIC charges |
| `backend/tests/test_clickhouse.py` | **NEW** — Full test coverage |
| `backend/tests/test_events.py` | Additional dual-write tests |

## What We're NOT Doing

- **No Kafka** — Direct write from API to ClickHouse (we don't have Kafka infra)
- **No enrichment pipeline** — We enrich at write time (extract `decimal_value` from properties)
- **No separate enriched table** — Single `events_raw` table with pre-computed values
- **No ClickHouse migrations framework** — Table created programmatically on startup
- **No Alembic migration** — ClickHouse schema is managed separately
