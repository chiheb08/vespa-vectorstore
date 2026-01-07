### 2025-12-16 — `vespa-deployer` tried localhost instead of the `vespa` service

---

### Symptom

Compose failed with:

> `service "vespa-deployer" didn't complete successfully: exit 1`

`docker logs rag_vespa_deployer` showed:

> Uploading application '/app' using `http://localhost:19071/...`  
> `Failed to connect to localhost port 19071: Connection refused`

---

### Main cause

`vespa-deploy` defaults to **config server = localhost** unless you specify one.

But the config server we need is in the **other container** (`vespa`), so the deployer must target `vespa:19071`.

---

### Fix

In `rag_app/docker-compose.yml`, we changed the deploy commands to set the config server explicitly:

```bash
/opt/vespa/bin/vespa-deploy -c vespa prepare /app
/opt/vespa/bin/vespa-deploy -c vespa activate
```

Then rerun:

```bash
cd rag_app
docker compose up -d --build
```



