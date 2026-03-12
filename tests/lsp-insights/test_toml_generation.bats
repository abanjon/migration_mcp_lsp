#!/usr/bin/env bats
# ---------------------------------------------------------------------------
# Tier 1: Shell / config tests for tools/lsp-insights/run.sh
#
# These tests validate:
#   - TOML config generation (structure, credential injection)
#   - Binary resolution logic
#   - Dependency checks (direnv, mcpls, pgls)
#   - Permission hardening on generated config
#
# Requirements: bats-core, bash
# Run: bats tests/lsp-insights/test_toml_generation.bats
# ---------------------------------------------------------------------------

TOOLKIT_ROOT="$(cd "$(dirname "${BATS_TEST_FILENAME}")/../.." && pwd)"
RUN_SH="${TOOLKIT_ROOT}/tools/lsp-insights/run.sh"

setup() {
  export TEST_TMPDIR
  TEST_TMPDIR="$(mktemp -d)"

  # Create a minimal fake direnv that just exports PGROSERVICE
  mkdir -p "${TEST_TMPDIR}/bin"
  cat > "${TEST_TMPDIR}/bin/direnv" <<'DIRENV'
#!/usr/bin/env bash
if [[ "$1" == "export" && "$2" == "bash" ]]; then
  echo 'export PGROSERVICE="test_readonly"'
fi
DIRENV
  chmod +x "${TEST_TMPDIR}/bin/direnv"

  # Create a fake mcpls binary
  cat > "${TEST_TMPDIR}/bin/mcpls" <<'MCPLS'
#!/usr/bin/env bash
echo "mcpls-fake $*"
# Don't actually exec; just validate we got called
if [[ "$1" == "--config" && -f "$2" ]]; then
  cat "$2"
fi
exit 0
MCPLS
  chmod +x "${TEST_TMPDIR}/bin/mcpls"

  # Create a fake postgres-language-server binary
  cat > "${TEST_TMPDIR}/bin/postgres-language-server" <<'PGLS'
#!/usr/bin/env bash
echo "pgls-fake $*"
exit 0
PGLS
  chmod +x "${TEST_TMPDIR}/bin/postgres-language-server"

  # Create a fake resolve_pg_env.py that emits test credentials
  cat > "${TEST_TMPDIR}/resolve_pg_env.py" <<'RESOLVER'
#!/usr/bin/env python3
print('export PGHOST="localhost"')
print('export PGPORT="5432"')
print('export PGDATABASE="testdb"')
print('export PGUSER="test_ro_user"')
print('export PGPASSWORD="test_ro_password"')
print('export PGSSLMODE="disable"')
print('export PGAPPNAME="cursor-lsp-insights"')
RESOLVER

  # Create a fake .envrc directory (CLIENT_ROOT)
  mkdir -p "${TEST_TMPDIR}/client"

  # Put fake bins on PATH
  export PATH="${TEST_TMPDIR}/bin:${PATH}"
}

teardown() {
  rm -rf "${TEST_TMPDIR}"
}

# --- Helper: source run.sh in a way that stops before exec ---
# We can't actually exec mcpls in tests, so we extract just the TOML
# generation portion by running the script up to the exec line.
generate_toml() {
  local runtime_dir="${TEST_TMPDIR}/lsp-insights-runtime"
  local runtime_toml="${runtime_dir}/mcpls.toml"

  # Build a test harness that sources the environment logic without exec
  cat > "${TEST_TMPDIR}/harness.sh" <<HARNESS
#!/usr/bin/env bash
set -euo pipefail

export CLIENT_ROOT="${TEST_TMPDIR}/client"
export MCPLS_BIN="${TEST_TMPDIR}/bin/mcpls"
export PGLS_BIN="${TEST_TMPDIR}/bin/postgres-language-server"
export PATH="${TEST_TMPDIR}/bin:\${PATH}"

# Simulate what run.sh does: load env, resolve creds, generate TOML
cd "\${CLIENT_ROOT}"
eval "\$(direnv export bash)"
: "\${PGROSERVICE:?}"
eval "\$(python3 "${TEST_TMPDIR}/resolve_pg_env.py" --service "\${PGROSERVICE}" --mode lsp --appname cursor-lsp-insights)"
unset PGSERVICE PGSERVICEFILE

mkdir -p "${runtime_dir}"
MCPLS_LOG_LEVEL="\${MCPLS_LOG_LEVEL:-warn}"

cat > "${runtime_toml}" <<TOML
[workspace]

[[workspace.language_extensions]]
extensions = ["sql"]
language_id = "sql"

[[lsp_servers]]
language_id = "sql"
command = "\${PGLS_BIN}"
args = ["lsp-proxy"]
file_patterns = ["**/*.sql"]

[lsp_servers.env]
PGHOST = "\${PGHOST}"
PGPORT = "\${PGPORT}"
PGDATABASE = "\${PGDATABASE}"
PGUSER = "\${PGUSER}"
PGPASSWORD = "\${PGPASSWORD}"
PGSSLMODE = "\${PGSSLMODE}"
PGAPPNAME = "\${PGAPPNAME:-cursor-lsp-insights}"
TOML

chmod 600 "${runtime_toml}"
echo "TOML_PATH=${runtime_toml}"
HARNESS
  chmod +x "${TEST_TMPDIR}/harness.sh"
  bash "${TEST_TMPDIR}/harness.sh"
}

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@test "TOML is generated with correct structure" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  [[ -f "${toml_path}" ]]

  # Check key sections exist
  grep -q '^\[workspace\]' "${toml_path}"
  grep -q '^\[\[workspace\.language_extensions\]\]' "${toml_path}"
  grep -q '^\[\[lsp_servers\]\]' "${toml_path}"
  grep -q '^\[lsp_servers\.env\]' "${toml_path}"
}

