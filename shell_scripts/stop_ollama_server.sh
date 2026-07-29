#!/bin/bash

# Script to stop a running local Ollama server.
# This is useful for pipelines or when the server was started in the background.

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
# Configuration paths
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
CONFIG_FILE="${WORKSPACE_DIR}/config/ollama_server.yaml"

# shellcheck source=lib_common.sh
source "${SCRIPT_DIR}/lib_common.sh"

# -----------------------------------------------------------------------------
# Check if the Ollama server is currently running
# -----------------------------------------------------------------------------
is_server_running() {
    local host="$1"
    local port="$2"

    if curl -fsS "http://${host}:${port}/" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Stop the Ollama server process
# -----------------------------------------------------------------------------
stop_server() {
    log_info "Stopping Ollama server..."

    if pkill -x "ollama" > /dev/null 2>&1; then
        sleep 2
        log_ok "Ollama server process stopped."
    else
        log_warn "No Ollama server process was found."
    fi
}

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  Ollama server stopper"
    echo "============================================================"

    local host port

    if [ -f "${CONFIG_FILE}" ]; then
        log_info "Using configuration file: ${CONFIG_FILE}"
        host=$(read_yaml_value "${CONFIG_FILE}" "host" "127.0.0.1")
        port=$(read_yaml_value "${CONFIG_FILE}" "port" "11434")
    else
        log_warn "Configuration file not found: ${CONFIG_FILE}"
        log_warn "Using default values: 127.0.0.1:11434"
        host="127.0.0.1"
        port="11434"
    fi

    if is_server_running "${host}" "${port}"; then
        log_info "Ollama server is running on ${host}:${port}."
        stop_server
    else
        log_warn "Ollama server is not running on ${host}:${port}."
    fi
}

main "$@"
