"""
Shared fixtures for LSP-Insights integration tests.

These tests require:
  - mcpls binary (on PATH or at tools/lsp-insights/bin/mcpls)
  - postgres-language-server binary (on PATH or PGLS_BIN)

Tests skip gracefully if dependencies are missing.
"""

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Generator

import pytest

TOOLKIT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
FIXTURES_DIR = TOOLKIT_ROOT / "tests" / "fixtures"
SQL_FIXTURES = FIXTURES_DIR / "sql"


def find_mcpls() -> str | None:
    """Find mcpls binary."""
    local_bin = TOOLKIT_ROOT / "tools" / "lsp-insights" / "bin" / "mcpls"
    if local_bin.is_file() and os.access(local_bin, os.X_OK):
        return str(local_bin)
    return shutil.which("mcpls")


def find_pgls() -> str | None:
    """Find postgres-language-server binary."""
    pgls_bin = os.environ.get("PGLS_BIN")
    if pgls_bin and os.path.isfile(pgls_bin):
        return pgls_bin

    # Check bundled installs (same logic as run-pgls.sh and run.sh)
    home = Path.home()
    bundled_aarch64 = home / "node_modules/@postgres-language-server/cli-aarch64-apple-darwin/postgres-language-server"
    bundled_wrapper = home / "node_modules/@postgres-language-server/cli/bin/postgres-language-server"

    if bundled_aarch64.is_file() and os.access(bundled_aarch64, os.X_OK):
        return str(bundled_aarch64)
    if bundled_wrapper.is_file() and os.access(bundled_wrapper, os.X_OK):
        return str(bundled_wrapper)

    return shutil.which("postgres-language-server")


MCPLS_BIN = find_mcpls()
PGLS_BIN = find_pgls()

requires_mcpls = pytest.mark.skipif(
    MCPLS_BIN is None,
    reason="mcpls binary not found",
)

requires_pgls = pytest.mark.skipif(
    PGLS_BIN is None,
    reason="postgres-language-server binary not found",
)

requires_all = pytest.mark.skipif(
    MCPLS_BIN is None or PGLS_BIN is None,
    reason="mcpls and/or postgres-language-server not found",
)


@pytest.fixture()
def mcpls_config(tmp_path: Path) -> Path:
    """Generate a minimal mcpls.toml for integration testing.

    Uses the real postgres-language-server binary but with no DB connection
    (syntax-only mode — no type checking).
    """
    assert PGLS_BIN is not None, "PGLS_BIN must be set"

    config = tmp_path / "mcpls.toml"
    config.write_text(f"""\
[workspace]

[[workspace.language_extensions]]
extensions = ["sql"]
language_id = "sql"

[[lsp_servers]]
language_id = "sql"
command = "{PGLS_BIN}"
args = ["lsp-proxy"]
file_patterns = ["**/*.sql"]

[lsp_servers.env]
# No real DB — syntax-only diagnostics
PGHOST = ""
PGPORT = ""
PGDATABASE = ""
PGUSER = ""
PGPASSWORD = ""
""")
    return config


class McplsProcess:
    """Wrapper around a running mcpls process for sending MCP messages.

    mcpls uses newline-delimited JSON for MCP stdio transport (NOT LSP's
    Content-Length framing).
    """

    def __init__(self, proc: subprocess.Popen[bytes], timeout: float = 30.0):
        self.proc = proc
        self.timeout = timeout
        self._id = 0

    def next_id(self) -> int:
        self._id += 1
        return self._id

    def send(self, method: str, params: dict | None = None) -> dict:
        """Send a JSON-RPC request and read the response."""
        msg_id = self.next_id()
        request: dict = {
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": method,
        }
        if params is not None:
            request["params"] = params

        body = json.dumps(request)

        assert self.proc.stdin is not None
        self.proc.stdin.write((body + "\n").encode())
        self.proc.stdin.flush()

        return self._read_response(msg_id)

    def send_notification(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification: dict = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            notification["params"] = params

        body = json.dumps(notification)

        assert self.proc.stdin is not None
        self.proc.stdin.write((body + "\n").encode())
        self.proc.stdin.flush()

    def _read_response(self, expected_id: int) -> dict:
        """Read a JSON-RPC response from stdout (newline-delimited JSON)."""
        assert self.proc.stdout is not None
        deadline = time.time() + self.timeout

        os.set_blocking(self.proc.stdout.fileno(), False)
        buffer = b""

        while time.time() < deadline:
            try:
                data = self.proc.stdout.read(8192)
                if data:
                    buffer += data
                    # Process complete lines
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        # Skip notifications (no "id" field)
                        if "id" in msg and msg["id"] == expected_id:
                            return msg
                elif data == b"":
                    # EOF — process closed stdout
                    if self.proc.poll() is not None:
                        raise RuntimeError(f"mcpls process exited with code {self.proc.returncode}")
            except (BlockingIOError, TypeError):
                pass
            time.sleep(0.05)

        raise TimeoutError(f"No response from mcpls within {self.timeout}s")

    def shutdown(self) -> None:
        """Gracefully shut down the mcpls process."""
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()
            self.proc.wait(timeout=5)


@pytest.fixture()
def mcpls_server(mcpls_config: Path, tmp_path: Path) -> Generator[McplsProcess, None, None]:
    """Start an mcpls process and yield a client wrapper.

    Sends the MCP initialize handshake before yielding.
    """
    assert MCPLS_BIN is not None

    proc = subprocess.Popen(
        [MCPLS_BIN, "--config", str(mcpls_config), "--log-level", "debug"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(tmp_path),
    )

    client = McplsProcess(proc)

    try:
        # MCP initialize
        result = client.send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "0.0.1"},
            },
        )
        assert "error" not in result, f"Initialize failed: {result}"

        # Send initialized notification
        client.send_notification("notifications/initialized")

        # Give LSP servers a moment to start
        time.sleep(2)

        yield client
    finally:
        client.shutdown()
