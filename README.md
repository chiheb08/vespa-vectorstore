### Vespa Vector Store (Tutorial + Example App)

This repository is a small, practical “Vespa as a vector store” starter:

- **Beginner guide (start here)**: `VESPA_VECTOR_STORE_BEGINNER_GUIDE.md`
- **Tutorial (more detailed)**: `VESPA_VECTOR_STORE_TUTORIAL.md`
- **Example Vespa app package**: `my-vespa-app/`
- **Sample scripts**:
  - `scripts/generate_feed.py` generates JSONL “chunk” documents (with random embeddings) you can feed into Vespa
  - `scripts/query_examples.sh` contains copy/paste `curl` examples for vector search + delete

---

### Quick start (local)

#### 1) Start Vespa (Docker)

```bash
docker run --detach --name vespa --hostname vespa \
  --publish 8080:8080 --publish 19071:19071 \
  vespaengine/vespa
```

#### 2) Deploy the app package

Install Vespa CLI (macOS):

```bash
brew install vespa-cli
```

Point the CLI to the local container:

```bash
vespa config set target local
```

Deploy:

```bash
vespa deploy --wait 300 ./my-vespa-app
```

#### 3) Generate and feed sample chunks

Generate a feed file (example uses 128-d vectors; change to match your schema dimension):

```bash
python3 scripts/generate_feed.py --out feed.jsonl --count 200 --dim 128 --namespace my_ns
```

Feed it:

```bash
vespa feed feed.jsonl
```

#### 4) Query

Run the examples:

```bash
bash scripts/query_examples.sh
```

---

### Important note about vector dimension

The schema in `my-vespa-app/schemas/chunk.sd` defines the embedding dimension (default: **128** here to keep examples short).

If your real embeddings are 384/768/1536, update:

- `tensor<float>(x[128])` → `tensor<float>(x[YOUR_DIM])`
- the query vectors and the feed generator `--dim`


