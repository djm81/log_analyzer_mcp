#!/bin/bash
# Build the package

# --- Define Project Root ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Change to Project Root ---
cd "$PROJECT_ROOT"
echo "ℹ️ Changed working directory to project root: $PROJECT_ROOT"

# Install hatch if not installed
if ! command -v hatch &> /dev/null; then
    echo "Hatch not found. Installing hatch..."
    pip install hatch
fi

# Clean previous builds (use relative paths now)
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info

# Format code before building
echo "Formatting code with Black via Hatch..."
hatch run black .

# Build the package
echo "Building package with Hatch..."
hatch build

echo "Build complete. Distribution files are in the 'dist' directory."
ls -la dist/ # Use relative path 