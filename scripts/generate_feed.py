#!/usr/bin/env python3
"""
Generate a Vespa JSONL feed file for the `chunk` schema.

This script intentionally uses only the Python standard library.
Embeddings are random floats (for demo/testing). Replace with your real embeddings.
"""

from __future__ import annotations

import argparse
import json
import random
import string
from typing import List


def _rand_text(n_words: int) -> str:
    words: List[str] = []
    for _ in range(n_words):
        wlen = random.randint(3, 10)
        word = "".join(random.choice(string.ascii_lowercase) for _ in range(wlen))
        words.append(word)
    return " ".join(words)


def _rand_vec(dim: int) -> List[float]:
    # Small-ish floats to keep payload size reasonable in demos.
    return [round(random.uniform(-1.0, 1.0), 6) for _ in range(dim)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="Output JSONL file path")
    ap.add_argument("--count", type=int, default=200, help="Number of chunks to generate")
    ap.add_argument("--dim", type=int, default=128, help="Embedding dimension (must match schema)")
    ap.add_argument("--namespace", default="my_ns", help="Vespa document namespace")
    ap.add_argument("--doc-prefix", default="doc", help="doc_id prefix")
    ap.add_argument("--chunks-per-doc", type=int, default=20, help="How many chunks per doc_id")
    args = ap.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be > 0")
    if args.dim <= 0:
        raise SystemExit("--dim must be > 0")
    if args.chunks_per_doc <= 0:
        raise SystemExit("--chunks-per-doc must be > 0")

    with open(args.out, "w", encoding="utf-8") as f:
        for i in range(args.count):
            doc_num = i // args.chunks_per_doc
            chunk_id = f"chunk-{i}"
            doc_id = f"{args.doc_prefix}-{doc_num}"
            text = _rand_text(n_words=random.randint(8, 20))
            embedding = _rand_vec(args.dim)

            op = {
                "put": f"id:{args.namespace}:chunk::{chunk_id}",
                "fields": {
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "text": text,
                    "embedding": {"values": embedding},
                },
            }
            f.write(json.dumps(op, ensure_ascii=False) + "\n")

    print(f"Wrote {args.count} documents to {args.out} (dim={args.dim}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


