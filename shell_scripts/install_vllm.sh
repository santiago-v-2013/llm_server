#!/bin/bash

# Script to check and install vLLM inside the configured or active Conda environment

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
ENV_FILE="${WORKSPACE_DIR}/.env"

# shellcheck source=lib_common.sh
source "${SCRIPT_DIR}/lib_common.sh"

# -----------------------------------------------------------------------------
# Check if vLLM is installed in the current Python environment
# -----------------------------------------------------------------------------
check_vllm_installed() {
    if python -c "import vllm" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Install vLLM and required helpers inside the active Conda environment
# -----------------------------------------------------------------------------
install_vllm() {
    log_info "vLLM not found. Installing in the active Python environment..."

    if ! command -v conda &> /dev/null; then
        log_warn "Conda was not detected in PATH. vLLM will be installed in the active Python interpreter."
    elif [ -z "${CONDA_DEFAULT_ENV:-}" ]; then
        log_warn "No active Conda environment detected. vLLM will be installed in the active Python interpreter."
        log_warn "Activate an environment first with: conda activate <env_name>"
    else
        log_info "Active Conda environment detected: ${CONDA_DEFAULT_ENV}"
    fi

    log_info "Installing vLLM (this may take several minutes)..."
    pip install -q --upgrade vllm huggingface_hub

    if check_vllm_installed; then
        log_ok "vLLM was installed successfully."
        python -c "import vllm; print('vLLM version:', vllm.__version__)"
    else
        log_error "vLLM could not be installed correctly."
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  vLLM check and installation"
    echo "============================================================"

    load_env_file "${ENV_FILE}"

    local conda_env
    conda_env="${CONDA_ENV:-}"

    ensure_conda_env "${conda_env}" "true"

    if check_vllm_installed; then
        log_ok "vLLM is already installed."
        python -c "import vllm; print('vLLM version:', vllm.__version__)"
    else
        install_vllm
    fi

    echo ""
    log_ok "vLLM is installed and ready to use."
    log_info "Example model: microsoft/Phi-3-mini-4k-instruct"
    log_info "Example usage: ./shell_scripts/run_vllm_server.sh"
}

main "$@"
