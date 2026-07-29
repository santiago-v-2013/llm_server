#!/bin/bash
# Common utility functions shared across all project shell scripts.
#
# Usage from shell_scripts/:
#   source "$(dirname "${BASH_SOURCE[0]}")/lib_common.sh"
#
# Usage from pipelines/:
#   source "${WORKSPACE_DIR}/shell_scripts/lib_common.sh"

# ---------------------------------------------------------------------------
# Terminal colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------
log_info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
log_ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARNING]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------------------------------------------------------------------------
# read_yaml_value <config_file> <key> [default]
# Read a scalar value from a YAML file by key name (section-unaware).
# Use only when key names are unique across the entire file.
# ---------------------------------------------------------------------------
read_yaml_value() {
    local config_file="$1"
    local key="$2"
    local default_value="${3:-}"

    if [ ! -f "${config_file}" ]; then
        echo "${default_value}"
        return
    fi

    local value
    value=$(grep -E "^\s*${key}\s*:" "${config_file}" | head -n 1 \
        | sed -E "s/^\s*${key}\s*:\s*//" | sed -E "s/^(\"|'|)(.*)\1$/\2/")

    if [ -z "${value}" ]; then
        echo "${default_value}"
    else
        echo "${value}"
    fi
}

# ---------------------------------------------------------------------------
# read_yaml_section_value <config_file> <section> <key> [default]
# Read a scalar value from a specific YAML section (section-aware).
# ---------------------------------------------------------------------------
read_yaml_section_value() {
    local config_file="$1"
    local section="$2"
    local key="$3"
    local default_value="${4:-}"

    python3 - "${config_file}" "${section}" "${key}" "${default_value}" << 'PY'
import sys
config_path, section, key, default_value = sys.argv[1:5]
current_section = None
value = default_value
with open(config_path, "r", encoding="utf-8") as f:
    for line in f:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and stripped.endswith(":"):
            current_section = stripped[:-1].strip()
            continue
        if current_section == section and ":" in stripped:
            parts = stripped.split(":", 1)
            if parts[0].strip() == key:
                value = parts[1].strip().strip('"').strip("'")
                break
print(value)
PY
}

# ---------------------------------------------------------------------------
# load_env_file <env_file>
# Source a .env file into the current shell environment.
# ---------------------------------------------------------------------------
load_env_file() {
    local env_file="$1"
    if [ -f "${env_file}" ]; then
        log_info "Loading environment variables from ${env_file}"
        set -a
        # shellcheck source=/dev/null
        source "${env_file}"
        set +a
    fi
}

# ---------------------------------------------------------------------------
# ensure_directory <path>
# Create a directory and all parents if it does not already exist.
# ---------------------------------------------------------------------------
ensure_directory() {
    local dir_path="$1"
    if [ ! -d "${dir_path}" ]; then
        log_info "Creating directory: ${dir_path}"
        mkdir -p "${dir_path}"
    fi
}

# ---------------------------------------------------------------------------
# show_gpu_info
# Print detected NVIDIA GPU information when nvidia-smi is available.
# ---------------------------------------------------------------------------
show_gpu_info() {
    if command -v nvidia-smi &> /dev/null; then
        log_info "NVIDIA GPUs detected:"
        nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader | sed 's/^/  /'
    else
        log_warn "nvidia-smi not found. GPU information is unavailable."
    fi
}

# ---------------------------------------------------------------------------
# ensure_conda_env <env_name> [create_if_missing=false]
# Activate the given Conda environment.
# If create_if_missing=true, creates the environment when it does not exist.
# ---------------------------------------------------------------------------
ensure_conda_env() {
    local conda_env="$1"
    local create_if_missing="${2:-false}"

    if [ -z "${conda_env}" ]; then
        log_info "No Conda environment configured. Using active Python interpreter."
        return 0
    fi

    if ! command -v conda &> /dev/null; then
        log_error "Conda is required but not found in PATH."
        exit 1
    fi

    if [ "${CONDA_DEFAULT_ENV:-}" = "${conda_env}" ]; then
        log_info "Conda environment '${conda_env}' is already active."
        return 0
    fi

    if conda env list | grep -q "^${conda_env}\s"; then
        log_info "Activating Conda environment '${conda_env}'..."
        # shellcheck source=/dev/null
        eval "$(conda shell.bash hook)"
        conda activate "${conda_env}"
    elif [ "${create_if_missing}" = "true" ]; then
        log_info "Conda environment '${conda_env}' not found. Creating it..."
        # shellcheck source=/dev/null
        eval "$(conda shell.bash hook)"
        conda create -y -n "${conda_env}" python=3.11
        conda activate "${conda_env}"
    else
        log_error "Conda environment '${conda_env}' not found."
        log_error "Run ./shell_scripts/install_vllm.sh to create it first."
        exit 1
    fi
}
