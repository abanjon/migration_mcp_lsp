from typing import List

from config import AppConfig
from db import get_foreign_keys, get_indexes, get_primary_keys, get_table_columns, list_tables


def render_tables_resource(config: AppConfig) -> str:
    rows = list_tables(config)
    if not rows:
        return "No readable tables or views found."

    lines: List[str] = ["# Readable tables", ""]
    lines.append("| schema | table | ~rows |")
    lines.append("|---|---|---|")
    for row in rows:
        est = row["row_estimate"]
        est_str = str(est) if est >= 0 else "n/a"
        lines.append(f"| {row['table_schema']} | {row['table_name']} | {est_str} |")
    lines.append("")
    lines.append(
        "_~rows is an estimate from pg_stat_user_tables. Use `search_tables` for targeted lookup on large schemas._"
    )
    return "\n".join(lines)


def render_table_resource(config: AppConfig, table_name: str) -> str:
    columns = get_table_columns(config, table_name)
    if not columns:
        return f"No readable columns found for table: {table_name}"

    schema = columns[0]["table_schema"]
    table = columns[0]["table_name"]

    pks = get_primary_keys(config, schema, table)
    fks = get_foreign_keys(config, schema, table)
    indexes = get_indexes(config, schema, table)
    pk_set = set(pks)

    lines: List[str] = [f"# {schema}.{table}", ""]

    # Columns
    lines.append("## Columns")
    lines.append("")
    lines.append("| # | column | type | nullable | pk |")
    lines.append("|---|---|---|---|---|")
    for row in columns:
        pk_marker = "YES" if row["column_name"] in pk_set else ""
        lines.append(
            f"| {row['ordinal_position']} | {row['column_name']} | "
            f"{row['data_type']} | {row['is_nullable']} | {pk_marker} |"
        )

    # Primary key summary
    lines.append("")
    if pks:
        lines.append(f"**Primary key:** {', '.join(pks)}")
    else:
        lines.append("**Primary key:** none")

    # Foreign keys
    lines.append("")
    if fks:
        lines.append("## Foreign keys")
        lines.append("")
        lines.append("| column | references |")
        lines.append("|---|---|")
        for fk in fks:
            ref = f"{fk['foreign_schema']}.{fk['foreign_table']}({fk['foreign_column']})"
            lines.append(f"| {fk['column_name']} | {ref} |")

    # Indexes
    lines.append("")
    if indexes:
        lines.append("## Indexes")
        lines.append("")
        lines.append("| index | type | unique | columns | definition |")
        lines.append("|---|---|---|---|---|")
        for idx in indexes:
            unique = "YES" if idx["is_unique"] else ""
            lines.append(
                f"| {idx['index_name']} | {idx['index_type']} | {unique} | {idx['columns']} | {idx['index_def']} |"
            )
    else:
        lines.append("**Indexes:** none")

    return "\n".join(lines)
