#!/bin/bash
set -euo pipefail

# Install TraceCtrl plugin for OpenClaw
# Usage: ./install.sh [--endpoint URL]
#
# This script:
#   1. Finds the OpenClaw installation directory dynamically
#   2. Builds the plugin with TypeScript
#   3. Copies the plugin to ~/.openclaw/extensions/tracectrl/
#   4. Updates openclaw.json to enable both tracectrl AND diagnostics-otel

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENDPOINT="${ENDPOINT:-http://localhost:4318}"
DEST_DIR="${HOME}/.openclaw/extensions/tracectrl"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --endpoint)
      ENDPOINT="$2"
      shift 2
      ;;
    --endpoint=*)
      ENDPOINT="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--endpoint URL]"
      echo ""
      echo "Options:"
      echo "  --endpoint URL   OTLP collector endpoint (default: http://localhost:4318)"
      echo ""
      echo "Environment variables:"
      echo "  OPENCLAW_DIR     Override auto-detected OpenClaw install directory"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ---------------------------------------------------------------------------
# Colors (when stdout is a terminal)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  GREEN='\033[0;32m'
  YELLOW='\033[1;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN='' YELLOW='' RED='' BOLD='' RESET=''
fi

info()  { echo -e "${GREEN}[tracectrl]${RESET} $*"; }
warn()  { echo -e "${YELLOW}[tracectrl]${RESET} $*"; }
error() { echo -e "${RED}[tracectrl]${RESET} $*" >&2; }

# ---------------------------------------------------------------------------
# Step 1: Find OpenClaw install directory
# ---------------------------------------------------------------------------
info "Locating OpenClaw installation..."

if [[ -n "${OPENCLAW_DIR:-}" ]]; then
  OC_DIR="$OPENCLAW_DIR"
  info "Using OPENCLAW_DIR override: ${OC_DIR}"
elif command -v openclaw &>/dev/null; then
  OC_BIN="$(which openclaw)"
  OC_REAL="$(readlink -f "$OC_BIN" 2>/dev/null || realpath "$OC_BIN" 2>/dev/null || echo "$OC_BIN")"
  # Walk up from the resolved binary to find the package root
  # Typical: .../lib/node_modules/openclaw/dist/cli.js -> .../lib/node_modules/openclaw/
  OC_DIR="$(dirname "$OC_REAL")"
  for i in $(seq 1 10); do
    if [[ -f "${OC_DIR}/package.json" ]] && grep -q '"openclaw"' "${OC_DIR}/package.json" 2>/dev/null; then
      break
    fi
    OC_DIR="$(dirname "$OC_DIR")"
  done

  # Fallback: check sibling lib directory (nvm layout: bin/openclaw -> ../lib/node_modules/openclaw)
  if ! [[ -f "${OC_DIR}/package.json" ]] || ! grep -q '"openclaw"' "${OC_DIR}/package.json" 2>/dev/null; then
    BIN_DIR="$(dirname "$OC_REAL")"
    CANDIDATE="$(dirname "$BIN_DIR")/lib/node_modules/openclaw"
    if [[ -f "${CANDIDATE}/package.json" ]]; then
      OC_DIR="$CANDIDATE"
    fi
  fi

  if [[ -f "${OC_DIR}/package.json" ]] && grep -q '"openclaw"' "${OC_DIR}/package.json" 2>/dev/null; then
    info "Found OpenClaw at: ${OC_DIR}"
  else
    warn "Could not locate OpenClaw package root from binary: ${OC_BIN}"
    warn "Set OPENCLAW_DIR=/path/to/openclaw to override"
    OC_DIR=""
  fi
else
  warn "openclaw not found in PATH"
  warn "Set OPENCLAW_DIR=/path/to/openclaw to override"
  OC_DIR=""
fi

# Check if diagnostics-otel exists in the stock extensions
DIAG_API=""
if [[ -n "$OC_DIR" ]]; then
  DIAG_CANDIDATE="${OC_DIR}/dist/extensions/diagnostics-otel/api.js"
  if [[ -f "$DIAG_CANDIDATE" ]]; then
    DIAG_API="$DIAG_CANDIDATE"
    info "Found diagnostics-otel api at: ${DIAG_API}"
  else
    warn "diagnostics-otel api.js not found at expected path"
  fi
fi

# ---------------------------------------------------------------------------
# Step 2: Install npm dependencies and build
# ---------------------------------------------------------------------------
info "Installing dependencies..."
cd "$SCRIPT_DIR"
npm install --ignore-scripts 2>&1 | tail -1

info "Building TypeScript..."
npx tsc --skipLibCheck
info "Build successful"

# ---------------------------------------------------------------------------
# Step 3: Copy to ~/.openclaw/extensions/tracectrl/
# ---------------------------------------------------------------------------
info "Installing to ${DEST_DIR}..."
mkdir -p "$DEST_DIR"

# Copy dist, package.json, openclaw.plugin.json
cp -r dist/ "$DEST_DIR/dist/"
cp package.json "$DEST_DIR/package.json"
cp openclaw.plugin.json "$DEST_DIR/openclaw.plugin.json"

# Copy node_modules (OTEL deps are needed at runtime)
if [[ -d node_modules ]]; then
  cp -r node_modules/ "$DEST_DIR/node_modules/"
fi

info "Plugin installed to ${DEST_DIR}"

# ---------------------------------------------------------------------------
# Step 4: Update openclaw.json to enable both plugins
# ---------------------------------------------------------------------------
OC_CONFIG="${HOME}/.openclaw/openclaw.json"

if [[ -f "$OC_CONFIG" ]]; then
  info "Checking openclaw.json configuration..."

  # Check if tracectrl is already in the extensions allow list
  if grep -q '"tracectrl"' "$OC_CONFIG" 2>/dev/null; then
    info "tracectrl already present in openclaw.json"
  else
    warn "You may need to add tracectrl to the extensions allow list in:"
    warn "  ${OC_CONFIG}"
    warn ""
    warn "Example openclaw.json extensions section:"
    echo '  "extensions": {'
    echo '    "allow": ["tracectrl", "diagnostics-otel"],'
    echo '    "tracectrl": {'
    echo "      \"endpoint\": \"${ENDPOINT}\","
    echo '      "serviceName": "openclaw-gateway",'
    echo '      "traces": true,'
    echo '      "metrics": true'
    echo '    }'
    echo '  }'
  fi
else
  warn "No openclaw.json found at ${OC_CONFIG}"
  warn "Create one with the extensions section shown below."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${BOLD}====================================${RESET}"
echo -e "${GREEN}  TraceCtrl plugin installed${RESET}"
echo -e "${BOLD}====================================${RESET}"
echo ""
echo "  Plugin location:  ${DEST_DIR}"
echo "  OTLP endpoint:    ${ENDPOINT}"
if [[ -n "$DIAG_API" ]]; then
  echo "  Diagnostics API:  ${DIAG_API} (will auto-detect at runtime)"
fi
echo ""
echo "  Recommended openclaw.json extensions config:"
echo ""
echo '  "extensions": {'
echo '    "allow": ["tracectrl", "diagnostics-otel"],'
echo '    "tracectrl": {'
echo "      \"endpoint\": \"${ENDPOINT}\","
echo '      "serviceName": "openclaw-gateway",'
echo '      "traces": true,'
echo '      "metrics": true'
echo '    }'
echo '  }'
echo ""
echo -e "  ${YELLOW}Restart OpenClaw to activate:${RESET}"
echo "    openclaw restart"
echo ""
