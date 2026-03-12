"""
Tier 1: Unit tests for tools/lib/resolve_pg_env.py

Validates service loading, pgpass matching, and export emission
using test fixtures instead of real credential files.

Run: python -m pytest tests/test_resolve_pg_env.py -v
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

TOOLKIT_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = TOOLKIT_ROOT / "tools" / "lib" / "resolve_pg_env.py"
FIXTURES = TOOLKIT_ROOT / "tests" / "fixtures"


@pytest.fixture()
def fake_home(tmp_path: Path) -> Path:
    """Create a temporary HOME with test pg_service.conf and .pgpass."""
    service_conf = tmp_path / ".pg_service.conf"
    service_conf.write_text(
        textwrap.dedent("""\
        [test_readonly]
        host=localhost
        port=5432
        dbname=testdb
        user=test_ro_user
        sslmode=disable

        [test_admin]
        host=localhost
        port=5432
        dbname=testdb
        user=test_admin_user
        sslmode=require
        """)
    )

    pgpass = tmp_path / ".pgpass"
    pgpass.write_text(
        textwrap.dedent("""\
        localhost:5432:testdb:test_ro_user:test_ro_password
        localhost:5432:testdb:test_admin_user:test_admin_password
        """)
    )
    pgpass.chmod(0o600)

    return tmp_path


def run_resolver(
    fake_home: Path,
    service: str,
    mode: str,
    appname: str = "",
) -> dict[str, str]:
    """Run resolve_pg_env.py and parse exported variables."""
    cmd = [
        sys.executable,
        str(RESOLVER),
        "--service",
        service,
        "--mode",
        mode,
    ]
    if appname:
        cmd.extend(["--appname", appname])

    env = {**os.environ, "HOME": str(fake_home)}
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    exports: dict[str, str] = {}
    for line in result.stdout.strip().splitlines():
        if line.startswith("export "):
            key_val = line[len("export ") :]
            key, val = key_val.split("=", 1)
            # Strip shell quoting
            exports[key] = val.strip("'\"")

    return exports


class TestResolvePgEnvLSPMode:
    def test_resolves_host(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGHOST"] == "localhost"

    def test_resolves_port(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGPORT"] == "5432"

    def test_resolves_database(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGDATABASE"] == "testdb"

    def test_resolves_user(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGUSER"] == "test_ro_user"

    def test_resolves_password(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGPASSWORD"] == "test_ro_password"

    def test_resolves_sslmode(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert exports["PGSSLMODE"] == "disable"

    def test_appname_is_set(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp", appname="test-app")
        assert exports["PGAPPNAME"] == "test-app"


class TestResolvePgEnvMCPMode:
    def test_resolves_readonly_user_key(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "mcp")
        assert exports["PGROUSER"] == "test_ro_user"

    def test_resolves_readonly_password_key(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "mcp")
        assert exports["PGROPASSWORD"] == "test_ro_password"

    def test_lsp_mode_uses_pguser(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "lsp")
        assert "PGUSER" in exports
        assert "PGROUSER" not in exports

    def test_mcp_mode_uses_pgrouser(self, fake_home: Path) -> None:
        exports = run_resolver(fake_home, "test_readonly", "mcp")
        assert "PGROUSER" in exports
        assert "PGUSER" not in exports


class TestResolvePgEnvErrors:
    def test_missing_service_fails(self, fake_home: Path) -> None:
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            run_resolver(fake_home, "nonexistent_service", "lsp")
        assert exc_info.value.returncode != 0

    def test_missing_pgpass_entry_fails(self, tmp_path: Path) -> None:
        # Create service conf but no matching pgpass entry
        service_conf = tmp_path / ".pg_service.conf"
        service_conf.write_text(
            textwrap.dedent("""\
            [orphan_service]
            host=nowhere
            port=9999
            dbname=nodb
            user=nouser
            sslmode=disable
            """)
        )
        pgpass = tmp_path / ".pgpass"
        pgpass.write_text("# empty\n")
        pgpass.chmod(0o600)

        with pytest.raises(subprocess.CalledProcessError):
            run_resolver(tmp_path, "orphan_service", "lsp")

    def test_missing_service_file_fails(self, tmp_path: Path) -> None:
        # tmp_path has no .pg_service.conf at all
        pgpass = tmp_path / ".pgpass"
        pgpass.write_text("localhost:5432:db:user:pass\n")
        pgpass.chmod(0o600)

        with pytest.raises(subprocess.CalledProcessError):
            run_resolver(tmp_path, "any_service", "lsp")
