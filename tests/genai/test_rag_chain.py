"""Unit tests for the RAG chain module.

These tests mock external dependencies (Databricks SDK) so they can run
locally without a Databricks workspace connection.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.genai.rag_chain import (
    answer_question,
    format_context,
    model_serving_handler,
)


# ---------------------------------------------------------------------------
# format_context
# ---------------------------------------------------------------------------


class TestFormatContext:
    def test_empty_chunks_returns_fallback(self):
        result = format_context([])
        assert "No relevant documentation" in result

    def test_single_chunk(self):
        chunks = [
            {
                "doc_source": "/docs/install.md",
                "chunk_text": "Run pip install.",
                "relevance_score": 0.9,
            }
        ]
        result = format_context(chunks)
        assert "[1]" in result
        assert "/docs/install.md" in result
        assert "Run pip install." in result

    def test_multiple_chunks_numbered(self):
        chunks = [
            {"doc_source": "a.md", "chunk_text": "AAA", "relevance_score": 0.9},
            {"doc_source": "b.md", "chunk_text": "BBB", "relevance_score": 0.8},
            {"doc_source": "c.md", "chunk_text": "CCC", "relevance_score": 0.7},
        ]
        result = format_context(chunks)
        assert "[1]" in result
        assert "[2]" in result
        assert "[3]" in result

    def test_missing_fields_handled(self):
        chunks = [{"relevance_score": 0.5}]
        result = format_context(chunks)
        assert "[1]" in result
        assert "unknown" in result


# ---------------------------------------------------------------------------
# model_serving_handler
# ---------------------------------------------------------------------------


class TestModelServingHandler:
    @patch("src.genai.rag_chain.answer_question")
    def test_basic_request(self, mock_answer):
        mock_answer.return_value = {
            "answer": "The answer is 42.",
            "sources": [
                {
                    "doc_source": "guide.md",
                    "chunk_text": "42 is the answer.",
                    "relevance_score": 0.95,
                }
            ],
        }

        request = {"messages": [{"role": "user", "content": "What is the answer?"}]}
        response = model_serving_handler(request)

        assert "choices" in response
        assert len(response["choices"]) == 1
        choice = response["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == "The answer is 42."
        assert len(choice["sources"]) == 1
        assert choice["sources"][0]["doc_source"] == "guide.md"

    @patch("src.genai.rag_chain.answer_question")
    def test_conversation_history(self, mock_answer):
        mock_answer.return_value = {"answer": "Follow-up answer.", "sources": []}

        request = {
            "messages": [
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
                {"role": "user", "content": "Follow-up question"},
            ]
        }
        model_serving_handler(request)

        call_args = mock_answer.call_args
        assert call_args.args[0] == "Follow-up question"
        history = call_args.kwargs.get("conversation_history")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["role"] == "assistant"

    def test_empty_messages(self):
        response = model_serving_handler({"messages": []})
        assert "No question provided" in response["choices"][0]["message"]["content"]

    def test_no_messages_key(self):
        response = model_serving_handler({})
        assert "No question provided" in response["choices"][0]["message"]["content"]

    @patch("src.genai.rag_chain.answer_question")
    def test_response_matches_contract_shape(self, mock_answer):
        """Verify the response matches the genai-to-app contract schema."""
        mock_answer.return_value = {
            "answer": "Test.",
            "sources": [
                {
                    "doc_source": "doc.md",
                    "chunk_text": "chunk",
                    "relevance_score": 0.8,
                }
            ],
        }

        request = {"messages": [{"role": "user", "content": "test"}]}
        response = model_serving_handler(request)

        # Top-level: choices array
        assert isinstance(response["choices"], list)
        choice = response["choices"][0]

        # choice.message
        assert "message" in choice
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str)

        # choice.sources
        assert "sources" in choice
        source = choice["sources"][0]
        assert "doc_source" in source
        assert "chunk_text" in source
        assert "relevance_score" in source
        assert isinstance(source["relevance_score"], float)


# ---------------------------------------------------------------------------
# answer_question (integration-level with mocks)
# ---------------------------------------------------------------------------


class TestAnswerQuestion:
    @patch("src.genai.rag_chain.generate_answer")
    @patch("src.genai.rag_chain.retrieve_chunks")
    def test_end_to_end(self, mock_retrieve, mock_generate):
        mock_retrieve.return_value = [
            {
                "chunk_id": "abc",
                "doc_source": "readme.md",
                "chunk_text": "Install with pip.",
                "chunk_index": 0,
                "metadata": "{}",
                "relevance_score": 0.92,
            }
        ]
        mock_generate.return_value = "You can install with pip. (Source: readme.md)"

        result = answer_question("How do I install?")

        assert "answer" in result
        assert "sources" in result
        assert result["answer"] == "You can install with pip. (Source: readme.md)"
        assert len(result["sources"]) == 1
        assert result["sources"][0]["doc_source"] == "readme.md"

    @patch("src.genai.rag_chain.generate_answer")
    @patch("src.genai.rag_chain.retrieve_chunks")
    def test_no_chunks_found(self, mock_retrieve, mock_generate):
        mock_retrieve.return_value = []
        mock_generate.return_value = (
            "I don't have enough information to answer that question."
        )

        result = answer_question("What is quantum gravity?")

        assert result["sources"] == []
        mock_generate.assert_called_once()

    @patch("src.genai.rag_chain.generate_answer")
    @patch("src.genai.rag_chain.retrieve_chunks")
    def test_history_passed_through(self, mock_retrieve, mock_generate):
        mock_retrieve.return_value = []
        mock_generate.return_value = "Answer."

        history = [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"},
        ]
        answer_question("Follow-up", conversation_history=history)

        call_kwargs = mock_generate.call_args.kwargs
        assert call_kwargs["conversation_history"] == history


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    def test_prompt_file_exists(self):
        from pathlib import Path

        prompt_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "genai"
            / "prompts"
            / "system_prompt.txt"
        )
        assert prompt_path.exists(), f"Prompt template not found at {prompt_path}"

    def test_prompt_has_placeholders(self):
        from pathlib import Path

        prompt_path = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "genai"
            / "prompts"
            / "system_prompt.txt"
        )
        content = prompt_path.read_text()
        assert "{retrieved_chunks}" in content
        assert "{user_question}" in content
