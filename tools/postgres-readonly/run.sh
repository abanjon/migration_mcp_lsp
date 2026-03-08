#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLKIT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CLIENT_ROOT="${CLIENT_ROOT:-${PWD}}"
VENV_DIR="${SCRIPT_DIR}/.venv"
BOOTSTRAP_MARKER="${VENV_DIR}/.bootstrapped"
RESOLVER="${TOOLKIT_ROOT}/tools/lib/resolve_pg_env.py"
UV_AVAILABLE=false

if command -v uv >/dev/null 2>&1; then
  UV_AVAILABLE=true
fi

if [[ "${MCP_REQUIRE_UV:-false}" == "true" && "${UV_AVAILABLE}" != "true" ]]; then
  echo "MCP_REQUIRE_UV=true but 'uv' is not installed or not on PATH" >&2
  exit 1
fi

if ! command -v direnv >/dev/null 2>&1; then
  echo "direnv is required for the MCP launcher" >&2
  exit 1
fi

cd "${CLIENT_ROOT}"
eval "$(direnv export bash)"

: "${PGROSERVICE:?PGROSERVICE must be exported by .envrc}"

eval "$(python3 "${RESOLVER}" --service "${PGROSERVICE}" --mode mcp --appname "${MCP_PGAPPNAME:-cursor-postgres-readonly}")"

required_vars=(PGHOST PGPORT PGDATABASE PGROUSER PGROPASSWORD)
for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "Missing required env var: ${var_name}" >&2
    exit 1
  fi
done

if [[ ! -d "${VENV_DIR}" ]]; then
  echo "Creating MCP virtual environment" >&2
  if [[ "${UV_AVAILABLE}" == "true" ]]; then
    uv venv "${VENV_DIR}" >/dev/null
  else
    python3 -m venv "${VENV_DIR}"
  fi
fi

if ! "${VENV_DIR}/bin/python" -c "import mcp, psycopg" >/dev/null 2>&1; then
  rm -f "${BOOTSTRAP_MARKER}"
fi

if [[ ! -f "${BOOTSTRAP_MARKER}" || "${SCRIPT_DIR}/requirements.txt" -nt "${BOOTSTRAP_MARKER}" ]]; then
  echo "Installing MCP dependencies" >&2
  if [[ "${UV_AVAILABLE}" == "true" ]]; then
    uv pip install --python "${VENV_DIR}/bin/python" -r "${SCRIPT_DIR}/requirements.txt" >/dev/null
  else
    "${VENV_DIR}/bin/python" -m pip install --upgrade pip >/dev/null
    "${VENV_DIR}/bin/python" -m pip install -r "${SCRIPT_DIR}/requirements.txt" >/dev/null
  fi
  touch "${BOOTSTRAP_MARKER}"
fi

exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/server.py"
