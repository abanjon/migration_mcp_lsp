import logging
from time import perf_counter
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row, tuple_row

from config import AppConfig
from guards import is_explain_query

logger = logging.getLogger(__name__)

# Module-level connection singleton. The stdio MCP server is single-process
# and single-threaded, so one persistent connection is correct and avoids
# per-call TCP handshake overhead.
_conn: Optional[psycopg.Connection] = None
_conn_config: Optional[AppConfig] = None


def _connect(config: AppConfig) -> psycopg.Connection:
    return psycopg.connect(
        host=config.pg_host,
        port=config.pg_port,
        dbname=config.pg_database,
        user=config.pg_user,
        password=config.pg_password,
        sslmode=config.pg_sslmode,
        autocommit=True,
        application_name=config.pg_appname,
        options=(f"-c default_transaction_read_only=on -c statement_timeout={config.statement_timeout_ms}"),
        row_factory=dict_row,
    )


def _get_conn(config: AppConfig) -> psycopg.Connection:
    """Return the singleton connection, reconnecting if it has gone away."""
    global _conn, _conn_config
    if _conn is None or _conn_config is not config:
        _conn = _connect(config)
        _conn_config = config
        return _conn
    try:
        _conn.execute("SELECT 1")
    except Exception:
        logger.warning("Connection lost, reconnecting")
        try:
            _conn.close()
        except Exception:
            pass
        _conn = _connect(config)
        _conn_config = config
    return _conn


def run_query(
    config: AppConfig,
    sql: str,
    params: List[Any],
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    conn = _get_conn(config)
    start = perf_counter()

    if is_explain_query(sql):
        # EXPLAIN must not be wrapped in a subquery; return plan as plain text.
        with conn.cursor(row_factory=tuple_row) as cur:
            cur.execute(sql, list(params or []))
            plan_rows = cur.fetchall()
        elapsed_ms = round((perf_counter() - start) * 1000, 2)
        # row[0] is a str for TEXT/YAML format but a dict/list for FORMAT JSON.
        # Cast to str so the join is always safe regardless of EXPLAIN options.
        plan_text = "\n".join(str(row[0]) for row in plan_rows)
        return {
            "ok": True,
            "explain": True,
            "elapsed_ms": elapsed_ms,
            "plan": plan_text,
        }

    wrapped_sql = f"SELECT * FROM ({sql}) AS mcp_query LIMIT %s OFFSET %s"
    wrapped_params = list(params or []) + [limit, offset]

    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(wrapped_sql, wrapped_params)
        columns = [desc.name for desc in cur.description] if cur.description else []
        raw_rows = cur.fetchall()
    elapsed_ms = round((perf_counter() - start) * 1000, 2)

    return {
        "ok": True,
        "row_count": len(raw_rows),
        "limit": limit,
        "offset": offset,
        "elapsed_ms": elapsed_ms,
        "columns": columns,
        "rows": [list(row) for row in raw_rows],
    }


def list_tables(config: AppConfig) -> List[Dict[str, Any]]:
    sql = """
        SELECT
            t.table_schema,
            t.table_name,
            COALESCE(s.n_live_tup, -1) AS row_estimate
        FROM information_schema.tables t
        LEFT JOIN pg_stat_user_tables s
               ON s.schemaname = t.table_schema
              AND s.relname = t.table_name
        WHERE t.table_type IN ('BASE TABLE', 'VIEW')
          AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY t.table_schema, t.table_name
    """
    conn = _get_conn(config)
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def find_tables(config: AppConfig, pattern: str) -> List[Dict[str, Any]]:
    """Return tables/views whose name matches a ILIKE pattern (e.g. '%order%')."""
    sql = """
        SELECT
            t.table_schema,
            t.table_name,
            COALESCE(s.n_live_tup, -1) AS row_estimate
        FROM information_schema.tables t
        LEFT JOIN pg_stat_user_tables s
               ON s.schemaname = t.table_schema
              AND s.relname = t.table_name
        WHERE t.table_type IN ('BASE TABLE', 'VIEW')
          AND t.table_schema NOT IN ('pg_catalog', 'information_schema')
          AND (t.table_name ILIKE %s OR t.table_schema || '.' || t.table_name ILIKE %s)
        ORDER BY t.table_schema, t.table_name
    """
    conn = _get_conn(config)
    with conn.cursor() as cur:
        cur.execute(sql, [pattern, pattern])
        return cur.fetchall()


def get_table_columns(config: AppConfig, table_name: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE lower(table_name) = lower(%s)
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, ordinal_position
    """
    conn = _get_conn(config)
    with conn.cursor() as cur:
        cur.execute(sql, [table_name])
        return cur.fetchall()


def get_primary_keys(config: AppConfig, schema: str, table: str) -> List[str]:
    """Return column names that form the primary key for the given table."""
    sql = """
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = %s
          AND tc.table_name = %s
        ORDER BY kcu.ordinal_position
    """
    conn = _get_conn(config)
    with conn.cursor(row_factory=tuple_row) as cur:
        cur.execute(sql, [schema, table])
        return [row[0] for row in cur.fetchall()]


def get_foreign_keys(config: AppConfig, schema: str, table: str) -> List[Dict[str, Any]]:
    """Return FK relationships for the given table."""
    sql = """
        SELECT
            kcu.column_name,
            ccu.table_schema AS foreign_schema,
            ccu.table_name   AS foreign_table,
            ccu.column_name  AS foreign_column
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON kcu.constraint_name = tc.constraint_name
         AND kcu.table_schema = tc.table_schema
         AND kcu.table_name = tc.table_name
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = %s
          AND tc.table_name = %s
        ORDER BY kcu.ordinal_position
    """
    conn = _get_conn(config)
    with conn.cursor() as cur:
        cur.execute(sql, [schema, table])
        return cur.fetchall()


def get_indexes(config: AppConfig, schema: str, table: str) -> List[Dict[str, Any]]:
    """Return indexes defined on the given table."""
    sql = """
        SELECT
            ix.relname                          AS index_name,
            am.amname                           AS index_type,
            ix.reloptions                       AS options,
            pg_get_indexdef(i.indexrelid)       AS index_def,
            i.indisunique                       AS is_unique,
            i.indisprimary                      AS is_primary,
            array_to_string(
                array_agg(a.attname ORDER BY x.ordinality), ', '
            )                                   AS columns
        FROM pg_index i
        JOIN pg_class t  ON t.oid = i.indrelid
        JOIN pg_class ix ON ix.oid = i.indexrelid
        JOIN pg_am am    ON am.oid = ix.relam
        JOIN pg_namespace n ON n.oid = t.relnamespace
        JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS x(attnum, ordinality)
          ON TRUE
        LEFT JOIN pg_attribute a
               ON a.attrelid = t.oid
              AND a.attnum = x.attnum
              AND a.attnum > 0
        WHERE n.nspname = %s
          AND t.relname = %s
        GROUP BY ix.relname, am.amname, ix.reloptions, i.indexrelid, i.indisunique, i.indisprimary
        ORDER BY i.indisprimary DESC, ix.relname
    """
    conn = _get_conn(config)
    with conn.cursor() as cur:
        cur.execute(sql, [schema, table])
        return cur.fetchall()
