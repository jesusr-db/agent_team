"""Configuration constants for the RAG pipeline.

All Databricks resource references use ${var.catalog} and ${var.schema}
from databricks.yml variables.  At runtime these are resolved by the
serving endpoint environment or passed as environment variables.
"""

import os

# ---------------------------------------------------------------------------
# Unity Catalog coordinates
# ---------------------------------------------------------------------------
CATALOG = os.environ.get("CATALOG", "main")
SCHEMA = os.environ.get("SCHEMA", "qa_chatbot")

# ---------------------------------------------------------------------------
# Vector Search
# ---------------------------------------------------------------------------
VS_ENDPOINT_NAME = "qa-chatbot-vs-endpoint"
VS_INDEX_NAME = f"{CATALOG}.{SCHEMA}.doc_chunks_vs_index"

# Source Delta table that the index syncs from
CHUNKS_TABLE = f"{CATALOG}.{SCHEMA}.doc_chunks"

# Embedding model served by Databricks Foundation Model API
EMBEDDING_MODEL_ENDPOINT = "databricks-bge-large-en"
EMBEDDING_DIMENSION = 1024

# Column in doc_chunks that contains the text to embed
EMBEDDING_SOURCE_COLUMN = "chunk_text"

# Columns returned from Vector Search alongside the score
VS_COLUMNS = ["chunk_id", "doc_source", "chunk_text", "chunk_index", "metadata"]

# Retrieval parameters
TOP_K = 5
RELEVANCE_THRESHOLD = 0.5

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
GENERATION_MODEL_ENDPOINT = "databricks-meta-llama-3-1-70b-instruct"
MAX_TOKENS = 1024
TEMPERATURE = 0.1

# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------
RAG_SERVING_ENDPOINT = "qa-chatbot-rag"
