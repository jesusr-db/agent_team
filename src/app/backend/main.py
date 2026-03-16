"""FastAPI backend for the Q&A chatbot Databricks App.

This backend proxies chat requests to the RAG serving endpoint defined in
the ``genai-to-app`` contract.  It also serves the React frontend as
static files in production.

Configuration is via environment variables (set in app.yaml):
  - RAG_SERVING_ENDPOINT: name of the Databricks model serving endpoint
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RAG_SERVING_ENDPOINT = os.environ.get("RAG_SERVING_ENDPOINT", "qa-chatbot-rag")
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Q&A Chatbot",
    description="Documentation Q&A chatbot powered by RAG on Databricks",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Workspace client (lazy singleton)
# ---------------------------------------------------------------------------
_ws: WorkspaceClient | None = None


def get_workspace_client() -> WorkspaceClient:
    global _ws
    if _ws is None:
        _ws = WorkspaceClient()
    return _ws


# ---------------------------------------------------------------------------
# Request / Response models (match genai-to-app contract)
# ---------------------------------------------------------------------------


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]


class Source(BaseModel):
    doc_source: str = ""
    chunk_text: str = ""
    relevance_score: float = 0.0


class ChoiceMessage(BaseModel):
    role: str = "assistant"
    content: str = ""


class Choice(BaseModel):
    message: ChoiceMessage
    sources: list[Source] = Field(default_factory=list)


class ChatResponse(BaseModel):
    choices: list[Choice]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Send a chat message and get a RAG-powered response.

    The request body matches the genai-to-app contract::

        {"messages": [{"role": "user", "content": "..."}]}

    The response matches::

        {"choices": [{"message": {"role": "assistant", "content": "..."},
                       "sources": [...]}]}
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages list cannot be empty")

    try:
        ws = get_workspace_client()

        # Forward to RAG serving endpoint using the contract shape
        payload = {
            "messages": [
                {"role": m.role, "content": m.content} for m in request.messages
            ]
        }

        response = ws.serving_endpoints.query(
            name=RAG_SERVING_ENDPOINT,
            inputs=[payload],
        )

        # Parse the serving endpoint response
        predictions = response.predictions
        if predictions and len(predictions) > 0:
            prediction = predictions[0]
            choices_data = prediction.get("choices", [])
        else:
            choices_data = []

        choices = []
        for choice_data in choices_data:
            msg_data = choice_data.get("message", {})
            sources_data = choice_data.get("sources", [])
            choices.append(
                Choice(
                    message=ChoiceMessage(
                        role=msg_data.get("role", "assistant"),
                        content=msg_data.get("content", ""),
                    ),
                    sources=[
                        Source(
                            doc_source=s.get("doc_source", ""),
                            chunk_text=s.get("chunk_text", ""),
                            relevance_score=s.get("relevance_score", 0.0),
                        )
                        for s in sources_data
                    ],
                )
            )

        if not choices:
            choices = [
                Choice(
                    message=ChoiceMessage(
                        content="Sorry, I could not generate an answer."
                    )
                )
            ]

        return ChatResponse(choices=choices)

    except Exception as e:
        logger.exception("Error calling RAG serving endpoint")
        raise HTTPException(
            status_code=502,
            detail=f"Error communicating with RAG endpoint: {str(e)}",
        )


# ---------------------------------------------------------------------------
# Serve frontend static files (production only)
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
