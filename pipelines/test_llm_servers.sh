#!/bin/bash

# Pipeline to test that a configured local LLM server is running.
#
# This pipeline:
#   1. Reads the active server type from config/llm_client.yaml.
#   2. Waits for the server to become responsive.
#   3. Runs scripts/run_llm_query.py to send a test request.
#
# The server must be started separately before running this pipeline,
# for example with ./pipelines/run_ollama_pipeline.sh or
# ./pipelines/run_vllm_pipeline.sh.

set -euo pipefail

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PIPELINE_NAME="$(basename "${BASH_SOURCE[0]}" .sh)"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_DIR="${WORKSPACE_DIR}/logs"
LOG_FILE="${LOG_DIR}/${PIPELINE_NAME}_${TIMESTAMP}.log"
CONFIG_FILE="${WORKSPACE_DIR}/config/llm_client.yaml"

# shellcheck source=../shell_scripts/lib_common.sh
source "${WORKSPACE_DIR}/shell_scripts/lib_common.sh"
# -----------------------------------------------------------------------------
mkdir -p "${LOG_DIR}"
touch "${LOG_FILE}"

# Export the log file path so that child scripts can write to the same file
export LOG_FILE_PATH="${LOG_FILE}"

# Redirect all shell output to the log file while keeping console output
exec > >(tee -a "${LOG_FILE}")
exec 2>&1

echo "============================================================"
echo "  Starting pipeline: ${PIPELINE_NAME}"
echo "  Log file: ${LOG_FILE}"
echo "  Timestamp: ${TIMESTAMP}"
echo "============================================================"

# -----------------------------------------------------------------------------
# Read server configuration
# -----------------------------------------------------------------------------
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "[ERROR] Configuration file not found: ${CONFIG_FILE}"
    exit 1
fi

SERVER_TYPE=$(read_yaml_value "${CONFIG_FILE}" "server_type" "")

if [ -z "${SERVER_TYPE}" ]; then
    echo "[ERROR] server_type not defined in ${CONFIG_FILE}"
    exit 1
fi

echo "[INFO] Testing server type: ${SERVER_TYPE}"

# -----------------------------------------------------------------------------
# Determine health endpoint based on server type
# -----------------------------------------------------------------------------
if [ "${SERVER_TYPE}" = "ollama" ]; then
    HOST=$(read_yaml_section_value "${CONFIG_FILE}" "ollama" "host" "127.0.0.1")
    PORT=$(read_yaml_section_value "${CONFIG_FILE}" "ollama" "port" "11434")
    HEALTH_URL="http://${HOST}:${PORT}/"
elif [ "${SERVER_TYPE}" = "vllm" ]; then
    HOST=$(read_yaml_section_value "${CONFIG_FILE}" "vllm" "host" "127.0.0.1")
    PORT=$(read_yaml_section_value "${CONFIG_FILE}" "vllm" "port" "8000")
    HEALTH_URL="http://${HOST}:${PORT}/health"
else
    echo "[ERROR] Unsupported server type: ${SERVER_TYPE}"
    exit 1
fi

echo "[INFO] Server address: ${HOST}:${PORT}"

# -----------------------------------------------------------------------------
# Wait for the server to become responsive
# -----------------------------------------------------------------------------
TIMEOUT=60
ELAPSED=0
echo "[INFO] Waiting up to ${TIMEOUT} seconds for the server to respond..."

while [ "${ELAPSED}" -lt "${TIMEOUT}" ]; do
    if curl -fsS "${HEALTH_URL}" > /dev/null 2>&1; then
        echo "[OK] Server is responsive at ${HOST}:${PORT}."
        break
    fi
    sleep 1
    ELAPSED=$((ELAPSED + 1))
done

if [ "${ELAPSED}" -ge "${TIMEOUT}" ]; then
    echo "[ERROR] Server did not become responsive within ${TIMEOUT} seconds."
    echo "[INFO] Make sure the server is running. Example:"
    echo "       ./pipelines/run_${SERVER_TYPE}_pipeline.sh"
    exit 1
fi

# -----------------------------------------------------------------------------
# Send a test request through the unified Python client
# -----------------------------------------------------------------------------
echo ""
echo "[STEP] Sending test request via scripts/run_llm_query.py..."
cd "${WORKSPACE_DIR}"
python scripts/run_llm_query.py

echo ""
echo "[OK] LLM server test completed successfully."
