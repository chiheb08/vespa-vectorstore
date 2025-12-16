### 2025-12-16 — Vespa container exits during auto-deploy (race / loop bug)

---

### Symptom

`docker compose up -d` failed with:

> `dependency failed to start: container rag_vespa exited (1)`

Vespa logs showed:

> `curl: (7) Failed to connect to localhost port 19071: Connection refused`

right when the container tried to run:

```bash
/opt/vespa/bin/vespa-deploy prepare /app
```

---

### Main cause

The `rag_app/vespa/entrypoint.sh` script attempted to wait for Vespa readiness using:

```bash
for i in $(seq 1 120); do ... done
```

On some images/setups, `seq` may not exist, causing the loop to effectively not wait.
Then the script tried to deploy while the control plane (`:19071`) was not ready yet, leading to "connection refused" and container exit.

---

### Fix

We replaced the wait loop with bash brace expansion (no external `seq` dependency), increased the wait budget, and fail fast with a clear error if Vespa never becomes ready:

- use:
  - `for i in {1..300}; do ...`
  - check `http://localhost:19071/state/v1/health`
  - `exit 1` with a helpful hint if not ready

After updating, rebuild + restart:

```bash
cd rag_app
docker compose up -d --build
```


