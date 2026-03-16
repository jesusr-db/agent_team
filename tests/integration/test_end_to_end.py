"""End-to-end integration tests for the Q&A chatbot.

These tests verify the wiring between all components:
  - Frontend API client -> Backend /chat endpoint -> RAG serving endpoint
  - Contract shapes are consistent across boundaries
  - Resource configurations reference each other correctly

All Databricks SDK calls are mocked so tests run locally.
"""

from __future__ import annotations

import os
import yaml
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.app.backend.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_serving_response():
    """Standard mock response matching the genai-to-app contract."""
    mock_response = MagicMock()
    mock_response.predictions = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Based on the documentation, the answer is X.",
                    },
                    "sources": [
                        {
                            "doc_source": "docs/guide.md",
                            "chunk_text": "The answer to this is X as described in...",
                            "relevance_score": 0.92,
                        },
                        {
                            "doc_source": "docs/reference.md",
                            "chunk_text": "Additional context about X...",
                            "relevance_score": 0.78,
                        },
                    ],
                }
            ]
        }
    ]
    return mock_response


# ---------------------------------------------------------------------------
# Resource configuration integration tests
# ---------------------------------------------------------------------------


class TestResourceConfigurations:
    """Verify that all resource YAML files are self-consistent and
    cross-reference each other correctly."""

    def test_databricks_yml_includes_all_resources(self):
        """databricks.yml includes resources/*.yml glob."""
        bundle_path = PROJECT_ROOT / "databricks.yml"
        with open(bundle_path) as f:
            bundle = yaml.safe_load(f)

        assert "include" in bundle
        assert "resources/*.yml" in bundle["include"]

    def test_all_resource_files_are_valid_yaml(self):
        """Every YAML file in resources/ parses without error."""
        resources_dir = PROJECT_ROOT / "resources"
        for yml_file in resources_dir.glob("*.yml"):
            with open(yml_file) as f:
                data = yaml.safe_load(f)
            assert data is not None, f"{yml_file.name} is empty"
            assert "resources" in data, f"{yml_file.name} missing 'resources' key"

    def test_app_resource_references_serving_endpoint(self):
        """The app resource env vars reference the correct serving endpoint name."""
        app_resource_path = PROJECT_ROOT / "resources" / "app.yml"
        with open(app_resource_path) as f:
            app_resource = yaml.safe_load(f)

        serving_path = PROJECT_ROOT / "resources" / "serving.yml"
        with open(serving_path) as f:
            serving_resource = yaml.safe_load(f)

        # Get the serving endpoint name
        serving_endpoints = serving_resource["resources"]["model_serving_endpoints"]
        endpoint_name = list(serving_endpoints.values())[0]["name"]

        # Get the app's RAG_SERVING_ENDPOINT env var
        app_config = app_resource["resources"]["apps"]
        app_env = list(app_config.values())[0]["config"]["env"]
        rag_env = next(e for e in app_env if e["name"] == "RAG_SERVING_ENDPOINT")

        assert rag_env["value"] == endpoint_name, (
            f"App RAG_SERVING_ENDPOINT ({rag_env['value']}) does not match "
            f"serving endpoint name ({endpoint_name})"
        )

    def test_app_yaml_matches_resource_config(self):
        """The app.yaml in src/app/backend/ matches the resource definition."""
        app_yaml_path = PROJECT_ROOT / "src" / "app" / "backend" / "app.yaml"
        with open(app_yaml_path) as f:
            app_yaml = yaml.safe_load(f)

        # Verify command is correct for deployed context
        assert app_yaml["command"][0] == "uvicorn"
        assert "main:app" in app_yaml["command"][1]

        # Verify env vars include RAG_SERVING_ENDPOINT
        env_names = [e["name"] for e in app_yaml["env"]]
        assert "RAG_SERVING_ENDPOINT" in env_names
        assert "CATALOG" in env_names
        assert "SCHEMA" in env_names

    def test_vector_search_index_references_ingestion_table(self):
        """The VS index source_table matches the ingestion pipeline output."""
        vs_path = PROJECT_ROOT / "resources" / "vector_search.yml"
        with open(vs_path) as f:
            vs_resource = yaml.safe_load(f)

        indexes = vs_resource["resources"]["vector_search_indexes"]
        index = list(indexes.values())[0]
        source_table = index["delta_sync_index_spec"]["source_table"]

        # Source table should be in the configured catalog.schema
        assert "doc_chunks" in source_table
        assert "${var.catalog}" in source_table
        assert "${var.schema}" in source_table

    def test_serving_endpoint_entity_uses_bundle_variables(self):
        """Serving endpoint config uses ${var.catalog} and ${var.schema}."""
        serving_path = PROJECT_ROOT / "resources" / "serving.yml"
        with open(serving_path) as f:
            serving_resource = yaml.safe_load(f)

        endpoints = serving_resource["resources"]["model_serving_endpoints"]
        endpoint = list(endpoints.values())[0]
        entity = endpoint["config"]["served_entities"][0]

        assert "${var.catalog}" in entity["entity_name"]
        assert "${var.schema}" in entity["entity_name"]

    def test_pipeline_libraries_reference_existing_files(self):
        """Pipeline notebook paths point to existing source files."""
        pipeline_path = PROJECT_ROOT / "resources" / "pipelines.yml"
        with open(pipeline_path) as f:
            pipeline_resource = yaml.safe_load(f)

        pipelines = pipeline_resource["resources"]["pipelines"]
        pipeline = list(pipelines.values())[0]

        for lib in pipeline["libraries"]:
            notebook_path = lib["notebook"]["path"]
            # Resolve relative to resources/ directory
            resolved = (PROJECT_ROOT / "resources" / notebook_path).resolve()
            assert resolved.exists(), (
                f"Pipeline notebook {notebook_path} does not exist at {resolved}"
            )


