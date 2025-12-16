#!/usr/bin/env bash
set -euo pipefail

VESPA_URL="${VESPA_URL:-http://localhost:8080}"

echo "Vespa URL: ${VESPA_URL}"
echo

echo "1) Simple vector kNN query (expects you already fed documents)"
curl -s "${VESPA_URL}/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "yql": "select chunk_id, doc_id, text from sources chunk where ({targetHits:10}nearestNeighbor(embedding, q));",
    "hits": 5,
    "ranking.profile": "vector",
    "input.query(q)": [0.01, 0.02, 0.03]
  }' | python3 -m json.tool | sed -n '1,120p'
echo

echo "2) Filter by doc_id + vector query"
curl -s "${VESPA_URL}/search/" \
  -H "Content-Type: application/json" \
  -d '{
    "yql": "select chunk_id, doc_id, text from sources chunk where doc_id contains \"doc-0\" and ({targetHits:10}nearestNeighbor(embedding, q));",
    "hits": 5,
    "ranking.profile": "vector",
    "input.query(q)": [0.01, 0.02, 0.03]
  }' | python3 -m json.tool | sed -n '1,120p'
echo

echo "3) Delete example chunk (change namespace/id if needed)"
echo "curl -X DELETE \"${VESPA_URL}/document/v1/my_ns/chunk/docid/chunk-1\""


