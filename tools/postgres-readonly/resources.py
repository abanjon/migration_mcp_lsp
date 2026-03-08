from typing import List

from config import AppConfig
from db import get_table_columns, list_tables


def render_tables_resource(config: AppConfig) -> str:
    rows = list_tables(config)
    if not rows:
        return "No readable tables or views found."

    lines: List[str] = ["# Readable tables", ""]
    for row in rows:
        lines.append(f"- {row['table_schema']}.{row['table_name']}")
    return "\n".join(lines)


def render_table_resource(config: AppConfig, table_name: str) -> str:
    rows = get_table_columns(config, table_name)
    if not rows:
        return f"No readable columns found for table: {table_name}"

    schema = rows[0]["table_schema"]
    table = rows[0]["table_name"]
    lines: List[str] = [f"# {schema}.{table}", "", "| # | column | type | nullable |", "|---|---|---|---|"]

    for row in rows:
        lines.append(
            f"| {row['ordinal_position']} | {row['column_name']} | "
            f"{row['data_type']} | {row['is_nullable']} |"
        )
    return "\n".join(lines)
