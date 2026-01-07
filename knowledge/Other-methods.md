### Other RAG retrieval methods (beyond BM25, RRF, re-ranking, metadata filters)

This page lists common techniques you’ll see in real RAG systems and breaks them down simply.

---

### 1) Dense vector retrieval (bi-encoder)

- **What it is**: embed the query and each chunk into vectors, then retrieve nearest neighbors.
- **Why it helps**: matches meaning even when words differ (synonyms, paraphrases).
- **Tiny example**:
  - Query: “Docker can’t talk to daemon”
  - Chunk contains: “Cannot connect to Docker daemon at docker.sock”
  - Words differ a bit, meaning matches → vectors bring it back.

---

### 2) Hybrid search (BM25 + vectors)

- **What it is**: use both keyword score and vector similarity.
- **Why it helps**: covers both “exact words” and “same meaning”.
- **When to use**: almost always a good default for tech docs and logs.
- **Tiny example**:
  - Query contains an error code `exit 137` (BM25 is great)
  - Also wants explanation (vectors help)

---

### 3) Query rewriting (LLM rewrite)

- **What it is**: the LLM rewrites the user question into a better “search query”.
- **Why it helps**: users ask vague questions; rewrite adds missing keywords.
- **Example**:
  - User: “it crashed”
  - Rewrite: “container exited 137 out of memory docker desktop increase memory”

---

### 4) Query expansion (add extra keywords)

- **What it is**: add extra related terms to improve recall (without changing meaning).
- **How**: synonyms list, domain dictionary, or an LLM.
- **Example**:
  - “OOM” ↔ “out of memory” ↔ “exit 137”

---

### 5) Multi-query retrieval (a.k.a. “query variations”)

- **What it is**: generate 3–8 variations of the query, retrieve for each, then merge (often with RRF).
- **Why it helps**: one query may miss, but another phrasing hits.
- **Tradeoff**: more queries → slower / more cost.

---

### 6) MMR (Maximal Marginal Relevance) — diversify results

- **What it is**: after you retrieve candidates, pick results that are both:
  - relevant to the query
  - not duplicates of each other
- **Why it helps**: avoids “top 5 are the same paragraph copied 5 times”.
- **When to use**: repetitive docs, long docs, many similar chunks.

---

### 7) Parent–child retrieval (chunk + parent document)

- **What it is**: store small chunks (child), but when you retrieve, you can also fetch a larger “parent” (page/section/doc).
- **Why it helps**: chunks are good for search, parents are good for context.
- **Example**:
  - Retrieve chunk about “distribution-key”
  - Provide the full section “Vespa services.xml nodes config”

---

### 8) Two-stage retrieval (coarse → fine)

- **What it is**: stage 1 quickly narrows down (cheap), stage 2 is higher quality (slower).
- **Example**:
  - Stage 1: vector retrieve top 200
  - Stage 2: re-rank top 200 with cross-encoder, return top 8

---

### 9) Time/freshness boosting (recency bias)

- **What it is**: boost newer docs/chunks (or demote very old ones).
- **Why it helps**: docs change; old instructions can be wrong.
- **Example**:
  - Prefer “2025 docker compose” over “2019 docker-compose”

---

### 10) Semantic caching (answer cache + retrieval cache)

- **What it is**:
  - cache retrieval results for similar queries
  - or cache full answers when the question repeats
- **Why it helps**: faster + cheaper for repeated questions.
- **Risk**: cache can serve stale answers if docs change (fix with TTL/versioning).

---

### 11) Sparse neural retrieval (SPLADE-style)

- **What it is**: a neural model produces a “sparse” vector of keyword weights (like BM25 but learned).
- **Why it helps**: keeps keyword matching strengths, but learns better expansions.
- **Tradeoff**: more complex than BM25; needs model + infra.

---

### 12) Late interaction retrieval (ColBERT-style)

- **What it is**: represent tokens and compute a smarter similarity than single-vector cosine.
- **Why it helps**: higher precision than basic dense vectors in many settings.
- **Tradeoff**: heavier index + slower than single-vector ANN.

---

### Practical beginner recipe (good default)

- **Start**: hybrid search (BM25 + vectors)
- **Add**: metadata filtering (security + precision)
- **Then**: re-rank (for quality)
- **If duplicates**: add MMR
- **If users are vague**: add query rewrite / multi-query



