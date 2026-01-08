from __future__ import annotations

import json
import os
import statistics
from typing import Any

import requests

LAB_URL = os.environ.get("LAB_URL", "http://localhost:8000")


def call_search(payload: dict[str, Any]) -> dict[str, Any]:
    r = requests.post(f"{LAB_URL}/search", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def recall_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: set[str], k: int) -> float:
    top = retrieved_doc_ids[:k]
    return 1.0 if any(d in relevant_doc_ids for d in top) else 0.0


def dcg_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: set[str], k: int) -> float:
    dcg = 0.0
    for i, d in enumerate(retrieved_doc_ids[:k], start=1):
        rel = 1.0 if d in relevant_doc_ids else 0.0
        dcg += (2.0**rel - 1.0) / (math_log2(i + 1))
    return dcg


def idcg_at_k(num_relevant: int, k: int) -> float:
    # Best case: all relevant docs at the top
    dcg = 0.0
    for i in range(1, min(k, num_relevant) + 1):
        dcg += (2.0**1.0 - 1.0) / (math_log2(i + 1))
    return dcg


def math_log2(x: float) -> float:
    # avoid importing math to keep this script ultra-minimal
    import math

    return math.log(x, 2)


def ndcg_at_k(retrieved_doc_ids: list[str], relevant_doc_ids: set[str], k: int) -> float:
    dcg = dcg_at_k(retrieved_doc_ids, relevant_doc_ids, k)
    idcg = idcg_at_k(len(relevant_doc_ids), k)
    return (dcg / idcg) if idcg > 0 else 0.0


def load_eval(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def eval_config(name: str, mode: str, target_hits: int, keyword: str | None, k: int) -> None:
    eval_items = load_eval("/data/eval_queries.json")
    recalls = []
    ndcgs = []

    for item in eval_items:
        q = item["query"]
        relevant = set(item["relevant_doc_ids"])

        payload: dict[str, Any] = {
            "query": q,
            "mode": mode,
            "hits": k,
            "target_hits": target_hits,
            "tenant_id": "t1",
        }
        if keyword:
            payload["keyword"] = keyword

        resp = call_search(payload)
        retrieved = [h.get("doc_id") for h in (resp.get("hits") or []) if h.get("doc_id")]

        recalls.append(recall_at_k(retrieved, relevant, k))
        ndcgs.append(ndcg_at_k(retrieved, relevant, k))

    print(f"== {name} ==")
    print(f"Recall@{k}: {statistics.mean(recalls):.3f}")
    print(f"nDCG@{k}:  {statistics.mean(ndcgs):.3f}")
    print()


def main() -> None:
    # This is intentionally simple: you’ll see relative changes when you tweak:
    # - mode (vector vs hybrid)
    # - target_hits (candidate count)
    # - chunking strategy (re-ingest fixed vs structure-aware)
    k = 5

    eval_config("Vector, target_hits=1", mode="vector", target_hits=1, keyword=None, k=k)
    eval_config("Vector, target_hits=50", mode="vector", target_hits=50, keyword=None, k=k)
    eval_config("Hybrid(keyword=docker), target_hits=50", mode="hybrid", target_hits=50, keyword="docker", k=k)


if __name__ == "__main__":
    main()



