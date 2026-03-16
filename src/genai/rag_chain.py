"""RAG chain for the Q&A documentation chatbot.

This module implements the core retrieve-then-generate pipeline:

1. Accept a user question (and optional conversation history).
2. Query Databricks Vector Search for the most relevant document chunks.
3. Assemble a prompt with the retrieved context.
4. Call a Foundation Model endpoint for answer generation.
5. Return the answer together with source references.

The public entry point is :func:`answer_question`, which is called by the
model serving endpoint wrapper registered in ``resources/serving.yml``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

from src.genai.config import (
    EMBEDDING_MODEL_ENDPOINT,
    EMBEDDING_SOURCE_COLUMN,
    GENERATION_MODEL_ENDPOINT,
    MAX_TOKENS,
    RELEVANCE_THRESHOLD,
    TEMPERATURE,
    TOP_K,
    VS_COLUMNS,
    VS_ENDPOINT_NAME,
    VS_INDEX_NAME,
)

# ---------------------------------------------------------------------------
# Prompt loading
# ---------------------------------------------------------------------------
_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
_SYSTEM_PROMPT_TEMPLATE: str | None = None


def _load_system_prompt() -> str:
    """Load and cache the system prompt template from disk."""
    global _SYSTEM_PROMPT_TEMPLATE
    if _SYSTEM_PROMPT_TEMPLATE is None:
        _SYSTEM_PROMPT_TEMPLATE = (_PROMPT_DIR / "system_prompt.txt").read_text()
    return _SYSTEM_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Workspace client (lazy singleton)
# ---------------------------------------------------------------------------
_ws: WorkspaceClient | None = None


def _get_workspace_client() -> WorkspaceClient:
    global _ws
    if _ws is None:
        _ws = WorkspaceClient()
    return _ws


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------


def retrieve_chunks(
    question: str,
    *,
    top_k: int = TOP_K,
    threshold: float = RELEVANCE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Query Vector Search for the most relevant document chunks.

    Parameters
    ----------
    question:
        The user's natural-language question.
    top_k:
        Maximum number of chunks to retrieve.
    threshold:
        Minimum relevance score (0-1).  Chunks below this are filtered out.

    Returns
    -------
    list[dict]
        Each dict contains the Vector Search columns plus a ``relevance_score``.
    """
    ws = _get_workspace_client()
    index = ws.vector_search_indexes.query_index(
        index_name=VS_INDEX_NAME,
        columns=VS_COLUMNS,
        query_text=question,
        num_results=top_k,
    )

    results: list[dict[str, Any]] = []
    if index.result and index.result.data_array:
        column_names = [col.name for col in index.manifest.columns]
        for row in index.result.data_array:
            record = dict(zip(column_names, row))
            score = record.get("score", 0.0)
            if score >= threshold:
                record["relevance_score"] = score
                results.append(record)

    return results


# ---------------------------------------------------------------------------
# Context formatting
# ---------------------------------------------------------------------------


def format_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks into a string suitable for the prompt.

    Each chunk is rendered as a numbered block with its source path so the
    model can cite sources in its answer.
    """
    if not chunks:
        return "(No relevant documentation found.)"

    parts: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        source = chunk.get("doc_source", "unknown")
        text = chunk.get("chunk_text", "")
        parts.append(f"[{i}] Source: {source}\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------


def generate_answer(
    question: str,
    context: str,
    *,
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Call the Foundation Model to generate an answer.

    Parameters
    ----------
    question:
        The user's question.
    context:
        Formatted context string from :func:`format_context`.
    conversation_history:
        Optional prior turns ``[{"role": ..., "content": ...}, ...]``.

    Returns
    -------
    str
        The model's generated answer text.
    """
    ws = _get_workspace_client()

    system_prompt = _load_system_prompt().format(
        retrieved_chunks=context,
        user_question=question,
    )

    messages: list[ChatMessage] = [
        ChatMessage(role=ChatMessageRole.SYSTEM, content=system_prompt),
    ]

    # Append conversation history if provided
    if conversation_history:
        for turn in conversation_history:
            role = (
                ChatMessageRole.ASSISTANT
                if turn.get("role") == "assistant"
                else ChatMessageRole.USER
            )
            messages.append(ChatMessage(role=role, content=turn["content"]))

    # Current question
    messages.append(ChatMessage(role=ChatMessageRole.USER, content=question))

    response = ws.serving_endpoints.query(
        name=GENERATION_MODEL_ENDPOINT,
        messages=messages,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )

    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def answer_question(
    question: str,
    *,
    conversation_history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """End-to-end RAG: retrieve context, generate answer, return with sources.

    This function is called by the model serving endpoint.

    Parameters
    ----------
    question:
        The user's question.
    conversation_history:
        Optional list of prior conversation turns.

    Returns
    -------
    dict
        ``{"answer": str, "sources": [{"doc_source": ..., "chunk_text": ...,
        "relevance_score": ...}]}``
    """
    chunks = retrieve_chunks(question)
    context = format_context(chunks)
    answer = generate_answer(
        question, context, conversation_history=conversation_history
    )

    sources = [
        {
            "doc_source": c.get("doc_source", ""),
            "chunk_text": c.get("chunk_text", ""),
            "relevance_score": c.get("relevance_score", 0.0),
        }
        for c in chunks
    ]

    return {"answer": answer, "sources": sources}


# ---------------------------------------------------------------------------
# Serving endpoint handler
# ---------------------------------------------------------------------------


def model_serving_handler(request: dict[str, Any]) -> dict[str, Any]:
    """Handler function for the Databricks Model Serving endpoint.

    Expects the ``genai-to-app`` contract request shape::

        {"messages": [{"role": "user", "content": "..."}]}

    Returns the contract response shape::

        {"choices": [{"message": {"role": "assistant", "content": "..."},
                       "sources": [...]}]}
    """
    messages = request.get("messages", [])
    if not messages:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "No question provided.",
                    },
                    "sources": [],
                }
            ]
        }

    # The last user message is the question; prior messages are history
    question = messages[-1].get("content", "")
    history = [
        {"role": m["role"], "content": m["content"]}
        for m in messages[:-1]
        if m.get("role") in ("user", "assistant")
    ]

    result = answer_question(question, conversation_history=history or None)

    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": result["answer"],
                },
                "sources": result["sources"],
            }
        ]
    }
