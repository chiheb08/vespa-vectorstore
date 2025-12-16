### Vespa vector store (easy documentation + tutorial)

Vespa can act like a **vector database** by storing each “chunk” as a **document** containing a dense **embedding tensor**, and enabling **approximate nearest neighbor (ANN)** search (HNSW) + optional **hybrid (text + vector)** ranking.

---

### What you’ll build

- **Documents (“chunks”)** with fields like `chunk_id`, `doc_id`, `text`, `embedding`.
- **Vector index** on `embedding` (HNSW).
- **Queries**:
  - vector kNN (“top K nearest chunks”)
  - optional hybrid (BM25 + vector similarity)
- **Performance checks**: latency, throughput, profiling, and key metrics.
- **Chunk deletion**: how to delete, what is immediate vs background, and what controls “how long it takes”.

---

### Prerequisites

- **Docker** (or Podman)
- **Vespa CLI** (recommended)

Install Vespa CLI (macOS):

```bash
brew install vespa-cli
```

---

### Start Vespa locally (Docker)

Run a local container:

```bash
docker run --detach --name vespa --hostname vespa \
  --publish 8080:8080 --publish 19071:19071 \
  vespaengine/vespa
```

- **8080**: data plane (feed + queries)
- **19071**: control plane (config, metrics)

Point the CLI to local:

```bash
vespa config set target local
```

---

### Create a minimal “vector store” application package

Create this structure:

```text
my-vespa-app/
  services.xml
  deployment.xml
  schemas/
    chunk.sd
```

#### `services.xml`

This runs a container + a content cluster that stores your documents:

```xml
<services version="1.0">
  <container id="default" version="1.0">
    <search/>
    <document-api/>
  </container>

  <content id="chunks" version="1.0">
    <redundancy>1</redundancy>
    <documents>
      <document type="chunk" mode="index"/>
    </documents>
    <nodes>
      <node hostalias="node1"/>
    </nodes>
  </content>
</services>
```

#### `deployment.xml`

A minimal deployment file:

```xml
<deployment version="1.0">
  <prod>
    <region active="true">default</region>
  </prod>
</deployment>
```

#### `schemas/chunk.sd` (vector schema + ANN index)

Example for 768-d embeddings (change `x[768]` to your dimension):

```text
schema chunk {

  document chunk {
    field chunk_id type string {
      indexing: summary | attribute
    }
    field doc_id type string {
      indexing: summary | attribute
    }
    field text type string {
      indexing: summary | index
      index: enable-bm25
    }

    field embedding type tensor<float>(x[768]) {
      indexing: attribute
      attribute {
        distance-metric: angular
        hnsw {
          max-links-per-node: 16
          neighbors-to-explore-at-insert: 200
        }
      }
    }
  }

  rank-profile vector {
    first-phase {
      expression: closeness(embedding)
    }
  }

  rank-profile hybrid inherits vector {
    first-phase {
      expression: 0.5 * bm25(text) + 0.5 * closeness(embedding)
    }
  }
}
```

- **`distance-metric`**: `angular` is common for cosine-like similarity.
- **HNSW knobs** affect recall/latency and ingest cost.

Deploy it:

```bash
vespa deploy --wait 300 /ABS/PATH/TO/my-vespa-app
```

---

### Feed chunks (add documents)

#### Option A) Feed one chunk with `curl`

Use the Document API (PUT by document id):

```bash
curl -X PUT "http://localhost:8080/document/v1/my_ns/chunk/docid/chunk-1" \
  -H "Content-Type: application/json" \
  -d '{
    "fields": {
      "chunk_id": "chunk-1",
      "doc_id": "doc-A",
      "text": "This is a sample chunk of text.",
      "embedding": { "values": [0.01, 0.02, 0.03] }
    }
  }'
```

Notes:

- Your `embedding.values` must have **exactly the same dimension** as the schema (e.g., 768 floats).
- `my_ns` is any namespace you choose (use one consistently).

#### Option B) Bulk feed with `vespa feed` (JSONL)

Example JSONL line format:

```json
{"put":"id:my_ns:chunk::chunk-1","fields":{"chunk_id":"chunk-1","doc_id":"doc-A","text":"...","embedding":{"values":[0.01,0.02]}}}
```

Then:

```bash
vespa feed /ABS/PATH/TO/feed.jsonl
```

---

### Query it (vector search)

#### Vector kNN (nearest neighbor)

With Vespa CLI:

```bash
vespa query \
  'yql=select chunk_id, doc_id, text from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));' \
  'ranking.profile=vector' \
  'hits=10' \
  'input.query(q)=[0.01,0.02,0.03]'
```

With `curl` (JSON search request):

```bash
curl -s "http://localhost:8080/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "yql": "select chunk_id, doc_id, text from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));",
    "hits": 10,
    "ranking.profile": "vector",
    "input.query(q)": [0.01, 0.02, 0.03]
  }'
```

#### Add filters (common in chunk stores)

Example: “only search chunks from doc-A”:

```bash
vespa query \
  'yql=select chunk_id, doc_id, text from sources chunk where doc_id contains "doc-A" and ({targetHits:10}nearestNeighbor(embedding, q));' \
  'ranking.profile=vector' \
  'hits=10' \
  'input.query(q)=[0.01,0.02,0.03]'
```

