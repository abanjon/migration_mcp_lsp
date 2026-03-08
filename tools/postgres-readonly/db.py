from time import perf_counter
from typing import Any, Dict, List

import psycopg
from psycopg.rows import dict_row

from config import AppConfig


def _connect(config: AppConfig) -> psycopg.Connection:
    return psycopg.connect(
        host=config.pg_host,
        port=config.pg_port,
        dbname=config.pg_database,
        user=config.pg_user,
        password=config.pg_password,
        sslmode=config.pg_sslmode,
        autocommit=True,
        options=(
            "-c default_transaction_read_only=on "
            f"-c statement_timeout={config.statement_timeout_ms}"
        ),
        row_factory=dict_row,
    )


def run_query(
    config: AppConfig,
    sql: str,
    params: List[Any],
    limit: int,
    offset: int,
) -> Dict[str, Any]:
    wrapped_sql = f"SELECT * FROM ({sql}) AS mcp_query LIMIT %s OFFSET %s"
    wrapped_params = list(params or []) + [limit, offset]

    start = perf_counter()
    with _connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(wrapped_sql, wrapped_params)
            rows = cur.fetchall()
    elapsed_ms = round((perf_counter() - start) * 1000, 2)

    return {
        "ok": True,
        "row_count": len(rows),
        "limit": limit,
        "offset": offset,
        "elapsed_ms": elapsed_ms,
        "rows": rows,
    }


def list_tables(config: AppConfig) -> List[Dict[str, Any]]:
    sql = """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_type IN ('BASE TABLE', 'VIEW')
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    """
    with _connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            return cur.fetchall()


def get_table_columns(config: AppConfig, table_name: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position
        FROM information_schema.columns
        WHERE lower(table_name) = lower(%s)
          AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, ordinal_position
    """
    with _connect(config) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, [table_name])
            return cur.fetchall()
