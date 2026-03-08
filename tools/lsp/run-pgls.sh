#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLIENT_ROOT="${CLIENT_ROOT:-${PWD}}"
RESOLVER="${TOOLKIT_ROOT}/tools/lib/resolve_pg_env.py"
BUNDLED_PGLS_AARCH64="${HOME}/node_modules/@postgres-language-server/cli-aarch64-apple-darwin/postgres-language-server"
BUNDLED_PGLS_WRAPPER="${HOME}/node_modules/@postgres-language-server/cli/bin/postgres-language-server"

if ! command -v direnv >/dev/null 2>&1; then
  echo "direnv is required for the Postgres LSP wrapper" >&2
  exit 1
fi

PGLS_BIN="${PGLS_BIN:-}"
if [[ -z "${PGLS_BIN}" ]]; then
  if [[ -x "${BUNDLED_PGLS_AARCH64}" ]]; then
    PGLS_BIN="${BUNDLED_PGLS_AARCH64}"
  elif [[ -x "${BUNDLED_PGLS_WRAPPER}" ]]; then
    PGLS_BIN="${BUNDLED_PGLS_WRAPPER}"
  elif command -v postgres-language-server >/dev/null 2>&1; then
    PGLS_BIN="$(command -v postgres-language-server)"
  else
    echo "postgres-language-server binary not found. Set PGLS_BIN or install it." >&2
    exit 1
  fi
fi

cd "${CLIENT_ROOT}"
eval "$(direnv export bash)"

: "${PGROSERVICE:?PGROSERVICE must be exported by .envrc}"

eval "$(python3 "${RESOLVER}" --service "${PGROSERVICE}" --mode lsp --appname "${PGLSP_APPNAME:-zed-pgls}")"

# Force the LSP to use the resolved read-only connection fields instead of
# inheriting the project's admin libpq service selection.
unset PGSERVICE
unset PGSERVICEFILE

exec "${PGLS_BIN}" lsp-proxy
