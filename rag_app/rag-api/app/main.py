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
        "chunk_words": CHUNK_WORDS,
        "chunk_overlap_words": CHUNK_OVERLAP_WORDS,
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


# Minimal OpenAI-compatible response (stub). We'll implement real RAG next.
@app.post("/v1/chat/completions")
def chat_completions(payload: dict) -> dict:
    user_text = ""
    for m in payload.get("messages", []) or []:
        if m.get("role") == "user":
            user_text = m.get("content", "") or ""
            break

    content = (
        "rag-api is up, but full RAG is not implemented yet.\n"
        "You sent: " + user_text
    )

    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": payload.get("model", "rag-ollama"),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }



