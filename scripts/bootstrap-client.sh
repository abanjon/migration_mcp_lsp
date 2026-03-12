#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CLIENT_ROOT="${PWD}"
PGSERVICE_NAME="client_admin"
PGROSERVICE_NAME="client_readonly"
FORCE=false
DRY_RUN=false

usage() {
  cat <<'EOF'
Usage:
  bootstrap-client.sh [options]

Options:
  --client-root <path>   Target client repo (default: current directory)
  --pgservice <name>     Value for PGSERVICE in .envrc
  --pgroservice <name>   Value for PGROSERVICE in .envrc
  --force                Overwrite generated files
  --dry-run              Print actions only
  -h, --help             Show help

This script writes:
  - <client>/.cursor/mcp.json
  - <client>/postgres-language-server.jsonc
This script does not write <client>/.envrc.
EOF
}

log() {
  printf '[bootstrap] %s\n' "$*"
}

fail() {
  printf '[bootstrap] ERROR: %s\n' "$*" >&2
  exit 1
}

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

write_file() {
  local target="$1"
  local content="$2"
  if [[ "${DRY_RUN}" == "true" ]]; then
    log "Would write ${target}"
    return 0
  fi
  printf '%s\n' "${content}" > "${target}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --client-root)
      shift
      CLIENT_ROOT="${1:-}"
      ;;
    --pgservice)
      shift
      PGSERVICE_NAME="${1:-}"
      ;;
    --pgroservice)
      shift
      PGROSERVICE_NAME="${1:-}"
      ;;
    --force)
      FORCE=true
      ;;
    --dry-run)
      DRY_RUN=true
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "Unknown argument: $1"
      ;;
  esac
  shift
done

[[ -n "${CLIENT_ROOT}" ]] || fail "Missing --client-root"
[[ -d "${CLIENT_ROOT}" ]] || fail "Client root does not exist: ${CLIENT_ROOT}"
[[ -f "${TOOLKIT_ROOT}/tools/lib/resolve_pg_env.py" ]] || fail "Toolkit appears incomplete"

if ! have_cmd direnv; then
  fail "direnv is required"
fi

if ! have_cmd uv; then
  log "uv not found; MCP launcher can fall back to python -m venv (set MCP_REQUIRE_UV=true to enforce uv)"
fi

if [[ ! -f "${HOME}/.pg_service.conf" ]]; then
  fail "Missing ~/.pg_service.conf"
fi

if [[ ! -f "${HOME}/.pgpass" ]]; then
  fail "Missing ~/.pgpass"
fi

if ! have_cmd postgres-language-server; then
  if [[ ! -x "${HOME}/node_modules/@postgres-language-server/cli-aarch64-apple-darwin/postgres-language-server" && ! -x "${HOME}/node_modules/@postgres-language-server/cli/bin/postgres-language-server" ]]; then
    log "postgres-language-server not found on PATH or home node_modules; set PGLS_BIN if needed"
  fi
fi

if ! have_cmd mcpls; then
  if [[ ! -x "${TOOLKIT_ROOT}/tools/lsp-insights/bin/mcpls" ]]; then
    log "mcpls not found. Run tools/lsp-insights/install-mcpls.sh or set MCPLS_BIN to enable LSP-Insights MCP server"
  fi
fi

if ! python3 "${TOOLKIT_ROOT}/tools/lib/resolve_pg_env.py" --service "${PGROSERVICE_NAME}" --mode lsp >/dev/null; then
  fail "Failed to resolve PGROSERVICE=${PGROSERVICE_NAME} via ~/.pg_service.conf + ~/.pgpass"
fi

if ! python3 "${TOOLKIT_ROOT}/tools/lib/resolve_pg_env.py" --service "${PGROSERVICE_NAME}" --mode mcp >/dev/null; then
  fail "Failed to resolve MCP env for PGROSERVICE=${PGROSERVICE_NAME}"
fi

mkdir -p "${CLIENT_ROOT}/.cursor"

MCP_JSON_PATH="${CLIENT_ROOT}/.cursor/mcp.json"
PGLS_CONFIG_PATH="${CLIENT_ROOT}/postgres-language-server.jsonc"
ENVRC_PATH="${CLIENT_ROOT}/.envrc"

if [[ ! -f "${ENVRC_PATH}" ]]; then
  fail "Missing ${ENVRC_PATH}. Create it first with PGSERVICE and PGROSERVICE exports."
fi

if [[ -f "${MCP_JSON_PATH}" && "${FORCE}" != "true" && "${DRY_RUN}" != "true" ]]; then
  fail "${MCP_JSON_PATH} exists. Re-run with --force to overwrite."
elif [[ -f "${MCP_JSON_PATH}" && "${DRY_RUN}" == "true" ]]; then
  log "Would overwrite existing ${MCP_JSON_PATH} (use --force when applying)"
fi

if [[ -f "${PGLS_CONFIG_PATH}" && "${FORCE}" != "true" && "${DRY_RUN}" != "true" ]]; then
  fail "${PGLS_CONFIG_PATH} exists. Re-run with --force to overwrite."
elif [[ -f "${PGLS_CONFIG_PATH}" && "${DRY_RUN}" == "true" ]]; then
  log "Would overwrite existing ${PGLS_CONFIG_PATH} (use --force when applying)"
fi

MCP_CONTENT="$(cat <<EOF
{
  "mcpServers": {
    "postgres-readonly": {
      "command": "/bin/bash",
      "args": [
        "${TOOLKIT_ROOT}/tools/postgres-readonly/run.sh"
      ]
    },
    "postgres-lsp-insights": {
      "command": "/bin/bash",
      "args": [
        "${TOOLKIT_ROOT}/tools/lsp-insights/run.sh"
      ]
    }
  }
}
EOF
)"

PGLS_CONTENT="$(cat <<EOF
{
  "\$schema": "https://pg-language-server.com/latest/schema.json",
  "extends": [
    "${TOOLKIT_ROOT}/tools/lsp/postgres-language-server.base.jsonc"
  ]
}
EOF
)"

write_file "${MCP_JSON_PATH}" "${MCP_CONTENT}"
write_file "${PGLS_CONFIG_PATH}" "${PGLS_CONTENT}"

log "Bootstrap completed for: ${CLIENT_ROOT}"
log "Next: run 'direnv allow \"${CLIENT_ROOT}\"' from your shell."
log "Note: bootstrap-client.sh does not modify ${ENVRC_PATH}."
log "In Zed, point SQL LSP binary to '${TOOLKIT_ROOT}/tools/lsp/run-pgls.sh' if not already configured."
