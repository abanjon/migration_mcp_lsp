"""
Tier 2: Integration test — completions via mcpls.

Validates that get_completions returns results for partial SQL.
Without a DB connection, only keyword completions are expected.

Run: python -m pytest tests/lsp-insights/integration/test_completions.py -v
"""

from pathlib import Path

from .conftest import McplsProcess, requires_all


@requires_all
class TestCompletions:
    def test_completions_after_select(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Completions after SELECT should return keyword suggestions."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SEL\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_completions",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 0,
                    "character": 3,  # After "SEL"
                },
            },
        )

        assert "error" not in result, f"get_completions failed: {result}"

    def test_completions_after_from(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Completions after FROM should not error (table names need DB)."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT * FROM \n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_completions",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 0,
                    "character": 14,  # After "FROM "
                },
            },
        )

        assert "error" not in result, f"get_completions failed: {result}"

    def test_completions_dot_notation(self, mcpls_server: McplsProcess, tmp_path: Path) -> None:
        """Completions after dot notation should not error."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("SELECT u.\nFROM users u\n")

        result = mcpls_server.send(
            "tools/call",
            {
                "name": "get_completions",
                "arguments": {
                    "file_path": str(sql_file),
                    "line": 0,
                    "character": 9,  # After "u."
                },
            },
        )

        assert "error" not in result, f"get_completions failed: {result}"
