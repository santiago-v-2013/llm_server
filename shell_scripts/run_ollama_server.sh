#!/bin/bash

# Script to start the local Ollama server using settings from config/ollama_server.yaml
# The configured model is downloaded automatically if it is not already present.

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
# Stop any running Ollama server process
# -----------------------------------------------------------------------------
stop_existing_server() {
    log_info "Stopping any existing Ollama server process..."
    pkill -x "ollama" > /dev/null 2>&1 || true
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
        if curl -fsS "http://${host}:${port}/" > /dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done

    return 1
}

# -----------------------------------------------------------------------------
# Send a warm-up request to force the model into RAM/VRAM
# -----------------------------------------------------------------------------
warm_up_model() {
    local model="$1"
    local host="$2"
    local port="$3"
    local prompt="$4"

    log_info "Warming up model '${model}' by sending an initial request..."

    local response
    response=$(curl -fsS "http://${host}:${port}/api/generate" \
        -d "{\"model\": \"${model}\", \"prompt\": \"${prompt}\", \"stream\": false}" \
        2>/dev/null | python3 -c "import sys, json; print(json.load(sys.stdin).get('response', '').strip())" 2>/dev/null || true)

    if [ -n "${response}" ]; then
        log_ok "Model '${model}' is warmed up and loaded into memory."
    else
        log_warn "Warm-up request did not return a response. The model may still load on first use."
    fi
}

# -----------------------------------------------------------------------------
# Apply Ollama environment variables
# -----------------------------------------------------------------------------
apply_ollama_env() {
    local host="$1"
    local port="$2"
    local models_dir="$3"
    local tmp_dir="$4"
    local origin="$5"
    local keep_alive="${6:-}"

    export OLLAMA_HOST="${host}:${port}"

    if [ -n "${models_dir}" ]; then
        export OLLAMA_MODELS="${models_dir}"
    fi

    if [ -n "${tmp_dir}" ]; then
        export OLLAMA_TMPDIR="${tmp_dir}"
    fi

    if [ -n "${origin}" ]; then
        export OLLAMA_ORIGINS="${origin}"
    fi

    if [ -n "${keep_alive}" ]; then
        export OLLAMA_KEEP_ALIVE="${keep_alive}"
    fi
}

# -----------------------------------------------------------------------------
# Apply GPU-related environment variables based on configuration
# -----------------------------------------------------------------------------
apply_gpu_env() {
    local use_gpu="$1"
    local visible_devices="$2"
    local max_loaded_models="$3"
    local num_parallel="$4"

    if [ "${use_gpu}" = "true" ]; then
        log_info "GPU acceleration is enabled."

        if [ -n "${visible_devices}" ]; then
            export CUDA_VISIBLE_DEVICES="${visible_devices}"
            export HIP_VISIBLE_DEVICES="${visible_devices}"
            log_info "Visible GPU devices set to: ${visible_devices}"
        fi
    else
        log_info "GPU acceleration is disabled. CPU inference will be used."
        export OLLAMA_NO_GPU="1"
        export CUDA_VISIBLE_DEVICES=""
        export HIP_VISIBLE_DEVICES=""
    fi

    if [ -n "${max_loaded_models}" ]; then
        export OLLAMA_MAX_LOADED_MODELS="${max_loaded_models}"
    fi

    if [ -n "${num_parallel}" ]; then
        export OLLAMA_NUM_PARALLEL="${num_parallel}"
    fi
}

# -----------------------------------------------------------------------------
# Download the configured model if it is not already present
# -----------------------------------------------------------------------------
ensure_model_available() {
    local model="$1"
    local host="$2"
    local port="$3"

    log_info "Checking if model '${model}' is already downloaded..."

    if ollama list | tail -n +2 | awk '{print $1}' | grep -Eq "^${model}(:|$)"; then
        log_ok "Model '${model}' is already downloaded."
    else
        log_info "Model '${model}' not found. Downloading now..."
        OLLAMA_HOST="${host}:${port}" ollama pull "${model}"
        log_ok "Model '${model}' was downloaded successfully."
    fi
}

