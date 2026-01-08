from __future__ import annotations

import io
import os
import time
import uuid
from typing import Any

import requests
from fastapi import FastAPI, File, Form, UploadFile
from pypdf import PdfReader

app = FastAPI(title="rag-api", version="0.1.0")

# Config (set in rag_app/docker-compose.yml)
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
OLLAMA_CHAT_MODEL = os.environ.get("OLLAMA_CHAT_MODEL", "llama3.1:8b")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")

VESPA_URL = os.environ.get("VESPA_URL", "http://vespa:8080").rstrip("/")
VESPA_NAMESPACE = os.environ.get("VESPA_NAMESPACE", "my_ns")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))

RAG_TOP_K = int(os.environ.get("RAG_TOP_K", "5"))
RAG_TARGET_HITS = int(os.environ.get("RAG_TARGET_HITS", "50"))

CHUNK_WORDS = int(os.environ.get("CHUNK_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(os.environ.get("CHUNK_OVERLAP_WORDS", "40"))


def _chunk_text(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return []

    out: list[str] = []
    i = 0
    while i < len(words):
        j = min(len(words), i + chunk_words)
        out.append(" ".join(words[i:j]).strip())
        if j >= len(words):
            break
        i = max(0, j - overlap_words)
    return [c for c in out if c]


def _ollama_embed_one(prompt: str) -> list[float]:
    """
    Ollama embeddings endpoint.
    Note: Ollama returns HTTP 404 for "model not found" (not just for unknown routes),
    so we must parse the body to give a good error message.
    """
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/embeddings",
        json={"model": OLLAMA_EMBED_MODEL, "prompt": prompt},
        timeout=120,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.ok:
        emb = data.get("embedding")
        if isinstance(emb, list):
            return emb
        raise RuntimeError(f"Unexpected Ollama embeddings response shape: {data}")

    # Common failure: model not pulled yet (Ollama often uses 404 for this).
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(
            f"Ollama embeddings error (HTTP {r.status_code}): {data['error']}. "
            f"Fix: pull the model inside the ollama container, e.g. "
            f"`docker exec rag_ollama ollama pull {OLLAMA_EMBED_MODEL}`"
        )

    raise RuntimeError(f"Ollama embeddings failed (HTTP {r.status_code}): {data}")


def _validate_embedding_dim(vec: list[float]) -> None:
    if len(vec) != EMBED_DIM:
        raise ValueError(
            f"Embedding dim mismatch: got {len(vec)}, expected {EMBED_DIM}. "
            "Fix by aligning: Ollama embedding model output dim == EMBED_DIM == Vespa schema tensor dim."
        )


def _vespa_feed_chunk(fields: dict[str, Any]) -> dict[str, Any]:
    """
    Feed one chunk document into Vespa.
    Schema expects: chunk_id, doc_id, text, embedding.
    """
    chunk_id = fields["chunk_id"]
    url = f"{VESPA_URL}/document/v1/{VESPA_NAMESPACE}/chunk/docid/{chunk_id}"
    r = requests.post(url, json={"fields": fields}, timeout=60)
    r.raise_for_status()
    return r.json()


def _vespa_retrieve(query_vec: list[float], top_k: int, target_hits: int) -> list[dict[str, Any]]:
    """
    Retrieve top chunks from Vespa using vector search.
    """
    yql = (
        "select chunk_id, doc_id, text from sources chunk "
        f"where ({{targetHits:{target_hits}}}nearestNeighbor(embedding, q));"
    )
    req = {
        "yql": yql,
        "hits": top_k,
        "ranking.profile": "vector",
        "input.query(q)": query_vec,
    }

    r = requests.post(f"{VESPA_URL}/search/", json=req, timeout=30)
    r.raise_for_status()
    body = r.json()
    children = (((body or {}).get("root") or {}).get("children") or []) or []

    out: list[dict[str, Any]] = []
    for h in children:
        fields = h.get("fields") or {}
        out.append(
            {
                "id": h.get("id"),
                "relevance": h.get("relevance"),
                "chunk_id": fields.get("chunk_id"),
                "doc_id": fields.get("doc_id"),
                "text": fields.get("text"),
            }
        )
    return out


def _ollama_chat(messages: list[dict[str, Any]]) -> str:
    """
    Call Ollama chat endpoint and return assistant content.
    """
    r = requests.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": OLLAMA_CHAT_MODEL, "messages": messages, "stream": False},
        timeout=300,
    )
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.ok:
        msg = (data.get("message") or {}) if isinstance(data, dict) else {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        raise RuntimeError(f"Unexpected Ollama chat response shape: {data}")

    # Ollama often returns 404 for model not found.
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(
            f"Ollama chat error (HTTP {r.status_code}): {data['error']}. "
            f"Fix: pull the chat model inside the ollama container, e.g. "
            f"`docker exec rag_ollama ollama pull {OLLAMA_CHAT_MODEL}`"
        )
    raise RuntimeError(f"Ollama chat failed (HTTP {r.status_code}): {data}")


def _ingest_text(doc_id: str, text: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    chunks = _chunk_text(text, CHUNK_WORDS, CHUNK_OVERLAP_WORDS)
    if not chunks:
        return {"ok": False, "error": "Text is empty after cleaning/chunking."}

    chunk_ids: list[str] = []
    embed_ms_total = 0.0
    feed_ms_total = 0.0

    for i, chunk_text in enumerate(chunks):
        chunk_id = f"{doc_id}::chunk-{i}"

        t_embed0 = time.perf_counter()
        emb = _ollama_embed_one(chunk_text)
        t_embed1 = time.perf_counter()
        _validate_embedding_dim(emb)
        embed_ms_total += (t_embed1 - t_embed0) * 1000.0

        fields = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "text": chunk_text,
            "embedding": emb,
        }

        t_feed0 = time.perf_counter()
        _vespa_feed_chunk(fields)
        t_feed1 = time.perf_counter()
        feed_ms_total += (t_feed1 - t_feed0) * 1000.0

        chunk_ids.append(chunk_id)

    t1 = time.perf_counter()
    return {
        "ok": True,
        "doc_id": doc_id,
        "namespace": VESPA_NAMESPACE,
        "chunks_fed": len(chunk_ids),
        "chunk_ids": chunk_ids,
        "embed": {"model": OLLAMA_EMBED_MODEL, "dim": EMBED_DIM, "total_ms": embed_ms_total},
        "feed": {"vespa_url": VESPA_URL, "total_ms": feed_ms_total},
        "total_ms": (t1 - t0) * 1000.0,
    }


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "vespa_url": VESPA_URL,
        "vespa_namespace": VESPA_NAMESPACE,
        "ollama_base_url": OLLAMA_BASE_URL,
        "ollama_chat_model": OLLAMA_CHAT_MODEL,
        "ollama_embed_model": OLLAMA_EMBED_MODEL,
        "embed_dim": EMBED_DIM,
        "rag_top_k": RAG_TOP_K,
        "rag_target_hits": RAG_TARGET_HITS,
        "chunk_words": CHUNK_WORDS,
        "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
    }


@app.get("/v1")
def v1_index() -> dict[str, Any]:
    """
    Helpful endpoint for humans who visit http://localhost:8000/v1 in a browser.
    OpenAI-compatible APIs typically don't define GET /v1, so we provide a small index.
    """
    return {
        "ok": True,
        "message": "OpenAI-compatible endpoints are available under /v1/*",
        "endpoints": {
            "models": {"method": "GET", "path": "/v1/models"},
            "chat_completions": {"method": "POST", "path": "/v1/chat/completions"},
        },
        "docs": {"swagger": "/docs", "openapi_json": "/openapi.json"},
    }


@app.post("/ingest/text")
def ingest_text(payload: dict) -> dict[str, Any]:
    doc_id = (payload.get("doc_id") or "").strip()
    text = (payload.get("text") or "").strip()
    if not doc_id:
        return {"ok": False, "error": "Missing doc_id"}
    if not text:
        return {"ok": False, "error": "Missing text"}

    request_id = payload.get("request_id") or str(uuid.uuid4())
    try:
        result = _ingest_text(doc_id=doc_id, text=text)
        result["request_id"] = request_id
        return result
    except Exception as e:
        return {"ok": False, "request_id": request_id, "error": str(e)}


@app.post("/ingest/file")
async def ingest_file(
    doc_id: str = Form(...),
    file: UploadFile = File(...),
    pdf_password: str | None = Form(None),
) -> dict[str, Any]:
    request_id = str(uuid.uuid4())
    filename = (file.filename or "").lower()
    data = await file.read()

    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data))
            if getattr(reader, "is_encrypted", False):
                if not pdf_password:
                    return {
                        "ok": False,
                        "request_id": request_id,
                        "filename": file.filename,
                        "bytes": len(data),
                        "error": (
                            "This PDF appears to be encrypted/password-protected. "
                            "Provide `pdf_password` as a multipart form field, e.g. "
                            "`-F \"pdf_password=...\"`. "
                            "If you still see an AES/cryptography error, rebuild rag-api to install cryptography."
                        ),
                    }

                # pypdf decrypt returns 0 if it fails, 1/2 if it succeeds (depending on algorithm)
                try:
                    ok = reader.decrypt(pdf_password)
                except Exception as e:
                    return {
                        "ok": False,
                        "request_id": request_id,
                        "filename": file.filename,
                        "bytes": len(data),
                        "error": f"Failed to decrypt PDF: {e}",
                    }

                if not ok:
                    return {
                        "ok": False,
                        "request_id": request_id,
                        "filename": file.filename,
                        "bytes": len(data),
                        "error": "PDF password was rejected (wrong password).",
                    }

            text = "\n\n".join((p.extract_text() or "") for p in reader.pages).strip()
        else:
            # treat as text by default (txt/md/etc)
            text = data.decode("utf-8", errors="replace").strip()

        result = _ingest_text(doc_id=doc_id, text=text)
        result["request_id"] = request_id
        result["filename"] = file.filename
        result["bytes"] = len(data)
        return result
    except Exception as e:
        return {
            "ok": False,
            "request_id": request_id,
            "filename": file.filename,
            "error": str(e),
        }


