### Retrieval Lab (learn-by-doing): tracing + monitoring + improving vector DB retrieval

This is a **small practice project** to test everything you learned so far:

- **Embeddings** (query → vector)
- **Vector search** in Vespa (`nearestNeighbor(...)`)
- **Filters** (tenant_id/source) and how over-filtering breaks results
- **Recall vs ranking** (using `targetHits`)
- **Hybrid** (BM25 + vector) using the `hybrid` rank profile
- **Tracing** (structured JSON logs per request with request_id, latencies, params)
- **Monitoring** (Vespa health + metrics endpoints)

---

## 0) What’s inside

- `docker-compose.yml`: Vespa + deployer + a small FastAPI lab service
- `vespa/app/`: Vespa application package (schema + services)
- `data/`: tiny dataset + evaluation queries
- `lab/`: Python app (API + tools)
- `logs/`: created on first run (request traces)

---

## 1) Start the lab

From repo root:

```bash
cd retrieval_lab
docker compose up -d --build
```

Health checks:

```bash
curl -fsS http://localhost:8001/health | python -m json.tool
curl -fsS http://localhost:19072/state/v1/health | python -m json.tool
```

---

## 2) Ingest the sample data (fixed-size chunking)

```bash
docker compose exec lab python tools/ingest_sample.py --chunking fixed
```

---

## 3) Run “guided” queries that match the concepts

```bash
docker compose exec lab python tools/run_queries.py
```

Now open the trace log on your host:

- `retrieval_lab/logs/requests.jsonl`

Each line is one request. You can see:
- filters used
- embedding model/dim + vector norm
- `target_hits`
- `ranking.profile`
- returned `doc_id`s
- latencies

This is the same “trace mindset” used in real production systems.

---

## 4) Practice: recall vs ranking (targetHits)

Try the same query with different `target_hits`:

```bash
curl -s http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"chmod entrypoint.sh operation not permitted","mode":"vector","hits":5,"target_hits":1,"tenant_id":"t1"}' | python -m json.tool

curl -s http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"chmod entrypoint.sh operation not permitted","mode":"vector","hits":5,"target_hits":50,"tenant_id":"t1"}' | python -m json.tool
```

What to observe:
- Do you get a better doc_id when you increase `target_hits`?
- Latency may go up a bit (trade-off).

---

## 5) Practice: over-filtering (a very common real bug)

This dataset contains a doc in **tenant `t2`**. If you query tenant `t1`, you should not see it.

Try:

```bash
curl -s http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"docker daemon not running","mode":"vector","hits":5,"target_hits":50,"tenant_id":"t2"}' | python -m json.tool
```

Now change tenant back to `t1` and compare.

---

## 6) Practice: hybrid (BM25 + vector)

Hybrid is useful when exact keywords matter (e.g., `chmod`, error codes, filenames).

```bash
curl -s http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"chmod entrypoint.sh operation not permitted","mode":"hybrid","keyword":"chmod","hits":5,"target_hits":50,"tenant_id":"t1"}' | python -m json.tool
```

In this lab, hybrid mode uses:
- the `hybrid` rank profile (bm25 + closeness)
- a simple keyword constraint (`text contains "chmod"`) so BM25 has something to score

---

## 7) Quick offline evaluation (see improvements as numbers)

```bash
docker compose exec lab python tools/evaluate.py
```

Then try improvements:

### Option A: change chunking (structure-aware)
Reset everything (including Vespa data), then re-ingest:

```bash
docker compose down -v
docker compose up -d --build
docker compose exec lab python tools/ingest_sample.py --chunking structure
docker compose exec lab python tools/evaluate.py
```

### Option B: tweak targetHits
Edit `tools/evaluate.py` configs and rerun, or call `/search` with different `target_hits`.

---

## 8) Monitoring (beginner-friendly)

Vespa health:

- `http://localhost:19072/state/v1/health`

Vespa metrics JSON:

- `http://localhost:19072/metrics/v2/values`

Fetch metrics:

```bash
curl -s http://localhost:19072/metrics/v2/values > /tmp/vespa_metrics.json
python -c 'import json; d=json.load(open("/tmp/vespa_metrics.json")); print("keys:", list(d.keys())[:5])'
```

Tip: search inside that JSON for terms like:
- `query`
- `latency`
- `feed`

---

## 9) What to do next (if you want to go deeper)

- Add a **reranker** (re-order top 50 candidates)
- Add more metadata fields and test filter combinations
- Replace the embedding model and observe how dimension/schema must change