# -----------------------------------------------------------------------------
# Start a temporary Ollama server, download the model, and stop it
# -----------------------------------------------------------------------------
prepare_model_with_temp_server() {
    local host="$1"
    local port="$2"
    local models_dir="$3"
    local tmp_dir="$4"
    local origin="$5"
    local keep_alive="$6"
    local startup_timeout="$7"
    local model="$8"
    local server_pid

    apply_ollama_env "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" "${keep_alive}"

    log_info "Starting temporary Ollama server on ${host}:${port}..."
    ollama serve > /dev/null 2>&1 &
    server_pid=$!

    if ! wait_for_server "${host}" "${port}" "${startup_timeout}"; then
        log_error "Temporary Ollama server did not become responsive."
        kill "${server_pid}" 2>/dev/null || true
        wait "${server_pid}" 2>/dev/null || true
        exit 1
    fi

    ensure_model_available "${model}" "${host}" "${port}"

    log_info "Stopping temporary Ollama server..."
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
}

# -----------------------------------------------------------------------------
# Start the Ollama server in the background
# -----------------------------------------------------------------------------
start_server_background() {
    local host="$1"
    local port="$2"
    local models_dir="$3"
    local tmp_dir="$4"
    local origin="$5"
    local keep_alive="$6"
    local log_file="$7"
    local startup_timeout="$8"
    local warm_up_model_enabled="$9"
    local warm_up_prompt="${10}"
    local model="${11}"

    apply_ollama_env "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" "${keep_alive}"

    ensure_directory "$(dirname "${log_file}")"

    log_info "Starting Ollama server in the background on ${host}:${port}..."
    nohup ollama serve > "${log_file}" 2>&1 &

    if wait_for_server "${host}" "${port}" "${startup_timeout}"; then
        log_ok "Ollama server is running in the background on ${host}:${port}."
        log_info "Log file: ${log_file}"
    else
        log_error "Ollama server did not become responsive within ${startup_timeout} seconds."
        log_info "Check the log file for details: ${log_file}"
        exit 1
    fi

    if [ "${warm_up_model_enabled}" = "true" ]; then
        warm_up_model "${model}" "${host}" "${port}" "${warm_up_prompt}"
    fi
}

# -----------------------------------------------------------------------------
# Start the Ollama server in the foreground
# -----------------------------------------------------------------------------
start_server_foreground() {
    local host="$1"
    local port="$2"
    local models_dir="$3"
    local tmp_dir="$4"
    local origin="$5"
    local keep_alive="$6"
    local warm_up_model_enabled="$7"
    local warm_up_prompt="$8"
    local model="$9"

    apply_ollama_env "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" "${keep_alive}"

    log_info "Starting Ollama server in foreground on ${host}:${port}..."
    log_info "Press Ctrl+C or close the terminal to stop."

    ollama serve &
    local server_pid=$!
    trap 'kill "${server_pid}" 2>/dev/null || true; wait "${server_pid}" 2>/dev/null || true; log_info "Ollama server stopped."; exit' INT TERM EXIT

    if wait_for_server "${host}" "${port}" "10"; then
        if [ "${warm_up_model_enabled}" = "true" ]; then
            warm_up_model "${model}" "${host}" "${port}" "${warm_up_prompt}"
        fi
    else
        log_error "Ollama server did not become responsive after starting."
        exit 1
    fi

    wait "${server_pid}"
}

