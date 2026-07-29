#!/bin/bash

# Pipeline to install and run the vLLM server.
#
# This pipeline:
#   1. Ensures vLLM is installed in the configured Conda environment.
#   2. Starts the vLLM server using the project's configuration.
#
# The server runs in the foreground. Press Ctrl+C or close the terminal
# to stop the server and end the pipeline.

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

# -----------------------------------------------------------------------------
# Create log directory and empty log file
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
# Pipeline steps
# -----------------------------------------------------------------------------
echo "[STEP 1] Checking / installing vLLM..."
"${WORKSPACE_DIR}/shell_scripts/install_vllm.sh"

echo ""
echo "[STEP 2] Starting vLLM server..."
"${WORKSPACE_DIR}/shell_scripts/run_vllm_server.sh"
