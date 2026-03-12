"""
Tier 2: Integration test — graceful degradation.

Validates that mcpls handles edge cases gracefully:
  - Non-existent files
  - Empty files
  - Non-SQL files
  - Out-of-range positions

Run: python -m pytest tests/lsp-insights/integration/test_degradation.py -v
"""

from pathlib import Path

from .conftest import McplsProcess, requires_all


@requires_all
class TestGracefulDegradation:
    def test_nonexistent_file(self, mcpls_server: McplsProcess) -> None:
        """Requesting diagnostics for a nonexistent file should not crash."""
        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_diagnostics",
                "arguments": {"file_path": "/nonexistent/path/fake.sql"},
            },
        )
        # Should return a result (possibly with an error message in content)
        # but should NOT crash the server
        assert mcpls_server.proc.poll() is None, "mcpls crashed on nonexistent file"

    def test_empty_file(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """An empty SQL file should return without error."""
        sql_file = tmp_path / "empty.sql"
        sql_file.write_text("")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_diagnostics",
                "arguments": {"file_path": str(sql_file)},
            },
        )

        assert mcpls_server.proc.poll() is None, "mcpls crashed on empty file"

    def test_non_sql_file(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """A non-SQL file should be handled gracefully."""
        py_file = tmp_path / "test.py"
        py_file.write_text("print('hello')\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_diagnostics",
                "arguments": {"file_path": str(py_file)},
            },
        )

        assert mcpls_server.proc.poll() is None, "mcpls crashed on non-SQL file"

    def test_hover_out_of_range(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Hovering at an out-of-range position should not crash."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT 1;\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_hover",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 999,
                    "character": 999,
                },
            },
        )

        assert mcpls_server.proc.poll() is None, "mcpls crashed on out-of-range hover"

    def test_server_survives_multiple_requests(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Send multiple requests in sequence; server should stay alive."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM users;\n")

        for _ in range(5):
            result = mcpls_server.send(
                "tools/call",
                {
                    "name": "get_hover",
                    "arguments": {"file_path": str(sql_file), "line": 0, "character": 0},
                },
            )
            assert mcpls_server.proc.poll() is None, "mcpls died mid-sequence"
