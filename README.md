# Portable LSP/MCP Toolkit

Reusable, service-first PostgreSQL tooling for SQL linting (LSP) and read-only MCP access.

This toolkit is designed to be shared across client repositories via git submodule or subtree.

## Architecture

- `tools/lsp/run-pgls.sh`
  - Launches `postgres-language-server` through `direnv`.
  - Resolves `PGROSERVICE` from `~/.pg_service.conf` + `~/.pgpass`.
- `tools/postgres-readonly/run.sh`
  - Launches a local stdio MCP server with read-only SQL guards.
  - Uses `uv` when available, falls back to `python -m venv`.
- `tools/lib/resolve_pg_env.py`
  - Required adapter that converts libpq service + pgpass entries into explicit env vars.
- `scripts/bootstrap-client.sh`
  - Wires client `.envrc`, `.cursor/mcp.json`, and `postgres-language-server.jsonc`.

## Credential Model (service-first)

This toolkit does **not** require repo `.env` files.

Expected inputs:
- client repo `.envrc` exports `PGSERVICE` and `PGROSERVICE`
- `~/.pg_service.conf` defines service connection metadata
- `~/.pgpass` stores matching passwords

`resolve_pg_env.py` is intentionally required and should not be removed unless both launchers are redesigned.

## Install in a Client Repo

1. Add toolkit as submodule (recommended):
   - `git submodule add <toolkit-repo-url> "XX - utils/portable-lsp-mcp-toolkit"`
2. Run bootstrap:
   - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" --client-root "$PWD" --pgservice <admin_service> --pgroservice <readonly_service> --force`
3. Allow direnv:
   - `direnv allow`
4. Zed setup:
   - point SQL LSP binary path to `.../portable-lsp-mcp-toolkit/tools/lsp/run-pgls.sh`

## Read-only Role Bootstrap

Use the helper to generate (and optionally apply) readonly-role SQL from the client `.envrc` service names:

- Generate SQL only:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force`
- Generate SQL and update `~/.pgpass`:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force --update-pgpass`
- Generate + apply with admin service (`PGSERVICE`):
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force --apply`

What it does:
- reads `PGSERVICE` and `PGROSERVICE` via `direnv export bash`
- resolves database/admin/readonly users from `~/.pg_service.conf`
- generates SQL for role create/update + grants + default privileges
- writes SQL to `XX - utils/generated/create_readonly_role.sql` in the client repo

## Generated Client Files

- `.cursor/mcp.json` with MCP command pointing to toolkit `run.sh`
- `postgres-language-server.jsonc` extending toolkit base config
- `.envrc` managed block for service names, app names, and defaults

## Bootstrap Validation

Bootstrap checks:
- `direnv` available
- `uv` availability (warn-only by default)
- `~/.pg_service.conf` exists
- `~/.pgpass` exists
- `PGROSERVICE` can be resolved for both LSP and MCP modes

## New Client Checklist

- Create read-only DB role and grants (see `tools/postgres-readonly/sql/create_readonly_role.sql`)
- Add service entries to `~/.pg_service.conf`
- Add matching entries to `~/.pgpass`
- Bootstrap the repo
- Confirm LSP loads and MCP `query` returns rows

## Troubleshooting

- `Service [...] not found`
  - Add missing section to `~/.pg_service.conf`.
- `No matching password found in ~/.pgpass`
  - Add/update host:port:dbname:user:password entry.
- MCP fails to start
  - Ensure `direnv allow` was run and `PGROSERVICE` is exported by `.envrc`.
- LSP connection errors
  - Confirm read-only service credentials and network/TLS settings in libpq service.

## Versioning and Rollout

- Tag toolkit releases (`vX.Y.Z`) in the toolkit repo.
- Pin each client submodule to a known-good tag/commit.
- Pilot changes in one client first, then roll out to additional clients.
- Keep `VERSION` updated alongside release tags.
