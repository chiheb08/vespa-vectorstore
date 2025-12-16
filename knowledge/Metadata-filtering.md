### Metadata filtering (simple explanation)

**Metadata filtering** means: “Only search inside a subset of documents/chunks that match some conditions.”

#### What is “metadata”?
Metadata is **extra fields** about a chunk, not the chunk text itself. Examples:

- `doc_id` (which source document it came from)
- `source` (pdf/url/wiki)
- `tenant_id` (which customer)
- `language`
- `created_at` / `updated_at`
- `page_number`
- `tags`

#### Why metadata filters matter in RAG
- **Security**: only show chunks the user is allowed to see (ACL / tenant filters).
- **Precision**: restrict search to “just this doc”, or “just English docs”.
- **Speed**: fewer candidates means faster search and better relevance.

#### Example filters
- “Search only in document `doc-123`”
- “Search only in tenant `acme`”
- “Search only in PDFs”
- “Search only in docs after 2025-01-01”

#### How it fits with vector search
Typical flow:

1. Apply metadata filter (reduce the search space).
2. Run vector/BM25 retrieval inside that filtered set.
3. Optionally re-rank.

#### Common beginner mistake
Forgetting metadata filters in a multi-user app means you can accidentally return another user’s data.


