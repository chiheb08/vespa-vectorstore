### 2025-12-16 — Vespa control plane `:19071` not ready in custom image

---

### Symptom

`docker compose up -d` failed because `rag_vespa` never became healthy and logs showed the control plane was unreachable:

> `Failed to connect to localhost port 19071: Connection refused`

---

### Main cause

We initially built a custom Vespa image and replaced the base image entrypoint with our own script.

On `vespaengine/vespa`, the default entrypoint is responsible for proper startup of the control plane components (including what serves `:19071`). By overriding the entrypoint, the container started only a subset of services, and `:19071` never became ready.

---

### Fix

We switched to a safer Docker Compose pattern:

- Run **Vespa** using the official image `vespaengine/vespa:latest` (no custom entrypoint).
- Mount the application package at `./vespa/app:/app:ro`.
- Add a one-shot **`vespa-deployer`** service that waits for Vespa health and then runs:

```bash
/opt/vespa/bin/vespa-deploy prepare /app
/opt/vespa/bin/vespa-deploy activate
```

This keeps Vespa startup stable and still gives “one command” deployment.





