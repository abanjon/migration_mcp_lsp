"""
Tier 2: Integration test — hover via mcpls.

Validates that get_hover returns information for SQL keywords.
Without a DB connection, hover results will be keyword/syntax-based only.

Run: python -m pytest tests/lsp-insights/integration/test_hover.py -v
"""

from pathlib import Path

from .conftest import McplsProcess, requires_all


@requires_all
class TestHover:
    def test_hover_on_keyword(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Hovering over a SQL keyword should not error."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM users;\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_hover",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 0,
                    "character": 0,  # "SELECT" keyword
                },
            },
        )

        # Should not error — may return empty content without DB
        assert "error" not in result, f"get_hover failed: {result}"

    def test_hover_on_table_name(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Hovering over a table name should not error (may be empty without DB)."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM users;\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_hover",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 0,
                    "character": 14,  # "users" table
                },
            },
        )

        assert "error" not in result, f"get_hover failed: {result}"