# -----------------------------------------------------------------------------
# Main program
# -----------------------------------------------------------------------------
main() {
    echo "============================================================"
    echo "  Ollama server launcher"
    echo "============================================================"

    if [ ! -f "${CONFIG_FILE}" ]; then
        log_error "Configuration file not found: ${CONFIG_FILE}"
        exit 1
    fi
    log_info "Using configuration file: ${CONFIG_FILE}"

    # Read settings from the YAML configuration file
    local model host port models_dir tmp_dir origin use_gpu visible_devices max_loaded_models num_parallel background log_file startup_timeout force_restart keep_alive warm_up_model warm_up_prompt
    model=$(read_yaml_value "${CONFIG_FILE}" "model" "llama3.1")
    host=$(read_yaml_value "${CONFIG_FILE}" "host" "127.0.0.1")
    port=$(read_yaml_value "${CONFIG_FILE}" "port" "11434")
    models_dir=$(read_yaml_value "${CONFIG_FILE}" "models_dir" "models/ollama")
    tmp_dir=$(read_yaml_value "${CONFIG_FILE}" "tmp_dir" "")
    origin=$(read_yaml_value "${CONFIG_FILE}" "origin" "")
    use_gpu=$(read_yaml_value "${CONFIG_FILE}" "use_gpu" "true")
    visible_devices=$(read_yaml_value "${CONFIG_FILE}" "visible_devices" "")
    max_loaded_models=$(read_yaml_value "${CONFIG_FILE}" "max_loaded_models" "")
    num_parallel=$(read_yaml_value "${CONFIG_FILE}" "num_parallel" "")
    background=$(read_yaml_value "${CONFIG_FILE}" "background" "false")
    log_file=$(read_yaml_value "${CONFIG_FILE}" "log_file" "logs/ollama_server.log")
    startup_timeout=$(read_yaml_value "${CONFIG_FILE}" "startup_timeout" "10")
    force_restart=$(read_yaml_value "${CONFIG_FILE}" "force_restart" "false")
    keep_alive=$(read_yaml_value "${CONFIG_FILE}" "keep_alive" "30m")
    warm_up_model=$(read_yaml_value "${CONFIG_FILE}" "warm_up_model" "false")
    warm_up_prompt=$(read_yaml_value "${CONFIG_FILE}" "warm_up_prompt" "Say 'ready' and nothing else.")

    # Resolve relative paths from the workspace root
    if [[ ! "${models_dir}" = /* ]]; then
        models_dir="${WORKSPACE_DIR}/${models_dir}"
    fi

    if [[ ! "${log_file}" = /* ]]; then
        log_file="${WORKSPACE_DIR}/${log_file}"
    fi

    log_info "Configured model: ${model}"
    log_info "Server address: ${host}:${port}"
    log_info "Models directory: ${models_dir}"
    log_info "Keep-alive duration: ${keep_alive}"

    if [ "${warm_up_model}" = "true" ]; then
        log_info "Model warm-up is enabled."
    fi

    show_gpu_info
    apply_gpu_env "${use_gpu}" "${visible_devices}" "${max_loaded_models}" "${num_parallel}"

    ensure_directory "${models_dir}"

    if is_server_running "${host}" "${port}"; then
        if [ "${force_restart}" = "true" ]; then
            log_warn "Ollama server is already running. Force restart is enabled."
            stop_existing_server
        else
            log_error "Ollama server is already running on ${host}:${port}."
            log_error "Stop it first or enable force_restart in ${CONFIG_FILE}."
            exit 1
        fi
    fi

    # Download the model if needed using a temporary server instance
    prepare_model_with_temp_server \
        "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" \
        "${keep_alive}" "${startup_timeout}" "${model}"

    # Start the final server
    if [ "${background}" = "true" ]; then
        start_server_background \
            "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" \
            "${keep_alive}" "${log_file}" "${startup_timeout}" \
            "${warm_up_model}" "${warm_up_prompt}" "${model}"
    else
        start_server_foreground \
            "${host}" "${port}" "${models_dir}" "${tmp_dir}" "${origin}" \
            "${keep_alive}" "${warm_up_model}" "${warm_up_prompt}" "${model}"
    fi
}

main "$@"
