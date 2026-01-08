from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import numpy as np
import requests
from fastapi import FastAPI
from sentence_transformers import SentenceTransformer

VESPA_URL = os.environ.get("VESPA_URL", "http://vespa:8080")
VESPA_NAMESPACE = os.environ.get("VESPA_NAMESPACE", "lab")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "384"))
LOG_PATH = os.environ.get("LOG_PATH", "/logs/requests.jsonl")

app = FastAPI(title="retrieval-lab", version="0.1.0")

_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model


def _embed(text: str) -> tuple[list[float], float, float]:
    t0 = time.perf_counter()
    vec = _get_model().encode([text], normalize_embeddings=True)[0]
    t1 = time.perf_counter()

    vec = np.asarray(vec, dtype=np.float32)
    if vec.shape != (EMBED_DIM,):
        raise ValueError(
            f"Embedding dim mismatch: model returned {vec.shape}, expected ({EMBED_DIM},). "
            f"Check EMBED_MODEL/EMBED_DIM and Vespa schema tensor dimension."
        )

    norm = float(np.linalg.norm(vec))
    return vec.tolist(), (t1 - t0) * 1000.0, norm


def _append_log(record: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "vespa_url": VESPA_URL,
        "vespa_namespace": VESPA_NAMESPACE,
        "embed_model": EMBED_MODEL,
        "embed_dim": EMBED_DIM,
    }


@app.post("/search")
def search(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Payload (examples):
      {
        "query": "docker daemon not running",
        "mode": "vector",
        "hits": 5,
        "target_hits": 50,
        "tenant_id": "t1",
        "source": "docs"
      }

      {
        "query": "chmod entrypoint.sh operation not permitted",
        "mode": "hybrid",
        "keyword": "chmod",
        "hits": 5,
        "target_hits": 50
      }
    """
    request_id = payload.get("request_id") or str(uuid.uuid4())
    raw_query = (payload.get("query") or "").strip()
    if not raw_query:
        return {"error": "Missing 'query'."}

    mode = (payload.get("mode") or "vector").strip().lower()
    if mode not in ("vector", "hybrid"):
        return {"error": "mode must be 'vector' or 'hybrid'."}

    hits = int(payload.get("hits") or 5)
    target_hits = int(payload.get("target_hits") or 50)

    tenant_id = (payload.get("tenant_id") or "").strip()
    source = (payload.get("source") or "").strip()
    keyword = (payload.get("keyword") or "").strip()

    vec, embed_latency_ms, vec_norm = _embed(raw_query)

    where_parts: list[str] = []
    if tenant_id:
        where_parts.append(f'tenant_id contains "{tenant_id}"')
    if source:
        where_parts.append(f'source contains "{source}"')
    if mode == "hybrid" and keyword:
        where_parts.append(f'text contains "{keyword}"')

    where_prefix = ""
    if where_parts:
        where_prefix = " and ".join(where_parts) + " and "

    yql = (
        "select chunk_id, doc_id, tenant_id, source, text "
        f"from sources chunk where {where_prefix}"
        f"({{targetHits:{target_hits}}}nearestNeighbor(embedding, q));"
    )

    req = {
        "yql": yql,
        "hits": hits,
        "ranking.profile": mode,
        "input.query(q)": vec,
    }

    t0 = time.perf_counter()
    r = requests.post(f"{VESPA_URL}/search/", json=req, timeout=30)
    t1 = time.perf_counter()

    retrieval_latency_ms = (t1 - t0) * 1000.0
    ok = r.ok

    body: dict[str, Any]
    try:
        body = r.json()
    except Exception:
        body = {"raw": r.text}

    hits_out: list[dict[str, Any]] = []
    children = (((body or {}).get("root") or {}).get("children") or []) if ok else []
    for h in children:
        fields = h.get("fields") or {}
        hits_out.append(
            {
                "id": h.get("id"),
                "relevance": h.get("relevance"),
                "chunk_id": fields.get("chunk_id"),
                "doc_id": fields.get("doc_id"),
                "tenant_id": fields.get("tenant_id"),
                "source": fields.get("source"),
                "text": fields.get("text"),
            }
        )

    log_record = {
        "request_id": request_id,
        "timestamp_ms": int(time.time() * 1000),
        "raw_query": raw_query,
        "final_query": raw_query,
        "filters": {"tenant_id": tenant_id or None, "source": source or None},
        "embedding": {
            "model": EMBED_MODEL,
            "dim": EMBED_DIM,
            "vector_norm": vec_norm,
            "latency_ms": embed_latency_ms,
        },
        "retrieval": {
            "vespa_url": VESPA_URL,
            "namespace": VESPA_NAMESPACE,
            "mode": mode,
            "keyword": keyword or None,
            "hits": hits,
            "target_hits": target_hits,
            "yql": yql,
            "latency_ms": retrieval_latency_ms,
            "http_status": r.status_code,
        },
        "results": [
            {
                "chunk_id": h.get("chunk_id"),
                "doc_id": h.get("doc_id"),
                "relevance": h.get("relevance"),
            }
            for h in hits_out
        ],
    }

    _append_log(log_record)

    return {
        "request_id": request_id,
        "ok": ok,
        "http_status": r.status_code,
        "embed_latency_ms": embed_latency_ms,
        "retrieval_latency_ms": retrieval_latency_ms,
        "yql": yql,
        "hits": hits_out,
        "error": None if ok else body,
    }



