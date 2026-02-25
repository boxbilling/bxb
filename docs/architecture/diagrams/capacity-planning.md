---
type: analysis
title: Capacity Planning — Cost vs. Throughput Analysis
created: 2026-02-25
tags:
  - capacity-planning
  - cost-analysis
  - infrastructure
related:
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Event-Ingestion-Architecture]]"
  - "[[Comparison-Matrix]]"
---

# Capacity Planning: Cost vs. Throughput

Infrastructure cost projections and resource requirements for each ingestion pattern at varying throughput levels.

## Cost vs. Throughput Overview

```
Monthly Infrastructure Cost ($)
│
│                                                          P5 [$5,300]
5000 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ●
│                                                      ╱
│                                                    ╱
4000 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╱─ ─ ─ ─ ─
│                                                ╱
│                                      P3 [$3,300]
3000 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─●─ ─╱─ ─ ─ ─ ─ ─
│                                  P5 ╱  ╱
│                              [$3,200] ╱
│                                ●   ╱
2000 ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╱─ ─●─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
│                       P3 ╱ P3 [$2,000]
│               P5    ╱[$1,710]
│             [$1,710]╱                             P4 [$1,400]
1000 ┤ ─ ─ ─ ─ ─ ─●╱─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─●─ ─ ─
│        P3  ╱[$1,000]            P4 [$700]       ╱
│       ●─╱─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─●─ ─ ─ ─╱─ ─ ─ ─ ─ ─
│     P2 [$800]                     ╱         ╱
│  P1 [$350]  P4 [$350]          ╱          ╱
│    ●────────●─ ─ ─ ─ ─ ─ ─ ╱─ ─ ─ ─ ─╱─ ─ ─ ─ ─ ─ ─ ─ ─
0 ┤───┬──────────┬──────────┬──────────┬──────────┬──────────
    0       10k        50k       100k       Throughput
                  Events per Second                (events/sec)

Legend: ● P1/P2 (PostgreSQL)  ● P3 (Kafka+CH)  ● P4 (CH Direct)  ● P5 (Kafka+Flink)
Note: P1 and P2 cannot scale beyond ~10k/sec (PostgreSQL write ceiling)
```

## Detailed Cost Breakdown by Pattern

### P1: PostgreSQL Only

| Throughput | PostgreSQL | App Server | Total/mo | Notes |
|-----------|-----------|-----------|---------|-------|
| 1k/sec | $100 (db.r6g.large) | $50 | **$150** | Comfortable |
| 5k/sec | $200 (db.r6g.xlarge) | $100 | **$300** | Moderate load |
| 10k/sec | $250 (db.r6g.2xlarge) | $100 | **$350** | At ceiling |
| 20k/sec | — | — | **N/A** | Exceeds PG write capacity |

**Scaling ceiling:** ~10k writes/sec with optimized batch inserts and connection pooling.

### P2: PostgreSQL + ETL → ClickHouse

| Throughput | PostgreSQL | ETL Infra | ClickHouse | Total/mo | Notes |
|-----------|-----------|----------|-----------|---------|-------|
| 1k/sec | $100 | $50 | $200 | **$350** | Over-provisioned |
| 5k/sec | $200 | $100 | $200 | **$500** | Good fit |
| 10k/sec | $250 | $150 | $400 | **$800** | PG at ceiling |
| 20k/sec | — | — | — | **N/A** | PG bottleneck |

**Scaling ceiling:** Same as P1; PostgreSQL is the bottleneck regardless of downstream.

### P3: Kafka + ClickHouse (Chosen)

| Throughput | Kafka | Consumers | ClickHouse | PostgreSQL | Total/mo | Notes |
|-----------|-------|----------|-----------|-----------|---------|-------|
| 1k/sec | $200 (3 brokers) | $50 | $200 | $100 | **$550** | Over-provisioned |
| 10k/sec | $300 (3 brokers) | $100 | $400 | $200 | **$1,000** | Current target |
| 50k/sec | $600 (5 brokers) | $200 | $800 (2 nodes) | $200 | **$2,000** | Phase 2 |
| 100k/sec | $900 (8 brokers) | $400 | $1,600 (3 nodes) | $200 | **$3,300** | Phase 3 |

**Cost per million events:**
- At 10k/sec: $1,000 / 26.4B events = **$0.038 per million events**
- At 50k/sec: $2,000 / 132B events = **$0.015 per million events**
- At 100k/sec: $3,300 / 264B events = **$0.012 per million events**

### P4: ClickHouse Direct

| Throughput | ClickHouse | App Server | Total/mo | Notes |
|-----------|-----------|-----------|---------|-------|
| 1k/sec | $200 | $50 | **$250** | Simplest setup |
| 10k/sec | $250 | $100 | **$350** | Cost-effective |
| 50k/sec | $500 (2 nodes) | $200 | **$700** | Add replication |
| 100k/sec | $1,000 (3 nodes) | $400 | **$1,400** | Sharded cluster |

**Trade-off:** Cheapest at every throughput level, but no event replay or decoupling.

### P5: Kafka + Flink + ClickHouse

