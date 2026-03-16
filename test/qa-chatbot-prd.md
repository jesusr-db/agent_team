# Q&A Chatbot over Documentation — PRD

## Overview

Build an intelligent Q&A chatbot that can answer questions about a
documentation corpus. Users interact through a simple chat interface
where they type questions and receive accurate, sourced answers.

## Target Users

- Technical writers seeking information across large doc sets
- Support engineers answering customer questions
- New team members onboarding to a codebase or product

## Features

### Document Ingestion
- Load documentation from a set of Markdown/text files
- Extract and clean text content
- Chunk documents into appropriate segments for embedding
- Store chunks in a Delta table with metadata (source, position)

### RAG Pipeline
- Generate embeddings for all document chunks
- Store embeddings in Databricks Vector Search index
- Retrieve relevant chunks for user queries
- Generate answers using an LLM with retrieved context
- Include source references in responses

### Chat Interface
- Simple web-based chat UI
- Message history within a session
- Display source documents for each answer
- Loading indicators during retrieval/generation

## Data Sources

- A collection of Markdown documentation files (provided at deploy time)
- No external APIs or databases required beyond Databricks services

## Technical Constraints

- Databricks workspace with Unity Catalog enabled
- Databricks Vector Search available
- Foundation Model API or external LLM endpoint accessible
- Deploy as a Databricks App

## Success Criteria

1. Documents are ingested and chunked into a Delta table
2. Vector Search index is populated with embeddings
3. Chat UI loads and accepts user input
4. Questions receive relevant, sourced answers within 10 seconds
5. Deployed as a Databricks App accessible via workspace URL
