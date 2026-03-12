import logging
import sys
from typing import Any, List

from config import AppConfig, ConfigError, load_config
from db import find_tables, run_query
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

_QUERY_DESCRIPTION = """\
Run a read-only SQL query against PostgreSQL.

Parameters
----------
sql : str
    A single SELECT, WITH, or EXPLAIN statement. Multi-statement input is
    rejected. Trailing semicolons are stripped automatically.
params : list, optional
    Positional bind parameters using psycopg3 pyformat style (%s placeholders).
    Example: sql="SELECT * FROM orders WHERE id = %s", params=[42]
    Pass values here instead of interpolating them into the SQL string
    to avoid injection risks and improve plan caching.
    Note: $1/$2 PostgreSQL-style placeholders are NOT supported here.
limit : int, default 50
    Maximum rows to return (server cap: MCP_MAX_LIMIT, default 500). Use
    pagination to walk large result sets.
offset : int, default 0
    Row offset for pagination. Combine with limit to page through results.

Response format
---------------
Success (regular query):
  { "ok": true, "columns": ["col1", …], "rows": [[v1, …], …],
    "row_count": N, "limit": L, "offset": O, "elapsed_ms": T }

Success (EXPLAIN):
  { "ok": true, "explain": true, "plan": "<plan text>", "elapsed_ms": T }

Error:
  { "ok": false, "error": { "code": "blocked_query"|"query_failed", "message": "…" } }

Notes
-----
- Regular queries are automatically wrapped as:
    SELECT * FROM (<your sql>) AS mcp_query LIMIT <limit> OFFSET <offset>
  This means ORDER BY in the outer query is not possible; sort inside your CTE
  or subquery instead.
- EXPLAIN is NOT wrapped — it is sent as-is and the plan text is returned.
- EXPLAIN ANALYZE is blocked (it executes the query).
- Mutation keywords (INSERT, UPDATE, DELETE, DROP, etc.) are blocked.
- Use `search_tables` to find table names before querying unknown schemas.
- Use `schema://table/{table_name}` to inspect columns, PK, and FK before
  writing JOINs or WHERE clauses referencing unfamiliar tables.
"""

_SEARCH_TABLES_DESCRIPTION = """\
Search for tables and views by name pattern.

Use this instead of `schema://tables` when you know part of a table name or
want to narrow down candidates without listing every table in the schema.

Parameters
----------
pattern : str
    A case-insensitive ILIKE pattern matched against both the bare table name
    and the fully-qualified `schema.table` form. Use SQL wildcards:
      %  matches any sequence of characters
      _  matches any single character
    Examples: '%order%', 'public.inv%', 'line_item'

Response
--------
List of { "table_schema": str, "table_name": str, "row_estimate": int }
row_estimate comes from pg_stat_user_tables.n_live_tup; -1 means no stats yet
(e.g. table has never been vacuumed/analyzed or is a view).
"""


@mcp.tool(description=_QUERY_DESCRIPTION)
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


@mcp.tool(description=_SEARCH_TABLES_DESCRIPTION)
def search_tables(pattern: str) -> dict:
    try:
        rows = find_tables(CONFIG, pattern)
        return {
            "ok": True,
            "count": len(rows),
            "tables": [
                {
                    "schema": r["table_schema"],
                    "table": r["table_name"],
                    "row_estimate": r["row_estimate"],
                }
                for r in rows
            ],
        }
    except Exception as exc:
        logging.exception("search_tables failed")
        return {
            "ok": False,
            "error": {
                "code": "search_failed",
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
