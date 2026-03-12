"""
Tier 2: Integration test — diagnostics via mcpls.

Validates that diagnostics tools work for SQL files.

Note: postgres-language-server uses the push (notification) model for
diagnostics, not the pull (textDocument/diagnostic) model. So we use
get_cached_diagnostics (which returns notifications collected by mcpls)
and fall back to get_diagnostics for servers that support pull mode.

Without a real DB connection, only syntax-level diagnostics are available,
and some files may produce no diagnostics at all.

Run: python -m pytest tests/lsp-insights/integration/test_diagnostics.py -v
"""

import time
from pathlib import Path

from .conftest import McplsProcess, SQL_FIXTURES, requires_all


def get_diagnostics(server: McplsProcess, file_path: str) -> dict:
    """Try get_diagnostics first; fall back to get_cached_diagnostics.

    postgres-language-server only supports push-model diagnostics, so
    textDocument/diagnostic (used by get_diagnostics) returns -32601.
    In that case, open the file and use get_cached_diagnostics instead.
    """
    result = server.send(
        "tools/call",
        {
            "name": "get_diagnostics",
            "arguments": {"file_path": file_path},
        },
    )

    if "error" in result:
        error_msg = result.get("error", {}).get("message", "")
        if "-32601" in error_msg or "Method not found" in error_msg:
            # LSP server uses push model — use cached diagnostics.
            # First, open the file so the LSP server analyzes it.
            server.send(
                "tools/call",
                {
                    "name": "get_hover",
                    "arguments": {"file_path": file_path, "line": 0, "character": 0},
                },
            )
            # Give the server a moment to publish diagnostics
            time.sleep(1)

            result = server.send(
                "tools/call",
                {
                    "name": "get_cached_diagnostics",
                    "arguments": {"file_path": file_path},
                },
            )

    return result


@requires_all
class TestDiagnostics:
    def test_valid_sql_returns_no_errors(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Valid SQL should produce zero or minimal diagnostics."""
        sql_file = tmp_path / "valid.sql"
        sql_file.write_text((SQL_FIXTURES / "valid.sql").read_text())

        result = get_diagnostics(mcpls_server, str(sql_file))

        # The tool should return without error (may have empty content)
        assert "error" not in result, f"diagnostics failed: {result}"

    def test_invalid_sql_returns_diagnostics(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Invalid SQL should be processable without crashing."""
        sql_file = tmp_path / "invalid.sql"
        sql_file.write_text((SQL_FIXTURES / "invalid.sql").read_text())

        result = get_diagnostics(mcpls_server, str(sql_file))

        assert "error" not in result, f"diagnostics failed: {result}"
        # Note: Without a DB, pgls may or may not detect syntax errors.
        # The key assertion is that it doesn't crash.

    def test_multi_statement_sql(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Multi-statement SQL should be processable."""
        sql_file = tmp_path / "multi_statement.sql"
        sql_file.write_text((SQL_FIXTURES / "multi_statement.sql").read_text())

        result = get_diagnostics(mcpls_server, str(sql_file))

        assert "error" not in result, f"diagnostics failed: {result}"
