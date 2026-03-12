# Portable LSP/MCP Toolkit

Reusable, service-first PostgreSQL tooling for:
- SQL linting/type checks in editors via Postgres Language Server (LSP)
- read-only database access for Cursor MCP tools
- LSP-powered SQL intelligence (diagnostics, hover, completions) via MCP for AI agents

This is intended to be shared across client repos (usually via git submodule).

## Quick Start (new client)

Refer to docs/new-client-checklist.md for a step-by-step walkthrough of onboarding a new client repo to use this toolkit.

## How credentials work

This toolkit does **not** require project `.env` files.  
It uses:
- project `.envrc` for service names
- `~/.pg_service.conf` for connection metadata
- `~/.pgpass` for passwords

`tools/lib/resolve_pg_env.py` is the adapter that converts service entries into explicit env vars for LSP/MCP processes.

## What to put in `.envrc` (project repo)

Minimum required:

```bash
export PGSERVICE="client_admin"
export PGROSERVICE="client_ai_ro"
```

Recommended full block:

```bash
export PGSERVICE="client"
export PGROSERVICE="client_ai_ro"
export PGAPPNAME="zed-client"
export PGLSP_APPNAME="zed-client-lsp"
export MCP_PGAPPNAME="cursor-client-mcp"
export MCP_LSPINSIGHTS_APPNAME="cursor-client-lsp-insights"
export PGLSP_CONFIG="$PWD/postgres-language-server.jsonc"
export MCP_DEFAULT_LIMIT="50"
export MCP_MAX_LIMIT="500"
export MCP_STATEMENT_TIMEOUT_MS="30000"
```

Notes:
- `PGSERVICE` is used for admin/setup operations (for example applying role SQL).
- `PGROSERVICE` is used by LSP and MCP read-only paths.
- After editing `.envrc`, run `direnv allow`.

## What to put in `~/.pg_service.conf` (home dir)

Create one admin service and one readonly service per client.

Example:

```ini
[client_admin]
host=example-host.rds.amazonaws.com
port=5432
dbname=client_database
user=postgres
sslmode=require

[client_ai_ro]
host=example-host.rds.amazonaws.com
port=5432
dbname=client_database
user=client_ai_readonly
sslmode=require
```

Notes:
- Service names must exactly match `.envrc` values for `PGSERVICE` and `PGROSERVICE`.
- The readonly service user should be the readonly DB role.

## What to put in `~/.pgpass` (home dir)

Format:

`host:port:dbname:user:password`

Example matching the readonly service above:

```text
example-host.rds.amazonaws.com:5432:client_database:client_ai_readonly:your_password_here
```

You may also include an admin entry if you use `psql service=<admin_service>` without interactive password prompts.

Security:
- `~/.pgpass` must be mode `600`.
- keep it local; do not commit to git.

## Scripts and what they do

### `scripts/bootstrap-client.sh`

Purpose:
- wire a client repo for LSP + MCP quickly

What it checks:
- `direnv` exists
- `~/.pg_service.conf` exists
- `~/.pgpass` exists
- `PGROSERVICE` resolves correctly for both LSP and MCP modes
- warns if `uv` is missing (MCP can still use `python -m venv`)

What it writes/updates:
- `<client>/.cursor/mcp.json`
- `<client>/postgres-language-server.jsonc`
- does not modify `<client>/.envrc` (create this manually first)

Commands:
- dry run:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" --client-root "$PWD" --pgservice <admin_service> --pgroservice <readonly_service> --dry-run`
- apply:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" --client-root "$PWD" --pgservice <admin_service> --pgroservice <readonly_service> --force`

### `scripts/setup-readonly-role.sh`

Purpose:
- generate SQL to create/update the readonly role and grants from service config
- optionally apply it
- optionally update `~/.pgpass` for readonly user

How it resolves values:
- loads `.envrc` via `direnv export bash`
- reads `PGSERVICE` + `PGROSERVICE`
- looks both up in `~/.pg_service.conf`
- derives database, host, port, readonly username, and default owner role

What it writes:
- SQL file in client repo:
  - `<client>/XX - utils/generated/create_readonly_role.sql`

Optional effects:
- `--apply` runs SQL against `service=$PGSERVICE`
- `--update-pgpass` upserts the readonly entry in `~/.pgpass`

Commands:
- generate SQL only:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force`
- generate + apply:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force --apply`
- generate + update pgpass + apply:
  - `bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" --client-root "$PWD" --force --update-pgpass --apply`

## LSP and MCP runtime scripts