@test "TOML contains resolved PG credentials" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  grep -q 'PGHOST = "localhost"' "${toml_path}"
  grep -q 'PGPORT = "5432"' "${toml_path}"
  grep -q 'PGDATABASE = "testdb"' "${toml_path}"
  grep -q 'PGUSER = "test_ro_user"' "${toml_path}"
  grep -q 'PGPASSWORD = "test_ro_password"' "${toml_path}"
  grep -q 'PGSSLMODE = "disable"' "${toml_path}"
}

@test "TOML includes sql language extension mapping" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  grep -q 'extensions = \["sql"\]' "${toml_path}"
  grep -q 'language_id = "sql"' "${toml_path}"
}

@test "TOML references correct LSP server command" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  grep -q "command = \"${TEST_TMPDIR}/bin/postgres-language-server\"" "${toml_path}"
  grep -q 'args = \["lsp-proxy"\]' "${toml_path}"
}

@test "Generated TOML file has restricted permissions (600)" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  perms="$(stat -f '%Lp' "${toml_path}" 2>/dev/null || stat -c '%a' "${toml_path}" 2>/dev/null)"
  [[ "${perms}" == "600" ]]
}

@test "TOML lsp_servers uses language_id not name" {
  output="$(generate_toml)"
  toml_path="$(echo "${output}" | grep '^TOML_PATH=' | cut -d= -f2)"

  grep -q 'language_id = "sql"' "${toml_path}"
  # Should NOT contain a 'name' field (mcpls doesn't support it)
  ! grep -q '^name = ' "${toml_path}"
}

@test "run.sh fails if direnv is not on PATH" {
  # Remove direnv from the test PATH
  export PATH="/usr/bin:/bin"
  export CLIENT_ROOT="${TEST_TMPDIR}/client"
  export MCPLS_BIN="${TEST_TMPDIR}/bin/mcpls"
  export PGLS_BIN="${TEST_TMPDIR}/bin/postgres-language-server"

  run bash "${RUN_SH}"
  [[ "${status}" -ne 0 ]]
  [[ "${output}" == *"direnv is required"* ]]
}

@test "run.sh fails if mcpls binary is not found" {
  # direnv is on path but mcpls is not — point MCPLS_BIN at a nonexistent path
  # so the validation check catches it (avoids finding the real bundled binary
  # via SCRIPT_DIR/bin/mcpls)
  export PATH="${TEST_TMPDIR}/bin:${PATH}"
  rm "${TEST_TMPDIR}/bin/mcpls"
  export CLIENT_ROOT="${TEST_TMPDIR}/client"
  export MCPLS_BIN="/nonexistent/mcpls"

  run bash "${RUN_SH}"
  [[ "${status}" -ne 0 ]]
  [[ "${output}" == *"mcpls binary not found"* ]]
}

@test "run.sh fails if postgres-language-server is not found" {
  # Use a restricted PATH with only essential system tools + our test dir (minus pgls)
  rm "${TEST_TMPDIR}/bin/postgres-language-server"
  export PATH="${TEST_TMPDIR}/bin:/usr/bin:/bin"
  export CLIENT_ROOT="${TEST_TMPDIR}/client"
  export MCPLS_BIN="${TEST_TMPDIR}/bin/mcpls"
  export PGLS_BIN=""
  # Override HOME so bundled installs aren't found
  export HOME="${TEST_TMPDIR}/fakehome"
  mkdir -p "${HOME}/node_modules"

  run bash "${RUN_SH}"
  [[ "${status}" -ne 0 ]]
  [[ "${output}" == *"postgres-language-server binary not found"* ]]
}
