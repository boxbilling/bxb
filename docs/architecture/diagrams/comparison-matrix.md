---
type: reference
title: Ingestion Pattern Comparison Matrix
created: 2026-02-25
tags:
  - architecture
  - comparison
  - decision-record
related:
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Event-Ingestion-Architecture]]"
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[Streaming-Ingestion]]"
  - "[[API-Direct-Write]]"
---

# Ingestion Pattern Comparison Matrix

Visual comparison of all evaluated event ingestion patterns for the bxb usage-based billing platform.

## Pattern Overview

| ID | Pattern | Data Flow |
|----|---------|-----------|
| P1 | PostgreSQL Only | `API → PostgreSQL` |
| P2 | PostgreSQL + ETL | `API → PostgreSQL → ETL → ClickHouse` |
| P3 | Kafka + ClickHouse | `API → Kafka → Batch Consumer → ClickHouse` |
| P4 | ClickHouse Direct | `API → ClickHouse` |
| P5 | Kafka + Flink | `API → Kafka → Flink → ClickHouse` |

## Detailed Comparison

### Throughput & Latency

| Dimension | P1: PG Only | P2: PG + ETL | P3: Kafka + CH | P4: CH Direct | P5: Kafka + Flink |
|-----------|:-----------:|:------------:|:--------------:|:-------------:|:-----------------:|
| **Max Throughput** | 5-10k/sec | 5-10k/sec | 50-100k/sec | 100-500k/sec | 100k-1M/sec |
| **Ingestion Latency** | <10ms | 5-60 min | 1-2 min | <100ms | <1 sec |
| **Query Latency (100M rows)** | 2-30 sec | 10-500ms | 10-500ms | 10-500ms | 10-500ms |
| **Throughput Rating** | :small_orange_diamond: | :small_orange_diamond: | :white_check_mark: | :white_check_mark: | :white_check_mark: |

### Reliability & Durability

| Dimension | P1: PG Only | P2: PG + ETL | P3: Kafka + CH | P4: CH Direct | P5: Kafka + Flink |
|-----------|:-----------:|:------------:|:--------------:|:-------------:|:-----------------:|
| **Event Replay** | No | No | **Yes (7 days)** | No | **Yes (7 days)** |
| **Data Loss Risk** | Very Low | Low | Very Low | Medium | Very Low |
| **ACID Transactions** | **Yes** | Yes (PG side) | No (eventual) | No | No |
| **Deduplication** | Built-in | Built-in | Eventual (merge) | Eventual (merge) | Exactly-once |
| **Durability Rating** | :white_check_mark: | :white_check_mark: | :white_check_mark: | :small_orange_diamond: | :white_check_mark: |

### Cost & Operations

| Dimension | P1: PG Only | P2: PG + ETL | P3: Kafka + CH | P4: CH Direct | P5: Kafka + Flink |
|-----------|:-----------:|:------------:|:--------------:|:-------------:|:-----------------:|
| **Infra Cost (10k/sec)** | ~$350/mo | ~$800/mo | ~$1,000/mo | ~$350/mo | ~$1,710/mo |
| **Infra Cost (50k/sec)** | N/A | N/A | ~$2,000/mo | ~$700/mo | ~$3,200/mo |
| **Infra Cost (100k/sec)** | N/A | N/A | ~$3,300/mo | ~$1,400/mo | ~$5,300/mo |
| **Component Count** | 2 | 4-5 | 4 | 2 | 6-7 |
| **Team Expertise Needed** | SQL | SQL + ETL | SQL + Kafka | SQL + CH | SQL + Kafka + JVM |
| **Cost Rating** | :white_check_mark: | :small_orange_diamond: | :small_orange_diamond: | :white_check_mark: | :red_circle: |

### Scalability & Flexibility

| Dimension | P1: PG Only | P2: PG + ETL | P3: Kafka + CH | P4: CH Direct | P5: Kafka + Flink |
|-----------|:-----------:|:------------:|:--------------:|:-------------:|:-----------------:|
| **Horizontal Scale** | Limited | Limited | **Easy** | Easy | **Easy** |
| **Add Processors** | Difficult | Moderate | **Easy** | Difficult | **Easy** |
| **Multi-Consumer** | No | No | **Yes** | No | **Yes** |
| **Backpressure Handling** | DB locks | DB locks | **Kafka buffering** | Manual | **Kafka buffering** |
| **Scalability Rating** | :red_circle: | :red_circle: | :white_check_mark: | :small_orange_diamond: | :white_check_mark: |

## Scoring Summary

Rating scale: 3 = Excellent, 2 = Acceptable, 1 = Poor

| Criterion (Weight) | P1 | P2 | P3 | P4 | P5 |
|---------------------|:--:|:--:|:--:|:--:|:--:|
| Throughput (25%) | 1 | 1 | 3 | 3 | 3 |
| Replay Capability (20%) | 1 | 1 | 3 | 1 | 3 |
| Cost Efficiency (20%) | 3 | 2 | 2 | 3 | 1 |
| Operational Simplicity (15%) | 3 | 1 | 2 | 3 | 1 |
| Scalability (10%) | 1 | 1 | 3 | 2 | 3 |
| Query Performance (10%) | 1 | 3 | 3 | 3 | 3 |
| **Weighted Score** | **1.60** | **1.30** | **2.65** | **2.35** | **2.20** |

### Ranking

1. **P3: Kafka + ClickHouse — 2.65** (Chosen)
2. P4: ClickHouse Direct — 2.35
3. P5: Kafka + Flink — 2.20
4. P1: PostgreSQL Only — 1.60
5. P2: PostgreSQL + ETL — 1.30

## Decision Rationale

P3 (Kafka + ClickHouse) was selected because:

- **Replay is non-negotiable** — every event affects revenue; ability to reprocess after bug fixes is critical (eliminates P1, P2, P4)
- **Cost-effective at 10k/sec** — $1,000/mo vs P5's $1,710/mo, with no JVM overhead for simple write-through
- **Clear scaling path** — grows from 10k to 100k/sec by adding partitions, consumers, and ClickHouse nodes
- **Python-native** — batch consumer is simple Python; no Flink/JVM expertise required
- **Proven fallback** — PostgreSQL remains source of truth; queries fall back during ClickHouse downtime

## When to Reconsider

| Trigger | Consider |
|---------|----------|
| Sustained throughput > 80k/sec with complex enrichment | Migrate to P5 (add Flink) |
| Analytics-only workload, no billing | Simplify to P4 (ClickHouse direct) |
| Event volume < 1k/sec, cost-constrained startup | Start with P1 (PostgreSQL only) |
| Real-time fraud detection needed | Add Kafka Streams alongside P3 |
