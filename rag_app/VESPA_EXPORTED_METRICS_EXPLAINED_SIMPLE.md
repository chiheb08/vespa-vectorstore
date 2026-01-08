### Vespa metrics (super simple): what you’re seeing in `http://localhost:9109/metrics`

If you’re new: think of **metrics** like the “dashboard lights” in a car:

- **Speed** → how fast requests are handled (latency)
- **Engine load** → CPU usage
- **Fuel / temperature** → memory usage
- **How many passengers** → how many results returned (hits)

This file explains the exporter output in the easiest possible way.

---

## 1) What is `http://localhost:9109/metrics`?

It’s a “translator”:

- Vespa produces metrics (as JSON).
- Prometheus/Grafana likes metrics in a specific text format.
- The exporter converts Vespa → Prometheus format.

So Grafana can draw graphs.

---

## 2) How to read one line (like reading a label on a box)

Example line:

```
vespa_metric_value{metric="query_latency",node="vespa",service="container",stat="average"} 181.0
```

Read it like:

> “For **service=container** on **node=vespa**, the **average query latency** is **181.0** (units depend on the metric; often ms).”

### What the pieces mean (very simple)

- **`vespa_metric_value`**: the exporter’s “generic metric name”
  - Think: “all Vespa metrics are stored under this one umbrella”.
- **`metric="..."`**: which metric we’re talking about
  - Example: `query_latency`, `memory_rss`, `cpu_util`
- **`stat="..."`**: which statistic of that metric
  - `average` = average in the last window
  - `max` = worst/slowest seen
  - `count` = how many samples were measured
  - `rate` = how fast something happens per second (roughly)
  - `value` = raw value (no average/max breakdown)
- **`service="..."`**: which Vespa component produced it
  - `container` = HTTP query + document API layer
  - `searchnode` = indexing/search engine (“where documents live”)
  - others exist too
- **`node="..."`**: the machine/container name
- **the number at the end**: the current value

### What does `3.740782592e+09` mean?

That is scientific notation:

- `3.740782592e+09` ≈ **3,740,782,592**

It’s used for big numbers like bytes.

---

## 3) The “big 4” beginner metrics (start here)

### A) `query_latency` (speed of search)

You might see:

- `query_latency average`
- `query_latency max`

Analogy:
- **average** = your normal commute time
- **max** = the worst traffic jam

If max is huge while average is ok:
- some requests are slow (tail latency issue)

### B) `cpu_util` (engine load)

- `cpu_util` is usually between **0 and 1**
  - 0.50 ≈ “half a CPU core busy”
  - 1.00 ≈ “one CPU core fully busy”

Analogy:
- CPU is the “engine”
- High CPU for long time usually means things will get slower.

### C) `memory_rss` (real RAM used)

- RSS is “real RAM”
- If it grows and never stabilizes, that’s suspicious.

Analogy:
- RAM is your “table space”
- If the table gets too full, things become messy (OOM / crashes).

### D) `feed.latency` / `feed.operations` (how ingestion behaves)

These show activity during ingestion:
- `feed.operations rate` should go up when feeding
- `feed.latency` tells if feeding is slow

Analogy:
- Feeding is “loading boxes into the warehouse”
- If loading is slow, maybe the warehouse is overloaded (CPU/memory/disk).

---

## 4) Quick “if you see X → do Y” troubleshooting

### Case 1: Grafana shows “No data”

1) Check exporter has values:

```bash
curl -s http://localhost:9109/metrics | grep vespa_metric_value | head
```

2) Check Prometheus has series:
- open `http://localhost:9090`
- run: `count(vespa_metric_value)`

### Case 2: query latency looks high

Try these in order:
- run one query again (warm caches)
- reduce `hits` and return fewer fields (avoid huge `text`)
- reduce `targetHits` (faster, maybe worse recall)
- check CPU and memory — high load = higher latency

### Case 3: memory_rss keeps rising

Check:
- are you ingesting a lot?
- are you running big models on the same machine?
- is Docker Desktop memory too small?

---

## 5) Practical examples (copy/paste)

### Example: show query latency series only

```bash
curl -s http://localhost:9109/metrics | grep 'metric=\"query_latency\"' | head -n 20
```

### Example: show memory RSS

```bash
curl -s http://localhost:9109/metrics | grep 'metric=\"memory_rss\"' | head -n 5
```

---

## 6) If you want the “deep” version

For a more technical explanation (units, more metrics, PromQL ideas), read:

- `rag_app/VESPA_EXPORTED_METRICS_EXPLAINED.md`



