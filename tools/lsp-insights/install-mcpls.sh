#!/usr/bin/env bash
set -euo pipefail

# ---------------------------------------------------------------------------
# Install mcpls binary for the LSP-Insights MCP server.
#
# Supports:
#   - cargo install (if cargo is available)
#   - Pre-built binary download from GitHub releases
#
# Installs to: tools/lsp-insights/bin/mcpls (local to the toolkit)
#
# Override version: MCPLS_VERSION=v0.3.4-patched.1 ./install-mcpls.sh
# ---------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${SCRIPT_DIR}/bin"
MCPLS_VERSION="${MCPLS_VERSION:-v0.3.4-patched.1}"

# We host a patched mcpls binary on our own repo because upstream v0.3.4 has
# three bugs we've fixed:
#   1. path_to_uri() doesn't percent-encode spaces  (state.rs)
#   2. Workspace folder URIs don't percent-encode spaces (lifecycle.rs)
#   3. [lsp_servers.env] TOML section is parsed but never applied (lifecycle.rs)
# See docs/mcpls-patches.md (or upstream issues once filed) for details.
MCPLS_REPO="${MCPLS_REPO:-abanjon/migration_mcp_lsp}"

# Fallback to upstream repo if patched release not found
MCPLS_UPSTREAM_REPO="bug-ops/mcpls"
MCPLS_UPSTREAM_VERSION="v0.3.4"

log() {
  printf '[install-mcpls] %s\n' "$*" >&2
}

fail() {
  printf '[install-mcpls] ERROR: %s\n' "$*" >&2
  exit 1
}

# Detect platform
detect_target() {
  local os arch
  os="$(uname -s)"
  arch="$(uname -m)"

  case "${os}" in
    Darwin)
      case "${arch}" in
        arm64|aarch64) echo "aarch64-apple-darwin" ;;
        x86_64)        echo "x86_64-apple-darwin" ;;
        *)             fail "Unsupported macOS architecture: ${arch}" ;;
      esac
      ;;
    Linux)
      case "${arch}" in
        aarch64)       echo "aarch64-unknown-linux-gnu" ;;
        x86_64)        echo "x86_64-unknown-linux-gnu" ;;
        *)             fail "Unsupported Linux architecture: ${arch}" ;;
      esac
      ;;
    *)
      fail "Unsupported OS: ${os}. Install manually or use 'cargo install mcpls'."
      ;;
  esac
}

# Try cargo install as last resort (builds UPSTREAM from source — unpatched)
install_via_cargo() {
  if ! command -v cargo >/dev/null 2>&1; then
    return 1
  fi

  log "WARNING: cargo install builds UPSTREAM mcpls (unpatched)."
  log "  Spaces-in-paths and env var bugs will be present."
  log "Installing mcpls via cargo (version ${MCPLS_UPSTREAM_VERSION})..."
  cargo install mcpls --version "${MCPLS_UPSTREAM_VERSION#v}" --root "${INSTALL_DIR%/bin}" 2>&1 | while read -r line; do
    log "  ${line}"
  done

  if [[ -x "${INSTALL_DIR}/mcpls" ]]; then
    return 0
  fi
  return 1
}

# Download pre-built binary from GitHub releases
# Tries the patched binary from our toolkit repo first, falls back to upstream.
install_via_download() {
  local target asset_name

  if ! command -v curl >/dev/null 2>&1; then
    fail "curl is required for binary download"
  fi

  target="$(detect_target)"
  asset_name="mcpls-${target}.tar.gz"

  # --- Try patched binary from our repo first ---
  local patched_url="https://github.com/${MCPLS_REPO}/releases/download/${MCPLS_VERSION}/${asset_name}"
  log "Trying patched mcpls ${MCPLS_VERSION} for ${target}..."
  log "  URL: ${patched_url}"

  if _download_and_extract "${patched_url}" "${asset_name}"; then
    log "Installed PATCHED mcpls (spaces-in-paths + env passthrough fixes)"
    return 0
  fi

  # --- Fall back to upstream ---
  local upstream_url="https://github.com/${MCPLS_UPSTREAM_REPO}/releases/download/${MCPLS_UPSTREAM_VERSION}/${asset_name}"
  log "Patched binary not available; falling back to upstream ${MCPLS_UPSTREAM_VERSION}..."
  log "  URL: ${upstream_url}"
  log "  WARNING: upstream has bugs with spaces in file paths and env var passthrough."

  if _download_and_extract "${upstream_url}" "${asset_name}"; then
    return 0
  fi

  return 1
}

# Helper: download a .tar.gz and extract the mcpls binary
_download_and_extract() {
  local url="$1" asset_name="$2"

  DOWNLOAD_TMP="$(mktemp -d)"

  if ! curl -fsSL "${url}" -o "${DOWNLOAD_TMP}/${asset_name}"; then
    rm -rf "${DOWNLOAD_TMP}"
    return 1
  fi

  mkdir -p "${INSTALL_DIR}"
  tar xzf "${DOWNLOAD_TMP}/${asset_name}" -C "${DOWNLOAD_TMP}"

  # The tarball contains the mcpls binary directly
  if [[ -f "${DOWNLOAD_TMP}/mcpls" ]]; then
    mv "${DOWNLOAD_TMP}/mcpls" "${INSTALL_DIR}/mcpls"
  else
    # Some releases may nest it differently; find it
    local found
    found="$(find "${DOWNLOAD_TMP}" -name mcpls -type f | head -1)"
    if [[ -n "${found}" ]]; then
      mv "${found}" "${INSTALL_DIR}/mcpls"
    else
      rm -rf "${DOWNLOAD_TMP}"
      return 1
    fi
  fi

  rm -rf "${DOWNLOAD_TMP}"
  chmod +x "${INSTALL_DIR}/mcpls"
}

# --- Main ---

# Check if already installed at the expected location
if [[ -x "${INSTALL_DIR}/mcpls" ]]; then
  current_version="$("${INSTALL_DIR}/mcpls" --version 2>/dev/null || echo "unknown")"
  log "mcpls already installed: ${current_version}"
  log "To reinstall, remove ${INSTALL_DIR}/mcpls first."
  exit 0
fi

# Also check if mcpls is on PATH
if command -v mcpls >/dev/null 2>&1; then
  current_version="$(mcpls --version 2>/dev/null || echo "unknown")"
  log "mcpls found on PATH: ${current_version}"
  log "run.sh will use the PATH version. No local install needed."
  exit 0
fi

mkdir -p "${INSTALL_DIR}"

# Prefer download (faster, no build dependencies) over cargo
log "Attempting binary download..."
if install_via_download; then
  log "mcpls installed to ${INSTALL_DIR}/mcpls"
  "${INSTALL_DIR}/mcpls" --version
  exit 0
fi

log "Binary download failed; trying cargo install..."
if install_via_cargo; then
  log "mcpls installed to ${INSTALL_DIR}/mcpls"
  "${INSTALL_DIR}/mcpls" --version
  exit 0
fi

fail "Could not install mcpls. Install it manually: cargo install mcpls"