# ---------------------------------------------------------------------------
# End-to-end request flow tests
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    """Test the full request flow from frontend API shape through backend
    to the (mocked) serving endpoint and back."""

    @patch("src.app.backend.main.get_workspace_client")
    def test_full_chat_flow_matches_contract(
        self, mock_get_ws, client, mock_serving_response
    ):
        """A complete chat request/response cycle matches the genai-to-app contract."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws
        mock_ws.serving_endpoints.query.return_value = mock_serving_response

        # Send request in the contract shape
        request_payload = {
            "messages": [{"role": "user", "content": "How do I install the SDK?"}]
        }

        response = client.post("/chat", json=request_payload)

        assert response.status_code == 200
        data = response.json()

        # Validate response matches contract shape
        assert "choices" in data
        assert isinstance(data["choices"], list)
        assert len(data["choices"]) > 0

        choice = data["choices"][0]
        assert "message" in choice
        assert "role" in choice["message"]
        assert "content" in choice["message"]
        assert choice["message"]["role"] == "assistant"
        assert len(choice["message"]["content"]) > 0

        assert "sources" in choice
        assert isinstance(choice["sources"], list)
        for source in choice["sources"]:
            assert "doc_source" in source
            assert "chunk_text" in source
            assert "relevance_score" in source
            assert isinstance(source["relevance_score"], float)

    @patch("src.app.backend.main.get_workspace_client")
    def test_backend_forwards_all_messages_to_serving(
        self, mock_get_ws, client, mock_serving_response
    ):
        """Backend passes the full conversation history to the serving endpoint."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws
        mock_ws.serving_endpoints.query.return_value = mock_serving_response

        request_payload = {
            "messages": [
                {"role": "user", "content": "What is RAG?"},
                {"role": "assistant", "content": "RAG is..."},
                {"role": "user", "content": "Can you give an example?"},
            ]
        }

        response = client.post("/chat", json=request_payload)
        assert response.status_code == 200

        # Verify the serving endpoint was called with all messages
        call_kwargs = mock_ws.serving_endpoints.query.call_args.kwargs
        forwarded_payload = call_kwargs["inputs"][0]
        assert len(forwarded_payload["messages"]) == 3

    @patch("src.app.backend.main.get_workspace_client")
    def test_backend_calls_correct_serving_endpoint(
        self, mock_get_ws, client, mock_serving_response
    ):
        """Backend uses the RAG_SERVING_ENDPOINT env var (default: qa-chatbot-rag)."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws
        mock_ws.serving_endpoints.query.return_value = mock_serving_response

        client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "test"}]},
        )

        call_kwargs = mock_ws.serving_endpoints.query.call_args.kwargs
        assert call_kwargs["name"] == "qa-chatbot-rag"

    @patch("src.app.backend.main.get_workspace_client")
    def test_serving_endpoint_error_returns_502(
        self, mock_get_ws, client
    ):
        """When the serving endpoint is unreachable, backend returns 502."""
        mock_ws = MagicMock()
        mock_get_ws.return_value = mock_ws
        mock_ws.serving_endpoints.query.side_effect = ConnectionError(
            "Serving endpoint qa-chatbot-rag is not ready"
        )

        response = client.post(
            "/chat",
            json={"messages": [{"role": "user", "content": "test"}]},
        )

        assert response.status_code == 502
        assert "RAG endpoint" in response.json()["detail"]

    def test_health_endpoint_available(self, client):
        """Health endpoint responds without requiring any Databricks connection."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Contract shape consistency tests
