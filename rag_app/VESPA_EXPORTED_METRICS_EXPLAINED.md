### Understanding `http://localhost:9109/metrics` (Vespa exporter) — deep beginner explanation

When you run:

```bash
curl -s http://localhost:9109/metrics | head -n 20
```

you see lines like:

```
vespa_metric_value{metric="memory_virt",node="vespa",service="container",stat="value"} 3.740782592e+09
```

This file explains **exactly what these values mean** and how to interpret them.

If you prefer a super simple version first (analogies + examples), start with:
- `rag_app/VESPA_EXPORTED_METRICS_EXPLAINED_SIMPLE.md`

---

## 1) What is this endpoint?

- **Vespa** exposes metrics as **JSON** at: `http://vespa:19071/metrics/v2/values`
- **Prometheus** expects metrics in **text format** at: `/metrics`
- So we run a small **exporter** container that:
  - fetches Vespa JSON
  - converts it into Prometheus text format

In `rag_app`, the exporter runs at:

- `http://localhost:9109/metrics`

---

## 2) How to read one metric line (Prometheus format)

General format:

```
<metric_name>{<labels>} <value>
```

For example:

```
vespa_metric_value{metric="query_latency",node="vespa",service="container",stat="average"} 181.0
```

Meaning:

- **metric name**: `vespa_metric_value`
  - This is a single “container metric” we use to export many Vespa metrics.
- **labels** (metadata attached to the value):
  - **`metric`**: which Vespa metric this is (example: `query_latency`)
  - **`stat`**: which statistic of that metric (`average`, `max`, `count`, `rate`, …)
  - **`node`**: hostname of the Vespa node (here: `vespa`)
  - **`service`**: which Vespa service produced the metric (`container`, `searchnode`, `distributor`, …)
- **value**: the numeric value at scrape time

### About scientific notation

This:

```
3.740782592e+09
```

means:

- \(3.740782592 \times 10^9\) ≈ **3,740,782,592**

This is common for large byte values (memory sizes).

---

## 3) What the common metrics mean (the ones you saw)

### 3.1 `memory_virt` and `memory_rss`

- **`memory_virt`**: *virtual memory size* (bytes)
  - Includes memory mapped regions and reserved address space.
  - Can look “huge” and is not always the best indicator of real memory pressure.
- **`memory_rss`**: *resident set size* (bytes)
  - This is a better “real RAM used” signal.

How to interpret:
- Watch **RSS** over time. If it keeps growing without stabilizing, you may have a memory leak or too much caching.

### 3.2 `cpu` and `cpu_util`

- **`cpu`**: CPU usage number reported by Vespa metrics (unit depends on Vespa’s internal sampling; treat it as “CPU consumed”)
- **`cpu_util`**: CPU utilization fraction (0.0 to 1.0)
  - Example: `0.55` ≈ “55% of one CPU core”

How to interpret:
- For a single-node Docker setup, sustained high `cpu_util` often correlates with query latency increases.

### 3.3 `query_latency.*` (container queries)

Example:

```
vespa_metric_value{metric="query_latency",service="container",stat="average"} 181.0
vespa_metric_value{metric="query_latency",service="container",stat="max"} 181.0
```

Interpretation:
- This is *query latency measured by Vespa’s container layer* (not client-side HTTP time).
- **Units**: often milliseconds in Vespa’s internal metrics (the exact unit can vary by metric name).

Important: look at these together:
- **`query_latency.average`**: average latency over the sampling window
- **`query_latency.max`**: slowest query observed in the window
- **`query_latency.count`**: how many samples contributed (if `count` is 0, the “average” might be a default/old sample)

If you want a practical end-to-end latency, also measure from the client:

```bash
curl -s -o /dev/null -w "time_total=%{time_total}\n" \
  -H "Content-Type: application/json" \
  -d '{"yql":"select * from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));","hits":10,"ranking.profile":"vector","input.query(q)":[0.01,0.02,0.03]}' \
  "http://localhost:8080/search/"
```

### 3.4 `hits_per_query.*` and `totalhits_per_query.*`

- **`hits_per_query`**: number of hits returned per query (average/max over the window)
- **`totalhits_per_query`**: total matches found (can be larger than returned hits)

In Vespa terms:
- returned hits = what you asked for with `hits=...`
- total hits = how many documents matched the query conditions

### 3.5 Feed/ingest metrics (`feed.operations.rate`, `feed.latency.*`)

Examples:

```
vespa_metric_value{metric="feed.operations",stat="rate"} 0.0
vespa_metric_value{metric="feed.latency",stat="sum"} 0.0
vespa_metric_value{metric="feed.latency",stat="count"} 0.0
```

Interpretation:
- These only become non-zero when you ingest documents (Document API feed).
- If you run `/ingest/text` or `/ingest/file`, you should see activity here soon after.

---

## 4) Why Grafana sometimes shows “No data”

The “No data” cases are usually:

- **Exporter is not exporting series** (Prometheus sees 0 series)
  - check: `curl -s http://localhost:9109/metrics | grep vespa_metric_value | head`
- **Prometheus isn’t scraping exporter**
  - open Prometheus and run: `count(vespa_metric_value)`
- **You didn’t generate traffic**
  - run a query and ingestion, then refresh Grafana:
    - ingestion: `POST /ingest/text`
    - query: `POST /search/` to Vespa or call `/v1/chat/completions` once RAG is active

---

## 5) What I recommend you watch first (beginner priorities)

If you only watch a few things, start with:

- **Query latency**: `vespa_metric_value{metric="query_latency",stat="average"}`
- **CPU utilization**: `vespa_metric_value{metric="cpu_util"}`
- **RSS memory**: `vespa_metric_value{metric="memory_rss"}`
- **Feed latency** (when ingesting): `vespa_metric_value{metric="feed.latency",stat="count"}` and `...stat="sum"`

These quickly tell you:
- “is Vespa slow because it’s overloaded?”
- “is ingest causing pressure?”
- “is memory growing?”


