#!/bin/bash
# Project cleanup script
# This script cleans up temporary files, build artifacts, and logs.

set -e

# ANSI color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Starting project cleanup...${NC}"

# --- Define Project Root ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Change to Project Root ---
cd "$PROJECT_ROOT"
echo -e "${YELLOW}ℹ️ Changed working directory to project root: $PROJECT_ROOT${NC}"

# 1. Use hatch clean for standard Hatch artifacts
echo -e "${YELLOW}Running 'hatch clean' to remove build artifacts and caches...${NC}"
hatch clean
echo -e "${GREEN}✓ Hatch clean completed.${NC}"

# 2. Clean project-specific log directories
#    We want to remove all files and subdirectories within these, but keep the directories themselves
#    and any .gitignore files.
LOG_DIRS_TO_CLEAN=(
    "logs/mcp"
    "logs/runtime"
    "logs/tests/coverage"
    "logs/tests/junit"
    # Add other log subdirectories here if needed
)

echo -e "${YELLOW}Cleaning project log directories...${NC}"
for log_dir_to_clean in "${LOG_DIRS_TO_CLEAN[@]}"; do
    if [ -d "$log_dir_to_clean" ]; then
        echo "   Cleaning contents of $log_dir_to_clean/"
        # Find all files and directories within, excluding .gitignore, and remove them.
        # This is safer than rm -rf $log_dir_to_clean/* to avoid issues with globs and hidden files
        find "$log_dir_to_clean" -mindepth 1 -not -name '.gitignore' -delete
        echo -e "${GREEN}   ✓ Contents of $log_dir_to_clean/ cleaned.${NC}"
    else
        echo -e "${YELLOW}   ℹ️ Log directory $log_dir_to_clean/ not found, skipping.${NC}"
    fi
done

# 3. Clean project-wide __pycache__ and .pyc files (Hatch might get these, but being explicit doesn't hurt)
echo -e "${YELLOW}Cleaning Python cache files (__pycache__, *.pyc)...${NC}"
find . -path '*/__pycache__/*' -delete # Delete contents of __pycache__ folders
find . -type d -name "__pycache__" -empty -delete # Delete empty __pycache__ folders
find . -name "*.pyc" -delete
echo -e "${GREEN}✓ Python cache files cleaned.${NC}"

# 4. Remove .coverage files from project root (if any are created there by mistake)
if [ -f ".coverage" ]; then
    echo -e "${YELLOW}Removing .coverage file from project root...${NC}"
    rm -f .coverage
    echo -e "${GREEN}✓ .coverage file removed.${NC}"
fi
# And any .coverage.* files (from parallel runs if not correctly placed)
find . -maxdepth 1 -name ".coverage.*" -delete


echo -e "${GREEN}Project cleanup completed successfully!${NC}" 