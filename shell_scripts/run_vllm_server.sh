#!/bin/bash

# Script to start the local vLLM server using settings from config/vllm_server.yaml

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
CONFIG_FILE="${WORKSPACE_DIR}/config/vllm_server.yaml"
ENV_FILE="${WORKSPACE_DIR}/.env"

# shellcheck source=lib_common.sh
source "${SCRIPT_DIR}/lib_common.sh"

# -----------------------------------------------------------------------------
# Convert a string to lowercase
# -----------------------------------------------------------------------------
to_lower() {
    echo "$1" | tr '[:upper:]' '[:lower:]'
}

# -----------------------------------------------------------------------------
# Check if the vLLM server is currently running
# -----------------------------------------------------------------------------
is_server_running() {
    local host="$1"
    local port="$2"

    if curl -fsS "http://${host}:${port}/health" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# -----------------------------------------------------------------------------
# Stop any running vLLM server process
# -----------------------------------------------------------------------------
stop_existing_server() {
    log_info "Stopping any existing vLLM server process..."
    pkill -f "vllm.entrypoints.openai.api_server" > /dev/null 2>&1 || true
    sleep 2
}

# -----------------------------------------------------------------------------
# Wait for the server to become responsive
# -----------------------------------------------------------------------------
wait_for_server() {
    local host="$1"
    local port="$2"
    local timeout="$3"
    local elapsed=0

    log_info "Waiting up to ${timeout} seconds for the server to respond..."
    while [ "${elapsed}" -lt "${timeout}" ]; do
        if curl -fsS "http://${host}:${port}/health" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

# -----------------------------------------------------------------------------
# Check if the model is already cached locally
# -----------------------------------------------------------------------------
is_model_downloaded() {
    local model="$1"
    local download_dir="$2"

    local normalized_model
    normalized_model=$(echo "${model}" | sed 's/\//--/g')

    # Hugging Face cache format (legacy and new hf CLI layout)
    if [ -d "${download_dir}/models--${normalized_model}" ]; then
        return 0
    fi

    # Direct download layout used by hf CLI
    if [ -d "${download_dir}/${model}" ]; then
        return 0
    fi

    return 1
}

# -----------------------------------------------------------------------------
# Download the model if it is not already cached
# -----------------------------------------------------------------------------
ensure_model_available() {
    local model="$1"
    local download_dir="$2"

    log_info "Checking if model '${model}' is already downloaded..."

    if is_model_downloaded "${model}" "${download_dir}"; then
        log_ok "Model '${model}' is already downloaded."
        return 0
    fi

    log_info "Model '${model}' not found locally. Downloading now..."
    ensure_directory "${download_dir}"

    # Prefer the new Hugging Face CLI if available
    if command -v hf &> /dev/null; then
        log_info "Using hf CLI to download the model..."
        if [ -n "${HF_TOKEN:-}" ]; then
            HF_TOKEN="${HF_TOKEN}" hf download "${model}" --local-dir "${download_dir}/${model}"
        else
            hf download "${model}" --local-dir "${download_dir}/${model}"
        fi
    elif command -v huggingface-cli &> /dev/null; then
        log_info "Using huggingface-cli to download the model..."
        local token_arg=""
        if [ -n "${HF_TOKEN:-}" ]; then
            token_arg="--token ${HF_TOKEN}"
        fi
        # shellcheck disable=SC2086
        huggingface-cli download "${model}" --cache-dir "${download_dir}" ${token_arg}
    else
        log_warn "No Hugging Face CLI found. Skipping pre-download."
        log_warn "vLLM will attempt to download the model on startup."
        return 0
    fi

    if is_model_downloaded "${model}" "${download_dir}"; then
        log_ok "Model '${model}' was downloaded successfully."
    else
        log_warn "Model '${model}' could not be verified after download."
        log_warn "vLLM will attempt to download it on startup if needed."
    fi
}

# -----------------------------------------------------------------------------
# Apply GPU-related environment variables based on configuration
# -----------------------------------------------------------------------------
apply_gpu_env() {
    local visible_devices="$1"

    if [ -n "${visible_devices}" ]; then
        export CUDA_VISIBLE_DEVICES="${visible_devices}"
        log_info "Visible GPU devices set to: ${visible_devices}"
    fi
}

# -----------------------------------------------------------------------------
# Build the vLLM server command from configuration
# -----------------------------------------------------------------------------
build_server_command() {
    local model="$1"
    local host="$2"
    local port="$3"
    local dtype="$4"
    local tensor_parallel_size="$5"
    local gpu_memory_utilization="$6"
    local max_model_len="$7"
    local download_dir="$8"
    local trust_remote_code="$9"
    local seed="${10}"

    local cmd="python -m vllm.entrypoints.openai.api_server"
    cmd="${cmd} --model ${model}"
    cmd="${cmd} --host ${host}"
    cmd="${cmd} --port ${port}"
    cmd="${cmd} --dtype ${dtype}"
    cmd="${cmd} --tensor-parallel-size ${tensor_parallel_size}"
    cmd="${cmd} --gpu-memory-utilization ${gpu_memory_utilization}"
    cmd="${cmd} --max-model-len ${max_model_len}"
    cmd="${cmd} --download-dir ${download_dir}"
    cmd="${cmd} --seed ${seed}"

    if [ "$(to_lower "${trust_remote_code}")" = "true" ]; then
        cmd="${cmd} --trust-remote-code"
    fi

    echo "${cmd}"
}

# -----------------------------------------------------------------------------
# Start the vLLM server in the background
# -----------------------------------------------------------------------------
start_server_background() {
    local host="$1"
    local port="$2"
    local log_file="$3"
    local startup_timeout="$4"
    local server_command="$5"

    ensure_directory "$(dirname "${log_file}")"

    log_info "Starting vLLM server in the background on ${host}:${port}..."
    # shellcheck disable=SC2086
    nohup ${server_command} > "${log_file}" 2>&1 &

    if wait_for_server "${host}" "${port}" "${startup_timeout}"; then
        log_ok "vLLM server is running in the background on ${host}:${port}."
        log_info "Log file: ${log_file}"
    else
        log_error "vLLM server did not become responsive within ${startup_timeout} seconds."
        log_info "Check the log file for details: ${log_file}"
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Start the vLLM server in the foreground
# -----------------------------------------------------------------------------
start_server_foreground() {
    local host="$1"
    local port="$2"
    local startup_timeout="$3"
    local server_command="$4"

    log_info "Starting vLLM server in foreground on ${host}:${port}..."
    log_info "Press Ctrl+C or close the terminal to stop."

    # shellcheck disable=SC2086
    ${server_command} &
    local server_pid=$!
    trap 'kill "${server_pid}" 2>/dev/null || true; wait "${server_pid}" 2>/dev/null || true; log_info "vLLM server stopped."; exit' INT TERM EXIT

    if wait_for_server "${host}" "${port}" "${startup_timeout}"; then
        log_ok "vLLM server is ready on ${host}:${port}."
    else
        log_error "vLLM server did not become responsive within ${startup_timeout} seconds."
        exit 1
    fi

    wait "${server_pid}"
}

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  vLLM server launcher"
    echo "============================================================"

    if [ ! -f "${CONFIG_FILE}" ]; then
        log_error "Configuration file not found: ${CONFIG_FILE}"
        exit 1
    fi
    log_info "Using configuration file: ${CONFIG_FILE}"

    load_env_file "${ENV_FILE}"

    local conda_env model host port dtype tensor_parallel_size gpu_memory_utilization max_model_len download_dir trust_remote_code seed
    local visible_devices background log_file startup_timeout force_restart
    conda_env="${CONDA_ENV:-}"
    model=$(read_yaml_value "${CONFIG_FILE}" "model" "microsoft/Phi-3-mini-4k-instruct")
    host=$(read_yaml_value "${CONFIG_FILE}" "host" "127.0.0.1")
    port=$(read_yaml_value "${CONFIG_FILE}" "port" "8000")
    dtype=$(read_yaml_value "${CONFIG_FILE}" "dtype" "auto")
    tensor_parallel_size=$(read_yaml_value "${CONFIG_FILE}" "tensor_parallel_size" "1")
    gpu_memory_utilization=$(read_yaml_value "${CONFIG_FILE}" "gpu_memory_utilization" "0.9")
    max_model_len=$(read_yaml_value "${CONFIG_FILE}" "max_model_len" "4096")
    download_dir=$(read_yaml_value "${CONFIG_FILE}" "download_dir" "models/vllm")
    trust_remote_code=$(read_yaml_value "${CONFIG_FILE}" "trust_remote_code" "true")
    seed=$(read_yaml_value "${CONFIG_FILE}" "seed" "42")
    visible_devices=$(read_yaml_value "${CONFIG_FILE}" "visible_devices" "")
    background=$(read_yaml_value "${CONFIG_FILE}" "background" "false")
    log_file=$(read_yaml_value "${CONFIG_FILE}" "log_file" "logs/vllm_server.log")
    startup_timeout=$(read_yaml_value "${CONFIG_FILE}" "startup_timeout" "60")
    force_restart=$(read_yaml_value "${CONFIG_FILE}" "force_restart" "false")

    ensure_conda_env "${conda_env}"

    # Resolve relative paths from the workspace root
    if [[ ! "${download_dir}" = /* ]]; then
        download_dir="${WORKSPACE_DIR}/${download_dir}"
    fi

    if [[ ! "${log_file}" = /* ]]; then
        log_file="${WORKSPACE_DIR}/${log_file}"
    fi

    log_info "Configured model: ${model}"
    log_info "Server address: ${host}:${port}"
    log_info "Download directory: ${download_dir}"
    log_info "Tensor parallelism: ${tensor_parallel_size} GPU(s)"

    show_gpu_info
    apply_gpu_env "${visible_devices}"
    ensure_model_available "${model}" "${download_dir}"

    if is_server_running "${host}" "${port}"; then
        if [ "${force_restart}" = "true" ]; then
            log_warn "vLLM server is already running. Force restart is enabled."
            stop_existing_server
        else
            log_error "vLLM server is already running on ${host}:${port}."
            log_error "Stop it first or enable force_restart in ${CONFIG_FILE}."
            exit 1
        fi
    fi

    local server_command
    server_command=$(build_server_command \
        "${model}" "${host}" "${port}" "${dtype}" "${tensor_parallel_size}" \
        "${gpu_memory_utilization}" "${max_model_len}" "${download_dir}" \
        "${trust_remote_code}" "${seed}")

    log_info "Server command: ${server_command}"

    if [ "${background}" = "true" ]; then
        start_server_background \
            "${host}" "${port}" "${log_file}" "${startup_timeout}" "${server_command}"
    else
        start_server_foreground \
            "${host}" "${port}" "${startup_timeout}" "${server_command}"
    fi
}

main "$@"
