#!/bin/bash

# Script to check and install Ollama on Linux systems

set -euo pipefail

# -----------------------------------------------------------------------------
# Pipeline log redirection
# -----------------------------------------------------------------------------
# If this script is called from a pipeline that defines LOG_FILE_PATH,
# redirect all output to that log file while still showing it on the console.
if [ -n "${LOG_FILE_PATH:-}" ]; then
    exec > >(tee -a "${LOG_FILE_PATH}")
    exec 2>&1
fi

# -----------------------------------------------------------------------------
# Common utilities
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib_common.sh
source "${SCRIPT_DIR}/lib_common.sh"

# -----------------------------------------------------------------------------
# Check if Ollama is already installed and available in PATH
# -----------------------------------------------------------------------------
check_ollama_installed() {
    if command -v ollama &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Install Ollama using the official script
# -----------------------------------------------------------------------------
install_ollama() {
    log_info "Ollama not found. Starting official installation..."
    log_info "Downloading and running the installer from ollama.com..."

    curl -fsSL https://ollama.com/install.sh | sh

    if check_ollama_installed; then
        log_ok "Ollama was installed successfully."
    else
        log_error "Ollama could not be installed correctly."
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  Ollama check and installation"
    echo "============================================================"

    if check_ollama_installed; then
        log_ok "Ollama is already installed: $(command -v ollama)"
        ollama --version
    else
        install_ollama
    fi

    echo ""
    log_ok "Ollama is installed and ready to use."
    log_info "Available models: https://ollama.com/library"
    log_info "Interactive usage example:   ollama run llama3.1"
}

main "$@"
