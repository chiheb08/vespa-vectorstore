### `rag_app` — OpenWebUI + Ollama + Vespa RAG (Docker Compose)

This folder contains a runnable RAG stack:

- **OpenWebUI** (UI): `http://localhost:3000`
- **RAG API (OpenAI-compatible)**: `http://localhost:8000`
- **Ollama** (LLM + embeddings): `http://localhost:11434`
- **Vespa** (vector store): `http://localhost:8080` (data plane), `http://localhost:19071` (metrics/control)
- **Prometheus**: `http://localhost:9090`
- **Grafana**: `http://localhost:3001` (user/pass: `admin` / `admin`)

The integration is:

1. You ingest documents into Vespa using `rag-api` (it chunks + embeds using Ollama).
2. You chat in OpenWebUI, but you point it to `rag-api` as an OpenAI-compatible endpoint.
3. `rag-api` retrieves top chunks from Vespa and calls Ollama to generate the final answer.
4. Vespa metrics are exported to Prometheus and visualized in Grafana.

---

### 1) Start everything

From the repository root:

```bash
cd rag_app
docker compose up -d --build
```

Wait for Vespa to become healthy (first start can take a bit).

Note: this stack uses a small one-shot container `vespa-deployer` that deploys the Vespa schema automatically once Vespa is healthy.

If you see a build error like:

> `unable to prepare context: path ".../vespa-metrics-exporter" not found`

it means you are running an older checkout. Fix by:

```bash
cd /Users/chihebmhamdi/Desktop/vespa
git pull
cd rag_app
docker compose up -d --build
```

---

### 2) Pull Ollama models (first time only)

OpenWebUI only shows **models that exist in Ollama**. If you don’t pull any models, the model dropdown will be empty.

This project defaults to:

- Chat model: `llama3.1:8b`
- Embedding model: `nomic-embed-text`

Pull them (recommended: start with a small model first, then upgrade):

```bash
docker exec rag_ollama ollama pull llama3.2:1b
docker exec rag_ollama ollama pull nomic-embed-text
```

List installed models:

```bash
docker exec rag_ollama ollama list
```

If you see errors like `model "nomic-embed-text" not found` when calling `/ingest/text`,
it means you **did not pull the embedding model yet**. Fix by running the pull command above.

If OpenWebUI still shows no models after pulling, restart it:

```bash
docker compose restart open-webui
```

Optional: pull a bigger chat model (slower/heavier):

```bash
docker exec rag_ollama ollama pull llama3.1:8b
```

---

### 3) Ingest documents into Vespa (via rag-api)

#### 3.1 Ingest plain text

```bash
curl -s http://localhost:8000/ingest/text \
  -H "Content-Type: application/json" \
  -d '{
    "doc_id": "doc-1",
    "text": "Paste a few paragraphs here. This will be chunked, embedded, and stored in Vespa."
  }' | python3 -m json.tool
```

##### Understanding the `/ingest/text` response (what the values mean)

Example response:

```json
{
  "ok": true,
  "doc_id": "doc-1",
  "namespace": "my_ns",
  "chunks_fed": 1,
  "chunk_ids": ["doc-1::chunk-0"],
  "embed": { "model": "nomic-embed-text", "dim": 768, "total_ms": 4656.0 },
  "feed": { "vespa_url": "http://vespa:8080", "total_ms": 1027.9 },
  "total_ms": 5683.9,
  "request_id": "..."
}
```

How to read it:

- **`ok`**: `true` means the whole pipeline succeeded (chunk → embed → feed).
- **`doc_id`**: your original document id (used to group chunks).
- **`namespace`**: Vespa document namespace used by the API (`VESPA_NAMESPACE`).
- **`chunks_fed`**: how many chunks were created and stored in Vespa.
  - If your text is longer, you’ll see a bigger number here.
- **`chunk_ids`**: the exact ids stored in Vespa (format: `<doc_id>::chunk-<index>`).
- **`embed.total_ms`**: total time spent generating embeddings for all chunks (in milliseconds).
  - In your case ~4656ms means **~4.6 seconds** to embed 1 chunk.
- **`feed.total_ms`**: total time spent sending those chunks to Vespa (HTTP + indexing work).
  - In your case ~1028ms means **~1.0 second** to feed 1 chunk.
- **`total_ms`**: overall time for this request (≈ embed + feed + small overhead).
- **`request_id`**: useful for tracing a single request in logs.

##### My opinion on your numbers (what’s “normal” and how to improve)

Your split looked like:
- embedding ~4.6s
- feeding ~1.0s
- total ~5.7s

