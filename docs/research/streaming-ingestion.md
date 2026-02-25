---
type: research
title: Streaming Ingestion Patterns (Flink, Kafka Streams, Kinesis, Pulsar)
created: 2026-02-25
tags:
  - kafka
  - flink
  - streaming
  - real-time
author: bxb Engineering
reviewed_by: bxb Engineering
version: "1.0"
related:
  - "[[Direct-Clickhouse-Ingestion]]"
  - "[[API-Direct-Write]]"
  - "[[Ingestion-Pattern-Comparison]]"
  - "[[Event-Ingestion-Architecture]]"
---

# Streaming Ingestion Patterns

This document investigates stream processing frameworks and managed streaming services as alternatives or complements to bxb's chosen Kafka → ClickHouse ingestion architecture. It evaluates Apache Flink, Kafka Streams, AWS Kinesis, and Apache Pulsar — covering their trade-offs for real-time event processing at 10k–100k events/sec.

## Table of Contents

- [Overview](#overview)
- [Apache Flink for Stream Processing](#apache-flink-for-stream-processing)
- [Kafka Streams as Lightweight Alternative](#kafka-streams-as-lightweight-alternative)
- [AWS Kinesis Data Streams and Kinesis Firehose](#aws-kinesis-data-streams-and-kinesis-firehose)
- [Apache Pulsar as Kafka Alternative](#apache-pulsar-as-kafka-alternative)
- [Pros: Streaming Ingestion Patterns](#pros-streaming-ingestion-patterns)
- [Cons: Streaming Ingestion Patterns](#cons-streaming-ingestion-patterns)
- [Decision Matrix: Streaming vs. Batch](#decision-matrix-streaming-vs-batch)
- [Relevance to bxb's Current Architecture](#relevance-to-bxbs-current-architecture)

---

## Overview

Streaming ingestion patterns add a real-time processing layer between event producers and the analytical data store. Instead of simply buffering events (as Kafka does in bxb's current architecture), a stream processor applies transformations, enrichment, aggregation, and filtering in flight.

**Pattern (Stream Processing):**
```
API Server → Kafka → Stream Processor (Flink / Kafka Streams) → ClickHouse
```

**Pattern (Managed Streaming):**
```
API Server → Kinesis Data Streams → Kinesis Firehose → ClickHouse / S3
```

**Pattern (Pulsar-based):**
```
API Server → Pulsar → Pulsar Functions → ClickHouse
```

Compared to bxb's chosen pattern:
```
API Server → Kafka → Batch Consumer → ClickHouse
```

The key distinction: bxb's current batch consumer is a simple process that reads from Kafka and writes to ClickHouse. A stream processor adds stateful computation — windowed aggregations, joins, deduplication, and complex event processing — between the broker and the sink.

---

## Apache Flink for Stream Processing

### Overview

Apache Flink is a distributed stream processing framework designed for stateful computations over unbounded data streams. It is the de facto standard for high-throughput, low-latency stream processing in production deployments.

### Architecture

```
                    ┌─────────────────────────┐
                    │      JobManager         │
                    │  (coordinator/scheduler) │
                    └─────┬───────┬───────┬──┘
                          │       │       │
                    ┌─────▼┐ ┌───▼──┐ ┌──▼────┐
                    │ Task │ │ Task │ │ Task  │
                    │Mgr 1 │ │Mgr 2 │ │Mgr 3  │
                    │      │ │      │ │       │
                    │[slot]│ │[slot]│ │[slot] │
                    │[slot]│ │[slot]│ │[slot] │
                    └──────┘ └──────┘ └───────┘
```

- **JobManager**: Coordinates job execution, manages checkpoints, handles failover.
- **TaskManagers**: Worker processes that execute stream operators. Each has a fixed number of task slots.
- **Task Slots**: Units of resource isolation within a TaskManager (memory + CPU fraction).

### Stateful Transformations

Flink's core strength is managing large-scale distributed state:

```java
// Stateful deduplication using Flink's keyed state
public class EventDeduplicator extends KeyedProcessFunction<String, Event, Event> {

    private ValueState<Boolean> seenState;

    @Override
    public void open(Configuration parameters) {
        ValueStateDescriptor<Boolean> descriptor =
            new ValueStateDescriptor<>("seen", Boolean.class);
        // State TTL: auto-expire after 24 hours to bound memory
        StateTtlConfig ttlConfig = StateTtlConfig.newBuilder(Time.hours(24))
            .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
            .cleanupFullSnapshot()
            .build();
        descriptor.enableTimeToLive(ttlConfig);
        seenState = getRuntimeContext().getState(descriptor);
    }

    @Override
    public void processElement(Event event, Context ctx, Collector<Event> out)
            throws Exception {
        String txnId = event.getTransactionId();
        if (seenState.value() == null) {
            seenState.update(true);
            out.collect(event);  // First occurrence — emit
        }
        // Duplicate — drop silently
    }
}
```

**State backends:**

| Backend | Storage | Use Case | State Size |
|---------|---------|----------|------------|
| **HashMapStateBackend** | JVM heap | Low-latency, small state | < ~5 GB per TaskManager |
| **EmbeddedRocksDBStateBackend** | RocksDB (disk + memory) | Large state, incremental checkpoints | Terabytes per TaskManager |

For bxb's deduplication use case (tracking `transaction_id` for 24 hours at 10k/sec = ~864M keys/day), **RocksDB** is required — heap-based state would cause OOM.

### Exactly-Once Semantics

Flink provides exactly-once processing guarantees through a combination of checkpointing and two-phase commit:

**Checkpointing:**
1. JobManager injects a checkpoint barrier into the source streams.
2. Barriers flow through the DAG. When an operator receives barriers from all inputs, it snapshots its state.
3. State snapshots are persisted to a durable store (S3, HDFS, or GCS).
4. On failure, Flink restores state from the last completed checkpoint and replays events from the source offset.

**Two-Phase Commit (for sinks):**
- Flink's `TwoPhaseCommitSinkFunction` ensures that sink writes are committed atomically with checkpoint completion.
- For ClickHouse: no native two-phase commit support. The practical approach is idempotent writes with `ReplacingMergeTree` deduplication.
- For Kafka sinks: Flink supports Kafka transactions, providing true exactly-once end-to-end.

**Checkpoint configuration:**

```java
StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();
env.enableCheckpointing(60_000);  // Checkpoint every 60 seconds
env.getCheckpointConfig().setCheckpointingMode(CheckpointingMode.EXACTLY_ONCE);
env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30_000);
env.getCheckpointConfig().setCheckpointTimeout(120_000);
env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);
// Persist checkpoints to S3
env.getCheckpointConfig().setCheckpointStorage("s3://flink-checkpoints/");
```

**Checkpoint overhead:**
- At 10k events/sec with 60-second intervals: ~600k events buffered per checkpoint cycle.
- RocksDB incremental checkpoints: typically <1 second for moderate state sizes.
- Full checkpoints on large state (>100 GB): can take minutes and cause backpressure.

### Windowing

Flink provides rich windowing semantics for time-based aggregations:

```java
// Tumbling window: aggregate events every 5 minutes
DataStream<UsageAggregate> aggregated = events
    .keyBy(Event::getOrganizationId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .aggregate(new UsageAggregator());

// Sliding window: compute rolling 1-hour sum, updated every minute
DataStream<UsageAggregate> rolling = events
    .keyBy(Event::getOrganizationId)
    .window(SlidingEventTimeWindows.of(Time.hours(1), Time.minutes(1)))
    .aggregate(new UsageAggregator());

// Session window: group events with gaps < 30 minutes
DataStream<UsageAggregate> sessions = events
    .keyBy(Event::getExternalCustomerId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .aggregate(new UsageAggregator());
```

**Window types:**

| Type | Behavior | Use Case |
|------|----------|----------|
| **Tumbling** | Fixed, non-overlapping intervals | Hourly billing aggregation |
| **Sliding** | Overlapping intervals | Rolling averages, rate limiting |
| **Session** | Activity-based, dynamic gaps | User session analytics |
| **Global** | Single window per key, custom triggers | Accumulate until explicit flush |

**Late-arrival handling:**

```java
// Allow events up to 5 minutes late
.window(TumblingEventTimeWindows.of(Time.minutes(5)))
.allowedLateness(Time.minutes(5))
.sideOutputLateData(lateOutputTag)  // Route very late events to side output
```

### Flink SQL / Table API

For teams that prefer SQL over Java/Python APIs:

```sql
-- Real-time aggregation using Flink SQL
CREATE TABLE events (
    organization_id STRING,
    code STRING,
    value DOUBLE,
    event_time TIMESTAMP(3),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' MINUTE
) WITH (
    'connector' = 'kafka',
    'topic' = 'billing-events',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format' = 'json'
);

CREATE TABLE hourly_usage (
    window_start TIMESTAMP(3),
    organization_id STRING,
    code STRING,
    event_count BIGINT,
    total_value DOUBLE
) WITH (
    'connector' = 'jdbc',
    'url' = 'jdbc:clickhouse://clickhouse:8123/default',
    'table-name' = 'hourly_usage'
);

INSERT INTO hourly_usage
SELECT
    TUMBLE_START(event_time, INTERVAL '1' HOUR) AS window_start,
    organization_id,
    code,
    COUNT(*) AS event_count,
    SUM(value) AS total_value
FROM events
GROUP BY
    TUMBLE(event_time, INTERVAL '1' HOUR),
    organization_id,
    code;
```

### Performance Characteristics

| Metric | Value | Conditions |
|--------|-------|------------|
| **Throughput (single node)** | 1–5M events/sec | Stateless transformations |
| **Throughput (stateful, RocksDB)** | 100k–1M events/sec | Keyed state, checkpointing enabled |
| **Latency (event-to-output)** | 10–100ms | With checkpointing; lower without |
| **Checkpoint duration** | 1–10 sec | Incremental, moderate state |
| **State size supported** | Terabytes | RocksDB backend, S3 checkpoints |
| **Recovery time** | 10–60 sec | From latest checkpoint |

### Deployment Options

| Option | Ops Complexity | Cost | Notes |
|--------|---------------|------|-------|
| **Self-managed (Kubernetes)** | High | Low (compute only) | Full control, requires Flink expertise |
| **Amazon Managed Flink (formerly Kinesis Data Analytics)** | Low | Medium–High | Serverless, auto-scaling |
| **Confluent Cloud (Flink)** | Low | High | Integrated with Confluent Kafka |
| **Ververica Platform** | Medium | Medium | Commercial Flink management |

---

## Kafka Streams as Lightweight Alternative

### Overview

Kafka Streams is a client library for building stream processing applications on top of Apache Kafka. Unlike Flink (which is a separate distributed system), Kafka Streams runs as part of the application process — no separate cluster to deploy.

### Architecture

```
┌──────────────────────────────────────────┐
│         Application Process              │
│                                          │
│  ┌────────────┐    ┌──────────────────┐  │
│  │  Kafka     │    │  State Store     │  │
│  │  Consumer  │───▶│  (RocksDB/       │  │
│  │            │    │   In-Memory)     │  │
│  └────────────┘    └──────────────────┘  │
│        │                    │             │
│        ▼                    ▼             │
│  ┌────────────┐    ┌──────────────────┐  │
│  │  Stream    │    │  Kafka Producer  │  │
│  │  Topology  │───▶│  (output topics) │  │
│  └────────────┘    └──────────────────┘  │
└──────────────────────────────────────────┘
```

- **No separate cluster**: Kafka Streams is a library embedded in the application JVM.
- **Scaling**: Deploy multiple application instances. Kafka Streams uses Kafka's consumer group protocol to distribute partitions across instances.
- **State stores**: Backed by RocksDB (default) with changelog topics in Kafka for fault tolerance.

### Topology and Processing

```java
StreamsBuilder builder = new StreamsBuilder();

// Read from input topic
KStream<String, Event> events = builder.stream("billing-events");

// Stateless transformation: enrich events
KStream<String, EnrichedEvent> enriched = events.mapValues(event -> {
    return new EnrichedEvent(event, lookupCustomerTier(event.getCustomerId()));
});

// Stateful aggregation: count events per org per hour
KTable<Windowed<String>, Long> hourlyCounts = enriched
    .groupByKey()
    .windowedBy(TimeWindows.ofSizeWithNoGrace(Duration.ofHours(1)))
    .count(Materialized.as("hourly-counts"));

// Write aggregations to output topic
hourlyCounts.toStream()
    .map((windowedKey, count) -> KeyValue.pair(
        windowedKey.key(),
        new UsageAggregate(windowedKey.window().start(), windowedKey.key(), count)
    ))
    .to("usage-aggregates");
```

### State Stores and Fault Tolerance

| Feature | Kafka Streams | Flink |
|---------|--------------|-------|
| **State backend** | RocksDB or in-memory | RocksDB or HashMapState |
| **State persistence** | Changelog topics in Kafka | Checkpoints to S3/HDFS |
| **Recovery mechanism** | Replay changelog topic | Restore from checkpoint + replay |
| **Recovery time** | Minutes (rebuilds from changelog) | Seconds (restores snapshot) |
| **Standby replicas** | Yes (`num.standby.replicas`) | Yes (via checkpoint) |
| **State size** | Limited by local disk | Terabytes (RocksDB + S3) |

**Changelog topics**: Every state mutation is logged to a Kafka topic (e.g., `app-hourly-counts-changelog`). On failure, the new instance replays the changelog to rebuild state. This can take minutes for large state stores.

**Standby replicas**: Configure `num.standby.replicas=1` to maintain hot standby copies of state stores, reducing recovery time to seconds.

### Exactly-Once Semantics

Kafka Streams supports exactly-once processing via Kafka's transactional protocol:

```java
Properties props = new Properties();
props.put(StreamsConfig.PROCESSING_GUARANTEE_CONFIG,
          StreamsConfig.EXACTLY_ONCE_V2);  // Requires Kafka 2.5+
```

- **How it works**: Kafka Streams wraps each processing step (read → transform → state update → write) in a Kafka transaction. Either all changes commit atomically, or none do.
- **Throughput impact**: ~10–30% reduction vs. at-least-once.
- **Limitation**: Only guarantees exactly-once within the Kafka ecosystem. Writing to an external system (ClickHouse) is at-least-once unless the sink is idempotent.

### When to Use Kafka Streams vs. Flink

| Dimension | Kafka Streams | Flink |
|-----------|--------------|-------|
| **Deployment** | Library in your app (no cluster) | Separate distributed system |
| **Ops overhead** | Low (just Kafka) | High (JobManager + TaskManagers) |
| **Throughput** | 10k–500k events/sec per instance | 100k–5M events/sec per node |
| **State size** | GBs (limited by local disk) | TBs (RocksDB + remote storage) |
| **Windowing** | Basic (tumbling, hopping, session) | Rich (custom triggers, late data) |
| **Multi-source joins** | Kafka topics only | Kafka, files, databases, sockets |
| **SQL support** | ksqlDB (separate component) | Flink SQL (built-in) |
| **Best for** | Simple enrichment, filtering, small aggregations | Complex event processing, large state |

**For bxb**: If the stream processing needs are limited to deduplication, enrichment, and basic aggregations, Kafka Streams is the simpler choice. If complex windowed joins, large-state computations, or multi-source processing is needed, Flink is the better fit.

---

## AWS Kinesis Data Streams and Kinesis Firehose

### Overview

AWS Kinesis provides a fully managed streaming platform as an alternative to self-managed Kafka. It consists of two primary services:

- **Kinesis Data Streams (KDS)**: A real-time data streaming service (analogous to Kafka topics).
- **Kinesis Data Firehose**: A managed ETL/delivery service that loads streaming data into destinations (S3, Redshift, OpenSearch, HTTP endpoints).

### Kinesis Data Streams

**Architecture:**
```
Producers → Kinesis Data Stream (shards) → Consumers
                                           ├── Lambda
                                           ├── KCL Application
                                           └── Firehose
```

**Key concepts:**

| Concept | Description |
|---------|-------------|
| **Shard** | Unit of throughput capacity. Each shard: 1 MB/sec write, 2 MB/sec read. |
| **Partition key** | Determines shard assignment (hash-based). Analogous to Kafka partition key. |
| **Retention** | 24 hours default, up to 365 days (extended retention). |
| **Enhanced fan-out** | Dedicated 2 MB/sec per consumer per shard (vs. shared 2 MB/sec). |
| **On-demand mode** | Auto-scales shards based on throughput (no capacity planning). |

**Capacity planning for bxb (10k events/sec):**

| Mode | Shards Needed | Monthly Cost (estimate) |
|------|--------------|------------------------|
| **Provisioned** | 10 shards (at ~1k events/sec per shard, 1 KB avg) | ~$365/month |
| **On-demand** | Auto-scaled | ~$450/month (pay per GB ingested) |

**vs. Kafka (self-managed):**

| Dimension | Kinesis Data Streams | Kafka (self-managed) |
|-----------|---------------------|---------------------|
| **Ops overhead** | Zero (fully managed) | High (broker management, ZooKeeper/KRaft) |
| **Throughput per shard/partition** | 1 MB/sec write | 10+ MB/sec per partition |
| **Consumer model** | KCL, Lambda, enhanced fan-out | Consumer groups, flexible |
| **Retention** | Up to 365 days | Unlimited (disk-bound) |
| **Cost at 10k/sec** | ~$400–600/month | ~$600–900/month (3 brokers) |
| **Replay** | Yes (by timestamp or sequence number) | Yes (by offset) |
| **Ecosystem** | AWS-native (Lambda, Firehose, Analytics) | Broader ecosystem (Connect, Streams, Flink) |

### Kinesis Data Firehose

Firehose provides managed batch delivery from streaming sources to destinations — no code required for the delivery pipeline.

**Architecture:**
```
Kinesis Data Stream ──┐
                      ├──▶ Firehose ──▶ S3 / Redshift / OpenSearch / HTTP
Direct PUT ──────────┘       │
                             ├── Optional: Lambda transformation
                             ├── Buffering (size or time)
                             └── Compression (gzip, snappy, zip)
```

**Key features:**

| Feature | Detail |
|---------|--------|
| **Buffering** | Buffer by size (1–128 MB) or time (60–900 seconds) before delivery |
| **Transformation** | Invoke Lambda for record transformation (enrich, filter, format) |
| **Compression** | gzip, Snappy, Zip, Hadoop-compatible Snappy |
| **Format conversion** | JSON → Parquet/ORC (using Glue Data Catalog schema) |
| **Error handling** | Failed records to S3 error bucket |
| **Delivery guarantee** | At-least-once |

**ClickHouse delivery via Firehose:**

Firehose does not have a native ClickHouse destination. Options:

1. **HTTP endpoint destination**: Firehose delivers batches to an HTTP endpoint → write a small service that receives batches and inserts into ClickHouse.
2. **S3 + ClickHouse S3 table function**: Firehose writes Parquet to S3 → ClickHouse reads via `s3()` table function or S3Queue engine.
3. **S3 + ClickHouse S3Queue engine**: ClickHouse continuously polls an S3 prefix for new files and ingests them.

```sql
-- ClickHouse S3Queue engine: auto-ingest from S3
CREATE TABLE events_s3_queue (
    organization_id String,
    transaction_id String,
    external_customer_id String,
    code String,
    timestamp DateTime64(3),
    properties String,
    value Nullable(Float64),
    decimal_value Nullable(Decimal128(18))
) ENGINE = S3Queue(
    'https://s3.amazonaws.com/billing-events/firehose/*',
    'JSONEachRow'
) SETTINGS
    mode = 'unordered',
    s3queue_polling_min_timeout_ms = 5000,
    s3queue_polling_max_timeout_ms = 30000;

-- Materialized view to move data into MergeTree
CREATE MATERIALIZED VIEW events_from_s3 TO events_raw AS
SELECT * FROM events_s3_queue;
```

**Latency considerations:**

| Path | End-to-End Latency |
|------|--------------------|
| Firehose → S3 (60s buffer) → S3Queue (30s poll) | **~90–120 seconds** |
| Firehose → HTTP endpoint (60s buffer) | **~60–90 seconds** |
| Kafka → Consumer → ClickHouse (batch every 5s) | **~5–10 seconds** |

Firehose adds significant latency due to its buffering model. For bxb's 1–2 minute latency target, Firehose → S3 → S3Queue is marginal; Kafka → Consumer is well within budget.

---

## Apache Pulsar as Kafka Alternative

### Overview

Apache Pulsar is a distributed messaging and streaming platform originally developed at Yahoo. It separates the serving layer (brokers) from the storage layer (Apache BookKeeper), enabling independent scaling of compute and storage.

### Architecture

```
                    ┌──────────────────┐
                    │   Pulsar Broker   │
                    │  (stateless)     │
                    └──┬──────────┬───┘
                       │          │
              ┌────────▼┐    ┌───▼───────┐
              │BookKeeper│    │BookKeeper │
              │ Bookie 1 │    │ Bookie 2  │
              └──────────┘    └───────────┘
                       │          │
                    ┌──▼──────────▼──┐
                    │  Tiered Storage │
                    │  (S3 / GCS)    │
                    └────────────────┘
```

- **Brokers** (stateless): Handle produce/consume requests, topic lookup, load balancing. Easily scaled horizontally.
- **BookKeeper Bookies** (stateful): Persist messages in a write-ahead log. Provide low-latency durable writes.
- **Tiered storage**: Offload older segments to S3/GCS for cost-efficient long-term retention.

### Multi-Tenancy

Pulsar has native multi-tenancy built into its topic hierarchy:

```
persistent://tenant/namespace/topic
```

| Level | Purpose | Example |
|-------|---------|---------|
| **Tenant** | Organizational boundary | `billing-platform` |
| **Namespace** | Logical grouping with shared policies | `billing-platform/production` |
| **Topic** | Individual message stream | `billing-platform/production/events` |

**Isolation policies:**
- Per-namespace: retention, TTL, replication, backlog quota, schema enforcement.
- Per-tenant: authentication, authorization, resource quotas.
- **Kafka comparison**: Kafka has no native multi-tenancy. Isolation requires separate clusters or complex ACL configurations.

### Tiered Storage

Pulsar's tiered storage offloads older topic segments to object storage:

```
Hot data (recent): BookKeeper (SSD) → low latency, higher cost
Warm data (older): S3 / GCS → higher latency, much lower cost
```

**Configuration:**
- Offload policy: by size (e.g., offload when topic exceeds 10 GB on BookKeeper) or by time (e.g., offload segments older than 24 hours).
- **Transparent reads**: Consumers reading offloaded data see no API difference — Pulsar fetches from object storage transparently.
- **Cost benefit**: Retain months/years of event data at S3 prices (~$0.023/GB/month) instead of SSD prices (~$0.10–0.20/GB/month).

**Kafka comparison**: Kafka added tiered storage in KIP-405 (GA in Kafka 3.6+), but it is less mature than Pulsar's implementation. Confluent Cloud offers it as a managed feature.

### Geo-Replication

Pulsar supports synchronous and asynchronous geo-replication at the namespace level:

```
┌─────────────┐         ┌─────────────┐
│  Cluster A  │◄───────▶│  Cluster B  │
│  (us-east)  │  async  │  (eu-west)  │
└─────────────┘  replic │             │
                        └─────────────┘
```

**Modes:**
- **Async replication**: Messages produced in Cluster A are asynchronously replicated to Cluster B. Sub-second replication lag under normal conditions.
- **Sync replication**: Acknowledge produce only after replicated. Higher latency but stronger durability.
- **Active-active**: Both clusters accept produces and replicate to each other. Requires conflict resolution for ordering.

**Kafka comparison**: Kafka geo-replication options:
- **MirrorMaker 2**: Async replication between Kafka clusters. Works but limited (topic-level, no active-active).
- **Confluent Cluster Linking**: Managed, lower latency, but Confluent-only.

### Pulsar Functions (Lightweight Stream Processing)

Pulsar Functions provide serverless-style stream processing:

```python
# Pulsar Function: enrich billing events
from pulsar import Function

class EnrichEvent(Function):
    def process(self, event, context):
        enriched = {
            **event,
            'customer_tier': lookup_tier(event['external_customer_id']),
            'enriched_at': datetime.utcnow().isoformat(),
        }
        return enriched
```

- **Deployment**: Run as threads (in broker process), processes, or Kubernetes pods.
- **Comparison to Kafka Streams**: Simpler (single-function model) but less powerful (no multi-step topologies, limited windowing).
- **Comparison to Flink**: Much simpler but no support for complex stateful processing, large state, or sophisticated windowing.

### Pulsar vs. Kafka Comparison

| Dimension | Apache Pulsar | Apache Kafka |
|-----------|--------------|-------------|
| **Architecture** | Separate compute (brokers) and storage (BookKeeper) | Brokers handle both compute and storage |
| **Scaling** | Scale brokers and storage independently | Scale brokers (both together) |
| **Multi-tenancy** | Native (tenant/namespace/topic) | Not native (requires ACLs, separate clusters) |
| **Tiered storage** | Mature, built-in | KIP-405 (Kafka 3.6+), less mature |
| **Geo-replication** | Built-in, namespace-level | MirrorMaker 2 or Confluent Cluster Linking |
| **Consumer model** | Exclusive, shared, failover, key-shared | Consumer groups only |
| **Message ordering** | Per-key (key-shared), per-subscription (exclusive) | Per-partition |
| **Max throughput** | ~1–2M messages/sec per topic | ~2–5M messages/sec per partition |
| **Latency (p99)** | 5–10ms (publish) | 2–5ms (publish) |
| **Ecosystem maturity** | Smaller, growing | Very large, battle-tested |
| **Managed offerings** | StreamNative Cloud, limited | Confluent, MSK, Redpanda, many |
| **Community** | Smaller, ASF-governed | Very large, industry-standard |

### When to Choose Pulsar Over Kafka

| Scenario | Pulsar Advantage |
|----------|-----------------|
| **Multi-tenant SaaS** | Native tenant isolation without cluster-per-tenant |
| **Long retention (months/years)** | Tiered storage to S3 at low cost |
| **Geo-distributed workloads** | Built-in async/sync geo-replication |
| **Independent compute/storage scaling** | Scale brokers without moving data |
| **Mixed workloads (streaming + queuing)** | Shared subscriptions for queue semantics |

**For bxb**: Kafka is the stronger choice today. bxb is single-tenant, doesn't require geo-replication, and benefits from Kafka's larger ecosystem (Kafka Connect, schema registry, Flink integration). Pulsar would be worth reconsidering if bxb needs to serve multiple tenants with isolated event streams or requires very long-term event retention at low cost.

---

## Pros: Streaming Ingestion Patterns

### 1. Real-Time Processing

- **Sub-second transformations**: Events can be enriched, validated, and routed within milliseconds.
- **Streaming aggregations**: Compute running totals, rates, and summaries without batch delays.
- **Immediate alerting**: Detect anomalies (usage spikes, fraud patterns) as they happen, not minutes later.

### 2. Complex Event Correlation

- **Stream-stream joins**: Correlate events across multiple streams (e.g., join API calls with billing events by customer ID within a time window).
- **Pattern detection**: CEP (Complex Event Processing) detects sequences like "3 failed payments in 5 minutes" using Flink CEP or stateful operators.
- **Sessionization**: Group related events into sessions based on activity gaps.

### 3. Late-Arrival Handling

- **Watermarks**: Flink's watermark mechanism tracks event-time progress, allowing the system to handle out-of-order events gracefully.
- **Allowed lateness**: Windows can accept late events up to a configurable threshold, recomputing aggregates as needed.
- **Side outputs**: Very late events (beyond the allowed lateness) are routed to a side output for manual handling or separate processing.
- **For billing**: Late-arriving usage events (e.g., from offline devices) are correctly attributed to the right billing period.

### 4. Scalability

- **Horizontal scaling**: Both Flink and Kafka Streams scale horizontally by adding instances.
- **Flink auto-scaling**: Reactive mode adjusts parallelism based on backpressure (Kubernetes-based).
- **Partition-level parallelism**: Processing parallelism is bounded by the number of Kafka partitions, allowing fine-grained control.
- **State partitioning**: Stateful computations are distributed across nodes based on key, enabling linear scaling for most workloads.

### 5. Decoupled Processing Pipeline

- **Separation of concerns**: The ingestion layer (Kafka), processing layer (Flink/Kafka Streams), and storage layer (ClickHouse) are independently scalable and replaceable.
- **Multiple outputs**: A single stream processor can write to multiple sinks (ClickHouse for analytics, PostgreSQL for transactional records, S3 for archival).
- **Pipeline evolution**: Add new processing steps (fraud detection, rate limiting) without modifying the ingestion API.

---

## Cons: Streaming Ingestion Patterns

### 1. Operational Complexity

- **Flink cluster management**: JobManager + TaskManagers + state checkpoints + monitoring. Requires dedicated expertise.
- **Failure modes**: Checkpoint failures, state corruption, rebalancing delays, backpressure propagation.
- **Kafka Streams complexity**: Simpler than Flink but still requires understanding of topology, state store recovery, and repartitioning.
- **Debugging**: Distributed stateful stream processing is inherently harder to debug than batch processing. State inspection tools are immature.

### 2. Additional Infrastructure

- **Flink**: Requires a dedicated cluster (or managed service). Adds JobManager, TaskManagers, ZooKeeper (or standalone HA), and checkpoint storage.
- **Infrastructure at 10k/sec**:

| Component | Instances | Estimated Cost |
|-----------|----------|---------------|
| Flink JobManager | 1 (HA: 2) | ~$100–200/month |
| Flink TaskManagers | 2–4 | ~$400–800/month |
| Checkpoint storage (S3) | N/A | ~$5–10/month |
| **Total Flink overhead** | — | **~$500–1,000/month** |

- **vs. simple Kafka consumer**: bxb's current batch consumer runs as a single lightweight process. Adding Flink increases infrastructure cost by ~$500–1,000/month with no throughput benefit for simple ingestion.

### 3. Steeper Learning Curve

- **Flink**: Java/Scala API, DataStream/Table API, checkpoint tuning, watermarks, state TTL, RocksDB tuning.
- **Kafka Streams**: Topology DSL, state stores, GlobalKTable vs. KTable, timestamp extractors.
- **Operational knowledge**: Understanding backpressure, checkpoint alignment, event-time vs. processing-time semantics.
- **Team impact**: bxb's backend is Python-based. Introducing Flink requires JVM expertise or using PyFlink (which has limitations — no support for certain state backends, fewer connectors).

### 4. Cost

- **At bxb's current scale (10k/sec)**: The stream processing overhead is not justified for simple write-through ingestion.
- **Break-even point**: Stream processing becomes cost-effective when:
  - Multiple downstream consumers need different transformations (avoid duplicate work).
  - Aggregations that would be expensive in ClickHouse can be pre-computed.
  - Real-time alerting requirements cannot be met by polling ClickHouse.

| Scale | Simple Consumer Cost | Flink Cost | Justification |
|-------|---------------------|------------|---------------|
| 10k/sec | ~$50/month | ~$700/month | Not justified |
| 50k/sec | ~$100/month | ~$1,000/month | Only if processing needed |
| 100k/sec | ~$200/month | ~$1,500/month | Justified if 3+ consumers |

### 5. End-to-End Exactly-Once Challenges

- **Within Kafka ecosystem**: Exactly-once is well-supported (Kafka transactions + Flink checkpoints).
- **To external systems (ClickHouse)**: No native two-phase commit. Must rely on idempotent writes + ReplacingMergeTree deduplication.
- **Practical reality**: Most production systems settle for "effectively-once" (at-least-once delivery + idempotent processing) rather than true exactly-once.

---

## Decision Matrix: Streaming vs. Batch

### When to Use Streaming

| Use Case | Why Streaming | Example |
|----------|--------------|---------|
| **Real-time dashboards** | Sub-second metric updates | Live API usage monitoring |
| **Fraud detection** | Pattern matching on live events | Detect anomalous usage spikes |
| **Rate limiting** | Per-key rate computation in flight | Enforce API quotas in real-time |
| **Complex event processing** | Multi-stream joins, sessionization | Correlate API calls with billing events |
| **Real-time alerting** | Immediate response to thresholds | Alert when customer exceeds budget |
| **Event enrichment (multi-source)** | Join events with reference data streams | Add customer tier from CRM stream |

### When to Use Batch (bxb's Current Approach)

| Use Case | Why Batch | Example |
|----------|----------|---------|
| **Billing aggregation** | Hourly/daily billing cycles tolerate latency | Monthly invoice generation |
| **Analytics and reporting** | Dashboards refresh every 1–5 minutes | Usage analytics for customer portal |
| **Cost-effective bulk processing** | Simple consumer is 10x cheaper than Flink | Write-through to ClickHouse |
| **Historical reprocessing** | Replay Kafka topic, rebatch into ClickHouse | Fix a bug in aggregation logic |
| **Simple data pipeline** | No transformations needed between source and sink | Events pass through unchanged |
| **Small team / limited JVM expertise** | Kafka Streams / Flink require JVM knowledge | Python-based team |

### Decision Tree

```
Need real-time event processing (< 1 sec)?
├── YES: Need complex stateful processing (joins, windows, CEP)?
│   ├── YES: → Apache Flink
│   └── NO: Need to stay within Kafka ecosystem?
│       ├── YES: → Kafka Streams
│       └── NO: → Pulsar Functions or Lambda
└── NO: Latency 1–2 minutes acceptable?
    ├── YES: Need event replay capability?
    │   ├── YES: → Kafka → Simple Consumer → ClickHouse (bxb's choice)
    │   └── NO: → Direct ClickHouse ingestion or PostgreSQL
    └── NO: (1 sec – 2 min range)
        → Kafka → Consumer with smaller batch windows
```

### Combined Architecture Patterns

For systems that need both real-time and batch capabilities:

```
                              ┌──────────────────────┐
                              │   Flink (real-time)  │──▶ Alerts / Dashboards
                              │   - fraud detection  │
                              │   - rate limiting     │
                              └──────────────────────┘
                                        ▲
API Server ──▶ Kafka ──────────────────┤
                                        ▼
                              ┌──────────────────────┐
                              │  Batch Consumer      │──▶ ClickHouse
                              │  (bulk write)        │    (analytics / billing)
                              └──────────────────────┘
```

This "lambda-lite" architecture uses Kafka as the single source of truth, with multiple consumers serving different latency requirements. bxb could adopt this incrementally: start with the batch consumer (current plan), add Flink later for specific real-time use cases.

---

## Relevance to bxb's Current Architecture

### Current State

bxb's chosen architecture is **API → Kafka → Simple Consumer → ClickHouse**, which is a batch ingestion pattern with a message broker for durability and decoupling. This is the right choice for the current requirements:

- **10k events/sec target**: A simple Kafka consumer can handle this easily.
- **1–2 minute latency acceptable**: No need for sub-second processing.
- **Cost-effectiveness**: A batch consumer costs ~$50/month vs. ~$700+/month for Flink.
- **Team skill set**: Python-based team; no JVM expertise required for simple consumer.

### When to Reconsider

Streaming ingestion should be reconsidered when:

1. **Real-time requirements emerge**: If bxb needs sub-second event processing (e.g., real-time fraud detection, live rate limiting, instant budget alerts), a stream processor becomes necessary.
2. **Multiple downstream consumers**: If 3+ consumers need different transformations of the same event stream, a stream processor centralizes the logic and avoids duplicating work.
3. **Complex event correlation**: If billing requires joining events across multiple streams or detecting multi-event patterns, Kafka Streams or Flink is needed.
4. **Scale beyond 50k/sec with processing**: At very high scale, pre-aggregating in Flink reduces the write load on ClickHouse and the cost of aggregation queries.

### Recommended Evolution Path

| Phase | Scale | Architecture | Stream Processing |
|-------|-------|-------------|-------------------|
| **Current** | 10k/sec | Kafka → Consumer → ClickHouse | None (batch consumer) |
| **Phase 2** | 10–50k/sec | Same + more partitions/consumers | Kafka Streams for simple enrichment |
| **Phase 3** | 50–100k/sec | Same + Flink for pre-aggregation | Flink for windowed aggregation |
| **Phase 4** | 100k+/sec | Multi-cluster Kafka + Flink | Flink for complex processing + routing |

### Key Takeaway

**Don't add stream processing until you need it.** The operational and cost overhead of Flink or Kafka Streams is not justified for bxb's current use case (simple write-through ingestion). Kafka's consumer API with batch writes to ClickHouse is sufficient, cost-effective, and operationally simple. When real-time processing needs arise, Kafka Streams (for simple cases) or Flink (for complex cases) can be added incrementally without changing the upstream architecture.

---

## References

- [Apache Flink Documentation](https://flink.apache.org/docs/stable/)
- [Flink Stateful Stream Processing](https://nightlies.apache.org/flink/flink-docs-stable/docs/concepts/stateful-stream-processing/)
- [Flink Checkpointing](https://nightlies.apache.org/flink/flink-docs-stable/docs/ops/state/checkpoints/)
- [Flink Windowing](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/datastream/operators/windows/)
- [Kafka Streams Documentation](https://kafka.apache.org/documentation/streams/)
- [Kafka Streams Architecture](https://docs.confluent.io/platform/current/streams/architecture.html)
- [AWS Kinesis Data Streams Developer Guide](https://docs.aws.amazon.com/streams/latest/dev/introduction.html)
- [AWS Kinesis Data Firehose Developer Guide](https://docs.aws.amazon.com/firehose/latest/dev/what-is-this-service.html)
- [ClickHouse S3Queue Engine](https://clickhouse.com/docs/en/engines/table-engines/integrations/s3queue)
- [Apache Pulsar Documentation](https://pulsar.apache.org/docs/)
- [Pulsar vs. Kafka Comparison](https://pulsar.apache.org/docs/concepts-messaging/)
- [Pulsar Tiered Storage](https://pulsar.apache.org/docs/tiered-storage-overview/)
- [Pulsar Geo-Replication](https://pulsar.apache.org/docs/concepts-replication/)
- [Pulsar Functions](https://pulsar.apache.org/docs/functions-overview/)
- [Amazon Managed Flink](https://docs.aws.amazon.com/managed-flink/latest/java/what-is.html)
- [Confluent Cloud Flink](https://docs.confluent.io/cloud/current/flink/overview.html)
