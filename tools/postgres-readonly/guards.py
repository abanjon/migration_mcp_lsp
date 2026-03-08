import re
from typing import Tuple


class GuardError(ValueError):
    pass


BLOCKED_KEYWORDS = (
    "insert",
    "update",
    "delete",
    "merge",
    "alter",
    "drop",
    "truncate",
    "create",
    "grant",
    "revoke",
    "copy",
    "do",
    "call",
    "execute",
    "comment",
    "security",
    "set",
    "reset",
    "vacuum",
    "analyze",
    "refresh",
    "reindex",
    "cluster",
    "attach",
    "detach",
)


def _strip_sql_comments(sql: str) -> str:
    no_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    no_line = re.sub(r"--.*?$", " ", no_block, flags=re.MULTILINE)
    return no_line


def _normalize_sql(sql: str) -> str:
    return re.sub(r"\s+", " ", _strip_sql_comments(sql)).strip()


def _is_single_statement(sql: str) -> bool:
    trimmed = sql.strip()
    if trimmed.endswith(";"):
        trimmed = trimmed[:-1].strip()
    return ";" not in trimmed


def _is_allowed_statement(sql: str) -> bool:
    lowered = sql.lstrip().lower()
    return lowered.startswith("select ") or lowered.startswith("with ")


def _contains_blocked_keyword(sql: str) -> Tuple[bool, str]:
    for keyword in BLOCKED_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", sql, flags=re.IGNORECASE):
            return True, keyword
    return False, ""


def sanitize_and_validate_query(raw_sql: str) -> str:
    if not raw_sql or not raw_sql.strip():
        raise GuardError("SQL is required")

    sql = _normalize_sql(raw_sql)
    if not sql:
        raise GuardError("SQL is empty after removing comments")

    if not _is_single_statement(sql):
        raise GuardError("Only one SQL statement is allowed")

    if not _is_allowed_statement(sql):
        raise GuardError("Only SELECT statements are allowed")

    blocked, keyword = _contains_blocked_keyword(sql)
    if blocked:
        raise GuardError(f"Blocked SQL keyword detected: {keyword}")

    return sql.rstrip(";").strip()


def sanitize_pagination(limit: int, offset: int, default_limit: int, max_limit: int) -> Tuple[int, int]:
    if limit is None:
        limit = default_limit
    if offset is None:
        offset = 0

    safe_limit = max(1, min(int(limit), int(max_limit)))
    safe_offset = max(0, int(offset))
    return safe_limit, safe_offset
