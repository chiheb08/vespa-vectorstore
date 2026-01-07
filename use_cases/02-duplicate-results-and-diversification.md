### Use case 2 — Duplicate results drowned out diversity (retrieval “looks bad”)

#### What “bad” looked like
- Top-5 retrieved chunks are basically the same paragraph repeated.
- LLM answers are repetitive, or miss a key detail that exists elsewhere.
- Increasing `top_k` doesn’t help: you just get more duplicates.

---

### Architecture (where the failure happens)

```mermaid
flowchart LR
  Q["Question"] --> R["Retriever top-50"]
  R --> D["Diversify (MMR)"]
  D --> K["Top-8 unique chunks"]
  K --> L["LLM answer"]
  style D fill:#fff6e5,stroke:#aa6b00
```

The fix is an extra step between “retrieve” and “prompt”.

---

### Root causes

#### Cause A: Overlap too large
If you use heavy overlap, many chunks share 30–50% of the same text. Vector search loves that and returns near-duplicates.

#### Cause B: Repeated boilerplate
Docs often repeat the same warning/intro/footer, and the retriever keeps selecting those chunks.

#### Cause C: One “dominant” section matches everything
Sometimes a general section (like “overview”) is semantically close to many queries and crowds out specific fixes.

---

### Workarounds (step-by-step)

#### Step 1: Reduce overlap
- If you use 20% overlap, try 10% or 0%.

#### Step 2: Add diversification (MMR)
MMR = pick chunks that are:
- relevant to the query
- **not too similar to already selected chunks**

MMR is a simple and effective workaround when duplicates dominate.

#### Step 3: Deduplicate by metadata
If you have metadata like `doc_id`, `section_id`, `page`, you can enforce rules:
- “max 2 chunks per doc”
- “max 1 chunk per section”

This often improves answers immediately.

---

### Checklist (quick)
- **If results are too similar** → reduce overlap or add MMR.
- **If results are all from one doc** → cap per doc/section.



