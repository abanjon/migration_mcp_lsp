import os
from dataclasses import dataclass


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    pg_host: str
    pg_port: int
    pg_database: str
    pg_user: str
    pg_password: str
    pg_sslmode: str
    pg_appname: str
    default_limit: int
    max_limit: int
    statement_timeout_ms: int


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def load_config() -> AppConfig:
    appname = os.getenv("MCP_PGAPPNAME", "").strip() or os.getenv("PGAPPNAME", "").strip() or "postgres-readonly-mcp"
    return AppConfig(
        pg_host=_require_env("PGHOST"),
        pg_port=int(os.getenv("PGPORT", "5432")),
        pg_database=_require_env("PGDATABASE"),
        pg_user=_require_env("PGROUSER"),
        pg_password=_require_env("PGROPASSWORD"),
        pg_sslmode=os.getenv("PGSSLMODE", "require"),
        pg_appname=appname,
        default_limit=max(1, int(os.getenv("MCP_DEFAULT_LIMIT", "50"))),
        max_limit=max(1, int(os.getenv("MCP_MAX_LIMIT", "500"))),
        statement_timeout_ms=max(1000, int(os.getenv("MCP_STATEMENT_TIMEOUT_MS", "30000"))),
    )