This is not “wrong”, but it’s **slow for production**. Common reasons:

- **First run is slower**: the embedding model may be loading/warming up.
- **CPU-only**: Ollama on CPU can be slow, especially on larger models.
- **One embedding request per chunk**: if you ingest many chunks, times add up.

Quick improvements:
- Run ingestion again (2nd run is often faster after warmup).
- Use a faster/smaller embedding model if available for your hardware.
- If you have a GPU, run Ollama with GPU support (big speedup).
- Keep chunk count reasonable (chunk size/overlap directly affect total embed time).

#### 3.2 Ingest a file (txt/md/pdf)

```bash
curl -s http://localhost:8000/ingest/file \
  -F "doc_id=myfile-1" \
  -F "file=@/ABS/PATH/TO/file.pdf" | python3 -m json.tool
```

Common mistake:
- If you write `-F "file=/path/to/file.pdf"` (no `@`), you are sending a **string**, not uploading the file.
- Use `@` to upload: `-F "file=@/path/to/file.pdf"`

If your PDF is password-protected, pass the password like this:

```bash
curl -s http://localhost:8000/ingest/file \
  -F "doc_id=myfile-1" \
  -F "pdf_password=YOUR_PASSWORD" \
  -F "file=@/ABS/PATH/TO/file.pdf" | python3 -m json.tool
```

---

### 4) Chat with RAG in OpenWebUI

OpenWebUI: `http://localhost:3000`

In OpenWebUI, add a new **OpenAI-compatible** connection:

- **Base URL**: `http://rag-api:8000/v1` (from inside OpenWebUI container)
  - If the UI requires a host URL, use: `http://localhost:8000/v1`
- **API key**: any dummy value (the demo API does not enforce auth)

Then select the model exposed by `rag-api` (example: `rag-ollama`).

---

### 5) Test the RAG API directly (no UI)

```bash
curl -s http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "rag-ollama",
    "messages": [
      { "role": "user", "content": "What is this document about?" }
    ]
  }' | python3 -m json.tool
```

---

### 6) Monitoring Vespa (Grafana)

Open Grafana: `http://localhost:3001` (admin/admin)

- A Prometheus datasource is auto-provisioned.
- A starter dashboard is included under “Vespa”.

Also useful endpoints:

- Vespa health: `http://localhost:19071/state/v1/health`
- Vespa raw metrics JSON: `http://localhost:19071/metrics/v2/values`
- Exporter metrics (Prometheus text): `http://localhost:9109/metrics`

If Grafana shows “No data” on the Vespa dashboard:
- first verify the exporter returns **many** `vespa_metric_value{...}` lines at `http://localhost:9109/metrics`
- then verify Prometheus sees series: open `http://localhost:9090` and run `count(vespa_metric_value)`

Deep explanation of what you see in `http://localhost:9109/metrics`:
- `rag_app/VESPA_EXPORTED_METRICS_EXPLAINED.md`

---

### 7) Configuration (most important knobs)

Edit these in `docker-compose.yml` under `rag-api`:

- `OLLAMA_CHAT_MODEL`: generation model
- `OLLAMA_EMBED_MODEL`: embedding model
- `EMBED_DIM`: must match the embedding model output AND Vespa schema
- `RAG_TOP_K`: how many chunks to return to the prompt
- `RAG_TARGET_HITS`: ANN candidate count (higher = often better recall, slower)

If you change `EMBED_DIM`, you must also update the Vespa schema:

- `rag_app/vespa/app/schemas/chunk.sd`

Then rebuild:

```bash
docker compose up -d --build
```

---

### 8) Troubleshooting

- **OpenWebUI shows no models**
  - run: `docker exec rag_ollama ollama list`
  - if empty, pull one: `docker exec rag_ollama ollama pull llama3.2:1b`
  - restart UI: `docker compose restart open-webui`

- **`rag_vespa exited (137)`**
  - this is usually **out-of-memory (OOM)** in Docker Desktop
  - fix: increase Docker Desktop memory (try 6–8GB+), then restart:

```bash
docker compose down
docker compose up -d --build
```

- **No answers / empty context**:
  - you probably didn’t ingest documents yet
  - verify with: `curl -s http://localhost:8080/search/ ...` (see `rag-api` logs too)

- **Embedding dimension errors**:
  - ensure `EMBED_DIM` matches the model output and schema `tensor<float>(x[...])`

- **Ollama is slow**:
  - first generation after pulling a model is slower
  - large models on CPU can be very slow

---

### 9) Stop everything

```bash
docker compose down
```


