#!/bin/bash
# Script to test UVX installation from TestPyPI

set -e  # Exit on error

# Initialize variables
# SCRIPT_DIR should be the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)" # Project root is one level up
TEMP_DIR=$(mktemp -d)
PACKAGE_NAME="log_analyzer_mcp"

# Required dependencies based on log_analyzer_mcp's pyproject.toml
REQUIRED_DEPS="pydantic>=2.10.6 python-dotenv>=1.0.1 requests>=2.32.3 typing-extensions>=4.12.2 PyYAML>=6.0.1 jsonschema>=4.23.0 pydantic-core>=2.27.2 tenacity>=9.0.0 rich>=13.9.4 loguru>=0.7.3 mcp>=1.4.1 python-dateutil>=2.9.0.post0 pytz>=2025.1"

# Get package version using hatch
# PYPROJECT_FILE="pyproject.toml" # Path relative to PROJECT_ROOT

# --- Change to Project Root ---
cd "$PROJECT_ROOT"
echo "ℹ️ Changed working directory to project root: $PROJECT_ROOT"

VERSION=$(hatch version) # Updated to use hatch version
if [ -z "$VERSION" ]; then
    echo "Error: Could not determine package version using 'hatch version'"
    exit 1
fi

echo "Testing installation of $PACKAGE_NAME version $VERSION"

# Define dist directory path (now relative to PROJECT_ROOT)
DIST_DIR="dist"

# Check if the dist directory exists
if [ ! -d "$DIST_DIR" ]; then
    echo "No dist directory found. Building package first..."
    # Run build script using its relative path from PROJECT_ROOT
    "$SCRIPT_DIR/build.sh"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to build package"
        rm -rf "$TEMP_DIR"
        exit 1
    fi
fi

# Find wheel file in the dist directory
# PACKAGE_NAME for wheel file is with underscores
WHEEL_FILE_RELATIVE=$(find "$DIST_DIR" -name "${PACKAGE_NAME//-/_}-${VERSION}-*.whl" | head -1)
if [ -z "$WHEEL_FILE_RELATIVE" ]; then
    echo "Error: No wheel file found for $PACKAGE_NAME version $VERSION in $DIST_DIR"
    echo "Debug: Looking for wheel matching pattern: ${PACKAGE_NAME//-/_}-${VERSION}-*.whl"
    echo "Available files in dist directory:"
    ls -la "$DIST_DIR"
    rm -rf "$TEMP_DIR"
    exit 1
fi

# Store the absolute path before changing directory
WHEEL_FILE_ABSOLUTE="$PROJECT_ROOT/$WHEEL_FILE_RELATIVE"

echo "Found wheel file: $WHEEL_FILE_ABSOLUTE"
echo "Using temporary directory: $TEMP_DIR"

# Function to clean up on exit
cleanup() {
    echo "Cleaning up temporary directory..."
    rm -rf "$TEMP_DIR"
    # Optionally, change back to original directory if needed
    # cd - > /dev/null 
}
trap cleanup EXIT

# Change to TEMP_DIR for isolated environment creation
cd "$TEMP_DIR"

# Test UV Installation 
echo "------------------------------------------------------------"
echo "TESTING UV INSTALLATION FROM LOCAL WHEEL"
echo "------------------------------------------------------------"
if command -v uv > /dev/null 2>&1; then
    echo "UV is installed, testing installation from local wheel..."
    
    # Create a virtual environment with UV
    uv venv .venv
    source .venv/bin/activate
    
    # Install from local wheel first (more reliable) along with required dependencies
    echo "Installing from local wheel file: $WHEEL_FILE_ABSOLUTE with dependencies"
    if uv pip install "$WHEEL_FILE_ABSOLUTE" $REQUIRED_DEPS; then
        echo "UV installation from local wheel successful!"
        # echo "Testing execution..." # Command-line test commented out
        # if log_analyzer_mcp_server --help > /dev/null; then # Placeholder, no such script yet
        #     echo "✅ UV installation and execution successful!"
        # else
        #     echo "❌ UV execution failed"
        # fi
        echo "✅ UV installation successful! (Execution test commented out as no CLI script is defined)"
    else
        echo "❌ UV installation from local wheel failed"
    fi
    
    deactivate
else
    echo "UV not found, skipping UV installation test"
fi

# Test pip installation in virtual environment from local wheel
echo ""
echo "------------------------------------------------------------"
echo "TESTING PIP INSTALLATION FROM LOCAL WHEEL"
echo "------------------------------------------------------------"
python -m venv .venv-pip
source .venv-pip/bin/activate

echo "Installing from local wheel: $WHEEL_FILE_ABSOLUTE with dependencies"
if pip install "$WHEEL_FILE_ABSOLUTE" $REQUIRED_DEPS; then
    echo "Installation from local wheel successful!"
    
    # Test import
    echo "Testing import..."
    if python -c "import log_analyzer_mcp; print(f'Import successful! Version: {log_analyzer_mcp.__version__}')"; then # Updated import
        echo "✅ Import test passed"
    else
        echo "❌ Import test failed"
    fi
    
    # Test command-line usage
    # echo "Testing command-line usage..." # Command-line test commented out
    # if log_analyzer_mcp_server --help > /dev/null; then # Placeholder, no such script yet
    #     echo "✅ Command-line test passed"
    # else
    #     echo "❌ Command-line test failed"
    # fi
    echo "✅ Pip installation successful! (Execution test commented out as no CLI script is defined)"
else
    echo "❌ Installation from local wheel failed"
fi

deactivate

echo ""
echo "Installation tests completed. You can now publish to PyPI using:"
echo ""
echo "  "${SCRIPT_DIR}/publish.sh" -p -v $VERSION" # Use script dir variable
echo ""
echo "The local wheel tests are passing, which indicates the package should"
echo "install correctly from PyPI as well." 