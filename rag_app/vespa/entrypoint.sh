#!/usr/bin/env bash
set -euo pipefail

echo "[vespa] Starting Vespa services..."
/opt/vespa/bin/vespa-start-services

echo "[vespa] Waiting for config/health endpoint..."
ok=0
for i in {1..300}; do
  if curl -fsS "http://localhost:19071/state/v1/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 1
done

if [ "${ok}" -ne 1 ]; then
  echo "[vespa] ERROR: Vespa control plane on :19071 did not become ready in time."
  echo "[vespa] Hint: check logs with: docker logs rag_vespa"
  exit 1
fi

echo "[vespa] Deploying application package from /app ..."
/opt/vespa/bin/vespa-deploy prepare /app
/opt/vespa/bin/vespa-deploy activate

echo "[vespa] Ready. Tailing vespa log."
tail -F /opt/vespa/logs/vespa/vespa.log


