"""Tests for docker-compose RAG MCP service configuration."""

import yaml  # type: ignore[import-untyped]


class TestDockerComposeService:
    """Test docker-compose.yml RAG MCP service."""

    def test_rag_mcp_service_defined(self) -> None:
        """Test that rag-mcp service is defined in docker-compose.yml."""
        with open("/Users/abdul.rafey1/dev/Edly/sparkth/docker-compose.yml") as f:
            data = yaml.safe_load(f)

        assert "rag-mcp" in data["services"], "rag-mcp service not found in docker-compose.yml"

    def test_rag_mcp_depends_on_db(self) -> None:
        """Test that rag-mcp depends on db service."""
        with open("/Users/abdul.rafey1/dev/Edly/sparkth/docker-compose.yml") as f:
            data = yaml.safe_load(f)

        rag_mcp_service = data["services"]["rag-mcp"]
        assert "depends_on" in rag_mcp_service, "rag-mcp service has no depends_on"

        depends = rag_mcp_service["depends_on"]
        if isinstance(depends, dict):
            assert "db" in depends, "db not in rag-mcp depends_on"
        else:
            assert "db" in depends, "db not in rag-mcp depends_on"

    def test_rag_mcp_command_contains_module(self) -> None:
        """Test that rag-mcp command runs the correct module."""
        with open("/Users/abdul.rafey1/dev/Edly/sparkth/docker-compose.yml") as f:
            data = yaml.safe_load(f)

        rag_mcp_service = data["services"]["rag-mcp"]
        assert "command" in rag_mcp_service, "rag-mcp service has no command"

        command = rag_mcp_service["command"]
        assert "app.rag_mcp.main" in command, "app.rag_mcp.main not in rag-mcp command"

    def test_rag_mcp_has_database_url_env(self) -> None:
        """Test that rag-mcp has DATABASE_URL environment variable."""
        with open("/Users/abdul.rafey1/dev/Edly/sparkth/docker-compose.yml") as f:
            data = yaml.safe_load(f)

        rag_mcp_service = data["services"]["rag-mcp"]
        assert "environment" in rag_mcp_service, "rag-mcp service has no environment"

        env = rag_mcp_service["environment"]
        assert "DATABASE_URL" in env, "DATABASE_URL not in rag-mcp environment"
