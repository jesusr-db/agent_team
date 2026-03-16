# Domain Playbook: Q&A Chatbot over Documentation

## 1. Recommended Architecture

The system follows a standard Retrieval-Augmented Generation (RAG) architecture:

```
User Question
    |
    v
[Chat UI (React/TypeScript)]
    |
    v
[FastAPI Backend]
    |
    v
[Databricks Model Serving Endpoint]
    |
    +---> [Vector Search: Retrieve relevant chunks]
    +---> [Foundation Model: Generate answer with context]
    |
    v
[Response with sources]
```

### Components

1. **Data Ingestion Pipeline** -- Databricks Streaming Delta Pipeline (SDP) that ingests raw documentation files via Auto Loader, cleans and chunks the text, and writes to a Delta table.

2. **Embedding and Indexing** -- Databricks Vector Search index on the chunks table. Uses a Databricks Foundation Model embedding endpoint (e.g., `databricks-bge-large-en`) to generate embeddings. The index syncs from the Delta table in TRIGGERED mode.

3. **RAG Serving Endpoint** -- A Databricks Model Serving endpoint that:
   - Takes a user question
   - Queries the Vector Search index for relevant chunks
   - Constructs a prompt with retrieved context
   - Calls a Foundation Model (e.g., `databricks-meta-llama-3-1-70b-instruct`) for answer generation
   - Returns the answer with source references

4. **Chat Application** -- A Databricks App with:
   - React/TypeScript frontend for the chat interface
   - FastAPI Python backend that proxies requests to the serving endpoint

## 2. Chunking Strategy

### Recommendation: Fixed-size with overlap, section-aware

- **Chunk size:** 512 tokens (approximately 2000 characters)
- **Overlap:** 64 tokens (approximately 250 characters)
- **Section awareness:** Prefer splitting at Markdown heading boundaries (`#`, `##`, `###`) when possible. If a section exceeds the chunk size, split within the section using sentence boundaries.

### Rationale

- 512 tokens balances retrieval precision (smaller chunks = more precise) with context completeness (larger chunks = more self-contained).
- Overlap ensures that content near chunk boundaries is not lost.
- Section-aware splitting preserves logical structure -- a chunk about "Installation" will not bleed into "Configuration."
- This size works well with most embedding models (which accept up to 512 tokens) and leaves room in the LLM context window for multiple retrieved chunks.

### Implementation Notes

- Use a tokenizer-aware splitter (e.g., tiktoken with `cl100k_base` encoding) to count tokens accurately.
- Preserve metadata: each chunk should carry its source document path, section heading hierarchy, and position index.
- Strip excessive whitespace and normalize formatting before chunking.

## 3. Embedding Model Recommendation

### Recommendation: `databricks-bge-large-en` (via Foundation Model API)

- **Dimensions:** 1024
- **Max tokens:** 512
- **Strengths:** Strong performance on technical text retrieval benchmarks (MTEB). Native integration with Databricks Vector Search.

### Alternatives

- `databricks-gte-large-en` -- Similar performance, 1024 dimensions
- For multilingual docs: `databricks-bge-large-en` still performs reasonably; consider multilingual models only if the corpus is predominantly non-English.

### Why Foundation Model API

- No infrastructure to manage -- the embedding endpoint is serverless.
- Direct integration with Vector Search (embedding is computed automatically when using a Delta Sync index with an embedding source column).

## 4. Retrieval Strategy

### Recommendation: Dense retrieval via Databricks Vector Search

- **Top-k:** Retrieve top 5 chunks per query
- **Score threshold:** Filter out chunks with relevance score below 0.5 (on a 0-1 scale)
- **Reranking:** Not required for V1; can add a cross-encoder reranker in future iterations

### Why Dense Over Hybrid

- Dense retrieval with a strong embedding model (BGE-large) performs well for focused documentation corpora.
- Hybrid retrieval (dense + BM25 sparse) adds complexity and is most beneficial for very large, heterogeneous corpora. For a single documentation set, dense is sufficient.
- Databricks Vector Search natively supports dense retrieval with automatic embedding sync.

### Query Expansion (Future Enhancement)

- For V1, use the raw user question as the query.
- Future: use the LLM to reformulate the question into a more retrieval-friendly form before searching.

## 5. Generation Model and Prompt Design

### Model: `databricks-meta-llama-3-1-70b-instruct` (via Foundation Model API)

Alternatively, use `databricks-dbrx-instruct` or any available foundation model endpoint.

### Prompt Template

```
You are a helpful documentation assistant. Answer the user's question based ONLY on the provided context. If the context does not contain enough information to answer the question, say "I don't have enough information to answer that question based on the available documentation."

Always cite which source document(s) your answer comes from.

Context:
{retrieved_chunks}

Question: {user_question}

Answer:
```

### Key Prompt Design Principles

1. **Grounding instruction:** Explicitly tell the model to use ONLY the provided context. This reduces hallucination.
2. **Refusal instruction:** Tell the model what to say when it cannot answer. This prevents fabricated answers.
3. **Source citation:** Require the model to reference source documents, enabling the UI to display provenance.
4. **No system-level knowledge:** The model should not draw on its training data for answers -- only the retrieved documentation.

### Token Budget

- System prompt: ~100 tokens
- Retrieved chunks (5 x 512): ~2560 tokens
- User question: ~50 tokens
- Answer generation: up to 1024 tokens
- **Total:** ~3734 tokens -- well within the 8K context window of most models

## 6. Common Pitfalls and Mitigations

### Pitfall 1: Chunk Boundaries Splitting Important Context
- **Symptom:** Answers miss critical information that spans two chunks.
- **Mitigation:** Use overlap (64 tokens). Prefer splitting at section/paragraph boundaries.

### Pitfall 2: Stale Embeddings When Docs Update
- **Symptom:** New or updated docs are not reflected in search results.
- **Mitigation:** Use TRIGGERED sync mode on the Vector Search index. Run a sync after each ingestion pipeline run. Include a pipeline step that triggers the index refresh.

### Pitfall 3: Context Window Overflow
- **Symptom:** Too many retrieved chunks exceed the model's context limit.
- **Mitigation:** Limit to top-5 chunks. Use 512-token chunks (not larger). Monitor total prompt size.

### Pitfall 4: Hallucinated Answers Not Grounded in Context
- **Symptom:** Model generates plausible but incorrect answers.
- **Mitigation:** Strong grounding instruction in the prompt. Include "say I don't know" fallback. UI can display retrieved sources alongside the answer so users can verify.

### Pitfall 5: Poor Retrieval for Ambiguous Queries
- **Symptom:** User asks vague questions, retrieval returns irrelevant chunks.
- **Mitigation (V1):** Accept this limitation; provide source references so users can evaluate. **(Future):** Add query reformulation or clarification prompts.

### Pitfall 6: Metadata Loss During Ingestion
- **Symptom:** Chunks lose their document source or section context.
- **Mitigation:** Carry metadata through the entire pipeline. Store document path, section headings, and chunk index in the Delta table.

## 7. Architecture Decision Records

### ADR-1: Delta Table as Single Source of Truth
All document chunks are stored in a Delta table. The Vector Search index syncs from this table. This means the Delta table is the authoritative store -- rebuilding the index is always possible from the table.

### ADR-2: Databricks Apps for Deployment
The chat UI is deployed as a Databricks App (FastAPI + React), not as a standalone web service. This simplifies authentication (workspace SSO), networking (no public endpoints), and operations (managed by Databricks).

### ADR-3: Serverless Foundation Models
Use Databricks Foundation Model API for both embeddings and generation. This avoids provisioning GPU clusters and simplifies the serving infrastructure.
