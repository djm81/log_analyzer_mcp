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

# Synchronize version from pyproject.toml to setup.py
echo "Synchronizing version from pyproject.toml to setup.py..."
VERSION=$(hatch version)

if [ -z "$VERSION" ]; then
    echo "❌ Error: Could not extract version from pyproject.toml."
    exit 1
fi

echo "ℹ️ Version found in pyproject.toml: $VERSION"

# Update version in setup.py using sed
# This assumes setup.py has a line like: version="0.1.0",
# It will replace the content within the quotes.
sed -i.bak -E "s/(version\\s*=\\s*)\"[^\"]*\"/\\1\"$VERSION\"/" setup.py

if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to update version in setup.py."
    # Restore backup if sed failed, though modern sed -i might not need this as much
    [ -f setup.py.bak ] && mv setup.py.bak setup.py
    exit 1
fi

echo "✅ Version in setup.py updated to $VERSION"
rm -f setup.py.bak # Clean up backup file

# Build the package
echo "Building package with Hatch..."
hatch build

echo "Build complete. Distribution files are in the 'dist' directory."
ls -la dist/ # Use relative path 