# Minimal OpenAI-compatible model list so OpenWebUI can connect.
@app.get("/v1/models")
def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": "rag-ollama",
                "object": "model",
                "owned_by": "rag_app",
            }
        ],
    }


# OpenAI-compatible response with real RAG:
# - embed the latest user message
# - retrieve top chunks from Vespa
# - call Ollama chat model with context
@app.post("/v1/chat/completions")
def chat_completions(payload: dict) -> dict:
    request_id = str(uuid.uuid4())
    messages_in = payload.get("messages", []) or []

    user_text = ""
    for m in reversed(messages_in):
        if (m or {}).get("role") == "user":
            user_text = (m.get("content") or "").strip()
            break

    if not user_text:
        user_text = ""

    try:
        # 1) Embed query
        t0 = time.perf_counter()
        q = _ollama_embed_one(user_text)
        _validate_embedding_dim(q)
        t1 = time.perf_counter()

        # 2) Retrieve
        hits = _vespa_retrieve(q, top_k=RAG_TOP_K, target_hits=RAG_TARGET_HITS)
        t2 = time.perf_counter()

        context_blocks: list[str] = []
        for h in hits:
            cid = h.get("chunk_id") or ""
            did = h.get("doc_id") or ""
            txt = (h.get("text") or "").strip()
            if not txt:
                continue
            context_blocks.append(f"[{did} | {cid}]\n{txt}")

        context_text = "\n\n---\n\n".join(context_blocks).strip()
        if not context_text:
            answer = (
                "I couldn't find any stored context in Vespa yet.\n"
                "Ingest some documents first using /ingest/text or /ingest/file, then ask again."
            )
        else:
            system = (
                "You are a helpful assistant. Answer the user using ONLY the provided CONTEXT.\n"
                "If the context is not enough, say you don't know.\n"
                "Keep the answer clear and concise.\n\n"
                "CONTEXT:\n"
                + context_text
            )

            # Preserve the user's conversation, but inject our context as the first system message.
            messages_out: list[dict[str, Any]] = [{"role": "system", "content": system}]
            for m in messages_in:
                role = (m or {}).get("role")
                content = (m or {}).get("content")
                if role in ("system", "user", "assistant") and isinstance(content, str):
                    messages_out.append({"role": role, "content": content})

            answer = _ollama_chat(messages_out)

            # Append sources (ids only) so you can verify what was used.
            source_lines = [f"- {h.get('doc_id')} :: {h.get('chunk_id')}" for h in hits if h.get("chunk_id")]
            if source_lines:
                answer = answer.rstrip() + "\n\nSources:\n" + "\n".join(source_lines)

        embed_ms = (t1 - t0) * 1000.0
        retrieve_ms = (t2 - t1) * 1000.0

        content = answer
        model_name = payload.get("model", "rag-ollama")
        created = int(time.time())
    except Exception as e:
        content = f"RAG error: {e}"
        model_name = payload.get("model", "rag-ollama")
        created = int(time.time())

    return {
        "id": f"chatcmpl-{request_id}",
        "object": "chat.completion",
        "created": created,
        "model": model_name,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        # Extra debug info (non-OpenAI standard). Safe to ignore by clients.
        "rag_debug": {
            "request_id": request_id,
            "vespa_namespace": VESPA_NAMESPACE,
            "top_k": RAG_TOP_K,
            "target_hits": RAG_TARGET_HITS,
            "embed_model": OLLAMA_EMBED_MODEL,
            "chat_model": OLLAMA_CHAT_MODEL,
        },
    }



