#!/usr/bin/env bash
#
# install.sh — Web installer for multica-template
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/thefrol/multica-boostrap/main/install.sh | bash
#   curl -sSL https://raw.githubusercontent.com/thefrol/multica-boostrap/main/install.sh | bash -s -- --system
#
# Two-step (safer):
#   curl -sSL -o install.sh https://raw.githubusercontent.com/thefrol/multica-boostrap/main/install.sh
#   cat install.sh | less
#   bash install.sh

set -euo pipefail

REPO="thefrol/multica-boostrap"
BRANCH="main"
SCRIPT_NAME="multica-template"
RAW_URL="https://raw.githubusercontent.com/${REPO}/${BRANCH}/${SCRIPT_NAME}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

info() {
    echo "  → $1"
}

warn() {
    echo "  ⚠ $1" >&2
}

error() {
    echo "  ✖ $1" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

SYSTEM_INSTALL=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --system)
            SYSTEM_INSTALL=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            cat <<'EOF'
Usage: install.sh [OPTIONS]

Options:
  --system      Install to /usr/local/bin instead of ~/.local/bin
  --dry-run     Print what would be done without making changes
  -h, --help    Show this help message

Examples:
  bash install.sh
  bash install.sh --system
  bash install.sh --dry-run
EOF
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Detect install directory
# ---------------------------------------------------------------------------

if [[ "$SYSTEM_INSTALL" == true ]]; then
    INSTALL_DIR="/usr/local/bin"
else
    INSTALL_DIR="${HOME}/.local/bin"
fi

INSTALL_PATH="${INSTALL_DIR}/${SCRIPT_NAME}"

# ---------------------------------------------------------------------------
# Detect OS / Arch (for future binary distribution)
# ---------------------------------------------------------------------------

OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

case "$ARCH" in
    x86_64)  ARCH="amd64" ;;
    aarch64|arm64) ARCH="arm64" ;;
    *)       ARCH="unknown" ;;
esac

info "Detected OS: ${OS}, Arch: ${ARCH}"

# ---------------------------------------------------------------------------
# Dry-run banner
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  DRY RUN — no changes will be made"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
fi

# ---------------------------------------------------------------------------
# Ensure install directory exists
# ---------------------------------------------------------------------------

if [[ ! -d "$INSTALL_DIR" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
        info "Would create directory: ${INSTALL_DIR}"
    else
        info "Creating directory: ${INSTALL_DIR}"
        mkdir -p "$INSTALL_DIR"
    fi
fi

# ---------------------------------------------------------------------------
# Check write permission (for system install)
# ---------------------------------------------------------------------------

if [[ "$SYSTEM_INSTALL" == true && "$DRY_RUN" != true ]]; then
    if [[ ! -w "$INSTALL_DIR" ]]; then
        error "Cannot write to ${INSTALL_DIR}. Run with sudo or use --system with appropriate privileges."
    fi
fi

# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    info "Would download: ${RAW_URL}"
    info "Would install to: ${INSTALL_PATH}"
else
    info "Downloading ${SCRIPT_NAME} from ${REPO} (${BRANCH}) ..."

    if command -v curl >/dev/null 2>&1; then
        HTTP_CODE=$(curl -fsSL -w "%{http_code}" -o "$INSTALL_PATH" "$RAW_URL" || true)
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$INSTALL_PATH" "$RAW_URL" && HTTP_CODE="200" || HTTP_CODE=""
    else
        error "Neither curl nor wget found. Please install one of them and try again."
    fi

    if [[ "${HTTP_CODE:-}" != "200" && "${HTTP_CODE:-}" != "" ]]; then
        rm -f "$INSTALL_PATH"
        error "Download failed (HTTP ${HTTP_CODE})."
    fi

    if [[ ! -f "$INSTALL_PATH" ]]; then
        error "Download failed. File not found at ${INSTALL_PATH}"
    fi

    chmod +x "$INSTALL_PATH"
    info "Installed to ${INSTALL_PATH}"
fi

# ---------------------------------------------------------------------------
# Verify Python 3 is available
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" != true ]]; then
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 is required but not found in PATH."
        warn "Please install Python 3 before using ${SCRIPT_NAME}."
    fi

    # Verify YAML module is available (used by multica-template)
    if ! python3 -c "import yaml" >/dev/null 2>&1; then
        warn "Python 'PyYAML' module is required but not found."
        warn "Install it with: pip install pyyaml"
    fi
fi

# ---------------------------------------------------------------------------
# Update PATH if needed
# ---------------------------------------------------------------------------

if [[ "$SYSTEM_INSTALL" != true ]]; then
    case ":${PATH}:" in
        *":${INSTALL_DIR}:"*) ;;
        *)
            SHELL_RC=""
            if [[ -n "${SHELL:-}" ]]; then
                case "$(basename "$SHELL")" in
                    bash) SHELL_RC="${HOME}/.bashrc" ;;
                    zsh)  SHELL_RC="${HOME}/.zshrc" ;;
                esac
            fi

            if [[ -z "$SHELL_RC" ]]; then
                if [[ -f "${HOME}/.bashrc" ]]; then
                    SHELL_RC="${HOME}/.bashrc"
                elif [[ -f "${HOME}/.zshrc" ]]; then
                    SHELL_RC="${HOME}/.zshrc"
                fi
            fi

            if [[ "$DRY_RUN" == true ]]; then
                if [[ -n "$SHELL_RC" ]]; then
                    info "Would append ${INSTALL_DIR} to PATH in ${SHELL_RC}"
                else
                    info "Would add ${INSTALL_DIR} to PATH (no shell rc file found)"
                fi
            else
                if [[ -n "$SHELL_RC" ]]; then
                    info "Adding ${INSTALL_DIR} to PATH in ${SHELL_RC}"
                    echo "export PATH=\"${INSTALL_DIR}:\$PATH\"" >> "$SHELL_RC"
                else
                    warn "Could not detect shell rc file. Add this to your shell profile:"
                    warn "  export PATH=\"${INSTALL_DIR}:\$PATH\""
                fi
            fi
            ;;
    esac
fi

# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------

if [[ "$DRY_RUN" == true ]]; then
    echo ""
    echo "Dry run complete. Run without --dry-run to install."
    exit 0
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ ${SCRIPT_NAME} installed successfully"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Location: ${INSTALL_PATH}"
echo ""
echo "  Quick start:"
echo "    ${SCRIPT_NAME} apply ./examples/basic-workspace"
echo "    ${SCRIPT_NAME} dump ./exported-template"
echo "    ${SCRIPT_NAME} clone --from-name \"Source\" --to-name \"Target\" --create-workspace"
echo "    ${SCRIPT_NAME} update"
echo ""

if [[ "$SYSTEM_INSTALL" != true ]]; then
    case ":${PATH}:" in
        *":${INSTALL_DIR}:"*)
            echo "  ${SCRIPT_NAME} is ready to use."
            ;;
        *)
            echo "  Restart your terminal or run: source ${SHELL_RC:-your shell rc file}"
            ;;
    esac
fi

echo ""
