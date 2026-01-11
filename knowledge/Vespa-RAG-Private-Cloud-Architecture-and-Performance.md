## Vespa-backed RAG: Architecture + Private-Cloud Deployment + Performance Tuning

This guide summarizes what **production RAG systems** commonly do when **Vespa is the retrieval engine** (vector store + hybrid search + ranking).

It is intentionally **Vespa-focused**: what Vespa does, when it does it, and what knobs matter for quality/latency.

---

## What Vespa typically owns in a RAG system

Vespa is not “just a vector DB”. In many production RAG stacks, Vespa is responsible for:

- **Fast filtering** on metadata/ACL: `tenant_id`, `source`, `doc_type`, `language`, time ranges, groups/users
- **Vector ANN** retrieval (HNSW) over a tensor `attribute`
- **Keyword search** (BM25) over inverted indexes
- **Hybrid retrieval + score normalization** (vector + keyword + business signals)
- **Multi-phase ranking** (cheap first-phase, expensive rerank on a small set)
- **Returning structured hits**: chunk text + ids + metadata for the LLM prompt builder

---

## Architecture diagram (private cloud, Vespa as retrieval engine)

```mermaid
flowchart LR
  U[User / App] --> GW[API Gateway / Ingress]
  GW --> Q[Query Service (RAG Orchestrator)]

  Q -->|embed query| EQ[Embedding service]
  Q -->|YQL + filters + ranking.profile| V[(Vespa)]
  V -->|topK chunks + metadata| Q
  Q -->|build prompt| LLM[LLM service]
  LLM --> Q --> U

  subgraph Ingestion path
    SRC[Sources: Drive/Slack/Confluence/etc] --> CONN[Connectors + Extract]
    CONN --> CH[Chunk + enrich metadata/ACL]
    CH -->|embed chunks (batch)| EP[Embedding service]
    EP --> FEED[Feeder / Indexing worker]
    FEED -->|Document API feed| V
  end

  subgraph Observability
    Q --> LOG[Logs: query + filters + timings]
    V --> MET[Metrics: latency/CPU/memory/feed]
    LOG --> OBS[Prom/Grafana/ELK]
    MET --> OBS
  end
```

---

## Query flow: what Vespa does (step-by-step)

### 1) Matching (candidate generation)

Common pattern:

- **Filters first** (must be cheap): tenant, source, time range, ACL
- **Candidate retrieval**:
  - Vector ANN: `nearestNeighbor(embedding, query_embedding)` with `{targetHits: Kcandidates}`
  - Optional keyword clause (BM25) for hybrid retrieval

**Why**: pure vector is weak on internal jargon; keyword helps enterprise search.

### 2) Ranking (multi-phase)

Use **phased ranking**:

- **first-phase**: cheap scoring on many candidates (vector closeness + bm25 + light boosts)
- **second-phase or global-phase**: expensive rerank on a bounded set (`rerank-count`)

This keeps latency predictable while allowing better ranking quality.

### 3) Response

Return:

- chunk text (or snippet)
- ids (doc_id / chunk_id)
- key metadata (source/doc_type/lang/time/tenant)

These fields are used by the RAG orchestrator to build the final LLM prompt.

---

## Private-cloud deployment blueprint (Kubernetes)

### Vespa cluster shape (typical)

- **Config server(s)**: control plane
- **Container cluster**: stateless query/processing
- **Content nodes**: stateful (indexes + vectors + HNSW + attributes)

### Practical production checklist

- **Isolation**: put Vespa content nodes on dedicated nodes (avoid noisy neighbors)
- **Storage**: fast PVs for content nodes (SSD/NVMe preferred)
- **Memory**: ensure enough RAM for vector/attribute heavy workloads
- **Network policies**: restrict Vespa endpoints to trusted namespaces/services
- **mTLS (optional but common)**: for service-to-service comms if required by your org
- **Upgrades**: plan rolling upgrades with enough replication headroom
- **Multi-tenancy**: enforce `tenant_id` filter everywhere and log it

---

## Performance tuning (the knobs that matter)

### A) Make filters cheap (mandatory)

Store filter fields as **attributes** (fast at query time), e.g.:

- `tenant_id`, `source`, `doc_type`, `language`
- `created_at` / `updated_at` / `last_touched_at`
- ACL fields like `allowed_users`, `allowed_groups`

### B) Control ANN work at query time

Key knobs:

- **`targetHits`** in `nearestNeighbor(...)`:
  - higher = better recall, slower
  - lower = faster, risk missing good chunks
- **`hnsw.exploreAdditionalHits`** annotation:
  - higher = explores more of the graph (better quality), slower

Rule of thumb:

- Raise `targetHits` first when recall is bad.
- If recall still bad, raise `hnsw.exploreAdditionalHits`.

### C) Keep expensive scoring bounded

Use phased ranking:

- Keep first-phase cheap.
- Put expensive logic in second/global phase with a tight `rerank-count`.

### D) Index-time HNSW build parameters (trade-offs)

Schema-side HNSW build parameters:

- `max-links-per-node` (M): higher improves quality, increases memory/build cost
- `neighbors-to-explore-at-insert` (ef_construction): higher improves quality, slows indexing

### E) Hardware levers (often biggest impact)

- **More RAM** on content nodes → less tail latency
- **Fast storage** for content nodes → fewer stalls
- **CPU headroom** → stable latency under concurrency

---

## “Debug mode” that teams use (filters vs no-filters)

When results are wrong:

- Run the query **with filters** (production behavior)
- Run the **same query** with filters removed (or relaxed one by one)

Interpretation:

- With filters = 0 hits, without filters = many hits → filters/metadata mismatch
- With filters = many hits but irrelevant → recall/ranking issue (ANN params, embeddings, chunking, reranking)

---

## References (high-signal)

- **Nearest neighbor search** (Vespa docs): `https://docs.vespa.ai/en/querying/nearest-neighbor-search.html`
- **Approximate NN using HNSW** (Vespa docs): `https://docs.vespa.ai/en/querying/approximate-nn-hnsw.html`
- **YQL nearestNeighbor / hnsw.exploreAdditionalHits** (Vespa docs): `https://docs.vespa.ai/en/reference/querying/yql.html#nearestneighbor`
- **Phased ranking** (Vespa docs): `https://docs.vespa.ai/en/ranking/phased-ranking.html`
- **Why Danswer uses Vespa** (Vespa blog): `https://blog.vespa.ai/why-danswer-users-vespa/`


