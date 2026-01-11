### 2025-12-16 — Docker Compose build issues (daemon + chmod)

This document records two issues seen when running:

```bash
docker compose up -d --build
```

---

### Issue 1: Cannot connect to Docker daemon

#### Symptom

You saw:

> Unable to get image ... Cannot connect to the Docker daemon at `unix:///Users/.../.docker/run/docker.sock`. Is the docker daemon running?

#### Main cause

Docker Desktop (the Docker daemon) was **not running** (or not ready yet), so `docker compose` could not build/pull images.

#### Fix

- Start **Docker Desktop**, wait until it’s “running”.
- Re-run:

```bash
docker compose up -d --build
```

---

### Issue 2: Vespa image build fails on `chmod`

#### Symptom

During the `vespa` image build:

> `chmod: changing permissions of '/entrypoint.sh': Operation not permitted`

#### Main cause

The base image `vespaengine/vespa` does not always run build steps as `root` on all setups, so doing:

```dockerfile
RUN chmod +x /entrypoint.sh
```

can fail with permission errors on Docker Desktop / BuildKit.

#### Fix

Avoid `RUN chmod` and set the executable bit at copy time:

- Updated `rag_app/vespa/Dockerfile` to:
  - remove `RUN chmod ...`
  - use `COPY --chmod=755 ...` (and `--chown=vespa:vespa`) for `entrypoint.sh`

After the change:

```bash
docker compose up -d --build
```

should build successfully.





