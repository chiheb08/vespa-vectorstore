### Re-ranking (simple explanation)

**Re-ranking** means:

1. First, you retrieve a **candidate set** quickly (example: top 50 chunks).
2. Then, you apply a **stronger but slower** model/scoring method to reorder those candidates (example: pick the best 5).

#### Why do we do this?
Because the best models are usually too slow/expensive to run over the whole database.

So we do:

- **Fast retrieval** for recall (“don’t miss relevant chunks”)
- **Re-rank** for precision (“put the best chunks at the top”)

#### Common re-rankers in RAG
- **Cross-encoder** (very strong): model reads *(query, chunk text)* together and outputs a relevance score.
- **LLM-as-a-judge** (possible but can be slow/costly).
- **More complex ranking features** (hybrid scoring, domain rules, freshness boost).

#### Tiny example
Query: “Why did Docker fail to build my Vespa image?”

- Retriever returns 50 chunks: some about Docker, some about chmod, some about Vespa.
- Re-ranker puts “chmod Operation not permitted” chunks at the top.

#### Quick mental model
- Retrieval answers: “Which chunks are *possibly* relevant?”
- Re-ranking answers: “Which of these chunks are *most* relevant?”

#### Key tradeoff
- Higher `candidate_count` → better chance to include the right chunk, but more re-rank cost.


