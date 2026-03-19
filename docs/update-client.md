# Updating an Existing Client

Run these steps whenever the toolkit has been updated (new features, rule changes, security fixes).

---

## Recommended Upgrade Path (Low Friction)

For normal day-to-day upgrades, treat the toolkit as a submodule that tracks `main`.

You do not need to wipe and re-initialize a client repo just because the toolkit changed.

Typical update flow:

```bash
cd "/path/to/client-repo"
git submodule update --remote --merge "XX - utils/portable-lsp-mcp-toolkit"
rm -rf "XX - utils/portable-lsp-mcp-toolkit/tools/postgres-readonly/__pycache__"

bash "XX - utils/portable-lsp-mcp-toolkit/scripts/bootstrap-client.sh" \
  --client-root "$PWD" \
  --pgservice <admin_service> \
  --pgroservice <readonly_service> \
  --force

direnv allow
```

Use this flow for:
- new or changed Cursor rules under `templates/.cursor/rules`
- updates to `tools/lsp/*`
- updates to `.cursor/mcp.json`
- updates to generated `postgres-language-server.jsonc`

Re-initialize only if the submodule itself is broken or missing.

---

## 1) Optional One-Time Setup: Make `--remote` Track `main`

If you want the least friction across client repos, configure the submodule to track `main`:

```bash
cd "/path/to/client-repo"
git config -f .gitmodules submodule."XX - utils/portable-lsp-mcp-toolkit".branch main
git submodule sync -- "XX - utils/portable-lsp-mcp-toolkit"
git add .gitmodules
git commit -m "chore: track portable-lsp-mcp-toolkit main branch"
```

After that, `git submodule update --remote --merge` will consistently pull from `main`.

---

## 2) Update the Toolkit Submodule

The toolkit lives inside each client repo as a git submodule.

### Pull the latest commit on the tracked branch

```bash
cd "/path/to/client-repo"
git submodule update --remote --merge "XX - utils/portable-lsp-mcp-toolkit"
```

`--remote` fetches from the submodule's upstream and moves the pointer to the latest commit on its tracking branch.

### Clear the Python bytecode cache

Always do this after a submodule update. `git submodule update` resets file timestamps, which can cause Python to use stale `.pyc` files and the MCP server to appear unchanged to Cursor.

```bash
rm -rf "XX - utils/portable-lsp-mcp-toolkit/tools/postgres-readonly/__pycache__"
```

### Or pin to a specific tag or commit

If you want a more controlled rollout, you can still pin to an explicit tag or commit instead of tracking `main`:

```bash
cd "/path/to/client-repo/XX - utils/portable-lsp-mcp-toolkit"
git fetch --tags
git checkout v1.2.0   # replace with the desired tag or commit SHA
cd ../..
```

### Commit the updated submodule pointer

```bash
git add "XX - utils/portable-lsp-mcp-toolkit"
git commit -m "chore: update portable-lsp-mcp-toolkit"
```

---

## 3) Re-run Bootstrap

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

## 4) Check for New or Changed Env Vars

```bash
diff .envrc \
     "XX - utils/portable-lsp-mcp-toolkit/templates/.envrc.example"
```

The bootstrap will warn about any missing recommended vars. Add them to `.envrc` as needed.

---

## 5) Re-allow Direnv and Restart Cursor

```bash
direnv allow
```

Then restart Cursor (or reload the MCP server from the Cursor MCP settings panel) so it picks up any config changes.

---

## 6) If the Toolkit Repo Is Managed with Jujutsu (`jj`)

A colocated `jj` repo may appear as a detached `HEAD` in Git. That is normal.

Client repos still consume the toolkit as a normal Git submodule, so the only requirement is that the desired toolkit commit is pushed to a Git-visible ref such as `main`.

---

## 7) Re-initialize Only If Something Is Broken

Do not wipe and re-clone for normal toolkit upgrades.

Only re-initialize if:
- the submodule directory is missing
- the submodule is not initialized
- the submodule metadata is corrupted
- `git submodule update --remote --merge` fails because the submodule is in a bad state

If that happens, re-initialize cleanly:

```bash
git submodule update --init --recursive
```

Then follow steps 3–5 above.

---

## What Gets Updated by the Submodule vs Bootstrap

| Artifact | Updated by submodule bump alone? | Requires bootstrap? | Notes |
|---|---|---|---|
| Toolkit scripts/config under submodule | Yes | No | Comes from updated submodule commit |
| `.cursor/rules/*.mdc` | No | Yes (`--force`) | Copied from toolkit templates |
| `.cursor/mcp.json` | No | Yes (`--force`) | MCP server wiring |
| `postgres-language-server.jsonc` | No | Yes (`--force`) | Zed LSP config |
| `.envrc` | No | No — manual | Bootstrap only warns about missing vars |
| `~/.pgpass` | No | No — use `setup-readonly-role.sh --update-pgpass` | Only needed if credentials changed |
| Readonly role SQL / DB grants | No | No — use `setup-readonly-role.sh --apply` | Only needed if role setup changed |
