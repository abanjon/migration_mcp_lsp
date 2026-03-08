# Portable LSP/MCP Toolkit

Reusable, service-first PostgreSQL tooling for:
- SQL linting/type checks in editors via Postgres Language Server (LSP)
- read-only database access for Cursor MCP tools

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

## Required local dependencies

- `direnv`
- Python 3
- `uv` (recommended)
- `postgres-language-server` binary (or configured `PGLS_BIN`)
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

## Versioning and rollout

- Tag toolkit releases as `vX.Y.Z`.
- Keep `VERSION` file aligned with release tags.
- Pin client submodules to known-good tags/commits.
- Roll out to one pilot client first, then expand.
