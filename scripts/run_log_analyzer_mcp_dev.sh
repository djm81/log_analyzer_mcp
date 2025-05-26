#!/bin/bash
# Add known location of user-installed bins to PATH
# export PATH="/usr/local/bin:$PATH" # Adjust path as needed - REMOVED
set -euo pipefail
# Run log_analyzer_mcp_server using Hatch for development

# --- Define Project Root ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Change to Project Root ---
cd "$PROJECT_ROOT"
# Don't print the working directory change as it will break the MCP server integration here
echo "{\"info\": \"Changed working directory to project root: $PROJECT_ROOT\"}" >> logs/run_log_analyzer_mcp_dev.log

# Install hatch if not installed
if ! command -v hatch &> /dev/null; then
    echo "{\"warning\": \"Hatch not found. Installing now...\"}"
    pip install --user hatch # Consider if this is the best approach for your environment
fi

# Ensure logs directory exists
mkdir -p "$PROJECT_ROOT/logs"

# --- Set Environment Variables ---
export PYTHONUNBUFFERED=1
# export PROJECT_LOG_DIR="$PROJECT_ROOT/logs" # Server should ideally use relative paths or be configurable
export MCP_SERVER_LOG_LEVEL="${MCP_SERVER_LOG_LEVEL:-INFO}" # Server code should respect this

# --- Run the Server ---
echo "{\"info\": \"Starting log_analyzer_mcp_server with PYTHONUNBUFFERED=1 and MCP_SERVER_LOG_LEVEL=$MCP_SERVER_LOG_LEVEL\"}" >> logs/run_log_analyzer_mcp_dev.log
# The actual command will depend on how you define the run script in pyproject.toml
# Example: exec hatch run dev:start-server
# For now, assuming a script named 'start-dev-server' in default env or a 'dev' env
echo "{\"info\": \"Executing: hatch run start-dev-server\"}" >> logs/run_log_analyzer_mcp_dev.log
exec hatch run start-dev-server