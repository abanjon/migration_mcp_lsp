#!/usr/bin/env python3
import argparse
import shlex
from pathlib import Path


def split_pgpass_line(line: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    escape = False

    for ch in line.rstrip("\n"):
        if escape:
            buf.append(ch)
            escape = False
        elif ch == "\\":
            escape = True
        elif ch == ":":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)

    parts.append("".join(buf))
    return parts


def matches(pattern: str, value: str) -> bool:
    return pattern == "*" or pattern == value


def load_service(service_name: str) -> dict[str, str]:
    service_file = Path.home() / ".pg_service.conf"
    if not service_file.exists():
        raise SystemExit(f"Missing {service_file}")

    current_section = ""
    sections: dict[str, dict[str, str]] = {}

    for raw_line in service_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue

        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            sections.setdefault(current_section, {})
            continue

        if "=" not in line or not current_section:
            continue

        key, value = line.split("=", 1)
        sections[current_section][key.strip().lower()] = value.strip()

    if service_name not in sections:
        raise SystemExit(f"Service [{service_name}] not found in {service_file}")

    section = sections[service_name]
    return {
        "host": section.get("host", "").strip(),
        "port": section.get("port", "5432").strip(),
        "dbname": section.get("dbname", "").strip(),
        "user": section.get("user", "").strip(),
        "sslmode": section.get("sslmode", "require").strip(),
    }


def load_password(host: str, port: str, dbname: str, user: str) -> str:
    pgpass_file = Path.home() / ".pgpass"
    if not pgpass_file.exists():
        raise SystemExit(f"Missing {pgpass_file}")

    for raw_line in pgpass_file.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = split_pgpass_line(line)
        if len(parts) != 5:
            continue

        pg_host, pg_port, pg_dbname, pg_user, password = parts
        if (
            matches(pg_host, host)
            and matches(pg_port, port)
            and matches(pg_dbname, dbname)
            and matches(pg_user, user)
        ):
            return password

    raise SystemExit(
        "No matching password found in ~/.pgpass for "
        f"host={host} port={port} dbname={dbname} user={user}"
    )


def emit(exports: dict[str, str]) -> None:
    for key, value in exports.items():
        print(f"export {key}={shlex.quote(value)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve libpq service and pgpass entries into shell exports."
    )
    parser.add_argument("--service", required=True)
    parser.add_argument("--mode", required=True, choices=["lsp", "mcp"])
    parser.add_argument("--appname", default="")
    args = parser.parse_args()

    service = load_service(args.service)
    password = load_password(
        host=service["host"],
        port=service["port"],
        dbname=service["dbname"],
        user=service["user"],
    )

    if args.mode == "lsp":
        exports = {
            "PGHOST": service["host"],
            "PGPORT": service["port"],
            "PGDATABASE": service["dbname"],
            "PGUSER": service["user"],
            "PGPASSWORD": password,
            "PGSSLMODE": service["sslmode"],
        }
    else:
        exports = {
            "PGHOST": service["host"],
            "PGPORT": service["port"],
            "PGDATABASE": service["dbname"],
            "PGROUSER": service["user"],
            "PGROPASSWORD": password,
            "PGSSLMODE": service["sslmode"],
        }

    if args.appname:
        exports["PGAPPNAME"] = args.appname

    emit(exports)


if __name__ == "__main__":
    main()
