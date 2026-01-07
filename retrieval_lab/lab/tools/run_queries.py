from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests

LAB_URL = os.environ.get("LAB_URL", "http://localhost:8000")


def call_search(payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(f"{LAB_URL}/search", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def print_top(resp: dict[str, Any], max_hits: int = 5) -> None:
    print("request_id:", resp.get("request_id"))
    print("ok:", resp.get("ok"), "http_status:", resp.get("http_status"))
    print(
        "embed_latency_ms:",
        f"{resp.get('embed_latency_ms', 0):.1f}",
        "retrieval_latency_ms:",
        f"{resp.get('retrieval_latency_ms', 0):.1f}",
    )
    print("yql:", resp.get("yql"))
    print("hits:")
    for h in (resp.get("hits") or [])[:max_hits]:
        print(" -", h.get("doc_id"), h.get("chunk_id"), "relevance=", h.get("relevance"))
    print()


def main() -> None:
    # These queries are designed to match the concepts you learned:
    # - metadata filters (over-filtering)
    # - recall vs ranking (target_hits)
    # - vector vs hybrid (keyword constraint + hybrid rank profile)
    scenarios = [
        {
            "title": "1) Vector search: baseline (tenant t1)",
            "payload": {
                "query": "docker daemon not running",
                "mode": "vector",
                "hits": 5,
                "target_hits": 50,
                "tenant_id": "t1",
            },
        },
        {
            "title": "2) Over-filtering example: wrong tenant -> empty/irrelevant",
            "payload": {
                "query": "docker daemon not running",
                "mode": "vector",
                "hits": 5,
                "target_hits": 50,
                "tenant_id": "t2",
            },
        },
        {
            "title": "3) Recall tuning: tiny target_hits (may miss relevant docs)",
            "payload": {
                "query": "chmod entrypoint.sh operation not permitted",
                "mode": "vector",
                "hits": 5,
                "target_hits": 1,
                "tenant_id": "t1",
            },
        },
        {
            "title": "4) Recall tuning: larger target_hits (better recall, usually)",
            "payload": {
                "query": "chmod entrypoint.sh operation not permitted",
                "mode": "vector",
                "hits": 5,
                "target_hits": 50,
                "tenant_id": "t1",
            },
        },
        {
            "title": "5) Hybrid: constrain by a keyword + hybrid scoring",
            "payload": {
                "query": "chmod entrypoint.sh operation not permitted",
                "mode": "hybrid",
                "keyword": "chmod",
                "hits": 5,
                "target_hits": 50,
                "tenant_id": "t1",
            },
        },
    ]

    for s in scenarios:
        print(s["title"])
        resp = call_search(s["payload"])
        print_top(resp)

    print("Done. Tip: open ./logs/requests.jsonl on your host to see trace logs.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)


