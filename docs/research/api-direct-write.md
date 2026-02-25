---
type: research
title: API Direct-Write Patterns (PostgreSQL-Centric Architectures)
created: 2026-02-25
tags:
  - postgresql
  - scaling
  - architecture-comparison
author: bxb Engineering
reviewed_by: bxb Engineering
version: "1.0"
related:
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[Streaming-Ingestion]]"
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Event-Ingestion-Architecture]]"
---

# API Direct-Write Patterns

This document analyzes architectures where the API writes events directly to PostgreSQL — either as the sole event store or as the primary store with ETL pipelines feeding ClickHouse for analytics. It evaluates PostgreSQL scalability limits, ETL/CDC options, and the TimescaleDB extension as a middle-ground alternative.

## Table of Contents

- [Overview](#overview)
- [PostgreSQL-Only Architecture](#postgresql-only-architecture)
- [PostgreSQL to ClickHouse ETL Patterns](#postgresql-to-clickhouse-etl-patterns)
- [TimescaleDB as PostgreSQL Extension Alternative](#timescaledb-as-postgresql-extension-alternative)
- [Read Replica Strategies](#read-replica-strategies)
- [Pros: API Direct-Write Patterns](#pros-api-direct-write-patterns)
- [Cons: API Direct-Write Patterns](#cons-api-direct-write-patterns)
- [Migration Path: PostgreSQL to ClickHouse](#migration-path-postgresql-to-clickhouse)
- [Relevance to bxb's Current Architecture](#relevance-to-bxbs-current-architecture)

---

## Overview

The API direct-write pattern places PostgreSQL at the center of the event ingestion pipeline. Events are written synchronously to PostgreSQL via the API, and analytical workloads are served either directly from PostgreSQL or from a downstream OLAP store populated via ETL/CDC.

**Pattern (PostgreSQL-only):**
```
API Server → PostgreSQL
```

**Pattern (PostgreSQL + ETL):**
```
API Server → PostgreSQL → ETL/CDC → ClickHouse
```

Compared to the broker-mediated pattern:
```
API Server → Kafka → Consumer → ClickHouse
```

---

## PostgreSQL-Only Architecture

### Events Table Design

A PostgreSQL events table for usage-based billing typically follows this structure:

```sql
CREATE TABLE events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY,
    organization_id UUID NOT NULL,
    transaction_id  TEXT NOT NULL,
    external_customer_id TEXT NOT NULL,
    code            TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    properties      JSONB NOT NULL DEFAULT '{}',
    value           DOUBLE PRECISION,
    decimal_value   NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id)
);

-- Indexes for common query patterns
CREATE INDEX idx_events_org_code_ts
    ON events (organization_id, code, timestamp);
CREATE INDEX idx_events_customer_ts
    ON events (external_customer_id, timestamp);
CREATE UNIQUE INDEX idx_events_dedup
    ON events (organization_id, transaction_id);
```

### Partitioning Strategies

PostgreSQL's declarative partitioning is essential for managing large event tables:

#### Range Partitioning by Time (Recommended)

```sql
CREATE TABLE events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY,
    organization_id UUID NOT NULL,
    transaction_id  TEXT NOT NULL,
    external_customer_id TEXT NOT NULL,
    code            TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    properties      JSONB NOT NULL DEFAULT '{}',
    value           DOUBLE PRECISION,
    decimal_value   NUMERIC,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
) PARTITION BY RANGE (timestamp);

-- Daily partitions for high-volume ingestion
CREATE TABLE events_2026_02_25
    PARTITION OF events
    FOR VALUES FROM ('2026-02-25') TO ('2026-02-26');

-- Automate partition creation with pg_partman or cron
```

| Partition Interval | Best For | Partition Count (1 year) | Notes |
|-------------------|----------|--------------------------|-------|
| **Daily** | >10k events/sec, sharp retention windows | ~365 | Best for high write volumes |
| **Weekly** | Steady moderate streams | ~52 | Simpler management |
| **Monthly** | <1k events/sec, long retention | ~12 | Minimal overhead |

**Key constraints:**
- Optimal partition count: a few dozen to a few hundred partitions.
- Partitions smaller than ~10,000 rows cause excessive query planning overhead.
- Thousands of tiny partitions degrade planner performance, increase memory usage, and slow inserts.

#### Index Strategy for Partitioned Tables

| Index Type | Overhead on Writes | Size vs. Table | Best For |
|-----------|-------------------|----------------|----------|
| **B-tree** | ~85% slowdown | Approaches table size for narrow tables | Equality/range lookups on selective columns |
| **BRIN** | ~11% slowdown | 5–15% of table size | Naturally ordered columns (timestamps) |

For event tables, **BRIN indexes on `timestamp`** and **B-tree indexes on selective lookup columns** (`organization_id`, `transaction_id`) provide the best write-throughput to query-performance balance.

```sql
-- BRIN for timestamp (minimal write overhead)
CREATE INDEX idx_events_ts_brin ON events USING BRIN (timestamp);

-- B-tree for selective lookups (higher write overhead but needed for queries)
CREATE INDEX idx_events_org_code ON events (organization_id, code);
```

### VACUUM and Maintenance Overhead

PostgreSQL's MVCC architecture means deleted or updated rows produce dead tuples that must be reclaimed by VACUUM.

**Autovacuum tuning for high-write event tables:**

| Parameter | Default | High-Write Recommendation |
|-----------|---------|---------------------------|
| `autovacuum_vacuum_scale_factor` | 0.2 (20%) | 0.01–0.05 (1–5%) |
| `autovacuum_naptime` | 1 min | 30 sec |
| `autovacuum_vacuum_cost_delay` | 2 ms | 0–1 ms |
| `autovacuum_vacuum_cost_limit` | 200 | 1000–2000 |

**For append-only event tables** (INSERT-only, no UPDATE/DELETE), VACUUM overhead is minimal since there are no dead tuples to reclaim. The primary maintenance burden shifts to index bloat management and partition drop/create operations.

### Write Performance Limits

| Metric | Value | Conditions |
|--------|-------|------------|
| **Single-row INSERTs** | ~10,000/sec | Single node, concurrent connections, indexes |
| **Batch INSERTs (COPY)** | ~100,000/sec | COPY command, minimal indexes |
| **ACID transactions** | ~10,000–11,000 TPS | Full transactional guarantees |
| **With heavy indexes** | ~5,000–7,000/sec | Multiple B-tree indexes per table |

**Key bottlenecks at 10k+/sec:**
- **WAL write amplification**: First change to each 8 KB page after checkpoint triggers a full-page write. Tune `checkpoint_timeout` to 30–60 minutes and `max_wal_size` to 8 GB.
- **Index maintenance**: Each INSERT updates every index on the table. Minimize indexes on high-write tables.
- **Connection overhead**: Use connection pooling (PgBouncer) with transaction-level pooling.
- **Synchronous commit**: Set `synchronous_commit = off` for event tables where occasional loss of the last few milliseconds of data is acceptable.

### WAL Tuning for High Throughput

```ini
# postgresql.conf tuning for event ingestion
wal_buffers = 64MB
checkpoint_timeout = 30min
max_wal_size = 8GB
min_wal_size = 2GB
checkpoint_completion_target = 0.9
wal_compression = lz4          # Reduce WAL I/O
synchronous_commit = off        # ~10% throughput gain
```

---

## PostgreSQL to ClickHouse ETL Patterns

When PostgreSQL handles the transactional write path but analytical queries need ClickHouse's performance, several ETL/CDC patterns bridge the gap.

### 1. Debezium CDC (PostgreSQL → Kafka → ClickHouse)

The most mature production-grade CDC pipeline.

**Architecture:**
```
PostgreSQL WAL → Debezium → Kafka → ClickHouse Kafka Connect Sink → ClickHouse
```

**How it works:**
1. Debezium reads PostgreSQL's Write-Ahead Log via logical replication.
2. Change events (INSERT, UPDATE, DELETE) are published to Kafka topics.
3. The ClickHouse Kafka Connect Sink consumes from Kafka and writes to ClickHouse.

**Exactly-once semantics:**
- Debezium provides **at-least-once** delivery (events may be duplicated on failure/restart).
- The ClickHouse Kafka Connect Sink achieves **exactly-once** using KeeperMap as a state store and deduplication.
- ReplacingMergeTree in ClickHouse handles residual duplicates via eventual deduplication at merge time.

**Connectors:**
- **Altinity ClickHouse Sink Connector v2.0** (Apache 2.0, open source): Supports lightweight single-binary CDC and Kafka-based sink.
- **Official ClickHouse Kafka Connect Sink**: Recommended for production deployments.

**Note:** The legacy PostgreSQL CDC Source connector (Debezium) reaches EOL March 31, 2026 — migrate to v2.

### 2. ClickHouse MaterializedPostgreSQL Engine

Real-time replication built into ClickHouse.

```sql
-- ClickHouse-side: create a MaterializedPostgreSQL database
CREATE DATABASE pg_replica
ENGINE = MaterializedPostgreSQL('pg_host:5432', 'billing_db', 'repl_user', 'password')
SETTINGS materialized_postgresql_tables_list = 'events';
```

**How it works:**
1. ClickHouse takes an initial snapshot of the PostgreSQL table.
2. Continuously reads the PostgreSQL WAL as a logical replication subscriber.
3. Applies INSERT/UPDATE/DELETE operations to ClickHouse tables.

**Limitations:**
- Does NOT replicate DDL changes (schema migrations require manual intervention).
- Single-threaded WAL reader can become a bottleneck at very high write volumes.
- Overshadowed by newer solutions (PeerDB/ClickPipes) as of 2026.

### 3. PeerDB / ClickPipes (Modern Recommended)

PeerDB (acquired by ClickHouse) is the recommended CDC solution as of 2026.

**Key advantages:**
- Handles initial load + incremental CDC syncs.
- Solves WAL accumulation by staging changes to S3 before applying to ClickHouse.
- Sub-second replication latency.
- Supports PostgreSQL 17 failover-enabled replication slots.

### 4. Custom ETL Scripts

For simpler setups or one-time migrations:

```python
import psycopg2
import clickhouse_connect

# Incremental extraction using timestamp watermark
pg_conn = psycopg2.connect(dsn="postgresql://...")
ch_client = clickhouse_connect.get_client(host='localhost')

with pg_conn.cursor(name='etl_cursor') as cursor:
    cursor.execute("""
        SELECT organization_id, transaction_id, external_customer_id,
               code, timestamp, properties, value, decimal_value, created_at
        FROM events
        WHERE created_at > %(watermark)s
        ORDER BY created_at
    """, {'watermark': last_sync_timestamp})

    batch = []
    for row in cursor:
        batch.append(row)
        if len(batch) >= 10_000:
            ch_client.insert('events_raw', batch, column_names=[...])
            batch = []

    if batch:
        ch_client.insert('events_raw', batch, column_names=[...])
```

**Patterns:**
- **Timestamp-based incremental**: Track a `last_sync_timestamp` watermark. Simple but can miss concurrent writes.
- **Logical replication slot**: Stream WAL changes continuously. Risk: WAL file accumulation if the consumer falls behind.
- **COPY-based batch export**: `COPY events TO STDOUT` → file → `clickhouse-client --query "INSERT INTO ..."`. Best for initial loads.

### 5. ClickHouse PostgreSQL Table Engine (Federated Queries)

Query PostgreSQL directly from ClickHouse without moving data:

```sql
CREATE TABLE pg_events AS events_raw
ENGINE = PostgreSQL('pg_host:5432', 'billing_db', 'events', 'readonly_user', 'password');

-- Query PostgreSQL data from ClickHouse
SELECT organization_id, count()
FROM pg_events
WHERE timestamp > now() - INTERVAL 1 HOUR
GROUP BY organization_id;
```

This is useful for ad-hoc queries or late-arriving data but not suitable for high-throughput analytical workloads — every query hits PostgreSQL directly.

---

## TimescaleDB as PostgreSQL Extension Alternative

TimescaleDB extends PostgreSQL with time-series optimizations, offering a middle ground between vanilla PostgreSQL and a dedicated OLAP store like ClickHouse.

### Hypertables

TimescaleDB's core abstraction. A hypertable looks like a regular PostgreSQL table but automatically partitions data into time-based chunks.

```sql
-- Install TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Convert events table to a hypertable
SELECT create_hypertable('events', 'timestamp',
    chunk_time_interval => INTERVAL '1 day');

-- Optional: add space partitioning for multi-tenant workloads
SELECT add_dimension('events', 'organization_id', number_partitions => 4);
```

**Chunk management:**
- Default chunk interval: 7 days (adjustable).
- Chunks should be small enough to fit in memory for optimal write performance.
- Indexes are created automatically per chunk.

### Compression

TimescaleDB provides column-oriented compression on top of PostgreSQL's row storage:

```sql
-- Enable compression on the hypertable
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'organization_id, code',
    timescaledb.compress_orderby = 'timestamp DESC'
);

-- Add a compression policy (compress chunks older than 7 days)
SELECT add_compression_policy('events', INTERVAL '7 days');
```

**Compression performance:**

| Metric | Value |
|--------|-------|
| **Typical compression ratio** | 10–20x (vs. uncompressed PostgreSQL) |
| **Aggressive compression** | Up to 90x (data-dependent) |
| **Read performance on compressed data** | Up to 7x faster scans (SIMD vectorization) |
| **Analytical query speedup** | 2–10x due to reduced I/O |

### Continuous Aggregates

Incrementally-maintained materialized views that auto-refresh as new data arrives:

```sql
CREATE MATERIALIZED VIEW hourly_usage
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    organization_id,
    code,
    count(*) AS event_count,
    sum(value) AS total_value
FROM events
GROUP BY bucket, organization_id, code;

-- Refresh policy: update aggregates every 30 minutes
SELECT add_continuous_aggregate_policy('hourly_usage',
    start_offset    => INTERVAL '3 hours',
    end_offset      => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes');
```

Unlike standard PostgreSQL materialized views (which require full recomputation on refresh), continuous aggregates only recompute time buckets that have changed.

### Write Performance

| Scenario | Throughput | Notes |
|----------|-----------|-------|
| **TimescaleDB (sustained, 1B rows)** | ~111k rows/sec | No degradation at scale |
| **Vanilla PostgreSQL (at 1B rows)** | ~5k rows/sec | Severe degradation from ~115k initial |
| **TimescaleDB single-node max** | 100–200k rows/sec | Production deployments |

**Why TimescaleDB sustains performance:** Time-space partitioning keeps recent chunks in memory, so index updates on active chunks remain fast. Vanilla PostgreSQL degrades as B-tree indexes grow beyond memory.

### Scalability Limits

| Dimension | Limit |
|-----------|-------|
| **Single-node storage** | Tested to 350+ TB in production |
| **Practical recommended max** | 50–100 TB |
| **Multi-node support** | **Deprecated** as of TimescaleDB 2.14 (only ~1% used it) |
| **Daily growth handling** | 3+ TB/day demonstrated |

**When you outgrow TimescaleDB:**
- Petabyte-scale without retention policies → consider dedicated OLAP (ClickHouse).
- Sub-second analytical queries on cold data → ClickHouse's columnar engine is faster.
- Complex stream processing (joins, windowing) → Kafka + Flink.

### Licensing

| Edition | License | Key Restrictions |
|---------|---------|------------------|
| **Core** | Apache 2.0 | None |
| **Community (TSL)** | Timescale License | Cannot offer as hosted DBaaS |
| **Enterprise** | Commercial | Paid, additional features |

Compression, continuous aggregates, and hypertables are all available under the free TSL license for self-hosted and commercial use.

---

## Read Replica Strategies

### PostgreSQL Streaming Replication

Offload analytical queries to read replicas to protect the primary's write throughput:

```
                    ┌──────────────┐
                    │   Primary    │◄── API Writes
                    │ (read-write) │
                    └──┬───┬───┬──┘
                       │   │   │   WAL streaming
                    ┌──▼┐ ┌▼──┐ ┌▼──┐
                    │ R1 │ │R2 │ │R3 │  ◄── Analytical Queries
                    └───┘ └───┘ └───┘
```

**Configuration:**

| Setting | Primary | Replica |
|---------|---------|---------|
| `wal_level` | `replica` | — |
| `max_wal_senders` | 5+ | — |
| `hot_standby` | — | `on` |
| `max_standby_streaming_delay` | — | `30s` (tolerate lag) |

**Scale demonstrated:** OpenAI runs PostgreSQL for ChatGPT with a single primary and 50+ read replicas handling millions of queries/sec.

### Query Routing

```python
# Application-level read/write splitting
import psycopg2

write_conn = psycopg2.connect(dsn="postgresql://primary:5432/billing")
read_conn = psycopg2.connect(dsn="postgresql://replica:5432/billing")

# Writes always go to primary
write_conn.execute("INSERT INTO events ...")

# Analytical reads go to replica (may have slight lag)
read_conn.execute("""
    SELECT organization_id, count(*)
    FROM events
    WHERE timestamp > now() - INTERVAL '1 hour'
    GROUP BY organization_id
""")
```

### Replica Lag Considerations

- **Streaming replication lag**: Typically <1 second under normal load.
- **Under heavy write load**: Lag can increase to seconds or minutes.
- **For billing aggregations**: 1–2 minute lag is generally acceptable (billing cycles are hourly/daily).
- **Monitoring**: Track `pg_stat_replication.replay_lag` and alert on thresholds.

---

## Pros: API Direct-Write Patterns

### 1. Simpler Stack

- **Single database**: PostgreSQL handles both transactional and (limited) analytical workloads.
- **Familiar tooling**: Standard SQL, pg_dump, psql, mature ecosystem of ORMs and migration tools.
- **Simpler deployment**: One database to provision, monitor, back up, and upgrade.
- **Faster development**: No Kafka/ClickHouse to set up locally; `docker-compose` with just PostgreSQL.

### 2. Transactional Guarantees

- **ACID compliance**: Every event write is fully transactional. No "fire-and-forget" data loss risk.
- **Deduplication via UNIQUE constraint**: `ON CONFLICT (organization_id, transaction_id) DO NOTHING` — immediate, deterministic dedup (not eventual like ReplacingMergeTree).
- **Foreign key integrity**: Events can reference organizations, customers, and billing codes with enforced referential integrity.
- **Rollback capability**: Failed API requests cleanly roll back — no orphaned events.

### 3. Easier Development and Testing

- **Single test database**: Tests run against PostgreSQL only; no need to spin up Kafka + ClickHouse.
- **Simpler debugging**: Events are in one place with standard SQL queries.
- **Schema migrations**: Alembic/Flyway handle schema changes atomically; no need to coordinate migrations across PostgreSQL, Kafka schemas, and ClickHouse DDL.
- **Local development**: `pytest` with an in-memory or containerized PostgreSQL is fast and self-contained.

### 4. Strong Ecosystem

- **Monitoring**: pg_stat_statements, pg_stat_user_tables, pgBadger for query analysis.
- **Backup/restore**: pg_dump, pg_basebackup, WAL-G for continuous archiving.
- **Managed services**: AWS RDS, Cloud SQL, Azure Database — battle-tested managed PostgreSQL.
- **Extensions**: PostGIS, pg_trgm, TimescaleDB, pgvector — rich extension ecosystem.

---

## Cons: API Direct-Write Patterns

### 1. PostgreSQL Write Scalability Limits

- **Single-node ceiling**: ~10,000 single-row INSERTs/sec with indexes (higher with COPY, but COPY isn't API-friendly).
- **bxb's 10k/sec target is at the limit**: PostgreSQL can sustain it with tuning, but leaves no headroom for spikes.
- **Scaling writes is hard**: PostgreSQL has no native write sharding. Options are Citus (distributed PostgreSQL) or application-level sharding — both add significant complexity.

### 2. Expensive Aggregations

- **Row-oriented storage**: Aggregation queries (`SUM`, `COUNT`, `GROUP BY`) scan entire rows, not just the columns needed.
- **No columnar compression**: PostgreSQL stores data row-by-row. A `SELECT sum(value) FROM events WHERE ...` reads all columns, wasting I/O on `properties`, `transaction_id`, etc.
- **ClickHouse comparison**: ClickHouse's columnar storage makes aggregations 10–100x faster for wide tables.
- **Index-only scans help but are limited**: Only work when the query can be satisfied entirely from an index.

### 3. Storage Costs for High Volume

At 10,000 events/sec:

| Metric | Value |
|--------|-------|
| **Events per day** | 864 million |
| **Row size (avg, with indexes)** | ~500 bytes |
| **Daily storage (uncompressed)** | ~432 GB |
| **Monthly storage** | ~13 TB |
| **With TimescaleDB compression (10x)** | ~1.3 TB/month |
| **With ClickHouse compression (20–30x)** | ~450 GB/month |

PostgreSQL's row-oriented storage is 3–5x more expensive per byte of useful data than ClickHouse's columnar compression.

### 4. VACUUM Overhead (for UPDATE/DELETE workloads)

- **Append-only workloads** (INSERT-only events): Minimal VACUUM impact.
- **With dedup via `ON CONFLICT ... DO UPDATE`**: Dead tuples accumulate, requiring aggressive autovacuum.
- **Table bloat**: Without proper VACUUM tuning, tables grow beyond their actual data size, degrading scan performance.

### 5. No Native Event Replay

- **PostgreSQL is not a log**: There's no concept of "replay from offset" or consumer groups.
- **WAL retention**: WAL is for replication and crash recovery, not application-level replay.
- **Workaround**: Query events by `created_at` range — functional but much slower than Kafka offset-based replay.

---

## Migration Path: PostgreSQL to ClickHouse

A phased approach for transitioning from PostgreSQL-only to PostgreSQL + ClickHouse as event volume grows.

### Phase 1: PostgreSQL-Only (0–5k events/sec)

```
API → PostgreSQL (single primary + read replica)
```

- Use PostgreSQL for both writes and reads.
- Partition the events table by day.
- Use BRIN indexes on `timestamp` to minimize write overhead.
- Offload analytical queries to a read replica.

### Phase 2: Add ClickHouse for Analytics (5k–20k events/sec)

```
API → PostgreSQL (source of truth) → CDC → ClickHouse (analytics)
```

- Keep PostgreSQL as the write target and source of truth.
- Set up PeerDB/ClickPipes or Debezium CDC to replicate events to ClickHouse.
- Redirect analytical queries (dashboards, aggregations) to ClickHouse.
- PostgreSQL handles transactional queries (single-event lookups, dedup checks).

### Phase 3: Kafka as Write Buffer (20k–100k events/sec)

```
API → Kafka → Consumer → ClickHouse (primary analytics)
                       → PostgreSQL (transactional subset)
```

- PostgreSQL can no longer keep up with full event volume.
- Kafka decouples the API from both databases.
- PostgreSQL stores only a transactional subset (e.g., recent events, billing-critical records).
- ClickHouse becomes the primary event store for analytics.

### Migration Decision Triggers

| Trigger | Action |
|---------|--------|
| PostgreSQL write latency p99 > 50ms | Tune WAL, reduce indexes, or add write buffer |
| Sustained write rate > 8k/sec | Begin Phase 2 (add ClickHouse) |
| Aggregation queries > 5 sec | Redirect analytics to ClickHouse |
| Event volume > 500M rows/month | Evaluate storage costs, consider ClickHouse as primary |
| Need for event replay | Introduce Kafka (Phase 3) |

---

## Relevance to bxb's Current Architecture

bxb currently operates in a hybrid between Phase 1 and Phase 2: the API writes to PostgreSQL (source of truth) and fire-and-forget to ClickHouse. This is a pragmatic dual-write pattern but not a true CDC pipeline.

### Current State

- **PostgreSQL**: Primary event store with ACID guarantees. Handles deduplication via unique constraints.
- **ClickHouse**: Secondary analytics store. Writes are fire-and-forget (failures are logged, not raised).
- **No CDC pipeline**: Events are dual-written from the API, not replicated via WAL.

### If Scaling Beyond Current Load

1. **Short-term (moderate volume increase)**: Add a PostgreSQL read replica for analytical query offloading. Consider TimescaleDB for compression and continuous aggregates on the primary.
2. **Medium-term (approaching 10k/sec)**: Replace the fire-and-forget dual-write with a proper CDC pipeline (PeerDB/ClickPipes) from PostgreSQL to ClickHouse. This provides replay capability and decouples the write paths.
3. **Long-term (beyond 10k/sec)**: Introduce Kafka as a write buffer (the chosen architecture in bxb's event pipeline design). PostgreSQL becomes a transactional store for a subset of data; ClickHouse serves all analytical workloads.

---

## References

- [PostgreSQL Table Partitioning](https://www.postgresql.org/docs/current/ddl-partitioning.html)
- [PostgreSQL BRIN Indexes](https://www.postgresql.org/docs/current/brin-intro.html)
- [PostgreSQL Autovacuum Tuning](https://www.postgresql.org/docs/current/runtime-config-autovacuum.html)
- [TimescaleDB Documentation](https://docs.timescale.com/)
- [TimescaleDB vs PostgreSQL Benchmarks](https://www.timescale.com/blog/timescaledb-vs-6a696248104e/)
- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/connectors/postgresql.html)
- [ClickHouse MaterializedPostgreSQL Engine](https://clickhouse.com/docs/engines/database-engines/materialized-postgresql)
- [PeerDB: PostgreSQL to ClickHouse CDC](https://docs.peerdb.io/mirror/cdc-pg-clickhouse)
- [ClickHouse Kafka Connect Sink](https://clickhouse.com/docs/integrations/kafka/clickhouse-kafka-connect-sink)
- [Altinity ClickHouse Sink Connector v2.0](https://altinity.com/blog/announcing-version-2-0-of-the-altinity-clickhouse-sink-connector)
- [OpenAI Scales PostgreSQL to 50+ Replicas](https://www.infoq.com/news/2026/02/openai-runs-chatgpt-postgres/)
