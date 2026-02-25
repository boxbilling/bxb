---
type: analysis
title: Ingestion Pattern Comparison and Decision Framework
created: 2026-02-25
tags:
  - architecture
  - decision-record
  - comparison
author: bxb Engineering
reviewed_by: bxb Engineering
version: "1.0"
related:
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[API-Direct-Write]]"
  - "[[Streaming-Ingestion]]"
  - "[[Kafka-Event-Pipeline]]"
  - "[[Event-Ingestion-Architecture]]"
---

# Ingestion Pattern Comparison and Decision Framework

This document provides a structured comparison of event ingestion architectures evaluated for bxb's usage-based billing platform. It includes a multi-dimensional comparison matrix, total cost of ownership (TCO) analysis at multiple throughput tiers, and a decision framework for guiding future architectural choices.

## Table of Contents

- [Patterns Under Evaluation](#patterns-under-evaluation)
- [Comparison Matrix](#comparison-matrix)
- [Detailed Dimension Analysis](#detailed-dimension-analysis)
- [Decision Criteria for 10k/sec Use Case](#decision-criteria-for-10ksec-use-case)
- [TCO Analysis](#tco-analysis)
- [Decision Tree](#decision-tree)
- [Recommendation Summary](#recommendation-summary)
- [References](#references)

---

## Patterns Under Evaluation

| ID | Pattern | Data Flow |
|----|---------|-----------|
| **P1** | API → PostgreSQL | `API → PostgreSQL` |
| **P2** | API → PostgreSQL + ETL → ClickHouse | `API → PostgreSQL → CDC/ETL → ClickHouse` |
| **P3** | API → Kafka → ClickHouse (chosen) | `API → Kafka → Batch Consumer → ClickHouse` |
| **P4** | API → ClickHouse direct | `API → ClickHouse (HTTP/native)` |
| **P5** | API → Kafka → Flink → ClickHouse | `API → Kafka → Flink → ClickHouse` |

---

## Comparison Matrix

### Summary Table

| Dimension | P1: PostgreSQL | P2: PG + ETL → CH | P3: Kafka → CH (chosen) | P4: CH Direct | P5: Kafka → Flink → CH |
|-----------|:-:|:-:|:-:|:-:|:-:|
| **Throughput capacity** | 5-10k/sec | 5-10k/sec (PG-limited) | 50-100k/sec | 100-500k/sec | 100k-1M+/sec |
| **Ingestion-to-query latency** | <10ms | 1-30s (CDC lag) | 5-30s (batch window) | <1s (async insert) | 10-100ms |
| **Infrastructure cost (10k/sec)** | Low | Medium | Medium | Low | High |
| **Development complexity** | Low | Medium | Medium | Low-Medium | High |
| **Operational complexity** | Low | Medium | Medium | Medium | Very High |
| **Horizontal scalability** | Hard | Hard (PG side) | Easy | Medium | Easy |
| **Data durability** | Excellent | Excellent | Very Good | Good | Very Good |
| **Event replay capability** | Poor | Poor | Excellent | None | Excellent |
| **Multi-consumer support** | Poor | Poor | Excellent | Poor | Excellent |
| **Analytical query speed** | Poor | Good (CH side) | Good | Good | Good |

### Scoring (1-5 scale, 5 = best)

| Dimension | Weight | P1 | P2 | P3 | P4 | P5 |
|-----------|--------|:--:|:--:|:--:|:--:|:--:|
| Throughput capacity | 20% | 2 | 2 | 4 | 5 | 5 |
| Latency | 10% | 5 | 3 | 4 | 5 | 5 |
| Cost (10k/sec) | 20% | 5 | 3 | 3 | 5 | 1 |
| Development complexity | 15% | 5 | 3 | 3 | 4 | 1 |
| Operational complexity | 15% | 5 | 3 | 3 | 3 | 1 |
| Scalability | 10% | 1 | 2 | 5 | 3 | 5 |
| Durability | 5% | 5 | 5 | 4 | 3 | 4 |
| Replay capability | 5% | 1 | 1 | 5 | 1 | 5 |
| **Weighted Score** | **100%** | **3.60** | **2.70** | **3.60** | **3.85** | **2.60** |
| **Weighted Score (50k/sec)** | — | **1.80** | **2.10** | **3.80** | **3.35** | **3.60** |

> **At 10k/sec**, P4 (ClickHouse direct) and P3 (Kafka → ClickHouse) tie on weighted score. P3 is chosen because bxb requires event replay capability and multi-consumer support, which P4 cannot provide.
>
> **At 50k/sec**, P3 and P5 lead as PostgreSQL-based patterns hit their write ceiling.

---

## Detailed Dimension Analysis

### Throughput Capacity (events/sec)

| Pattern | Sustainable Throughput | Bottleneck | Scaling Path |
|---------|----------------------|------------|--------------|
| **P1** | 5-10k/sec | PostgreSQL single-node write limit; index maintenance overhead | Read replicas for reads only; Citus for writes (complex) |
| **P2** | 5-10k/sec (PG-limited) | PostgreSQL write path; CDC adds no write throughput | Same as P1; ClickHouse side scales easily |
| **P3** | 50-100k/sec | Kafka partition count × consumer parallelism | Add partitions + consumers; Kafka scales linearly |
| **P4** | 100-500k/sec | ClickHouse merge rate; batch size management | Distributed tables + sharding (requires re-sharding) |
| **P5** | 100k-1M+/sec | Flink parallelism × TaskManager resources | Add TaskManagers; Flink auto-scales on Kubernetes |

### Ingestion-to-Query Latency

| Pattern | Best Case | Typical | Worst Case | Notes |
|---------|-----------|---------|------------|-------|
| **P1** | <5ms | <10ms | 50-100ms (under load) | Immediate after INSERT commit |
| **P2** | 1s | 5-15s | 30-60s | CDC replication lag; depends on tool (PeerDB: sub-second; Debezium: seconds) |
| **P3** | 5s | 10-30s | 1-2 min | Batch window (5s) + consumer processing; higher under spike |
| **P4** | <100ms | <1s | 5-10s | Async insert flush window; immediate if sync |
| **P5** | 10ms | 50-100ms | 1-5s | Flink processing + checkpoint overhead |

### Infrastructure Cost at 10k/sec

| Pattern | Components | Estimated Monthly Cost |
|---------|------------|----------------------|
| **P1** | PostgreSQL (1 primary + 1 replica) | **~$400-600** |
| **P2** | PostgreSQL + CDC tool + ClickHouse | **~$800-1,200** |
| **P3** | Kafka (3 brokers) + Consumer + ClickHouse | **~$900-1,300** |
| **P4** | ClickHouse (1 node, async inserts) | **~$300-500** |
| **P5** | Kafka + Flink cluster + ClickHouse | **~$1,500-2,300** |

### Development Complexity

| Pattern | Languages/Skills | New Components | Schema Management | Debugging |
|---------|-----------------|----------------|-------------------|-----------|
| **P1** | Python + SQL | None (existing stack) | Alembic migrations only | Simple — single DB |
| **P2** | Python + SQL + CDC config | CDC tool (PeerDB/Debezium) | Alembic + ClickHouse DDL sync | Moderate — trace through CDC |
| **P3** | Python + Kafka client | Kafka, consumer process | Alembic + Kafka schema + CH DDL | Moderate — trace through broker |
| **P4** | Python + ClickHouse client | Application-level batcher | ClickHouse DDL only | Simple — direct write path |
| **P5** | Python + Java/Scala (Flink) | Kafka + Flink cluster | Alembic + Kafka + Flink + CH DDL | Hard — distributed stateful system |

### Operational Complexity

| Pattern | Monitoring Points | Failure Modes | Upgrade Difficulty | On-Call Burden |
|---------|-------------------|---------------|-------------------|----------------|
| **P1** | PostgreSQL metrics | PG down, replication lag | Low (single component) | Low |
| **P2** | PG + CDC + CH metrics | CDC lag, schema drift, PG bottleneck | Medium (coordinate CDC) | Medium |
| **P3** | Kafka + consumer + CH | Consumer lag, broker failure, partition skew | Medium (rolling Kafka upgrades) | Medium |
| **P4** | ClickHouse metrics | CH overload, too-many-parts, data loss (no buffer) | Low (single component) | Medium (backpressure handling) |
| **P5** | Kafka + Flink + CH | Checkpoint failures, state corruption, rebalancing | High (Flink version upgrades) | High |

### Horizontal Scalability

| Pattern | Write Scaling | Read Scaling | Data Rebalancing |
|---------|--------------|-------------|------------------|
| **P1** | Very hard (Citus, app-level sharding) | Easy (read replicas) | Manual with Citus |
| **P2** | Hard (PG side); Easy (CH side) | Easy (CH replicas) | Manual on PG, automatic-ish on CH |
| **P3** | Easy (add Kafka partitions + consumers) | Easy (CH replicas) | Kafka rebalances automatically |
| **P4** | Medium (ClickHouse sharding, Distributed tables) | Easy (CH replicas) | Manual re-sharding required |
| **P5** | Easy (Flink parallelism + Kafka partitions) | Easy (CH replicas) | Flink rescales automatically |

### Data Durability

| Pattern | Write Guarantee | Data Loss Window | Recovery Method |
|---------|----------------|------------------|-----------------|
| **P1** | ACID (fsync per commit) | None (synchronous commit) | pg_basebackup + WAL replay |
| **P2** | ACID (PG) + at-least-once (CDC) | CDC lag window (seconds) | PG backup + re-sync CDC |
| **P3** | Kafka replication (acks=all) | Consumer lag (seconds-minutes) | Kafka replay from offset |
| **P4** | At-least-once (async insert flush) | Async insert buffer (1-2s); Buffer table (configurable) | Re-ingest from source |
| **P5** | Flink checkpoint + Kafka | Checkpoint interval (seconds) | Restore from checkpoint + replay |

---

## Decision Criteria for 10k/sec Use Case

bxb's target architecture must satisfy these requirements at 10,000 events/sec:

### Must-Have Requirements

| Requirement | P1 | P2 | P3 | P4 | P5 |
|-------------|:--:|:--:|:--:|:--:|:--:|
| Handle 10k events/sec sustained | Marginal | Marginal | Yes | Yes | Yes |
| 1-2 minute ingestion-to-query latency acceptable | Yes | Yes | Yes | Yes | Yes |
| Event replay capability (rebuild materialized views) | No | No | **Yes** | No | **Yes** |
| Headroom to scale to 50k/sec | No | No | **Yes** | Yes | **Yes** |
| Cost-effective for bulk write-through (no transformations) | Yes | Moderate | **Yes** | Yes | No |
| ClickHouse-powered analytical queries | No | Yes | **Yes** | Yes | **Yes** |

**Result:** Only **P3** and **P5** satisfy all must-have requirements. P5 is eliminated on cost — Flink adds ~$500-1,000/month with no benefit for simple write-through ingestion.

### Nice-to-Have Requirements

| Requirement | P3 (chosen) | Notes |
|-------------|:-----------:|-------|
| Multi-consumer support for future processors | Yes | Kafka consumer groups; add fraud detection, alerting, etc. |
| Decoupled API from storage layer | Yes | Kafka buffers events; ClickHouse downtime doesn't affect API |
| At-least-once delivery with dedup | Yes | Kafka acks=all + ReplacingMergeTree |
| Operational simplicity for small team | Moderate | Kafka requires learning but is well-documented |
| Standard tooling and ecosystem | Yes | Kafka Connect, schema registry, extensive monitoring |

### Why P3 (Kafka → ClickHouse) Over Alternatives

1. **Over P1 (PostgreSQL-only):** PostgreSQL hits its write ceiling at 10k/sec, leaving no headroom for spikes. No event replay capability. Aggregation queries are 10-100x slower than ClickHouse.

2. **Over P2 (PostgreSQL + ETL):** PostgreSQL remains the write bottleneck. CDC adds complexity without removing the fundamental limitation. Two databases to maintain with a fragile sync pipeline.

3. **Over P4 (ClickHouse direct):** No event replay capability — once events are in ClickHouse, there is no "replay from offset." API becomes tightly coupled to ClickHouse availability. Adding downstream consumers (fraud detection, alerting) requires restructuring the write path.

4. **Over P5 (Kafka → Flink → ClickHouse):** Flink adds $500-1,000/month in infrastructure cost and significant operational complexity. bxb's current use case is simple write-through ingestion — no transformations, no windowed aggregations, no stream-stream joins. Flink can be added later if real-time processing requirements emerge.

---

## TCO Analysis

Total Cost of Ownership across three throughput tiers, including infrastructure, operations, and development costs.

### Infrastructure Costs

#### At 10k events/sec (~864M events/day)

| Component | P1 | P2 | P3 (chosen) | P4 | P5 |
|-----------|---:|---:|---:|---:|---:|
| PostgreSQL (primary) | $200 | $200 | — | — | — |
| PostgreSQL (replica) | $150 | $150 | — | — | — |
| CDC tool (PeerDB/Debezium) | — | $100 | — | — | — |
| Kafka (3 brokers) | — | — | $600 | — | $600 |
| Kafka consumer process | — | — | $50 | — | $50 |
| Flink (JobManager + TaskManagers) | — | — | — | — | $700 |
| ClickHouse (1 node) | — | $300 | $300 | $300 | $300 |
| ClickHouse storage (1 TB/mo compressed) | — | $50 | $50 | $50 | $50 |
| Checkpoint/state storage (S3) | — | — | — | — | $10 |
| **Total infrastructure** | **$350** | **$800** | **$1,000** | **$350** | **$1,710** |

#### At 50k events/sec (~4.3B events/day)

| Component | P1 | P2 | P3 (chosen) | P4 | P5 |
|-----------|---:|---:|---:|---:|---:|
| PostgreSQL (primary, scaled) | $800 | $800 | — | — | — |
| PostgreSQL (2 replicas) | $600 | $600 | — | — | — |
| Citus/sharding overhead | $500 | $500 | — | — | — |
| CDC tool (scaled) | — | $300 | — | — | — |
| Kafka (5 brokers) | — | — | $1,000 | — | $1,000 |
| Kafka consumers (3 instances) | — | — | $150 | — | $150 |
| Flink cluster (scaled) | — | — | — | — | $1,200 |
| ClickHouse (2-node cluster) | — | $600 | $600 | $600 | $600 |
| ClickHouse storage (5 TB/mo) | — | $250 | $250 | $250 | $250 |
| **Total infrastructure** | **$1,900** | **$3,050** | **$2,000** | **$850** | **$3,200** |

> Note: P1 at 50k/sec requires Citus or application-level sharding, adding significant development cost not reflected in infrastructure alone.

#### At 100k events/sec (~8.6B events/day)

| Component | P1 | P2 | P3 (chosen) | P4 | P5 |
|-----------|---:|---:|---:|---:|---:|
| PostgreSQL (sharded cluster) | N/A | N/A | — | — | — |
| Kafka (8 brokers) | — | — | $1,600 | — | $1,600 |
| Kafka consumers (6 instances) | — | — | $300 | — | $300 |
| Flink cluster (scaled) | — | — | — | — | $2,000 |
| ClickHouse (3-node cluster) | — | — | $900 | $900 | $900 |
| ClickHouse storage (10 TB/mo) | — | — | $500 | $500 | $500 |
| **Total infrastructure** | **N/A** | **N/A** | **$3,300** | **$1,400** | **$5,300** |

> P1 and P2 are not viable at 100k/sec — PostgreSQL cannot sustain this write rate without extreme sharding complexity.

### Operational Costs (Personnel)

Estimated additional engineering time for operations and maintenance:

| Pattern | FTE Overhead (10k/sec) | FTE Overhead (50k/sec) | FTE Overhead (100k/sec) |
|---------|:----------------------:|:----------------------:|:-----------------------:|
| **P1** | 0.1 FTE | 0.3 FTE | N/A |
| **P2** | 0.2 FTE | 0.5 FTE | N/A |
| **P3** | 0.2 FTE | 0.3 FTE | 0.5 FTE |
| **P4** | 0.1 FTE | 0.2 FTE | 0.3 FTE |
| **P5** | 0.5 FTE | 0.7 FTE | 1.0 FTE |

### TCO Summary (Infrastructure + Operations at $150k/FTE)

| Throughput | P1 | P2 | P3 (chosen) | P4 | P5 |
|------------|---:|---:|---:|---:|---:|
| **10k/sec (annual)** | $22,200 | $39,600 | $41,700 | $19,200 | $111,120 |
| **50k/sec (annual)** | $67,800 | $126,600 | $61,500 | $40,200 | $143,400 |
| **100k/sec (annual)** | N/A | N/A | $129,600 | $73,800 | $213,600 |

**Key insight:** P3's cost scales linearly and predictably. P4 is cheapest at every tier but lacks replay and decoupling. P5 is 2-3x more expensive than P3 with no throughput benefit for write-through ingestion.

---

## Decision Tree

Use this decision tree to guide architectural choices as bxb's requirements evolve.

```
Is the event volume > 10k/sec?
│
├── NO (< 10k/sec):
│   │
│   ├── Need analytical queries on events?
│   │   ├── NO → P1: PostgreSQL-only (simplest, cheapest)
│   │   └── YES → Do you need ClickHouse-speed aggregations?
│   │       ├── NO → P1 with TimescaleDB (compression + continuous aggregates)
│   │       └── YES → P2: PostgreSQL + CDC → ClickHouse
│   │
│   └── Need event replay capability?
│       ├── NO → Stay with current pattern (above)
│       └── YES → P3: Kafka → ClickHouse (chosen architecture)
│
└── YES (> 10k/sec):
    │
    ├── Is volume < 50k/sec?
    │   │
    │   └── Need real-time stream processing (< 1 sec latency)?
    │       ├── NO → P3: Kafka → ClickHouse (add partitions + consumers)
    │       └── YES → Is processing simple (filter, enrich)?
    │           ├── YES → P3 + Kafka Streams (library in consumer)
    │           └── NO → P5: Kafka → Flink → ClickHouse
    │
    └── Is volume > 50k/sec?
        │
        ├── Is the write path simple (no transformations)?
        │   ├── YES → P3: Kafka → ClickHouse (scale consumers)
        │   └── NO → P5: Kafka → Flink → ClickHouse
        │
        └── Need pre-aggregation to reduce ClickHouse write load?
            ├── NO → P3 with more partitions
            └── YES → P5: Flink for windowed pre-aggregation
```

### Migration Triggers

| Trigger | Current State | Action |
|---------|---------------|--------|
| Sustained write rate > 8k/sec on PostgreSQL | P1 or P2 | Begin migration to P3 (add Kafka) |
| Aggregation queries > 5 seconds | P1 | Add ClickHouse (move to P2 or P3) |
| Need event replay or rebuild capability | P1, P2, or P4 | Introduce Kafka (move to P3) |
| Need 3+ independent event consumers | Any without Kafka | Move to P3 |
| Real-time processing < 1s required | P3 | Add Kafka Streams (simple) or Flink (complex) → P5 |
| Volume approaching 50k/sec | P3 | Scale Kafka partitions + consumers; evaluate pre-aggregation |
| ClickHouse write pressure at 100k+/sec | P3 | Add Flink pre-aggregation → P5 |
| PostgreSQL no longer needed for transactional subset | P3 | Simplify: remove PG from write path, keep for metadata only |

---

## Recommendation Summary

### Chosen Architecture: P3 (API → Kafka → ClickHouse)

**For bxb at 10k events/sec**, P3 provides the best balance of:

- **Sufficient throughput** with clear headroom to 50-100k/sec
- **Event replay capability** for rebuilding materialized views and fixing processing bugs
- **Decoupled architecture** where Kafka absorbs spikes and ClickHouse downtime doesn't affect the API
- **Multi-consumer support** for adding future processors (fraud detection, alerting, webhooks) without modifying the ingestion API
- **Reasonable cost** (~$1,000/month infrastructure) that scales linearly
- **Moderate complexity** manageable by a small Python-based team with Kafka's well-documented ecosystem

### What We Deliberately Left on the Table

| Capability | Available In | Why We Deferred |
|------------|-------------|-----------------|
| Sub-second analytics | P4 (direct CH), P5 (Flink) | 1-2 min latency is acceptable for billing |
| Real-time stream processing | P5 (Flink) | No current need; adds $700+/month and JVM ops burden |
| Simplest possible architecture | P1 (PG-only) | Doesn't meet replay requirement; PG hits ceiling at 10k/sec |
| Cheapest infrastructure | P4 (direct CH) | No replay; API couples to CH availability |
| ACID per-event guarantees | P1, P2 | At-least-once + ReplacingMergeTree dedup is sufficient for billing |

### Future Evolution Path

1. **Now (10k/sec):** P3 — Kafka → simple batch consumer → ClickHouse
2. **Growth (20-50k/sec):** P3 scaled — more Kafka partitions, more consumer instances, ClickHouse cluster
3. **Real-time needs:** P3 + Kafka Streams — add lightweight stream processing in the consumer for enrichment or filtering
4. **Complex processing (50k+/sec):** P5 — add Flink for windowed aggregation, multi-stream joins, or CEP
5. **Extreme scale (100k+/sec):** P5 scaled — multi-cluster Kafka, Flink pre-aggregation, ClickHouse sharded cluster

---

## References

- [[Direct-Clickhouse-Ingestion]] — Detailed analysis of ClickHouse HTTP interface, Buffer tables, Distributed tables, and insert benchmarks
- [[API-Direct-Write]] — PostgreSQL-only architecture, ETL/CDC patterns, TimescaleDB, read replica strategies
- [[Streaming-Ingestion]] — Apache Flink, Kafka Streams, AWS Kinesis, Apache Pulsar analysis
- [[Kafka-Event-Pipeline]] — bxb's chosen Kafka → ClickHouse pipeline design
