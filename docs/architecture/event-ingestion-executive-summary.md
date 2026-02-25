---
type: report
title: "Event Ingestion Architecture: Executive Summary"
created: 2026-02-25
author: bxb Engineering
reviewed_by: bxb Engineering
version: "1.0"
tags:
  - summary
  - architecture
  - decision
related:
  - "[[Event-Ingestion-Architecture]]"
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Capacity-Planning]]"
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[API-Direct-Write]]"
  - "[[Streaming-Ingestion]]"
---

# Event Ingestion Architecture: Executive Summary

## Problem Statement

bxb is a usage-based billing platform that must ingest, store, and aggregate **10,000 events per second** (864 million events/day) with zero silent data loss. Every event directly affects revenue — lost or miscounted events mean incorrect invoices. The existing PostgreSQL-only architecture is approaching its write ceiling, and aggregation queries over hundreds of millions of rows take minutes instead of milliseconds. A new ingestion architecture is needed that handles current volume with headroom to grow, while keeping infrastructure costs reasonable.

## Chosen Solution: API → Kafka → ClickHouse

We selected a **Kafka-mediated batch pipeline** into ClickHouse for analytical storage: the API publishes events to a 3-broker Kafka cluster, a Python batch consumer accumulates events into batches of 5,000–10,000 rows, and bulk-inserts them into ClickHouse every 1–5 seconds. PostgreSQL remains the transactional source of truth; ClickHouse powers all billing aggregation queries with 40–100x speedup over PostgreSQL.

```
API Server ──▶ Kafka (3 brokers, 12 partitions) ──▶ Batch Consumer ──▶ ClickHouse
    │                                                                     │
    └──▶ PostgreSQL (source of truth)              Aggregation Queries ◀──┘
```

## Key Metrics

| Metric | Value |
|--------|-------|
| **Throughput** | 10,000 events/sec sustained (headroom to 50–100k/sec) |
| **Ingestion-to-query latency** | 10–30 seconds typical; <2 minutes worst case |
| **Infrastructure cost** | ~$1,000/month at 10k/sec |
| **Aggregation query speed** | 10–500 ms (40–100x faster than PostgreSQL) |
| **Data durability** | At-least-once delivery (Kafka `acks=all` + ClickHouse `ReplacingMergeTree` dedup) |
| **Event replay** | Full replay from any Kafka offset (7-day retention) |

## Decision Rationale

We evaluated five ingestion patterns and chose Kafka → ClickHouse (P3) because:

1. **Event replay is non-negotiable for billing.** Kafka retains events for replay — essential for rebuilding materialized views and fixing aggregation bugs. Direct ClickHouse writes (P4) scored equally on throughput and cost but cannot replay events.
2. **Sufficient throughput with clear scaling path.** P3 handles 50–100k/sec by adding Kafka partitions and consumer instances. PostgreSQL-based patterns (P1, P2) hit their write ceiling at our current target rate.
3. **Right-sized complexity and cost.** Apache Flink (P5) adds ~$700/month and JVM operational burden with no benefit for our simple write-through use case. Flink can be added later if real-time stream processing requirements emerge.

## Success Criteria

| Goal | Status |
|------|--------|
| Sustain 10,000 events/sec with <5% CPU utilization on ClickHouse | Achieved (5–15% CPU) |
| Aggregation queries under 500ms at 100M rows | Achieved (10–500ms depending on query type) |
| No silent event loss; at-least-once delivery end-to-end | Achieved (Kafka replication + ReplacingMergeTree dedup) |
| PostgreSQL fallback for billing queries during ClickHouse downtime | Achieved (automatic fallback path) |
| Infrastructure cost under $1,500/month at 10k/sec | Achieved (~$1,000/month) |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Kafka operational complexity** — Small team has limited Kafka experience; broker failures or partition rebalancing could cause ingestion delays | Medium | Kafka's well-documented ecosystem reduces learning curve. Consumer lag monitoring with automated alerts at >100k messages. Single consumer group keeps the initial deployment simple. Managed Kafka (e.g., Confluent Cloud, AWS MSK) is a fallback if self-hosting proves burdensome. |
| **ClickHouse eventual dedup** — `ReplacingMergeTree` deduplicates during background merges, not at insert time; billing queries before merge completion may see duplicate events | High (billing accuracy) | Use `FINAL` modifier on billing-critical queries (invoice generation) to force dedup at read time. Daily reconciliation job compares PostgreSQL and ClickHouse event counts, alerting on >1% drift. |
| **Scaling trigger timing** — Delayed response to growing event volume could cause consumer lag buildup and increased ingestion latency | Medium | Monitoring alerts on consumer lag (>100k messages), ClickHouse merge backlog (>300 parts), and throughput approaching 2x current capacity. Scaling playbook documented with clear triggers: add consumers at 20k/sec, add ClickHouse nodes at 50k/sec. |

## Further Reading

- [[Event-Ingestion-Architecture]] — Full technical blog post with implementation details, code examples, performance benchmarks, and troubleshooting guide
- [[Ingestion-Pattern-Comparison]] — Detailed comparison matrix and TCO analysis across all five ingestion patterns
- [[Capacity-Planning]] — Cost vs. throughput projections and resource requirements at 10k, 50k, and 100k events/sec
