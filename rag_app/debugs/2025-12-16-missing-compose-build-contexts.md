### 2025-12-16 — Missing docker-compose build contexts

---

### Symptom

Running:

```bash
docker compose up -d --build
```

failed with:

> `unable to prepare context: path ".../rag_app/vespa-metrics-exporter" not found`

---

### Main cause

In `rag_app/docker-compose.yml`, some services use **local build contexts**, for example:

- `vespa-metrics-exporter: build: ./vespa-metrics-exporter`

Docker Compose requires the folder path to exist on disk. At the time of the error, the folder **did not exist yet** (project scaffolding was incomplete / not pulled).

---

### Fix

We created the missing folders and files so Compose can build:

- `rag_app/vespa-metrics-exporter/` (a tiny Vespa->Prometheus exporter)
- `rag_app/monitoring/` (Prometheus + Grafana provisioning)
- `rag_app/rag-api/` (a minimal API container so the stack builds; full RAG comes next)

Then re-run:

```bash
cd /Users/chihebmhamdi/Desktop/vespa
git pull
cd rag_app
docker compose up -d --build
```