# ---------------------------------------------------------------------------


class TestContractConsistency:
    """Verify that the contract YAML, backend Pydantic models, and
    frontend TypeScript types all describe the same shapes."""

    def test_contract_yaml_defines_expected_fields(self):
        """The genai-to-app contract YAML has the expected structure."""
        contract_path = (
            PROJECT_ROOT / ".agent-team" / "contracts" / "genai-to-app.yaml"
        )
        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        # Request schema
        req_props = contract["endpoint"]["request_schema"]["properties"]
        assert "messages" in req_props
        msg_props = req_props["messages"]["items"]["properties"]
        assert "role" in msg_props
        assert "content" in msg_props

        # Response schema
        resp_props = contract["endpoint"]["response_schema"]["properties"]
        assert "choices" in resp_props
        choice_props = resp_props["choices"]["items"]["properties"]
        assert "message" in choice_props
        assert "sources" in choice_props

    def test_backend_pydantic_models_match_contract(self):
        """Backend Pydantic models produce JSON matching the contract schema."""
        from src.app.backend.main import (
            ChatRequest,
            ChatResponse,
            Choice,
            ChoiceMessage,
            Source,
        )

        # Build a complete request
        request = ChatRequest(
            messages=[{"role": "user", "content": "test question"}]
        )
        req_data = request.model_dump()
        assert "messages" in req_data
        assert req_data["messages"][0]["role"] == "user"
        assert req_data["messages"][0]["content"] == "test question"

        # Build a complete response
        response = ChatResponse(
            choices=[
                Choice(
                    message=ChoiceMessage(role="assistant", content="answer"),
                    sources=[
                        Source(
                            doc_source="doc.md",
                            chunk_text="chunk",
                            relevance_score=0.85,
                        )
                    ],
                )
            ]
        )
        resp_data = response.model_dump()
        assert "choices" in resp_data
        choice = resp_data["choices"][0]
        assert choice["message"]["role"] == "assistant"
        assert choice["message"]["content"] == "answer"
        assert choice["sources"][0]["doc_source"] == "doc.md"
        assert choice["sources"][0]["relevance_score"] == 0.85

    def test_genai_handler_output_matches_contract(self):
        """The RAG serving handler output shape matches what the backend expects."""
        from src.genai.rag_chain import model_serving_handler
        from unittest.mock import patch, MagicMock

        # Mock the workspace client and its dependencies
        with patch("src.genai.rag_chain._get_workspace_client") as mock_ws:
            ws = MagicMock()
            mock_ws.return_value = ws

            # Mock Vector Search response
            mock_index_result = MagicMock()
            mock_index_result.result.data_array = [
                ["chunk-1", "docs/guide.md", "The answer is here.", 0, "{}", 0.95]
            ]
            mock_col = MagicMock()
            mock_col.name = "chunk_id"
            mock_cols = [mock_col]
            for col_name in ["doc_source", "chunk_text", "chunk_index", "metadata", "score"]:
                c = MagicMock()
                c.name = col_name
                mock_cols.append(c)
            mock_index_result.manifest.columns = mock_cols
            ws.vector_search_indexes.query_index.return_value = mock_index_result

            # Mock generation response
            mock_gen_response = MagicMock()
            mock_gen_response.choices = [MagicMock()]
            mock_gen_response.choices[0].message.content = "Generated answer."
            ws.serving_endpoints.query.return_value = mock_gen_response

            result = model_serving_handler(
                {"messages": [{"role": "user", "content": "test"}]}
            )

        # Validate output shape matches what backend expects
        assert "choices" in result
        assert isinstance(result["choices"], list)
        assert len(result["choices"]) > 0

        choice = result["choices"][0]
        assert "message" in choice
        assert choice["message"]["role"] == "assistant"
        assert isinstance(choice["message"]["content"], str)
        assert "sources" in choice
        assert isinstance(choice["sources"], list)

    def test_app_to_deploy_contract_artifacts_exist(self):
        """All artifacts listed in app-to-deploy contract exist on disk."""
        contract_path = (
            PROJECT_ROOT / ".agent-team" / "contracts" / "app-to-deploy.yaml"
        )
        with open(contract_path) as f:
            contract = yaml.safe_load(f)

        for artifact in contract["artifacts"]:
            artifact_path = PROJECT_ROOT / artifact["path"]
            assert artifact_path.exists(), (
                f"Contract artifact missing: {artifact['path']} "
                f"({artifact['description']})"
            )
