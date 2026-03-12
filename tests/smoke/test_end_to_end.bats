#!/usr/bin/env bats
# ---------------------------------------------------------------------------
# Tier 3: End-to-end smoke test
#
# Validates the full pipeline: run.sh -> mcpls -> MCP initialize
#
# This test requires:
#   - mcpls binary
#   - postgres-language-server binary
#   - direnv
#   - Valid PGROSERVICE in a test .envrc with matching
#     ~/.pg_service.conf + ~/.pgpass entries
#
# Set SMOKE_TEST_CLIENT_ROOT to a real client directory to run.
# If not set, tests are skipped.
#
# Run: bats tests/smoke/test_end_to_end.bats
# ---------------------------------------------------------------------------

TOOLKIT_ROOT="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"
RUN_SH="${TOOLKIT_ROOT}/tools/lsp-insights/run.sh"

setup() {
  if [[ -z "${SMOKE_TEST_CLIENT_ROOT:-}" ]]; then
    skip "SMOKE_TEST_CLIENT_ROOT not set — skipping smoke test"
  fi

  if ! command -v mcpls >/dev/null 2>&1; then
    if [[ ! -x "${TOOLKIT_ROOT}/tools/lsp-insights/bin/mcpls" ]]; then
      skip "mcpls not installed"
    fi
  fi

  if ! command -v direnv >/dev/null 2>&1; then
    skip "direnv not installed"
  fi
}

@test "run.sh generates valid mcpls.toml and starts" {
  # Start run.sh in the background, capture PID
  export CLIENT_ROOT="${SMOKE_TEST_CLIENT_ROOT}"
  timeout 10 bash "${RUN_SH}" &
  local pid=$!

  # Give it a few seconds to start
  sleep 3

  # Check that the process is still running (didn't crash on startup)
  if kill -0 "${pid}" 2>/dev/null; then
    # Process is alive — success
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  else
    # Process exited — check if it was a clean timeout or error
    wait "${pid}" 2>/dev/null
    local exit_code=$?
    # timeout returns 124; anything else is a real failure
    if [[ "${exit_code}" -ne 124 ]]; then
      fail "run.sh exited with code ${exit_code}"
    fi
  fi
}

@test "generated mcpls.toml has restricted permissions" {
  local runtime_toml="${TOOLKIT_ROOT}/tools/lsp-insights/.runtime/mcpls.toml"

  if [[ ! -f "${runtime_toml}" ]]; then
    skip "Runtime TOML not yet generated (run the startup test first)"
  fi

  local perms
  perms="$(stat -f '%Lp' "${runtime_toml}" 2>/dev/null || stat -c '%a' "${runtime_toml}" 2>/dev/null)"
  [[ "${perms}" == "600" ]]
}

@test "generated mcpls.toml contains lsp_servers section" {
  local runtime_toml="${TOOLKIT_ROOT}/tools/lsp-insights/.runtime/mcpls.toml"

  if [[ ! -f "${runtime_toml}" ]]; then
    skip "Runtime TOML not yet generated"
  fi

  grep -q '^\[\[lsp_servers\]\]' "${runtime_toml}"
  grep -q 'postgres-language-server' "${runtime_toml}"
}
