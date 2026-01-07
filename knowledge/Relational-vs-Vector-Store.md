### Relational DB (MySQL/Postgres) vs Vector Store (Vespa) — beginner explanation

If you’re comfortable with MySQL/Postgres, the easiest way to understand a vector store is:

- A vector store is still a **database of records**…
- but the main “query” is: **“find the most similar records to this embedding vector”**

This document explains:

1. what changes between SQL databases and vector stores  
2. what a **chunk** is in RAG  
3. how your Vespa `chunk.sd` schema works (in simple terms)

---

## 1) Mental model: mapping SQL terms to Vespa terms

| SQL (MySQL/Postgres) | Vespa | Notes |
|---|---|---|
| Database | Vespa application | Your deployed schema + settings |
| Table | Document type / schema | Here it’s `chunk` |
| Row | Document | One “chunk” record |
| Column | Field | `chunk_id`, `doc_id`, `text`, `embedding` |
| Index (B-tree, GIN) | Index / attribute / ANN index | Different indexes for different query types |
| SELECT query | Search query (YQL) | Returns “hits” (results) |
| WHERE filters | Filters on attributes | Fast if field is an attribute |
| ORDER BY | Ranking profile | Ranking = scoring + sorting |

---

## 2) What changes in how you “query” data

### SQL mindset (exact matching + joins)
In Postgres you often do:

- exact filters: `WHERE doc_id='doc-1'`
- joins: `JOIN documents ON ...`
- sorting: `ORDER BY created_at DESC`

That’s great for:
- structured data
- exact lookups
- analytics

### Vector store mindset (semantic similarity)
In a vector store, your “main query” is:

- “Given a query vector \(q\), find the **top K nearest vectors** in the database.”

This is what powers semantic search and RAG retrieval.

You still do filters (like SQL), but the ranking is primarily **vector similarity** (sometimes combined with keyword ranking).

---

## 3) What is a “chunk” in RAG?

In RAG, you don’t usually store one full PDF as one record.
You split documents into smaller pieces called **chunks**.

- **doc_id**: which original document it came from
- **chunk_id**: which piece inside that document
- **text**: the chunk text
- **embedding**: the chunk meaning as a vector (numbers)

Why chunk?
- Because a question usually needs **one paragraph / one section**, not the entire document.
- Retrieval returns the best chunks, and the LLM uses them as context.

---

## 4) The big difference: indexes and ranking

### SQL indexes
SQL indexes help with:
- `WHERE` clauses
- sorting
- range scans

### Vector indexes (ANN)
Vector search needs a special index because comparing a query vector to **millions** of stored vectors is expensive.

Most vector DBs use **ANN** (Approximate Nearest Neighbor) indexes like **HNSW**:
- fast
- “close enough” (approximate)

Vespa supports this pattern.

---

## 5) Explaining your `chunk.sd` schema (line-by-line, easy)

This is your file:

```1:40:my-vespa-app/schemas/chunk.sd
schema chunk {

  document chunk {
    field chunk_id type string {
      indexing: summary | attribute
    }
    field doc_id type string {
      indexing: summary | attribute
    }
    field text type string {
      indexing: summary | index
      index: enable-bm25
    }

    # Keep this small by default so examples are readable.
    # Change 128 to your real embedding dimension (e.g., 384/768/1536).
    field embedding type tensor<float>(x[128]) {
      indexing: attribute
      attribute {
        distance-metric: angular
        hnsw {
          max-links-per-node: 16
          neighbors-to-explore-at-insert: 200
        }
      }
    }
  }

  rank-profile vector {
    first-phase {
      expression: closeness(embedding)
    }
  }

  rank-profile hybrid inherits vector {
    first-phase {
      expression: 0.5 * bm25(text) + 0.5 * closeness(embedding)
    }
  }
}
```

### 5.1 `schema chunk` and `document chunk`
Think: **table name = chunk**, and each stored record is one **chunk** document.

### 5.2 `chunk_id` and `doc_id`
These are metadata fields, like columns in SQL.

`indexing: summary | attribute` means:

- **summary**: return this field in the search response (like selecting columns to show).
- **attribute**: store it so Vespa can filter fast (like indexing a column for WHERE).

### 5.3 `text` (keyword search column)
`indexing: summary | index` means:

- **index**: build a text index so you can do keyword search
- **summary**: return text in results

`enable-bm25` means: “allow BM25 keyword ranking on this text”.

### 5.4 `embedding` (vector column)
`tensor<float>(x[128])` is a vector of length 128.

This is like a column that stores an array of floats, but used for similarity search.

- **dimension**: 128 here (must match your embedding model output)
- **distance-metric: angular**: similar to cosine distance

`hnsw { ... }` means: “build an ANN index” so vector search is fast.

### 5.5 Ranking profiles (ORDER BY for search)

#### `rank-profile vector`
This is “vector-only ranking”:
- score = `closeness(embedding)`
- higher score = more similar

#### `rank-profile hybrid`
This is “keyword + vector ranking”:

\[
score = 0.5 \cdot bm25(text) + 0.5 \cdot closeness(embedding)
\]

It’s similar to:
- “ORDER BY combined_score DESC”

---

## 6) How a query looks (SQL vs Vespa)

### SQL example
“Give me rows where doc_id is doc-1 and text contains ‘docker’, ordered by relevance”

### Vespa idea (high level)
“Retrieve nearest vectors (semantic) + optionally combine with BM25 (keyword)”

Vespa returns **hits** (top results).  
`hits=10` means “return 10 documents”.

---

## 7) Practical advice (what to remember)

- SQL DBs are great at **exact matching and joins**.
- Vector stores are great at **similarity search** (“meaning” matching).
- RAG needs both:
  - metadata filters (like SQL WHERE)
  - vector similarity (semantic)
  - sometimes BM25 (keyword)
- Chunking quality strongly affects retrieval quality.