#### Hybrid (text + vector)

Use the `hybrid` rank profile and include a text condition in YQL, e.g. contains/phrase filters, or your preferred text constraints:

```bash
vespa query \
  'yql=select chunk_id, doc_id, text from sources chunk where text contains "sample" and ({targetHits:50}nearestNeighbor(embedding, q));' \
  'ranking.profile=hybrid' \
  'hits=10' \
  'input.query(q)=[0.01,0.02,0.03]'
```

Reference: Vespa nearest-neighbor search guide: `https://docs.vespa.ai/en/querying/nearest-neighbor-search-guide.html`

---

### Check performance (latency, throughput, profiling)

#### 1) Quick latency check from the client side

Measure total HTTP time:

```bash
curl -s -o /dev/null -w "time_total=%{time_total}\n" \
  -H "Content-Type: application/json" \
  -d '{"yql":"select * from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));","hits":10,"ranking.profile":"vector","input.query(q)":[0.01,0.02,0.03]}' \
  "http://localhost:8080/search/"
```

Run it multiple times and track p50/p95 (or use a load tool below).

#### 2) Built-in metrics

Vespa exposes metrics here:

- `http://localhost:19071/metrics/v2/values`

Fetch them:

```bash
curl -s "http://localhost:19071/metrics/v2/values" > metrics.json
```

Then search inside `metrics.json` for relevant strings like:

- query latency / query rate
- feed latency / feed rate
- CPU / memory
- content node (proton) document DB metrics

(Exact metric names vary by version/config, so the practical workflow is: pull the JSON and grep/jq for “latency”, “query”, “feed”, “proton”, “hnsw”, etc.)

#### 3) Query profiling / tracing

Turn on tracing to see where time is spent:

```bash
vespa query \
  'yql=select * from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));' \
  'input.query(q)=[0.01,0.02,0.03]' \
  'ranking.profile=vector' \
  'tracelevel=3'
```

This helps distinguish:

- ANN search time
- ranking time
- summary fetch time
- network/serialization overhead

#### 4) Simple load test (throughput + tail latency)

If you have `hey` installed:

```bash
hey -n 2000 -c 20 -m POST -H "Content-Type: application/json" \
  -d '{"yql":"select * from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));","hits":10,"ranking.profile":"vector","input.query(q)":[0.01,0.02,0.03]}' \
  http://localhost:8080/search/
```

Watch:

- p95 / p99 latency
- requests/sec
- CPU usage of the container (via `docker stats`)

#### 5) What to tune if performance is not good

- **If queries are slow**:
  - reduce `hits`, reduce `targetHits`
  - keep summaries small (don’t return huge `text` fields unless needed)
  - ensure the vector is an **attribute** tensor with HNSW enabled
- **If recall is low**:
  - increase HNSW build params (`neighbors-to-explore-at-insert`, `max-links-per-node`)
  - increase `targetHits` (gives ANN more candidates before final ranking)
- **If feeding is slow**:
  - batch feeds, avoid huge documents, watch feed backpressure via metrics

---

### Delete chunks (documents) + “how long does it take?”

#### How to delete one chunk by id

If you used:

`PUT /document/v1/my_ns/chunk/docid/chunk-1`

Then delete it:

```bash
curl -X DELETE "http://localhost:8080/document/v1/my_ns/chunk/docid/chunk-1"
```

Or with CLI:

```bash
vespa document delete "id:my_ns:chunk::chunk-1"
```

#### Bulk delete (many chunks)

If you have the ids, send deletes for each id (often fastest and safest operationally).

Some setups also support delete-by-selection (use with care in production; test first):

```bash
vespa document delete --selection 'doc_id="doc-A"'
```

#### So… how long does deletion take?

It’s two different timelines:

- **Deletion visibility in queries (logical delete)**: **as soon as Vespa processes the delete**. In practice this is usually **milliseconds to seconds per chunk**, dominated by your **feed/delete throughput** and current load/queueing. After the delete request is acknowledged, the chunk should stop showing up in results.

- **Actual storage reclaim / internal cleanup (physical delete)**: **asynchronous**. Vespa typically marks documents as removed and later reclaims space through background maintenance/compaction. Depending on data size, churn, and load, **disk space and some internal structures may take minutes to hours** to fully reflect the deletion.

**What controls the end-to-end time for “delete N chunks”:**

- delete throughput (ops/sec you can push and Vespa can ingest)
- current load (ongoing feeds + query traffic)
- cluster size/resources (CPU, memory, disk IO)
- churn level (how many updates/deletes over time)
- background maintenance pace (compaction/GC), which governs physical reclaim

**How to measure it in your system:**

- send deletes and record **ack time** per request (client-side timing)
- confirm **query visibility** by re-running a query that previously returned the chunk
- watch `http://localhost:19071/metrics/v2/values` for feed/delete processing and document DB activity

---

### If you tell me 3 details, I’ll tailor this to your exact use case

- **Embedding dimension** (e.g., 384 / 768 / 1536)
- **Similarity** you want (cosine / dot / euclidean)
- **Chunk fields** you need (doc_id, source, page, tenant, timestamps, ACL)

Then I can rewrite the schema + queries precisely for your setup (including hybrid best practices and a safe bulk-delete strategy).


