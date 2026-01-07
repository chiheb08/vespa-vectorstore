### Vector DB Retrieval: how to trace results, monitor health, and improve quality (beginner-friendly)

If you’re new to vector databases, the most important idea is this:

**A “good result” is produced by a whole pipeline**, not just the vector DB.

Pipeline (typical RAG / semantic search):

- user types a query (text)
- your app may rewrite/normalize it + apply filters
- an embedding model converts the query into a vector (numbers)
- the vector DB retrieves top‑K similar vectors (optionally hybrid with BM25)
- optional: reranker reorders candidates
- optional (RAG): the LLM answers using retrieved chunks as context

So to debug and improve retrieval, you must instrument and evaluate **the whole retrieval pipeline**.

---

## 1) What you’re trying to monitor (3 layers)

### 1.1 Quality (are results relevant?)
This is “does it retrieve the right chunks/docs?”

You typically measure:
- **Recall@K**: did we retrieve at least one relevant chunk in top K?
- **Precision@K**: how many of top K are relevant?
- **MRR / nDCG**: ranking quality (relevant items near the top)

How to get these metrics:
- Best: build a small labeled set of queries with “relevant documents/chunks”.
- Also useful: user feedback (thumbs up/down), clicks, reformulations.

### 1.2 Performance (is it fast + stable?)
Measure p50/p95/p99 latencies for:
- embedding generation
- vector DB search
- reranking (if any)
- end‑to‑end request

Also track:
- QPS (queries/sec)
- error rate/timeouts

### 1.3 System health (is the DB under stress?)
Track:
- CPU / memory / disk IO
- container restarts / OOM kills
- index size growth
- saturation signals (queues, thread pools, slow queries)

---

## 2) What to log so you can trace “why did I get these results?”

Make sure every search request writes **one structured JSON log record**.
This is the single most useful habit for debugging retrieval.

Minimum recommended fields:

### 2.1 Request identity
- **request_id** (UUID)
- **timestamp**
- **user_id / tenant_id** (if multi‑tenant)
- **session_id** (optional but helpful)

### 2.2 Query inputs
- **raw_query**
- **final_query** (after normalization or rewriting)
- **filters** (metadata constraints)

### 2.3 Embedding trace
- **embedding_model** (name + version)
- **embedding_dim**
- **query_vector_norm** (sanity check: should not be ~0)
- **embedding_latency_ms**

### 2.4 Retrieval config (what did you ask the DB to do?)
- **top_k**
- **ANN candidate params** (e.g., “target hits / candidates” style setting)
- **ranking profile** (vector vs hybrid vs rerank)

### 2.5 Retrieval output (what did you get back?)
- **hit_ids** in ranked order
- **scores** (vector similarity, bm25 score, final score)
- **hit_metadata** (doc_id, chunk_id, source, timestamps)
- **retrieval_latency_ms**

### 2.6 RAG-specific (if you generate answers)
- **context_chunk_ids_used** (exact chunks inserted into the prompt)
- **llm_model**
- **llm_latency_ms**
- **answer_length_tokens** (or chars)

With this you can answer questions like:
- “Did filters remove the relevant docs?”
- “Did the embedding model change?”
- “Did ANN settings reduce recall?”
- “Was the chunking bad?”
- “Was it retrieved but ranked too low?”

---

## 2.7 (Beginner tip) How to interpret “vector scores”

Most systems return a **relevance** (a score). Beginners often think:
“Why is the score 0.37? Is that good or bad?”

The important rules:

- A score is mostly useful **relative to other scores for the same query**.
- Scores from different queries are often not comparable.
- If you see “many very close scores”, your retriever is unsure and reranking can help.

In Vespa:
- vector-only ranking often uses something like **`closeness(embedding)`**
- hybrid uses something like **`bm25(text) + closeness(embedding)`**

So the score is a combination of “keyword match strength” and “semantic similarity”.

---

## 3) The most important debugging skill: recall vs ranking

When results are bad, you must decide which problem you have:

### 3.1 Recall problem (not retrieved at all)
The “right” chunk is **not in top‑K**.

Typical causes:
- embedding model doesn’t match your domain/language
- poor chunking / missing text
- ANN is too “tight” (not enough candidates explored)
- over-filtering (metadata filters remove it)

Typical fixes:
- improve embeddings or chunking
- increase candidate pool (ANN candidates / targetHits conceptually)
- add hybrid retrieval (BM25 + vectors)

