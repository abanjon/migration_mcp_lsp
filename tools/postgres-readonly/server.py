import logging
import sys
from typing import Any, List

from config import AppConfig, ConfigError, load_config
from db import run_query
from guards import GuardError, sanitize_and_validate_query, sanitize_pagination
from mcp.server.fastmcp import FastMCP
from resources import render_table_resource, render_tables_resource

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(message)s",
)

mcp = FastMCP("postgres-readonly")


def _load_or_exit() -> AppConfig:
    try:
        return load_config()
    except ConfigError as exc:
        logging.error("Configuration error: %s", exc)
        raise


CONFIG = _load_or_exit()


@mcp.tool(description="Run a read-only SQL query against PostgreSQL")
def query(sql: str, params: List[Any] = None, limit: int = 50, offset: int = 0) -> dict:
    try:
        safe_sql = sanitize_and_validate_query(sql)
        safe_limit, safe_offset = sanitize_pagination(
            limit=limit,
            offset=offset,
            default_limit=CONFIG.default_limit,
            max_limit=CONFIG.max_limit,
        )
        return run_query(
            config=CONFIG,
            sql=safe_sql,
            params=params or [],
            limit=safe_limit,
            offset=safe_offset,
        )
    except GuardError as exc:
        return {
            "ok": False,
            "error": {
                "code": "blocked_query",
                "message": str(exc),
            },
        }
    except Exception as exc:
        logging.exception("Query execution failed")
        return {
            "ok": False,
            "error": {
                "code": "query_failed",
                "message": str(exc),
            },
        }


@mcp.resource("schema://tables")
def schema_tables() -> str:
    return render_tables_resource(CONFIG)


@mcp.resource("schema://table/{table_name}")
def schema_table(table_name: str) -> str:
    return render_table_resource(CONFIG, table_name)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
