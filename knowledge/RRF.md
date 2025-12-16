### RRF (Reciprocal Rank Fusion) — simple explanation

**RRF** is a simple way to **merge** multiple ranked lists into one ranked list.

#### The idea (in one sentence)
If an item appears near the top of **any** list, RRF gives it a good combined score.

#### Why RRF is used in RAG
In RAG, you often have multiple “retrievers”, for example:

- **BM25 results** (keyword search)
- **Vector results** (semantic similarity)

Each retriever produces a ranked list (top N chunks). RRF fuses them so you get one final list.

#### How the score works (intuitively)
RRF uses the **rank position** (1st, 2nd, 3rd…) not the original “raw score”.

- Being rank #1 is great.
- Being rank #50 is much less useful.

So RRF rewards items that consistently rank highly across lists.

#### A super simple formula (optional)
You don’t need to memorize this, but it helps you understand the behavior:

\[
\text{RRF}(d) = \sum_{i} \frac{1}{k + \text{rank}_i(d)}
\]

- \(d\) is a chunk/document
- \(i\) is the retriever (BM25, vector, etc.)
- `rank_i(d)` is 1 for first place, 2 for second place…
- \(k\) is a constant (often ~60) that controls how quickly the score drops

#### What RRF is good at
- Very easy to implement.
- Works even when one system’s scores are not comparable to another’s.
- Often improves recall: you don’t miss good results that one retriever finds.

#### Tiny example
You retrieve chunks using:

- BM25 top-5: [A, B, C, D, E]
- Vector top-5: [C, F, G, A, H]

RRF will likely rank **A** and **C** higher because they appear in both lists near the top.

Even if **A** is not #1 in either list, being “pretty high” in both lists usually beats being #1 in only one list.