### 3.2 Ranking problem (retrieved but ordered wrong)
The right chunk is present in top‑K but ranked too low (e.g., #25 when you show only 5).

Typical causes:
- your scoring function is weak
- hybrid weights not tuned
- query needs reranking to prefer the truly relevant chunk

Typical fixes:
- rerank top 50–200 with a stronger model
- tune scoring weights (hybrid)
- add query rewriting/multi-query and fuse (RRF)

**Quick test (beginner-friendly):**
- temporarily increase K (and/or ANN candidates)
- if the right chunk appears deeper → ranking problem
- if it never appears → recall problem

---

## 3.3 (Deeper but simple) What `targetHits` / candidate count really does

Vector search is usually done with an **ANN index** (like HNSW).
ANN is fast because it does *not* check every vector.

So you get a “knob”:
- **small candidate count** → faster, but may miss relevant items (lower recall)
- **large candidate count** → slower, but more likely to include the right items (higher recall)

In Vespa examples, that knob is often expressed as:
- `({targetHits:50}nearestNeighbor(embedding, q))`

When you debug a recall problem, increasing candidate count is one of the first safe experiments.

---

## 4) A step-by-step workflow to trace a bad result

When a user says “this result is wrong”, don’t guess. Do this:

### Step 1: Reproduce by request_id
Use the exact `raw_query`, `filters`, and pipeline settings from logs.

If you can’t reproduce, you likely have nondeterminism:
- model version changed
- index/data changed
- caching issues

### Step 2: Validate filters first (common silent failure)
If filters are too strict, vector search can’t help.

Debug action:
- run the query without filters (or with relaxed filters) and compare.

### Step 3: Validate embedding sanity
Look for:
- wrong model (query uses model A, documents embedded with model B)
- wrong dimension (should always match)
- weird query vector (near-zero norm from empty/garbage input)
- language mismatch (English model for Arabic queries, etc.)

### Step 4: Inspect the top results’ chunk texts
Print top 20 chunk texts and read them.

If they look “close but not answering”, it’s often:
- chunking quality
- ranking weakness (need rerank / hybrid tuning)

### Step 5: Decide recall vs ranking
Use the K/candidate trick described above.

---

## 4.1 A “10-minute checklist” for the most common real-world failures

When retrieval is suddenly bad, check these in this order:

- **Filters**: wrong tenant/user/source/time range? (over-filtering)
- **Embedding model**: did you change the model or dimension?
- **Index freshness**: did new documents get ingested successfully?
- **Data/cleaning**: is the extracted text empty/garbled?
- **Chunking**: are chunks too small/too big/duplicated?
- **Candidate count**: did you reduce `targetHits` / ANN exploration?

---

## 5) Monitoring: what to put on a dashboard (starter set)

### 5.1 Quality proxies (online)
Even before you have labeled evaluation:
- **reformulation rate**: user asks the same thing again differently (bad sign)
- **click-through rate** on sources/chunks (if you show them)
- **thumbs down rate** (if you collect it)

### 5.2 Latency and errors
Track times separately so you know where time is spent:
- embedding p95
- retrieval p95
- rerank p95
- end-to-end p95
- error rate (4xx/5xx)
- timeout rate

### 5.3 System health
- CPU / memory
- OOM kills / restarts
- disk usage
- index size growth

---

## 5.4 (Very practical) What to look for in Vespa itself

Even without Prometheus/Grafana, Vespa exposes:

- **Health**: `/state/v1/health`
- **Metrics (JSON)**: `/metrics/v2/values`

Beginner approach to metrics:

- Step 1: snapshot metrics when things feel good
- Step 2: snapshot again when things feel bad
- Step 3: diff them (latency, errors, resource pressure)

What you typically search for in the metrics JSON:
- query latency / query rate
- feed latency / feed errors (if you ingest)
- memory pressure (OOM risk)

---

## 6) Where improvements usually come from (in the order to try)

### 6.1 Data & chunking (highest ROI)
Common upgrades:
- structure-aware chunking (sections, headings)
- overlap (to preserve context)
- remove boilerplate and duplicates
- store metadata that helps filtering (doc type, product, timestamp)

### 6.2 Embedding model choice + consistency
Rules:
- use one embedding model family consistently for indexing and querying
- if multilingual users → use multilingual embeddings
- for domain-specific text → consider domain-tuned embeddings

### 6.3 Hybrid retrieval (vectors + BM25)
Helps when users include exact tokens:
- error codes
- function names
- product IDs

### 6.4 ANN tuning / candidate count (fix recall)
Increasing explored candidates usually improves recall but costs latency.

### 6.5 Reranking (fix ranking)
High impact when the right chunk is “in the candidate set but not #1”.

### 6.6 Query rewriting / multi-query + fusion (RRF)
Helpful when user queries are vague or underspecified.

---

## 6.7 (Beginner path) How to add “more technical depth” safely

If you’re new, avoid changing 5 things at once. A safe upgrade path:

1. **Add logging** (request_id, filters, model version, candidates, results)
2. **Add a small evaluation set** (even 30 queries is a start)
3. **Tune candidate count** (improve recall)
4. **Add hybrid** (help with exact terms)
5. **Add reranking** (fix ranking)

You’ll learn faster because each change has a measurable effect.

## 7) Common failure modes and how they show up

- **Embedding mismatch (model A vs B)**: results feel random, sudden drop after deployment.
- **Over-filtering**: empty results or unrelated results for specific users/tenants.
- **Chunking regression**: results are “almost relevant” but never answer.
- **Duplicate chunks**: repeated hits, low diversity.
- **Freshness lag**: new docs not found until later.
- **Overload/OOM**: latency spikes, timeouts, partial failures.

---

## 8) A simple weekly improvement loop (what teams actually do)

1. **Collect** 200–1000 real queries + outcomes (with privacy controls).
2. **Label** 50–100 queries with relevant chunks/docs.
3. **Measure** Recall@10 and nDCG@10 for your current pipeline.
4. **Change one thing** (chunking OR embeddings OR candidates OR hybrid OR rerank).
5. **Re-measure** quality metrics + latency.
6. **Roll out safely** (A/B test if possible, or gradual rollout).

This prevents “random tweaking” and shows you exactly where the big gains are.


