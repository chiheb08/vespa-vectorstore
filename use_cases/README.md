### RAG retrieval “bad performance” use cases (and detailed workarounds)

This folder contains practical case studies where **retrieval** (not the LLM) caused a RAG system to perform badly.

Each case includes:

- **Symptoms** (what users see)
- **Root causes** (why retrieval fails)
- **Workarounds** (what to change, step-by-step)
- **Architecture diagrams** (Mermaid)

#### Cases

- **Use case 1: Chunking caused wrong/partial retrieval**: `01-chunking-made-retrieval-bad.md`
- **Use case 2: “Duplicates” drowned out diversity (MMR/diversification)**: `02-duplicate-results-and-diversification.md`
- **Use case 3: Lexical-only or vector-only retrieval failed (hybrid + fusion)**: `03-hybrid-and-fusion-workarounds.md`
- **Use case 4: Queries were vague (query rewriting / multi-query)**: `04-query-rewriting-and-multiquery.md`


