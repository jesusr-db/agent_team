"""Unit tests for the FastAPI backend.

These tests use the FastAPI test client and mock the Databricks SDK so
they can run locally without a workspace connection.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app.backend.main import app, ChatRequest, ChatResponse, Choice, ChoiceMessage, Source


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    @patch("src.app.backend.main.get_workspace_client")
    def test_basic_chat(self, mock_get_ws, client):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        # Mock serving endpoint response
        mock_response = MagicMock()
        mock_response.predictions = [
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "The answer is 42.",
                        },
                        "sources": [
                            {
                                "doc_source": "guide.md",
                                "chunk_text": "42 is the answer.",
                                "relevance_score": 0.95,
                            }
                        ],
                    }
                ]
            }
        ]
        mock_ws.serving_endpoints.query.return_value = mock_response

        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "What is the answer?"}]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) == 1
        assert data["choices"][0]["message"]["content"] == "The answer is 42."
        assert len(data["choices"][0]["sources"]) == 1

    def test_empty_messages_returns_400(self, client):
        response = client.post("/chat", json={"messages": []})
        assert response.status_code == 400

    def test_invalid_role_returns_422(self, client):
        response = client.post(
            "/chat",
            json={"messages": [{"role": "invalid", "content": "test"}]},
        )
        assert response.status_code == 422

    @patch("src.app.backend.main.get_workspace_client")
    def test_conversation_history(self, mock_get_ws, client):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        mock_response = MagicMock()
        mock_response.predictions = [
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Follow-up."},
                        "sources": [],
                    }
                ]
            }
        ]
        mock_ws.serving_endpoints.query.return_value = mock_response

        response = client.post(
            "/chat",
            json={
                "messages": [
                    {"role": "user", "content": "First question"},
                    {"role": "assistant", "content": "First answer"},
                    {"role": "user", "content": "Follow-up question"},
                ]
            },
        )

        assert response.status_code == 200
        # Verify all messages were forwarded
        call_kwargs = mock_ws.serving_endpoints.query.call_args.kwargs
        payload = call_kwargs["inputs"][0]
        assert len(payload["messages"]) == 3

    @patch("src.app.backend.main.get_workspace_client")
    def test_endpoint_error_returns_502(self, mock_get_ws, client):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws
        mock_ws.serving_endpoints.query.side_effect = Exception("Connection error")

        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "test"}]},
        )

        assert response.status_code == 502

    @patch("src.app.backend.main.get_workspace_client")
    def test_empty_predictions_fallback(self, mock_get_ws, client):
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws

        mock_response = MagicMock()
        mock_response.predictions = []
        mock_ws.serving_endpoints.query.return_value = mock_response

        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "test"}]},
        )

        assert response.status_code == 200
        data = response.json()
        assert "could not generate" in data["choices"][0]["message"]["content"].lower()


# ---------------------------------------------------------------------------
# Response model validation
# ---------------------------------------------------------------------------


class TestResponseContract:
    """Verify response models match the genai-to-app contract."""

    def test_chat_response_shape(self):
        response = ChatResponse(
            choices=[
                Choice(
                    message=ChoiceMessage(role="assistant", content="Answer."),
                    sources=[
                        Source(
                            doc_source="doc.md",
                            chunk_text="chunk",
                            relevance_score=0.8,
                        )
                    ],
                )
            ]
        )
        data = response.model_dump()
        assert isinstance(data["choices"], list)
        choice = data["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str)
        assert isinstance(choice["sources"], list)
        source = choice["sources"][0]
        assert "doc_source" in source
        assert "chunk_text" in source
        assert "relevance_score" in source

    def test_chat_request_validation(self):
        req = ChatRequest(messages=[{"role": "user", "content": "test"}])
        assert len(req.messages) == 1
        assert req.messages[0].role == "user"
