# Updating an Existing Client

Run these steps whenever the toolkit has been updated (new features, rule changes, security fixes).

---

## 1) Update the toolkit submodule

The toolkit lives inside each client repo as a git submodule.

### Pull the latest commit on the tracked branch

```bash
cd "/path/to/client-repo"
git submodule update --remote --merge "XX - utils/portable-lsp-mcp-toolkit"
```

`--remote` fetches from the submodule's upstream and moves the pointer to the latest commit on its tracking branch (usually `main`).

### Clear the Python bytecode cache

Always do this after a submodule update. `git submodule update` resets file timestamps, which can cause Python to use stale `.pyc` files and the MCP server to appear unchanged to Cursor.

```bash
rm -rf "XX - utils/portable-lsp-mcp-toolkit/tools/postgres-readonly/__pycache__"
```

### Or pin to a specific tag or commit

```bash
cd "/path/to/client-repo/XX - utils/portable-lsp-mcp-toolkit"
git fetch --tags
git checkout v1.2.0   # replace with the desired tag or commit SHA
cd ../..
```

### Commit the updated submodule pointer

```bash
git add "XX - utils/portable-lsp-mcp-toolkit"
git commit -m "chore: update portable-lsp-mcp-toolkit to v1.2.0"
```

---

## 2) Re-run bootstrap

The bootstrap script copies Cursor rule templates, wires `.cursor/mcp.json`, and regenerates `postgres-language-server.jsonc`. Re-running it picks up any new or changed files from the updated toolkit.

```bash
bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" \
  --client-root "$PWD" \
  --pgservice <admin_service> \
  --pgroservice <readonly_service> \
  --force
```

`--force` overwrites existing generated files including `.cursor/rules/*.mdc`. If you have made **local edits** to any rule files, diff them first:

```bash
diff ".cursor/rules/" \
     "XX - utils/portable-lsp-mcp-toolkit/templates/.cursor/rules/"
```

Then cherry-pick any rules you want to keep before re-running with `--force`.

---

## 3) Check for new or changed env vars

```bash
diff .envrc \
     "XX - utils/portable-lsp-mcp-toolkit/templates/.envrc.example"
```

The bootstrap will warn about any missing recommended vars. Add them to `.envrc` as needed.

---

## 4) Re-allow direnv and restart Cursor

```bash
direnv allow
```

Then restart Cursor (or reload the MCP server from the Cursor MCP settings panel) so it picks up any config changes.

---

## 5) Re-initialize from scratch (if something is badly out of sync)

If the submodule is in a detached/broken state, re-initialize cleanly:

```bash
git submodule update --init --recursive
```

Then follow steps 2–4 above.

---

## What gets updated by the bootstrap

| Artifact | Updated by bootstrap? | Notes |
|---|---|---|
| `.cursor/rules/*.mdc` | Yes (`--force` required to overwrite) | Cursor agent guidance rules |
| `.cursor/mcp.json` | Yes (`--force` required to overwrite) | MCP server wiring |
| `postgres-language-server.jsonc` | Yes (`--force` required to overwrite) | Zed LSP config |
| `.envrc` | No — manual | Bootstrap only warns about missing vars |
| `~/.pgpass` | No — use `setup-readonly-role.sh --update-pgpass` | Only needed if credentials changed |
| Readonly role SQL / DB grants | No — use `setup-readonly-role.sh --apply` | Only needed if role setup changed |
