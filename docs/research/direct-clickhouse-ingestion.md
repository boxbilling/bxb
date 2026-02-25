---
type: research
title: Direct ClickHouse Ingestion Patterns
created: 2026-02-25
tags:
  - clickhouse
  - ingestion
  - architecture-comparison
related:
  - "[[API-Direct-Write]]"
  - "[[Streaming-Ingestion]]"
  - "[[Ingestion-Pattern-Comparison]]"
---

# Direct ClickHouse Ingestion Patterns

This document investigates the architecture of writing events directly into ClickHouse from the API layer — bypassing intermediate message brokers like Kafka — and evaluates the trade-offs for bxb's usage-based billing platform.

## Table of Contents

- [Overview](#overview)
- [ClickHouse HTTP Interface for Bulk Inserts](#clickhouse-http-interface-for-bulk-inserts)
- [ClickHouse Buffer Tables](#clickhouse-buffer-tables)
- [ClickHouse Distributed Tables](#clickhouse-distributed-tables)
- [Python clickhouse-driver Usage and Batch Insert Patterns](#python-clickhouse-driver-usage-and-batch-insert-patterns)
- [Insert Performance Benchmarks](#insert-performance-benchmarks)
- [Pros: Direct ClickHouse Ingestion](#pros-direct-clickhouse-ingestion)
- [Cons: Direct ClickHouse Ingestion](#cons-direct-clickhouse-ingestion)
- [Relevance to bxb's Current Architecture](#relevance-to-bxbs-current-architecture)

---

## Overview

Direct ClickHouse ingestion eliminates the intermediate message broker (e.g., Kafka) by having the application layer write events straight to ClickHouse. This simplifies the deployment topology but shifts buffering, batching, and backpressure responsibilities to the application layer.

**Pattern:**
```
API Server → ClickHouse (HTTP or Native protocol)
```

Compared to the broker-mediated pattern:
```
API Server → Kafka → Consumer → ClickHouse
```

---

## ClickHouse HTTP Interface for Bulk Inserts

### How It Works

ClickHouse exposes an HTTP interface on port 8123 that accepts INSERT queries with data in various formats (TabSeparated, CSV, JSONEachRow, Native). The HTTP interface is stateless and well-suited for bulk writes from web applications.

### Key Characteristics

| Property | Detail |
|----------|--------|
| **Default port** | 8123 (HTTP), 8443 (HTTPS) |
| **Supported formats** | JSONEachRow, TabSeparated, CSV, Native, and 60+ others |
| **Recommended batch format** | JSONEachRow or Native for best performance |
| **Compression** | Supports gzip, br, deflate, zstd, lz4 on request body |
| **Authentication** | HTTP Basic, or `user`/`password` query params |
| **Max query size** | `max_query_size` (default 256 KiB for SQL, unlimited for data in INSERT) |
| **Async inserts** | Available via `async_insert=1` setting (ClickHouse 21.11+) |

### Batching Requirements

ClickHouse is optimized for **infrequent, large inserts** rather than frequent, small ones:

- **Recommended batch size**: 10,000–100,000 rows per INSERT, or at least 1 MB of data.
- **Minimum interval**: No more than ~1 INSERT per second per table (for MergeTree family).
- **Why**: Each INSERT creates a new data "part" on disk. ClickHouse must merge parts in the background. Too many small parts cause "Too many parts" errors and degrade read performance.

### Async Inserts (ClickHouse 21.11+)

ClickHouse supports server-side batching via **async inserts**:

```sql
SET async_insert = 1;
SET wait_for_async_insert = 0;  -- fire-and-forget
SET async_insert_max_data_size = 10000000;  -- 10 MB buffer
SET async_insert_busy_timeout_ms = 1000;    -- flush every 1s
```

With async inserts enabled, ClickHouse buffers incoming rows on the server side and flushes them as a single batch. This alleviates the "too many parts" problem for high-frequency small inserts, but introduces a data loss window: buffered data is lost if the ClickHouse node crashes before flushing.

---

## ClickHouse Buffer Tables

### How They Work

Buffer tables provide an in-memory write buffer in front of a destination MergeTree table. Writes to the Buffer table are acknowledged immediately from memory, and ClickHouse automatically flushes data to the destination table based on configurable thresholds.

### Configuration

```sql
CREATE TABLE events_buffer AS events_raw
ENGINE = Buffer(
    currentDatabase(), events_raw,
    16,                -- num_layers (parallel flush buckets)
    10, 100,           -- min_time, max_time (seconds)
    10000, 1000000,    -- min_rows, max_rows
    10000000, 100000000 -- min_bytes, max_bytes
)
```

Flush triggers when **any** max threshold is exceeded, or when **all** min thresholds are exceeded simultaneously.

### Memory Limits

- Buffer tables hold data **entirely in RAM**. Each of the `num_layers` buffers accumulates independently.
- Memory usage = `num_layers × max_rows × avg_row_size` in the worst case.
- No built-in memory cap — if the source writes faster than the flush rate, memory grows unboundedly until OOM or a threshold triggers a flush.
- With 16 layers and 1M max_rows of ~200 bytes each: worst case ≈ 3.2 GB RAM.

### Flush Intervals

- **min_time / max_time**: Time-based flush triggers (seconds since last flush per layer).
- **min_rows / max_rows**: Row-count-based flush triggers.
- **min_bytes / max_bytes**: Byte-size-based flush triggers.
- Flush is **per layer**, not global — each of the 16 layers tracks its own thresholds.

### Data Loss Risks

**Buffer tables are NOT durable.** Data in the buffer is lost on:

- ClickHouse server crash or restart
- OOM kill
- `DETACH` / `DROP` of the buffer table
- Hardware failure

For billing data where every event affects revenue, this is a significant risk. Buffer tables are better suited for metrics/analytics where occasional data loss is tolerable.

### Querying Behavior

- `SELECT` from a Buffer table reads **both** the in-memory buffer and the destination table, so queries see all data.
- However, `FINAL` queries and deduplication (ReplacingMergeTree) may not work correctly because unflushed data hasn't been merged.

---

## ClickHouse Distributed Tables

### How They Work

Distributed tables provide a virtual layer for reading from and writing to multiple ClickHouse shards. They enable horizontal scaling by partitioning data across multiple nodes.

### Architecture

```
                    ┌──────────────────┐
                    │ Distributed Table│
                    │  (virtual layer) │
                    └────┬────┬────┬───┘
                         │    │    │
                    ┌────▼┐ ┌─▼──┐ ┌▼────┐
                    │Shard│ │Shard│ │Shard│
                    │  1  │ │  2  │ │  3  │
                    └─────┘ └────┘ └─────┘
```

### Configuration

```sql
-- On each shard, create the local table:
CREATE TABLE events_raw_local (...)
ENGINE = ReplacingMergeTree(created_at)
ORDER BY (organization_id, code, external_customer_id, toDate(timestamp), timestamp, transaction_id);

-- On coordinator node, create the distributed table:
CREATE TABLE events_raw_distributed AS events_raw_local
ENGINE = Distributed(
    'events_cluster',       -- cluster name from config.xml
    currentDatabase(),
    'events_raw_local',     -- local table name
    sipHash64(organization_id)  -- sharding key
);
```

### Sharding Strategies for Event Data

| Strategy | Sharding Key | Pros | Cons |
|----------|-------------|------|------|
| By organization | `sipHash64(organization_id)` | Co-locates org data for fast queries | Hot orgs create skew |
| By time | `toYYYYMM(timestamp)` | Even distribution over time | Cross-shard queries for single org |
| By org + time | `sipHash64(organization_id, toYYYYMM(timestamp))` | Balance between locality and distribution | More complex routing |

### Write Path

- INSERTs to a Distributed table are routed to the appropriate shard based on the sharding key.
- **Internal replication** (preferred): Distributed table writes to one shard, ZooKeeper-based replication handles copies.
- **Distributed writes**: The coordinator forwards data to shards. Temporary data is stored in the coordinator's filesystem queue — this can cause data loss if the coordinator crashes before forwarding.

### Horizontal Scaling Characteristics

- Adding shards requires re-sharding existing data (no automatic rebalancing).
- ClickHouse Keeper (or ZooKeeper) is required for replicated tables.
- Typical cluster sizes for event ingestion: 3–6 shards with 2–3 replicas each.

---

## Python clickhouse-driver Usage and Batch Insert Patterns

### Using `clickhouse-connect` (Current bxb Driver)

bxb currently uses `clickhouse-connect` (HTTP-based client). Here are batch insert patterns:

```python
import clickhouse_connect

client = clickhouse_connect.get_client(host='localhost', port=8123)

# Single batch insert (current bxb pattern)
rows = [
    ['org_1', 'txn_001', 'cust_a', 'api_calls', datetime.now(), '{}', None, None],
    ['org_1', 'txn_002', 'cust_a', 'api_calls', datetime.now(), '{}', None, None],
]
client.insert('events_raw', rows, column_names=[
    'organization_id', 'transaction_id', 'external_customer_id',
    'code', 'timestamp', 'properties', 'value', 'decimal_value',
])
```

### Using `clickhouse-driver` (Native Protocol Alternative)

The native protocol client (`clickhouse-driver`) uses the binary protocol on port 9000, which is faster for bulk inserts:

```python
from clickhouse_driver import Client

client = Client(host='localhost', port=9000)

# Batch insert using native protocol
rows = [
    {'organization_id': 'org_1', 'transaction_id': 'txn_001', ...},
    {'organization_id': 'org_1', 'transaction_id': 'txn_002', ...},
]
client.execute(
    'INSERT INTO events_raw VALUES',
    rows,
    types_check=True,
)
```

### Application-Level Batching Pattern

For direct ingestion at high volume, implement an in-process write buffer:

```python
import asyncio
import logging
from collections import deque
from datetime import datetime

logger = logging.getLogger(__name__)


class ClickHouseBatchWriter:
    """Application-level write buffer for ClickHouse inserts.

    Accumulates rows in memory and flushes to ClickHouse when
    the batch reaches a size or time threshold.
    """

    def __init__(
        self,
        client,
        table: str,
        columns: list[str],
        max_batch_size: int = 10_000,
        flush_interval_seconds: float = 1.0,
    ):
        self.client = client
        self.table = table
        self.columns = columns
        self.max_batch_size = max_batch_size
        self.flush_interval = flush_interval_seconds
        self._buffer: deque[list[object]] = deque()
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        """Start the periodic flush loop."""
        self._flush_task = asyncio.create_task(self._periodic_flush())

    async def stop(self):
        """Flush remaining rows and stop."""
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush()

    async def add_row(self, row: list[object]):
        """Add a row to the buffer. Triggers flush if batch is full."""
        self._buffer.append(row)
        if len(self._buffer) >= self.max_batch_size:
            await self._flush()

    async def _flush(self):
        """Flush buffered rows to ClickHouse."""
        if not self._buffer:
            return

        rows = list(self._buffer)
        self._buffer.clear()

        try:
            self.client.insert(self.table, rows, column_names=self.columns)
            logger.info("Flushed %d rows to %s", len(rows), self.table)
        except Exception:
            logger.exception("Failed to flush %d rows to %s", len(rows), self.table)
            # Re-queue failed rows (risk of duplicates with ReplacingMergeTree)
            self._buffer.extendleft(reversed(rows))

    async def _periodic_flush(self):
        """Flush on a timer to bound latency."""
        while True:
            await asyncio.sleep(self.flush_interval)
            await self._flush()
```

### Insert Settings for High Throughput

```python
# Optimize inserts with settings
client.insert(
    'events_raw', rows, column_names=columns,
    settings={
        'async_insert': 1,                    # Server-side batching
        'wait_for_async_insert': 0,           # Non-blocking
        'insert_quorum': 0,                   # Don't wait for replicas
        'max_insert_block_size': 1_048_576,   # 1M rows per block
    }
)
```

---

## Insert Performance Benchmarks

### Official ClickHouse Benchmarks

Based on ClickHouse documentation and published benchmarks:

| Scenario | Throughput | Conditions |
|----------|-----------|------------|
| **Native protocol bulk insert** | 500k–1M rows/sec | Batch of 100k rows, uncompressed, single node |
| **HTTP JSONEachRow** | 200k–500k rows/sec | Batch of 100k rows, single node |
| **Async insert (small batches)** | 50k–200k rows/sec | Individual rows, server-side batching enabled |
| **Single-row inserts (no async)** | 1k–5k rows/sec | Anti-pattern — creates too many parts |
| **With ReplacingMergeTree** | ~80% of MergeTree | Dedup overhead at merge time, not insert time |

### Impact of Batch Size on Insert Rate

| Batch Size (rows) | Inserts/sec | Rows/sec | Parts Created/sec |
|-------------------|------------|----------|-------------------|
| 1 | 1,000–5,000 | 1k–5k | 1,000–5,000 |
| 100 | 500–2,000 | 50k–200k | 500–2,000 |
| 10,000 | 50–200 | 500k–2M | 50–200 |
| 100,000 | 5–20 | 500k–2M | 5–20 |

The critical insight: **rows per second stays roughly constant at large batch sizes, but parts-per-second decreases dramatically**, which is essential for long-term table health.

### For bxb's 10k Events/sec Target

- **With application-level batching** (1-second flush): 10 batches of 1,000 rows → ~10 parts/sec. This is sustainable but on the higher end. Recommended: batch to 5,000–10,000 rows (flush every 0.5–1.0 seconds).
- **With ClickHouse async inserts**: Individual API-level inserts are fine. ClickHouse coalesces them server-side. Throughput of ~50k rows/sec is achievable.
- **With Buffer table**: Rows go to RAM immediately, parts created at flush intervals only. Sustainable at 10k/sec but introduces data loss risk.

---

## Pros: Direct ClickHouse Ingestion

### 1. Simpler Architecture (No Kafka)

- **Fewer components**: No Kafka brokers, no ZooKeeper/KRaft, no consumer processes.
- **Fewer failure modes**: No consumer lag, no partition rebalancing, no offset management.
- **Easier deployment**: Two services (API + ClickHouse) instead of four+ (API + Kafka + ZooKeeper + Consumer).
- **Lower operational cost**: Kafka clusters typically require 3+ brokers with dedicated storage.

### 2. Lower Latency

- **Direct write**: Events are queryable immediately after INSERT (or within async insert flush window of ~1 second).
- **No consumer lag**: With Kafka, consumer lag under load can push ingestion-to-query latency to seconds or minutes.
- **Real-time dashboards**: Sub-second event visibility for monitoring and alerting.

### 3. Fewer Moving Parts

- **Single data path**: API → ClickHouse, with no intermediate serialization/deserialization.
- **No schema registry**: Event schema lives in the application and ClickHouse DDL only.
- **Simplified monitoring**: Monitor ClickHouse health and insert rate rather than Kafka + consumer health.
- **Easier debugging**: When an event is missing, check ClickHouse directly instead of tracing through broker + consumer.

### 4. Cost Efficiency at Moderate Scale

- At 10k events/sec, a single ClickHouse node can handle the write load.
- Kafka infrastructure at this scale: 3 brokers × ~$200/month = ~$600/month extra.
- ClickHouse async inserts make direct writes viable without application-level batching complexity.

---

## Cons: Direct ClickHouse Ingestion

### 1. No Replay Capability

- **With Kafka**: Events are retained for days/weeks. Consumers can reprocess from any offset — critical for fixing bugs in event processing or rebuilding materialized views.
- **Without Kafka**: Once an event is in ClickHouse, there's no "replay from offset 0" capability. Rebuilding requires re-ingestion from the source or relying on PostgreSQL as the source of truth.
- **For bxb**: Since bxb dual-writes to PostgreSQL, replay could be done from PostgreSQL — but at significantly lower throughput.

### 2. Harder to Add Event Processors

- **With Kafka**: Adding a new consumer (e.g., fraud detection, real-time alerting, webhook trigger) is a simple consumer group addition. Each consumer reads independently.
- **Without Kafka**: Each new processor requires either polling ClickHouse, adding a trigger/notification mechanism, or restructuring the write path. This scales poorly as the number of downstream processors grows.

### 3. API Becomes ClickHouse-Coupled

- **Tight coupling**: API availability depends on ClickHouse availability. If ClickHouse is down for maintenance or overloaded, the API cannot accept events.
- **With Kafka**: The broker decouples the API from ClickHouse. The API writes to Kafka (which is designed for high availability), and ClickHouse consumers can lag without affecting the API.
- **Mitigation**: bxb's current dual-write pattern (PostgreSQL primary, ClickHouse fire-and-forget) partially mitigates this — ClickHouse failures don't block event ingestion. But if ClickHouse becomes the sole event store, this decoupling is lost.

### 4. Backpressure Handling Complexity

- **ClickHouse overload**: If ClickHouse cannot keep up (e.g., during a merge storm or maintenance), the API must handle backpressure: queue events in memory, reject requests (429), or drop events.
- **With Kafka**: Backpressure is absorbed by the broker. The producer writes to Kafka at full speed; the consumer processes at ClickHouse's pace.
- **Application-level buffering**: Building a reliable in-process buffer (as shown in the batch writer example) introduces its own data loss risk — buffered events are lost if the API process crashes.

### 5. Limited Exactly-Once Guarantees

- **ClickHouse inserts are at-least-once**: Network failures during INSERT can cause duplicate writes. `ReplacingMergeTree` deduplicates eventually (at merge time), but queries before merge may return duplicates.
- **With Kafka**: Exactly-once semantics are available with idempotent producers and transactional consumers, providing stronger guarantees for billing-critical data.

### 6. Scaling Challenges

- **Vertical scaling**: A single ClickHouse node handles ~100k–500k inserts/sec. Beyond that, sharding is required.
- **Adding shards**: ClickHouse does not auto-rebalance. Adding a shard requires creating the shard, updating the Distributed table, and optionally migrating historical data.
- **With Kafka**: Scaling consumers is simpler — add more consumer instances and rebalance partitions. The broker handles data distribution.

---

## Relevance to bxb's Current Architecture

bxb currently uses a **dual-write pattern**: events are written synchronously to PostgreSQL (source of truth) and asynchronously to ClickHouse (analytical queries). This is effectively a form of direct ClickHouse ingestion.

### Current Strengths

- **Fire-and-forget writes**: ClickHouse failures don't block the API (see `clickhouse_event_store.py` — exceptions are logged but not raised).
- **PostgreSQL as fallback**: If ClickHouse is disabled or unavailable, aggregation queries fall back to PostgreSQL.
- **ReplacingMergeTree**: Handles eventual deduplication via `created_at` version column.
- **Batch support**: The `insert_events_batch()` function already supports multi-row inserts.

### Current Limitations for Scaling to 10k+/sec

- **No application-level batching**: Each API request triggers an immediate ClickHouse insert. At 10k events/sec, this creates ~10k parts/sec (if single events) or ~100 parts/sec (if using the batch endpoint with 100 events each) — the latter is sustainable but the former is not.
- **Synchronous PostgreSQL write**: The PostgreSQL write is on the critical path. At 10k/sec, PostgreSQL becomes the bottleneck (~5–10k writes/sec limit for a single instance).
- **No replay mechanism**: If ClickHouse data is corrupted or needs rebuilding, the only option is to replay from PostgreSQL.

### Recommendation

For bxb's current scale (moderate event volume), direct ClickHouse ingestion with the dual-write pattern is pragmatic and cost-effective. For scaling to 10k+/sec with replay capability, introducing a message broker (Kafka) between the API and ClickHouse provides better durability, decoupling, and operational flexibility.

---

## References

- [ClickHouse HTTP Interface Documentation](https://clickhouse.com/docs/en/interfaces/http)
- [ClickHouse Async Inserts](https://clickhouse.com/docs/en/cloud/bestpractices/asynchronous-inserts)
- [ClickHouse Buffer Table Engine](https://clickhouse.com/docs/en/engines/table-engines/special/buffer)
- [ClickHouse Distributed Table Engine](https://clickhouse.com/docs/en/engines/table-engines/special/distributed)
- [ClickHouse Best Practices for Inserts](https://clickhouse.com/docs/en/cloud/bestpractices/bulk-inserts)
- [clickhouse-connect Python Client](https://clickhouse.com/docs/en/integrations/python)
- [clickhouse-driver (Native Protocol Client)](https://clickhouse-driver.readthedocs.io/)