| Throughput | Kafka | Flink | ClickHouse | PostgreSQL | Total/mo | Notes |
|-----------|-------|-------|-----------|-----------|---------|-------|
| 1k/sec | $200 | $300 | $200 | $100 | **$800** | Flink is expensive idle |
| 10k/sec | $300 | $510 | $400 | $200 | **$1,710** | JVM TaskManagers |
| 50k/sec | $600 | $800 | $800 | $200 | **$3,200** | Flink scales well |
| 100k/sec | $900 | $1,400 | $1,600 | $200 | **$5,300** | Full streaming stack |

**Break-even vs P3:** Flink adds value only when complex stream processing (windowed aggregations, CEP) is required.

## Cost Efficiency Comparison

```
Cost per Million Events (at each throughput level)
│
│  $0.15
│    ┃
│    ┃  P2
│  $0.10
│    ┃       P5
│    ┃  P1   ┃
│    ┃  ┃    ┃
│  $0.05
│    ┃  ┃    ┃     P3
│    ┃  ┃    ┃     ┃     P4
│    ┃  ┃    ┃     ┃     ┃
│  $0.038 ─ ─ ─ ─ ─ ┃─ ─ ─ ─ ─ ─ ─  ← P3 at 10k/sec
│    ┃  ┃    ┃     ┃     ┃
│  $0.015 ─ ─ ─ ─ ─ ─ ─ ─┃─ ─ ─ ─ ─  ← P3 at 50k/sec
│    ┃  ┃    ┃     ┃     ┃
│  $0.012 ─ ─ ─ ─ ─ ─ ─ ─ ─ ┃─ ─ ─ ─  ← P3 at 100k/sec
│  $0.005 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┃─ ─  ← P4 at 100k/sec
│    ┗━━━┻━━━━┻━━━━━┻━━━━━┛
│       10k   50k   100k
│         Events per Second
```

## Resource Requirements by Throughput

### At 10,000 events/sec (Current Target)

| Resource | P1 | P3 (Chosen) | P4 | P5 |
|----------|:--:|:-----------:|:--:|:--:|
| **CPU Cores** | 8 | 12 | 4 | 20 |
| **Memory (GB)** | 32 | 24 | 8 | 40 |
| **Storage (TB/mo)** | 2.5 | 1.2 | 0.8 | 1.2 |
| **Network (Mbps)** | 50 | 80 | 40 | 100 |
| **Instances** | 2 | 6 | 2 | 8 |

### At 100,000 events/sec (Future Target)

| Resource | P3 | P4 | P5 |
|----------|:--:|:--:|:--:|
| **CPU Cores** | 48 | 24 | 72 |
| **Memory (GB)** | 96 | 48 | 160 |
| **Storage (TB/mo)** | 12 | 8 | 12 |
| **Network (Mbps)** | 800 | 400 | 1000 |
| **Instances** | 15 | 6 | 20 |

## Storage Growth Projections

Based on average event size of ~500 bytes uncompressed, ~100 bytes compressed (lz4, ~5x ratio):

| Throughput | Events/Day | Raw/Day | Compressed/Day | Compressed/Month | Compressed/Year |
|-----------|-----------|---------|----------------|-----------------|----------------|
| 1k/sec | 86.4M | 43 GB | 8.6 GB | 258 GB | 3.1 TB |
| 10k/sec | 864M | 432 GB | 86 GB | 2.6 TB | 31 TB |
| 50k/sec | 4.32B | 2.16 TB | 432 GB | 13 TB | 156 TB |
| 100k/sec | 8.64B | 4.32 TB | 864 GB | 26 TB | 312 TB |

### Retention-Based Storage (with TTL)

| Retention | Storage at 10k/sec | Storage at 100k/sec |
|-----------|-------------------|---------------------|
| 30 days | 2.6 TB | 26 TB |
| 90 days | 7.8 TB | 78 TB |
| 1 year | 31 TB | 312 TB |
| 3 years | 93 TB | 936 TB |

**Recommendation:** 90-day hot storage in ClickHouse, archive older data to S3/cold storage.

## Scaling Decision Triggers

| Metric | Threshold | Action |
|--------|-----------|--------|
| Consumer lag | > 10,000 messages sustained | Add consumer instances |
| Consumer lag | > 100,000 messages | Add Kafka partitions + consumers |
| ClickHouse CPU | > 70% sustained | Add ClickHouse node/replica |
| ClickHouse merge time | > 60 seconds | Increase memory or add node |
| Kafka disk usage | > 70% | Add brokers or reduce retention |
| API latency P99 | > 200ms | Scale API servers |
| Event throughput | Approaching 2x current capacity | Begin next phase planning |

## TCO Summary (3-Year Projection at 10k/sec)

| Pattern | Monthly | Annual | 3-Year TCO | Engineering Cost | Total 3-Year |
|---------|---------|--------|------------|-----------------|-------------|
| P1 | $350 | $4,200 | $12,600 | Low ($0) | ~$12,600 |
| P2 | $800 | $9,600 | $28,800 | Medium ($20k) | ~$48,800 |
| **P3** | **$1,000** | **$12,000** | **$36,000** | **Medium ($15k)** | **~$51,000** |
| P4 | $350 | $4,200 | $12,600 | Low ($5k) | ~$17,600 |
| P5 | $1,710 | $20,520 | $61,560 | High ($40k) | ~$101,560 |

**Note:** P1 and P2 exclude the cost of re-architecture when hitting the 10k/sec ceiling, which is the likely outcome at bxb's growth trajectory. P3's premium over P4 buys event replay — a requirement for billing accuracy.
