### 2025-12-16 — Vespa deploy failed: `hnsw {}` not allowed inside `attribute {}` block

---

### Symptom

`vespa-deployer` failed with:

> Failed parsing schema from `chunk.sd`: Encountered `"hnsw"` ...  
> Was expecting ... `"distance-metric"` ...

---

### Main cause

In this Vespa version, the schema parser does **not** accept:

```text
attribute {
  distance-metric: angular
  hnsw { ... }
}
```

The `hnsw {}` configuration belongs under an `index {}` block for the field.

---

### Fix

We changed `rag_app/vespa/app/schemas/chunk.sd` to:

```text
field embedding type tensor<float>(x[768]) {
  indexing: attribute | index
  attribute {
    distance-metric: angular
  }
  index {
    hnsw {
      max-links-per-node: 16
      neighbors-to-explore-at-insert: 200
    }
  }
}
```

Then redeploy by restarting the stack (which re-runs `vespa-deployer`):

```bash
cd rag_app
docker compose up -d
```



