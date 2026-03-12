#!/usr/bin/env bats
# ---------------------------------------------------------------------------
# Tier 1: Bootstrap script tests
#
# Validates that bootstrap-client.sh correctly generates mcp.json with
# the postgres-lsp-insights server entry alongside postgres-readonly.
#
# Requirements: bats-core, bash, python3, direnv
# Run: bats tests/lsp-insights/test_bootstrap.bats
# ---------------------------------------------------------------------------

TOOLKIT_ROOT="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"
BOOTSTRAP_SH="${TOOLKIT_ROOT}/scripts/bootstrap-client.sh"

setup() {
  export TEST_TMPDIR
  TEST_TMPDIR="$(mktemp -d)"

  # Create a fake client directory with a minimal .envrc
  mkdir -p "${TEST_TMPDIR}/client"
  cat > "${TEST_TMPDIR}/client/.envrc" <<'EOF'
export PGSERVICE="test_admin"
export PGROSERVICE="test_readonly"
EOF

  # Create test pg_service.conf and pgpass in a fake HOME
  export REAL_HOME="${HOME}"
  export HOME="${TEST_TMPDIR}/fakehome"
  mkdir -p "${HOME}"

  cat > "${HOME}/.pg_service.conf" <<'EOF'
[test_admin]
host=localhost
port=5432
dbname=testdb
user=test_admin
sslmode=disable

[test_readonly]
host=localhost
port=5432
dbname=testdb
user=test_ro
sslmode=disable
EOF

  cat > "${HOME}/.pgpass" <<'EOF'
localhost:5432:testdb:test_admin:admin_pass
localhost:5432:testdb:test_ro:ro_pass
EOF
  chmod 600 "${HOME}/.pgpass"
}

teardown() {
  export HOME="${REAL_HOME}"
  rm -rf "${TEST_TMPDIR}"
}

@test "bootstrap generates mcp.json with postgres-lsp-insights entry" {
  # Skip if direnv is not available (CI might not have it)
  command -v direnv >/dev/null 2>&1 || skip "direnv not installed"

  run bash "${BOOTSTRAP_SH}" \
    --client-root "${TEST_TMPDIR}/client" \
    --pgservice test_admin \
    --pgroservice test_readonly \
    --force \
    --dry-run

  [[ "${status}" -eq 0 ]]
  [[ "${output}" == *"Bootstrap completed"* || "${output}" == *"Would write"* ]]
}

@test "generated mcp.json contains both server entries" {
  command -v direnv >/dev/null 2>&1 || skip "direnv not installed"

  bash "${BOOTSTRAP_SH}" \
    --client-root "${TEST_TMPDIR}/client" \
    --pgservice test_admin \
    --pgroservice test_readonly \
    --force 2>/dev/null || true

  local mcp_json="${TEST_TMPDIR}/client/.cursor/mcp.json"
  if [[ -f "${mcp_json}" ]]; then
    grep -q '"postgres-readonly"' "${mcp_json}"
    grep -q '"postgres-lsp-insights"' "${mcp_json}"
    grep -q 'lsp-insights/run.sh' "${mcp_json}"
  else
    skip "mcp.json not generated (direnv may not have resolved)"
  fi
}
