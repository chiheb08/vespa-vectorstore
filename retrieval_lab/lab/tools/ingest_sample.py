from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import requests
from sentence_transformers import SentenceTransformer

VESPA_URL = os.environ.get("VESPA_URL", "http://vespa:8080")
VESPA_NAMESPACE = os.environ.get("VESPA_NAMESPACE", "lab")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "384"))


@dataclass
class Doc:
    doc_id: str
    tenant_id: str
    source: str
    title: str
    body: str


def load_docs(path: str) -> list[Doc]:
    docs: list[Doc] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            docs.append(
                Doc(
                    doc_id=str(obj["doc_id"]),
                    tenant_id=str(obj.get("tenant_id") or "t1"),
                    source=str(obj.get("source") or "docs"),
                    title=str(obj.get("title") or ""),
                    body=str(obj.get("body") or ""),
                )
            )
    return docs


def chunk_fixed(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    words = text.split()
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


def chunk_structure_aware(text: str, chunk_words: int, overlap_words: int) -> list[str]:
    """
    Simple structure-aware chunker:
    - splits on markdown headings "## " if present
    - falls back to fixed chunking
    """
    if "\n## " not in text:
        return chunk_fixed(text, chunk_words, overlap_words)

    parts = []
    current = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                parts.append("\n".join(current).strip())
                current = []
        current.append(line)
    if current:
        parts.append("\n".join(current).strip())

    # Each section can still be long: apply fixed chunking per section
    out: list[str] = []
    for p in parts:
        out.extend(chunk_fixed(p, chunk_words, overlap_words))
    return [c for c in out if c]


def embed_texts(model: SentenceTransformer, texts: list[str]) -> list[list[float]]:
    vecs = model.encode(texts, normalize_embeddings=True)
    vecs = np.asarray(vecs, dtype=np.float32)
    if vecs.ndim != 2 or vecs.shape[1] != EMBED_DIM:
        raise ValueError(
            f"Embedding dim mismatch: got {vecs.shape}, expected (*, {EMBED_DIM}). "
            "Check EMBED_MODEL/EMBED_DIM and Vespa schema tensor dimension."
        )
    return [v.tolist() for v in vecs]


def feed_chunks(chunks: Iterable[dict[str, Any]]) -> None:
    for c in chunks:
        chunk_id = c["chunk_id"]
        url = f"{VESPA_URL}/document/v1/{VESPA_NAMESPACE}/chunk/docid/{chunk_id}"
        r = requests.post(url, json={"fields": c}, timeout=30)
        if not r.ok:
            raise RuntimeError(f"Feed failed for {chunk_id}: {r.status_code} {r.text}")


def iter_chunks(
    docs: list[Doc],
    chunking: str,
    chunk_words: int,
    overlap_words: int,
    model: SentenceTransformer,
) -> Iterable[dict[str, Any]]:
    for d in docs:
        text = (d.title + "\n\n" + d.body).strip()
        if chunking == "fixed":
            parts = chunk_fixed(text, chunk_words, overlap_words)
        else:
            parts = chunk_structure_aware(text, chunk_words, overlap_words)

        vecs = embed_texts(model, parts)
        for idx, (t, v) in enumerate(zip(parts, vecs, strict=True)):
            yield {
                "chunk_id": f"{d.doc_id}::chunk-{idx}",
                "doc_id": d.doc_id,
                "tenant_id": d.tenant_id,
                "source": d.source,
                "text": t,
                "embedding": v,
            }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", default="/data/docs.jsonl")
    ap.add_argument("--chunking", choices=["fixed", "structure"], default="fixed")
    ap.add_argument("--chunk-words", type=int, default=140)
    ap.add_argument("--overlap-words", type=int, default=25)
    args = ap.parse_args()

    t0 = time.perf_counter()
    docs = load_docs(args.docs)
    model = SentenceTransformer(EMBED_MODEL)

    chunks = list(
        iter_chunks(
            docs=docs,
            chunking="fixed" if args.chunking == "fixed" else "structure",
            chunk_words=args.chunk_words,
            overlap_words=args.overlap_words,
            model=model,
        )
    )

    feed_chunks(chunks)
    t1 = time.perf_counter()

    print(
        f"Fed {len(chunks)} chunks from {len(docs)} docs "
        f"using chunking={args.chunking} in {(t1 - t0):.2f}s"
    )
    print(f"Vespa: {VESPA_URL} namespace={VESPA_NAMESPACE}")


if __name__ == "__main__":
    main()




