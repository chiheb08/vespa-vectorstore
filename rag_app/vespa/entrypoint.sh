#!/usr/bin/env bash
set -euo pipefail

echo "[vespa] Starting Vespa services..."
/opt/vespa/bin/vespa-start-services

echo "[vespa] Waiting for config/health endpoint..."
for i in $(seq 1 120); do
  if curl -fsS "http://localhost:19071/state/v1/health" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "[vespa] Deploying application package from /app ..."
/opt/vespa/bin/vespa-deploy prepare /app
/opt/vespa/bin/vespa-deploy activate

echo "[vespa] Ready. Tailing vespa log."
tail -F /opt/vespa/logs/vespa/vespa.log