- `tools/lsp/run-pgls.sh`
  - loads project env via `direnv`
  - resolves readonly service creds via `resolve_pg_env.py`
  - launches `postgres-language-server lsp-proxy`

- `tools/postgres-readonly/run.sh`
  - loads project env via `direnv`
  - resolves readonly creds via `resolve_pg_env.py`
  - bootstraps local `.venv` with `uv` (or venv/pip fallback)
  - starts MCP server (`server.py`) over stdio

- `tools/lsp-insights/run.sh`
  - loads project env via `direnv`
  - resolves readonly creds via `resolve_pg_env.py`
  - generates a runtime `mcpls.toml` config with PG credentials
  - launches `mcpls` (LSP-to-MCP bridge) which spawns `postgres-language-server`
  - exposes LSP intelligence as MCP tools for AI agents

### LSP-Insights: supported MCP tools

`mcpls` exposes 16 MCP tools. Postgres Language Server (pgls) only implements a
subset of LSP methods, so many tools return "Method not found" (-32601). The
table below reflects tested behavior as of pgls v0.1.x / mcpls v0.3.4:

| MCP Tool | Status | Notes |
|---|---|---|
| `get_cached_diagnostics` | **Works** | Use this instead of `get_diagnostics`. Returns syntax/type errors after file is opened. |
| `get_completions` | **Works** | Returns column names (Field kind). Table name completions may require schema introspection. |
| `get_code_actions` | **Works** | Returns "Invalidate Schema Cache" action. |
| `get_server_logs` | **Works** | Returns pgls log output. |
| `get_server_messages` | **Works** | Returns pgls notification messages. |
| `get_hover` | Partial | Implemented by pgls but may return empty contents depending on cursor position and schema state. |
| `format_document` | Partial | Implemented by pgls but returns empty edits. Format is disabled in base config; enable in `postgres-language-server.base.jsonc` if desired. |
| `get_diagnostics` | No | pgls uses push-model diagnostics, not pull. Use `get_cached_diagnostics` instead. |
| `get_definition` | No | Not implemented by pgls (-32601). |
| `get_document_symbols` | No | Not implemented by pgls (-32601). |
| `get_references` | No | Not implemented by pgls (-32601). |
| `rename_symbol` | No | Not implemented by pgls (-32601). |
| `workspace_symbol_search` | No | Not implemented by pgls (-32601). |
| `prepare_call_hierarchy` | No | Not implemented by pgls (-32601). |
| `get_incoming_calls` | No | Requires `prepare_call_hierarchy`. |
| `get_outgoing_calls` | No | Requires `prepare_call_hierarchy`. |

The primary value today is **`get_cached_diagnostics`** (SQL syntax/type
validation), **`get_completions`** (column/table suggestions), and
**`get_code_actions`** (schema cache management). As pgls adds more LSP methods
upstream, they will automatically become available through mcpls without changes
to this toolkit.

## Required local dependencies

- `direnv`
- Python 3
- `uv` (recommended)
- `postgres-language-server` binary (or configured `PGLS_BIN`)
- `mcpls` binary (for LSP-Insights; install via `tools/lsp-insights/install-mcpls.sh` which downloads our patched build, or `cargo install mcpls` for upstream)
- `psql` (needed for `setup-readonly-role.sh --apply`)

## Troubleshooting

- `Service [...] not found`
  - missing entry in `~/.pg_service.conf` or service name mismatch with `.envrc`.
- `No matching password found in ~/.pgpass`
  - add/update matching readonly entry; or use `setup-readonly-role.sh --update-pgpass`.
- `.envrc is blocked`
  - run `direnv allow`.
- MCP starts but queries fail auth
  - verify readonly role password and `~/.pgpass` entry.
- LSP not connecting
  - verify Zed binary path points to toolkit `tools/lsp/run-pgls.sh`.
- LSP-Insights: `get_hover` / `get_completions` return empty
  - ensure `PGLSP_CONFIG` is set in `.envrc` and points to a valid `postgres-language-server.jsonc`.
  - pgls needs schema introspection to provide rich results; verify DB connectivity.
- LSP-Insights: "Method not found" (-32601)
  - this is expected for unimplemented pgls methods (see tool support table above).
- LSP-Insights: orphaned `postgres-language-server` processes
  - if mcpls is killed without clean shutdown, child pgls processes may become orphaned.
  - clean up with: `pkill -9 -f "postgres-language-server"`

## Versioning and rollout

- Tag toolkit releases as `vX.Y.Z`.
- Keep `VERSION` file aligned with release tags.
- Pin client submodules to known-good tags/commits.
- Roll out to one pilot client first, then expand.
