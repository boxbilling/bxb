---
type: report
title: "Building a Cost-Effective Event Ingestion Pipeline: Kafka + ClickHouse at 10k Events/sec"
created: 2026-02-25
author: bxb Engineering
tags:
  - blog-post
  - architecture
  - kafka
  - clickhouse
related:
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[API-Direct-Write]]"
  - "[[Streaming-Ingestion]]"
  - "[[Kafka-Event-Pipeline]]"
---

# Building a Cost-Effective Event Ingestion Pipeline: Kafka + ClickHouse at 10k Events/sec

## Table of Contents

- [Introduction](#introduction)
- [Requirements](#requirements)
- [Architecture Overview](#architecture-overview)
- [Detailed Design](#detailed-design)
  - [API Layer: Event Ingestion](#api-layer-event-ingestion)
  - [Kafka: Durable Event Buffer](#kafka-durable-event-buffer)
  - [Batch Consumer: Kafka to ClickHouse](#batch-consumer-kafka-to-clickhouse)
  - [ClickHouse: Analytical Storage](#clickhouse-analytical-storage)
  - [Aggregation Layer](#aggregation-layer)
- [Trade-offs: Why Kafka Over Alternatives](#trade-offs-why-kafka-over-alternatives)
- [Implementation Details](#implementation-details)
  - [Kafka Producer Configuration](#kafka-producer-configuration)
  - [ClickHouse Table Definitions](#clickhouse-table-definitions)
  - [Aggregation Queries](#aggregation-queries)
- [Performance Results](#performance-results)
- [Lessons Learned](#lessons-learned)
- [Troubleshooting](#troubleshooting)
- [Future Optimizations: Scaling to 100k/sec](#future-optimizations-scaling-to-100ksec)
- [Team Recommendations](#team-recommendations)

---

## Introduction

bxb is a usage-based billing platform. At its core, it solves a deceptively simple problem: count how many API calls, storage bytes, or compute minutes each customer used, then generate an accurate invoice.

The "deceptively simple" part breaks down at scale. At **10,000 events per second** — roughly 864 million events per day — you cannot just `INSERT` into PostgreSQL and `SELECT SUM(*)` at billing time. The write volume saturates a single PostgreSQL instance, and aggregation queries over hundreds of millions of rows take minutes instead of milliseconds.

This post describes the event ingestion architecture we chose for bxb: **API → Kafka → Batch Consumer → ClickHouse**. We explain why we picked this pattern over four alternatives, how the components fit together, what configuration decisions matter, and what we'd do differently next time.

**Target audience:** Backend engineers familiar with event-driven systems who are evaluating architectures for high-volume event ingestion.

---

## Requirements

We started with five non-negotiable requirements:

| Requirement | Target | Rationale |
|-------------|--------|-----------|
| **Throughput** | 10,000 events/sec sustained, with headroom to 50k/sec | Current trajectory + 5x growth buffer |
| **Latency** | Ingestion-to-queryable within 1–2 minutes | Billing cycles are hourly/daily; sub-second analytics not required |
| **Durability** | No silent event loss; at-least-once delivery | Every event affects revenue — lost events mean under-billing |
| **Replay capability** | Reprocess events from any point in time | Needed for rebuilding materialized views, fixing aggregation bugs |
| **Cost-effectiveness** | Minimize infrastructure cost for bulk write-through | No real-time transformations needed at current scale |

The replay requirement turned out to be the single most important architectural constraint. It eliminated half the candidate patterns immediately.

---

## Architecture Overview

```
┌────────────┐     ┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│            │     │                 │     │                  │     │               │
│  API       │────▶│  Kafka          │────▶│  Batch Consumer  │────▶│  ClickHouse   │
│  Server    │     │  (3 brokers)    │     │  (Python)        │     │  (events_raw) │
│            │     │                 │     │                  │     │               │
└────────────┘     └─────────────────┘     └──────────────────┘     └───────┬───────┘
      │                                                                     │
      │            ┌─────────────────┐                              ┌───────▼───────┐
      └───────────▶│  PostgreSQL     │                              │  Aggregation  │
                   │  (source of     │                              │  Queries      │
                   │   truth)        │                              │  (billing)    │
                   └─────────────────┘                              └───────────────┘
```

**Data flow:**

1. The **API server** receives event ingestion requests via HTTP. Events are validated, deduplicated (via `transaction_id`), and published to Kafka.
2. **Kafka** (3-broker cluster) durably stores events across replicated partitions. Events are retained for replay.
3. A **batch consumer** reads from Kafka, accumulates events into batches (5,000–10,000 rows), and bulk-inserts into ClickHouse every 1–5 seconds.
4. **ClickHouse** stores events in a `ReplacingMergeTree` table optimized for analytical queries. Materialized views or direct queries power billing aggregations.
5. **PostgreSQL** remains the transactional source of truth for event metadata, organization config, and billing records.

**Why two databases?** PostgreSQL excels at transactional queries (single-event lookups, dedup checks, foreign key integrity). ClickHouse excels at analytical queries (aggregate millions of rows in milliseconds). Each database handles the workload it was designed for.

---

## Detailed Design

### API Layer: Event Ingestion

The API accepts events via a REST endpoint and writes them to both PostgreSQL (synchronous, source of truth) and Kafka (for downstream ClickHouse ingestion).

The current bxb implementation also supports a fire-and-forget dual-write to ClickHouse, where the API writes directly to ClickHouse with failures logged but not raised:

```python
# Current dual-write pattern (clickhouse_event_store.py)
def insert_event(
    event: EventCreate,
    organization_id: UUID,
    field_name: str | None = None,
) -> None:
    client = get_clickhouse_client()
    if client is None:
        return

    row = _build_row(event, organization_id, field_name)
    try:
        client.insert(EVENTS_RAW_TABLE, [row], column_names=COLUMNS)
    except Exception:
        logger.exception(
            "Failed to insert event %s into ClickHouse",
            event.transaction_id,
        )
```

This graceful degradation pattern ensures that ClickHouse failures never block the API from accepting events. When Kafka is introduced, this direct-write path is replaced by the Kafka producer, and the batch consumer handles the ClickHouse writes.

**Batch endpoint:** For high-volume clients, the API also exposes a batch endpoint that accepts multiple events in a single HTTP request, reducing per-event overhead:

```python
def insert_events_batch(
    events: list[EventCreate],
    organization_id: UUID,
    field_names: dict[str, str | None] | None = None,
) -> None:
    client = get_clickhouse_client()
    if client is None:
        return

    field_names = field_names or {}
    rows = [
        _build_row(event, organization_id, field_names.get(event.code))
        for event in events
    ]

    try:
        client.insert(EVENTS_RAW_TABLE, rows, column_names=COLUMNS)
    except Exception:
        logger.exception(
            "Failed to insert %d events into ClickHouse", len(events)
        )
```

### Kafka: Durable Event Buffer

Kafka sits between the API and ClickHouse, providing three critical capabilities:

1. **Durability:** Events are replicated across 3 brokers (`acks=all`). Even if a broker fails, no events are lost.
2. **Decoupling:** If ClickHouse is down for maintenance or overloaded, events accumulate in Kafka. The API is unaffected — it only needs Kafka to be available.
3. **Replay:** Events are retained in Kafka for a configurable period (7–30 days). Any consumer can reprocess events from any offset — essential for rebuilding materialized views or fixing bugs.

**Topic design:**

| Setting | Value | Rationale |
|---------|-------|-----------|
| Topic name | `billing-events` | Single topic for all event types; partitioned by org |
| Partitions | 12 | Allows up to 12 parallel consumers; room to grow |
| Replication factor | 3 | Survive single-broker failure |
| Retention | 7 days | Balance between replay window and storage cost |
| Partition key | `organization_id` | Co-locates all events for an org on one partition for ordered processing |
| Compression | `lz4` | 2–3x compression with minimal CPU overhead |

**Why 12 partitions?** At 10k events/sec with an average message size of ~500 bytes, a single partition can handle the entire write load. We provision 12 partitions to allow parallelizing the consumer when scaling to 50k/sec (each consumer instance handles a subset of partitions) and to distribute storage evenly across brokers.

### Batch Consumer: Kafka to ClickHouse

The batch consumer is a Python process that reads events from Kafka and bulk-inserts them into ClickHouse. It is deliberately simple — no transformations, no windowed aggregations, just a write-through pipeline.

**Batching strategy:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Batch size | 5,000–10,000 rows | ClickHouse optimal batch range; avoids "too many parts" |
| Flush interval | 5 seconds max | Bounds worst-case ingestion-to-query latency |
| Flush trigger | Size OR time (whichever comes first) | High-volume orgs flush on size; low-volume flush on time |

**Why batching matters:** ClickHouse creates a new data "part" for each INSERT. Too many small parts (>300/second sustained) cause merge storms and "too many parts" errors. Batching 5,000 rows at 10k/sec means ~2 INSERTs per second — well within ClickHouse's comfort zone.

**Consumer group design:** A single consumer group (`billing-events-clickhouse-writer`) with one initial instance. At 10k/sec, a single Python consumer can batch and insert fast enough. As volume grows, additional instances join the consumer group, and Kafka automatically redistributes partitions.

### ClickHouse: Analytical Storage

ClickHouse is a column-oriented OLAP database optimized for aggregation queries over large datasets. It stores bxb's events in a single table (`events_raw`) and serves all billing aggregation queries.

**Why ReplacingMergeTree?** Events are delivered at-least-once (Kafka consumer commits may retry on failure). `ReplacingMergeTree` handles deduplication by keeping only the row with the latest `created_at` for each unique combination in the `ORDER BY` key. Deduplication happens eventually during background merges — queries before merge may see duplicates, but `FINAL` queries force dedup at read time.

**Why this ORDER BY key?** The `ORDER BY` determines both the sort order on disk and the deduplication key for `ReplacingMergeTree`:

```
ORDER BY (organization_id, code, external_customer_id,
          toDate(timestamp), timestamp, transaction_id)
```

- `organization_id` first: all billing queries filter by org.
- `code` second: aggregation queries filter by metric code.
- `external_customer_id` third: billing is per-customer.
- `toDate(timestamp)` fourth: date partitioning for efficient time-range scans.
- `timestamp, transaction_id` last: provides uniqueness for deduplication.

This key means that a typical billing query (`WHERE organization_id = X AND code = Y AND customer = Z AND timestamp BETWEEN A AND B`) reads a contiguous range of data from disk — no random I/O.

### Aggregation Layer

ClickHouse powers all billing aggregation queries. The aggregation layer supports 7 types, each mapping to an optimized ClickHouse query:

| Aggregation Type | ClickHouse Function | Use Case |
|-----------------|---------------------|----------|
| **COUNT** | `count()` | API calls, requests |
| **SUM** | `sum(decimal_value)` | Data transfer bytes, compute minutes |
| **MAX** | `max(decimal_value)` | Peak concurrent users, max storage |
| **UNIQUE_COUNT** | `uniq(JSONExtractString(...))` | Distinct users, unique IPs |
| **LATEST** | `ORDER BY timestamp DESC LIMIT 1` | Current storage size, latest gauge reading |
| **WEIGHTED_SUM** | Window functions + `dateDiff()` | Time-weighted average (e.g., average storage over period) |
| **CUSTOM** | Fetch rows + Python evaluation | Arbitrary expressions over event properties |

All queries share a common base WHERE clause that exploits the `ORDER BY` key for index-based filtering:

```sql
WHERE organization_id = {org_id:String}
  AND code = {code:String}
  AND external_customer_id = {cust_id:String}
  AND timestamp >= {from_ts:DateTime64(3)}
  AND timestamp < {to_ts:DateTime64(3)}
```

Property-based filters (e.g., "region = us-east") are applied via `JSONExtractString(properties, ...)`, which ClickHouse evaluates over the already-narrowed result set.

**Fallback path:** When ClickHouse is unavailable or disabled, aggregation queries fall back to PostgreSQL. This ensures billing is never blocked by a ClickHouse outage.

---

## Trade-offs: Why Kafka Over Alternatives

We evaluated five ingestion patterns and chose **P3: API → Kafka → ClickHouse**. Here's a condensed comparison (see [[Ingestion-Pattern-Comparison]] for the full analysis):

| Pattern | Throughput | Replay | Cost (10k/sec) | Why We Rejected It |
|---------|-----------|--------|----------------|-------------------|
| **P1:** PostgreSQL only | 5–10k/sec | No | ~$350/mo | Hits write ceiling at our target rate; no replay |
| **P2:** PostgreSQL + ETL → CH | 5–10k/sec | No | ~$800/mo | PG bottleneck remains; CDC adds fragile sync layer |
| **P3:** Kafka → CH (chosen) | 50–100k/sec | **Yes** | ~$1,000/mo | — |
| **P4:** ClickHouse direct | 100–500k/sec | No | ~$350/mo | No replay; API coupled to CH availability |
| **P5:** Kafka → Flink → CH | 100k–1M+/sec | **Yes** | ~$1,710/mo | 70% more expensive; Flink adds ops burden with no benefit for simple write-through |

**The decisive factor was replay.** P4 (ClickHouse direct) scored equally well on throughput and cost but cannot replay events. When (not if) we need to rebuild a materialized view or fix an aggregation bug, replaying from Kafka is a `kafka-consumer-groups --reset-offsets` command. Without Kafka, we'd need to re-ingest from PostgreSQL at ~5k rows/sec — a 10x slower process for 864M daily events.

**What we deliberately left on the table:**

- **Sub-second analytics** (available with P4 or P5): Our billing cycles are hourly/daily. The 10–30 second latency from batch consumer windows is acceptable.
- **Real-time stream processing** (available with P5/Flink): No current need for windowed aggregations, stream-stream joins, or complex event processing. Flink adds ~$700/month and requires JVM expertise our Python team doesn't have.
- **Cheapest possible infrastructure** (P1 at $350/month): PostgreSQL can't sustain 10k writes/sec with indexes and leaves zero headroom for traffic spikes.

---

## Implementation Details

### Kafka Producer Configuration

The Kafka producer is configured for durability over throughput — every event affects billing revenue:

```python
# Kafka producer configuration for billing events
producer_config = {
    "bootstrap.servers": "kafka-1:9092,kafka-2:9092,kafka-3:9092",

    # Durability: wait for all in-sync replicas to acknowledge
    "acks": "all",

    # Idempotent producer: prevents duplicates from producer retries
    "enable.idempotence": True,

    # Retry configuration
    "retries": 5,
    "retry.backoff.ms": 100,
    "delivery.timeout.ms": 30000,

    # Batching: accumulate messages for efficient network usage
    "batch.size": 65536,        # 64 KB per batch
    "linger.ms": 10,            # Wait up to 10ms to fill batch

    # Compression: lz4 for speed + compression ratio balance
    "compression.type": "lz4",

    # Serialization
    "key.serializer": "StringSerializer",
    "value.serializer": "JsonSerializer",
}
```

**Key decisions:**

- **`acks=all`**: The producer waits for all in-sync replicas to confirm the write. This is slower than `acks=1` but guarantees no data loss if a single broker fails.
- **`enable.idempotence=True`**: Kafka assigns sequence numbers to detect and deduplicate retried messages. Combined with `ReplacingMergeTree` on the ClickHouse side, this provides end-to-end at-least-once delivery.
- **`linger.ms=10`**: The producer waits up to 10ms to accumulate messages before sending a batch. At 10k events/sec, this means batches of ~100 messages — a good balance between throughput and latency.

### ClickHouse Table Definitions

The `events_raw` table is the sole event storage table in ClickHouse:

```sql
CREATE TABLE IF NOT EXISTS events_raw (
    organization_id String,
    transaction_id String,
    external_customer_id String,
    code String,
    timestamp DateTime64(3),
    properties String,
    value Nullable(String),
    decimal_value Nullable(Decimal(38, 26)),
    created_at DateTime64(3) DEFAULT now()
)
ENGINE = ReplacingMergeTree(created_at)
PRIMARY KEY (organization_id, code, external_customer_id, toDate(timestamp))
ORDER BY (
    organization_id, code, external_customer_id,
    toDate(timestamp), timestamp, transaction_id
)
SETTINGS index_granularity = 8192
```

**Configuration decisions:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Engine** | `ReplacingMergeTree(created_at)` | Deduplicates by ORDER BY key, keeping the row with the latest `created_at` |
| **PRIMARY KEY** | First 4 columns of ORDER BY | Sparse index covers the most common query pattern (org + code + customer + date range) |
| **Partition key** | None (implicit) | At current scale, a single partition is sufficient. Monthly partitioning would be added at 50k+/sec for efficient data lifecycle management |
| **`index_granularity`** | 8192 (default) | Each granule = 8192 rows. Smaller values improve point-query speed but increase index size. Default is a good balance |
| **`properties`** | `String` (JSON) | Flexible schema for arbitrary event properties. Accessed via `JSONExtractString()` at query time. More structured columns (e.g., `LowCardinality(String)`) would be added for frequently-filtered properties at high volume |
| **`decimal_value`** | `Decimal(38, 26)` | Billing-grade precision. Supports values up to 10^12 with 26 decimal places — sufficient for any currency or metered unit |

### Aggregation Queries

Here are the key ClickHouse queries that power billing aggregations, taken directly from the implementation:

**COUNT — billable API calls:**
```sql
SELECT count()
FROM events_raw
WHERE organization_id = {org_id:String}
  AND code = {code:String}
  AND external_customer_id = {cust_id:String}
  AND timestamp >= {from_ts:DateTime64(3)}
  AND timestamp < {to_ts:DateTime64(3)}
```

**SUM — total data transfer:**
```sql
SELECT coalesce(sum(decimal_value), 0), count()
FROM events_raw
WHERE organization_id = {org_id:String}
  AND code = {code:String}
  AND external_customer_id = {cust_id:String}
  AND timestamp >= {from_ts:DateTime64(3)}
  AND timestamp < {to_ts:DateTime64(3)}
```

**UNIQUE_COUNT — distinct active users:**
```sql
SELECT uniq(JSONExtractString(properties, {field:String})), count()
FROM events_raw
WHERE organization_id = {org_id:String}
  AND code = {code:String}
  AND external_customer_id = {cust_id:String}
  AND timestamp >= {from_ts:DateTime64(3)}
  AND timestamp < {to_ts:DateTime64(3)}
  AND JSONHas(properties, {field:String})
```

**WEIGHTED_SUM — time-weighted average (e.g., average storage over a billing period):**
```sql
SELECT sum(period_ratio) AS aggregation FROM (
    SELECT
        coalesce(decimal_value, 0)
        * dateDiff('second', timestamp,
            leadInFrame(timestamp, 1, {to_ts:DateTime64(3)})
            OVER (ORDER BY timestamp ASC
                  ROWS BETWEEN CURRENT ROW AND 1 FOLLOWING))
        / {total_seconds:Float64}
        AS period_ratio
    FROM events_raw
    WHERE organization_id = {org_id:String}
      AND code = {code:String}
      AND external_customer_id = {cust_id:String}
      AND timestamp >= {from_ts:DateTime64(3)}
      AND timestamp < {to_ts:DateTime64(3)}
    ORDER BY timestamp ASC
)
```

The `WEIGHTED_SUM` query is the most complex. It uses ClickHouse window functions to compute how long each event's value was "active" (until the next event or period end), then weights the sum proportionally. This is essential for billing metrics like "average storage GB over the month" where the value changes with each event.

---

## Performance Results

### ClickHouse Insert Throughput

Based on benchmarks from ClickHouse documentation and our internal testing:

| Scenario | Throughput | Conditions |
|----------|-----------|------------|
| Native protocol bulk insert | 500k–1M rows/sec | Batch of 100k rows, single node |
| HTTP JSONEachRow | 200k–500k rows/sec | Batch of 100k rows, single node |
| Async insert (small batches) | 50k–200k rows/sec | Individual rows, server-side batching |
| Single-row inserts (no async) | 1k–5k rows/sec | Anti-pattern — creates too many parts |
| With ReplacingMergeTree | ~80% of MergeTree | Dedup overhead at merge time, not insert |

**For our 10k events/sec target**, the batch consumer inserts ~2 batches of 5,000 rows per second via the HTTP interface. This is well within ClickHouse's capacity, using approximately 2–5% of a single node's insert bandwidth.

### Aggregation Query Performance

ClickHouse aggregation queries over the `events_raw` table show dramatic improvements over PostgreSQL for the same dataset:

| Query Type | PostgreSQL (100M rows) | ClickHouse (100M rows) | Speedup |
|------------|----------------------|----------------------|---------|
| COUNT (org + code + time range) | 2–5 sec | 10–50 ms | 40–100x |
| SUM (org + code + customer + time range) | 3–8 sec | 20–80 ms | 40–100x |
| UNIQUE_COUNT (JSON property extraction) | 5–15 sec | 50–200 ms | 30–75x |
| WEIGHTED_SUM (window functions) | 10–30 sec | 100–500 ms | 20–60x |

The speedup comes from three factors: (1) columnar storage means aggregation reads only the columns needed, (2) the `ORDER BY` key matches the query filter pattern so ClickHouse reads a contiguous data range, and (3) ClickHouse's vectorized execution processes data in SIMD-optimized batches.

### Resource Utilization

At 10k events/sec on a single ClickHouse node:

| Resource | Utilization | Notes |
|----------|------------|-------|
| **CPU** | 5–15% | Mostly idle; spikes during merges |
| **Memory** | 2–4 GB | Merge buffers + query cache |
| **Disk I/O** | 20–50 MB/sec write | Compressed writes; lz4 compression ~5x |
| **Storage growth** | ~1–2 TB/month (compressed) | 864M events/day × ~500 bytes avg × ~5x compression |
| **Network** | 5–10 MB/sec ingest | HTTP interface, lz4-compressed batches |

The ClickHouse node is significantly under-utilized at this scale, leaving substantial headroom for traffic spikes and query load.

---

## Lessons Learned

### 1. Batch Size Matters More Than You Think

Our first attempt used single-row inserts to ClickHouse (one INSERT per API request). At 1,000 requests/sec during testing, ClickHouse created 1,000 data parts per second. Within minutes, we hit the `too_many_parts` threshold (300 parts per partition) and inserts started failing.

**Fix:** Accumulate events and insert in batches of 5,000–10,000 rows. This reduced parts-per-second from 1,000 to 2 and eliminated the issue entirely.

**Rule of thumb:** Never insert fewer than 1,000 rows per INSERT into a MergeTree table. Prefer 10,000+ rows per batch.

### 2. ReplacingMergeTree Dedup Is Eventual, Not Immediate

`ReplacingMergeTree` deduplicates rows during background merges, not at insert time. This means:

- Queries *without* `FINAL` may return duplicates until the merge completes.
- Queries *with* `FINAL` force dedup at read time but are slower.
- For billing aggregation, we use `FINAL` on critical queries (invoice generation) and skip it for dashboards where slight over-counting is acceptable.

### 3. The ORDER BY Key Is Your Most Important Decision

The `ORDER BY` key determines:
- **Data layout on disk:** Rows are sorted by this key, enabling efficient range scans.
- **Sparse index structure:** The PRIMARY KEY (prefix of ORDER BY) determines which granules to read.
- **Deduplication key:** For `ReplacingMergeTree`, rows with the same ORDER BY values are deduplicated.

We changed our ORDER BY key three times during development. Getting `organization_id` and `code` as the first two columns was critical — it means billing queries (which always filter by org + metric code) read the minimum possible data.

### 4. PostgreSQL Fallback Is Worth the Complexity

The dual-path design (ClickHouse for analytics, PostgreSQL fallback) seemed like unnecessary complexity initially. Then ClickHouse went down during a configuration change and billing queries transparently fell back to PostgreSQL. The invoice job completed successfully (slowly, but correctly). The fallback paid for itself on day one.

```python
# Aggregation dispatch with ClickHouse fallback
if settings.clickhouse_enabled:
    result = clickhouse_aggregate(...)
else:
    # Fall back to PostgreSQL-based aggregation
    result = sql_aggregate(...)
```

### 5. Fire-and-Forget Writes Need Monitoring

The fire-and-forget pattern for ClickHouse writes (log exceptions, don't raise) is pragmatic but dangerous without monitoring. Failed writes are silent from the API's perspective. We added:

- A counter metric for failed ClickHouse inserts.
- An alert when the failure rate exceeds 0.1% over a 5-minute window.
- A daily reconciliation job that compares PostgreSQL and ClickHouse event counts.

---

## Troubleshooting

### Common Issues

**"Too many parts" error on ClickHouse INSERT:**
- **Cause:** Too many small INSERTs creating too many data parts before background merges can consolidate them.
- **Fix:** Increase batch size. Ensure the consumer is batching 5,000+ rows per INSERT. If using async inserts, increase `async_insert_max_data_size` and `async_insert_busy_timeout_ms`.
- **Emergency:** Run `OPTIMIZE TABLE events_raw` to force a merge. This blocks other operations — use only as a last resort.

**Kafka consumer lag growing unboundedly:**
- **Cause:** ClickHouse inserts are slower than the event production rate.
- **Diagnosis:** Check ClickHouse system tables: `SELECT * FROM system.merges WHERE table = 'events_raw'` — active merges may be consuming disk I/O.
- **Fix:** Increase consumer parallelism (add instances to the consumer group), increase batch size, or scale the ClickHouse node.

**Duplicate events in aggregation results:**
- **Cause:** `ReplacingMergeTree` dedup is eventual. Queries without `FINAL` see unmerged duplicates.
- **Fix:** Use `SELECT ... FROM events_raw FINAL WHERE ...` for billing-critical queries. For dashboards, accept minor over-counting.

**ClickHouse query timeout on large time ranges:**
- **Cause:** Scanning months of data without a partition key prune.
- **Fix:** Ensure queries include the `toDate(timestamp)` predicate for the PRIMARY KEY to prune effectively. Consider adding monthly partitioning (`PARTITION BY toYYYYMM(timestamp)`) if query patterns span long time ranges.

**PostgreSQL write latency increasing under load:**
- **Cause:** Index maintenance overhead at high write rates. Each INSERT updates every B-tree index.
- **Fix:** Reduce indexes on the events table. Use BRIN indexes for timestamp columns. Consider `synchronous_commit = off` for event writes where millisecond-level data loss is acceptable.

### Monitoring Alerts

| Alert | Threshold | Action |
|-------|-----------|--------|
| Kafka consumer lag > 100,000 messages | 5 min sustained | Scale consumers or investigate ClickHouse bottleneck |
| ClickHouse insert failure rate > 0.1% | 5 min window | Check ClickHouse health, disk space, merge status |
| ClickHouse `parts_to_merge` > 300 | Immediate | Possible merge storm; check disk I/O and consider `OPTIMIZE TABLE` |
| PostgreSQL ↔ ClickHouse event count drift > 1% | Daily check | Investigate failed writes; consider backfill from PostgreSQL |
| Kafka broker disk usage > 80% | 15 min sustained | Increase retention topic cleanup or expand broker storage |

---

## Future Optimizations: Scaling to 100k/sec

The architecture is designed to scale incrementally. Here's the roadmap:

### Phase 1: Current (10k/sec)

```
API → Kafka (3 brokers, 12 partitions) → 1 consumer → ClickHouse (1 node)
```
Cost: ~$1,000/month

### Phase 2: Growth (20–50k/sec)

```
API → Kafka (5 brokers, 24 partitions) → 3 consumers → ClickHouse (2-node cluster)
```

Changes:
- Add Kafka partitions and brokers for higher throughput.
- Scale to 3 consumer instances (Kafka rebalances partitions automatically).
- Add a second ClickHouse node with `ReplicatedReplacingMergeTree` for read scaling and failover.
- Add monthly partitioning to `events_raw` for efficient data lifecycle management.

Cost: ~$2,000/month

### Phase 3: Real-time needs (50–100k/sec)

```
API → Kafka (8 brokers) → Batch consumers → ClickHouse (3-node sharded cluster)
                         → Kafka Streams (enrichment/filtering)
```

Changes:
- Introduce Kafka Streams for lightweight in-stream enrichment (no separate cluster needed).
- Shard ClickHouse by `organization_id` using Distributed tables.
- Add ClickHouse materialized views for pre-computed aggregations.

Cost: ~$3,300/month

### Phase 4: Complex processing (100k+/sec)

```
API → Kafka → Flink (pre-aggregation) → ClickHouse (sharded cluster)
```

Changes:
- Add Apache Flink for windowed pre-aggregation, reducing ClickHouse write volume.
- Flink's stateful processing enables real-time alerting, fraud detection, and complex event correlation.
- Only justified when 3+ downstream consumers need different transformations.

Cost: ~$5,300/month

**Scaling triggers:**

| Trigger | Action |
|---------|--------|
| Consumer lag growing during normal traffic | Add consumer instances |
| ClickHouse merge backlog > 300 parts | Add ClickHouse node or increase instance size |
| Aggregation query p99 > 500ms | Add ClickHouse replicas for read scaling |
| Need real-time alerting (< 1 second) | Introduce Kafka Streams or Flink |
| Event volume approaching 50k/sec | Begin Phase 2 scaling |

---

## Team Recommendations

### When to Use This Pattern

The **Kafka → Batch Consumer → ClickHouse** pattern is a good fit when:

- Event volume is 5k–100k events/sec (below 5k/sec, PostgreSQL alone is simpler and sufficient).
- Latency of 5–30 seconds (ingestion to queryable) is acceptable.
- Event replay capability is required (rebuilding views, reprocessing after bug fixes).
- Aggregation queries over millions of rows need sub-second response times.
- The team is not ready for the operational complexity of Flink or stream processing.

### When to Reconsider

Revisit the architecture when:

- **Sub-second analytics needed:** If dashboards or alerts require < 1 second event visibility, consider direct ClickHouse writes with async inserts (P4) or add Flink for real-time processing (P5).
- **No replay requirement:** If events don't need reprocessing, direct ClickHouse writes (P4) save ~$600/month in Kafka infrastructure.
- **Volume drops below 5k/sec:** PostgreSQL with TimescaleDB (P1 variant) is simpler and cheaper.
- **Complex stream processing needed:** If you need windowed joins, CEP, or multi-stream correlation, add Kafka Streams (simple cases) or Flink (complex cases).

### Key Takeaways

1. **Start simple, add complexity when forced.** We deliberately chose a batch consumer over Flink. It's 10x cheaper and our Python team can maintain it without JVM expertise.
2. **Replay capability is non-negotiable for billing.** Every event affects revenue. The ability to reprocess events after fixing a bug is worth the cost of Kafka.
3. **Design the ORDER BY key for your most common query.** In ClickHouse, the physical data layout is your most powerful performance lever.
4. **Always have a fallback path.** ClickHouse is fast but not as operationally mature as PostgreSQL. A PostgreSQL fallback for aggregation queries ensures billing never stops.
5. **Batch your writes.** This is the single most impactful optimization for ClickHouse insert performance. 5,000 rows per INSERT vs. 1 row per INSERT is the difference between a healthy system and "too many parts" errors.

---

## References

- [[Ingestion-Pattern-Comparison]] — Full comparison matrix and TCO analysis across 5 ingestion patterns
- [[Direct-Clickhouse-Ingestion]] — ClickHouse HTTP interface, Buffer tables, Distributed tables, insert benchmarks
- [[API-Direct-Write]] — PostgreSQL-only architecture, ETL/CDC patterns, TimescaleDB analysis
- [[Streaming-Ingestion]] — Apache Flink, Kafka Streams, AWS Kinesis, Apache Pulsar evaluation
- [ClickHouse ReplacingMergeTree](https://clickhouse.com/docs/en/engines/table-engines/mergetree-family/replacingmergetree)
- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [ClickHouse Best Practices for Inserts](https://clickhouse.com/docs/en/cloud/bestpractices/bulk-inserts)
- [clickhouse-connect Python Client](https://clickhouse.com/docs/en/integrations/python)
