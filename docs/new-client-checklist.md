# New Client Checklist (Copy/Paste)

## 1) Add toolkit to client repo

```bash
cd "/path/to/client-repo"
git submodule add <toolkit-repo-url> "XX - utils/portable-lsp-mcp-toolkit"
```

## 2) Add `.envrc` in client repo

```bash
cat > ".envrc" <<'EOF'
export PGSERVICE="client"
export PGROSERVICE="client_ai_ro"
export PGAPPNAME="zed-client"
export PGLSP_APPNAME="zed-client-lsp"
export MCP_PGAPPNAME="cursor-client-mcp"
export PGLSP_CONFIG="$PWD/postgres-language-server.jsonc"
export MCP_DEFAULT_LIMIT="50"
export MCP_MAX_LIMIT="500"
export MCP_STATEMENT_TIMEOUT_MS="30000"
EOF
```

## 3) Add service entries in `~/.pg_service.conf`

```bash
cat >> "$HOME/.pg_service.conf" <<'EOF'
[client]
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
EOF
```


## 4) Generate readonly role SQL, update `~/.pgpass`, and apply grants

```bash
bash "XX - utils/portable-lsp-mcp-toolkit/scripts/setup-readonly-role.sh" \
  --client-root "$PWD" \
  --force \
  --update-pgpass \
  --apply
```

## 5) Bootstrap repo wiring (`.cursor/mcp.json`, `postgres-language-server.jsonc`)

```bash
bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" \
  --client-root "$PWD" \
  --pgservice client \
  --pgroservice client_ai_ro \
  --force
```

## 6) Approve direnv

```bash
direnv allow
```

## 7) Configure Zed SQL LSP binary

Set this path in Zed settings:

```text
.../XX - utils/portable-lsp-mcp-toolkit/tools/lsp/run-pgls.sh
```

## 8) Smoke tests

```bash
# Confirm readonly login works
psql "service=client_ai_ro" -c "select current_user, current_database();"

# Confirm readonly behavior
psql "service=client_ai_ro" -c "create table _should_fail(id int);"
```

## 9) Rollout hygiene

```bash
cd "XX - utils/portable-lsp-mcp-toolkit"
git fetch --tags
```

Pin submodule to a release tag/commit in each client repo.

---

## Upgrading an existing client

When the toolkit submodule is updated, existing clients may need manual steps:

```bash
# 1. Update the submodule
cd "XX - utils/portable-lsp-mcp-toolkit"
git fetch origin
git checkout origin/main   # or a specific tag
cd ../..

# 2. Re-run bootstrap to update .cursor/mcp.json and postgres-language-server.jsonc
bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" \
  --client-root "$PWD" \
  --pgservice <admin_service> \
  --pgroservice <readonly_service> \
  --force

# 3. Check .envrc for missing vars (bootstrap will warn you)
#    Add any missing recommended vars from templates/.envrc.example

# 4. Re-allow direnv and restart Cursor
direnv allow
```
