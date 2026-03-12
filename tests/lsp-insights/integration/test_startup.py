"""
Tier 2: Integration test — mcpls startup and tool listing.

Validates that mcpls starts, completes the MCP handshake, and
advertises the expected set of LSP tools.

Run: python -m pytest tests/lsp-insights/integration/test_startup.py -v
"""

from .conftest import McplsProcess, requires_all


@requires_all
class TestMcplsStartup:
    def test_initialize_succeeds(self, mcpls_server: McplsProcess) -> None:
        """mcpls should have already initialized in the fixture."""
        # If we got here, the initialize handshake succeeded
        assert mcpls_server.proc.poll() is None, "mcpls process exited unexpectedly"

    def test_tools_list_returns_tools(self, mcpls_server: McplsProcess) -> None:
        """mcpls should advertise MCP tools after initialization."""
        result = mcpls_server.send("tools/list")
        assert "error" not in result, f"tools/list failed: {result}"
        tools = result.get("result", {}).get("tools", [])
        assert len(tools) > 0, "No tools returned"

    def test_expected_tools_present(self, mcpls_server: McplsProcess) -> None:
        """Key LSP tools should be available."""
        result = mcpls_server.send("tools/list")
        tools = result.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        expected = {
            "get_diagnostics",
            "get_hover",
            "get_completions",
            "get_definition",
            "get_code_actions",
            "format_document",
        }
        missing = expected - tool_names
        assert not missing, f"Missing expected tools: {missing}. Available: {tool_names}"

    def test_server_status_tool_available(self, mcpls_server: McplsProcess) -> None:
        """The server monitoring tool should be available."""
        result = mcpls_server.send("tools/list")
        tools = result.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        assert "get_server_logs" in tool_names, f"get_server_logs tool not found. Available: {tool_names}"
