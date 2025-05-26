#!/bin/bash
# Wrapper script to automate the release process for log_analyzer_mcp

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PACKAGE_NAME="log-analyzer-mcp"
PYPI_URL="https://pypi.org/pypi"
TESTPYPI_URL="https://test.pypi.org/pypi"
PYPROJECT_PATH="${PROJECT_ROOT}/pyproject.toml"

# --- Dependency Check ---
if ! command -v curl &> /dev/null; then
    echo "❌ ERROR: curl is required but not found. Please install curl." >&2
    exit 1
fi
if ! command -v jq &> /dev/null; then
    echo "❌ ERROR: jq is required but not found. Please install jq (e.g., brew install jq)." >&2
    exit 1
fi
if ! command -v sed &> /dev/null; then
    echo "❌ ERROR: sed is required but not found." >&2
    exit 1
fi
if ! command -v grep &> /dev/null; then
    echo "❌ ERROR: grep is required but not found." >&2
    exit 1
fi

# --- Argument Parsing ---
VERSION=""
SKIP_TESTPYPI=false
TEST_ONLY=false
YES_FLAG=false
UPDATE_TARGET="prod" # Default

# Flags to track if options were set via command line
VERSION_SET=false
SKIP_TESTPYPI_SET=false
TEST_ONLY_SET=false
UPDATE_TARGET_SET=false

usage() {
    echo "Usage: $0 [-h] [-y] [--skip-testpypi] [--test-only] [--update-target <prod|test>] [--version VERSION]"
    echo ""
    echo "Automates the release process: TestPyPI build & test -> Prod PyPI build & publish -> Update Cursor Config."
    echo ""
    echo "Options:"
    echo "  -h, --help           Show this help message and exit."
    echo "  -y, --yes            Automatically answer yes to confirmation prompts (non-interactive)."
    echo "  --skip-testpypi      Skip the TestPyPI build and local install test steps."
    echo "  --test-only          Only perform the TestPyPI build and local install test, then exit."
    echo "  --update-target <prod|test>  Install version from prod (PyPI) or test (TestPyPI) for Cursor use (default: prod)."
    echo "  --version VERSION    Specify the version number to release directly."
    echo ""
    echo "If --version is not provided in interactive mode, you will be prompted."
    exit 0
}

# --- Helper Functions ---
check_if_version_exists() {
    local pkg_name="$1"
    local version_to_check="$2"
    local index_url="$3"
    local index_name="$4"

    echo "  Checking if version $version_to_check exists on $index_name..."
    # Use curl to get package info, jq to check if version exists in releases
    if curl -s "$index_url/$pkg_name/$version_to_check/json" | jq -e '(.info.version == "'"$version_to_check"'")' > /dev/null; then
        echo "  ❌ ERROR: Version $version_to_check already exists on $index_name!" >&2
        return 1 # Indicate failure (version exists)
    else
        # Check if the overall package fetch failed (e.g., 404), indicating version likely doesn't exist
        if ! curl -s -f "$index_url/$pkg_name/json" > /dev/null; then
             echo "  Package $pkg_name not found on $index_name (or network error). Assuming version $version_to_check does not exist."
             return 0 # Indicate success (version likely doesn't exist)
        fi
        echo "  Version $version_to_check does not appear to exist on $index_name. Proceeding."
        return 0 # Indicate success (version does not exist)
    fi
}

get_current_version() {
    if [ ! -f "$PYPROJECT_PATH" ]; then
        echo "❌ ERROR: pyproject.toml not found at $PYPROJECT_PATH" >&2
        return 1
    fi
    # Extract version using grep -E and the user's corrected sed -E command
    current_ver=$(grep -E '^version\s*=\s*\".+\"' "$PYPROJECT_PATH" | sed -E 's/^version[\ ]*=[\ ]*\"([0-9.]+)\"$/\1/')
    if [ -z "$current_ver" ]; then
        echo "❌ ERROR: Could not extract current version from $PYPROJECT_PATH using grep/sed." >&2
        return 1
    fi
    echo "$current_ver"
    return 0
}

suggest_next_patch_version() {
    local current_version="$1"
    # Basic suggestion: increments the last number after the last dot
    local prefix=$(echo "$current_version" | sed -E 's/\.[0-9]+$//')
    local patch=$(echo "$current_version" | sed -E 's/^.*\.(.*)/\1/')
    # Check if patch is purely numeric
    if [[ "$patch" =~ ^[0-9]+$ ]]; then
        local next_patch=$((patch + 1))
        echo "${prefix}.${next_patch}"
    else
        # Cannot auto-increment non-numeric patch (e.g., pre-releases)
        echo "$current_version" # Suggest current as fallback
    fi
}

is_version_greater() {
    local ver1="$1" # New version
    local ver2="$2" # Old version
    # Returns 0 if ver1 > ver2, 1 otherwise
    if [ "$ver1" == "$ver2" ]; then
        return 1 # Not greater if equal
    fi
    # Use sort -V: If the sorted list's last element is ver1, then ver1 > ver2
    if [ "$(printf '%s\n' "$ver1" "$ver2" | sort -V | tail -n 1)" == "$ver1" ]; then
        return 0 # ver1 is greater
    else
        return 1 # ver1 is not greater
    fi
}

validate_version_format() {
    local ver="$1"
    # Basic X.Y.Z format check, allows for suffixes like -alpha, .rc1 etc.
    if ! [[ "$ver" =~ ^[0-9]+\.[0-9]+\.[0-9]+([a-zA-Z0-9.-]*)?$ ]]; then
        echo "  ⚠️ Warning: Version format '$ver' seems unusual. Expected X.Y.Z or similar."
        # Allow proceeding but warn
    fi
    return 0
}

# --- Main Script Logic ---

# Change to the project root directory to ensure paths are correct
cd "$PROJECT_ROOT"
echo "ℹ️ Changed working directory to project root: $PROJECT_ROOT"

# CHANGELOG.md Reminder
echo "🔔 REMINDER: Before proceeding with the release, ensure you have:"
echo "   1. Verified all tests are passing with adequate coverage"
echo "   2. Updated CHANGELOG.md with all notable changes in this version"
echo "   3. Update of version number in pyproject.toml will be done automatically"
echo ""

# Argument parsing loop
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        -h|--help)
            usage
            ;;
        -y|--yes)
            YES_FLAG=true
            shift # past argument
            ;;
        --skip-testpypi)
            SKIP_TESTPYPI=true
            SKIP_TESTPYPI_SET=true # Track that it was set
            shift # past argument
            ;;
        --test-only)
            TEST_ONLY=true
            TEST_ONLY_SET=true # Track that it was set
            shift # past argument
            ;;
        --update-target)
            if [[ "$2" == "prod" || "$2" == "test" ]]; then
                UPDATE_TARGET="$2"
                UPDATE_TARGET_SET=true # Track that it was set
                shift # past argument
                shift # past value
            else
                echo "❌ ERROR: --update-target must be 'prod' or 'test'" >&2
                usage
            fi
            ;;
        --version)
            if [ -n "$2" ]; then
                VERSION="$2"
                VERSION_SET=true # Track that it was set
                shift # past argument
                shift # past value
            else
                echo "❌ ERROR: --version requires an argument." >&2
                usage
            fi
            ;;
        *)    # unknown option
            echo "❌ ERROR: Unknown option: $1" >&2
            usage
            ;;
    esac
done

# --- Interactive Prompts (if not -y and flags not set) ---
if [ "$YES_FLAG" = false ]; then
    echo "🔧 Entering interactive configuration mode (options not set via flags)..."
    
    # Prompt for Update Target
    if [ "$UPDATE_TARGET_SET" = false ]; then
        read -p "  Update target for local UVX installation? (prod/test) [prod]: " target_choice
        UPDATE_TARGET=${target_choice:-$UPDATE_TARGET} # Default to prod if empty
        if [[ "$UPDATE_TARGET" != "prod" && "$UPDATE_TARGET" != "test" ]]; then
            echo "  ❌ ERROR: Invalid target. Please enter 'prod' or 'test'." >&2
            exit 1
        fi
        echo "  Using update target: $UPDATE_TARGET"
    fi

    # Prompt for Test-Only (only if target is test)
    if [ "$TEST_ONLY_SET" = false ] && [ "$UPDATE_TARGET" = "test" ]; then
        read -p "  Run TestPyPI phase ONLY (--test-only)? (y/n) [n]: " test_only_choice
        if [[ ${test_only_choice:-\"n\"} =~ ^[Yy]$ ]]; then
            TEST_ONLY=true
        else
            TEST_ONLY=false
        fi
        echo "  Run TestPyPI only: $TEST_ONLY"
    fi

    # Prompt for Skip-TestPyPI (only if target is prod)
    if [ "$SKIP_TESTPYPI_SET" = false ] && [ "$UPDATE_TARGET" = "prod" ]; then
        read -p "  Skip TestPyPI build/test phase (--skip-testpypi)? (y/n) [n]: " skip_testpypi_choice
        if [[ ${skip_testpypi_choice:-\"n\"} =~ ^[Yy]$ ]]; then
            SKIP_TESTPYPI=true
        else
            SKIP_TESTPYPI=false
        fi
        echo "  Skip TestPyPI phase: $SKIP_TESTPYPI"
    fi

    # Prompt for Version (if not set via flag)
    if [ "$VERSION_SET" = false ]; then
        CURRENT_VERSION=$(get_current_version)
        if [ $? -ne 0 ]; then exit 1; fi
        SUGGESTED_VERSION=$(suggest_next_patch_version "$CURRENT_VERSION")
        echo "  Current version in pyproject.toml: $CURRENT_VERSION"

        while true; do
            read -p "  Enter the new version number (suggested: $SUGGESTED_VERSION): " entered_version
            if [ -z "$entered_version" ]; then
                entered_version="$SUGGESTED_VERSION"
                echo "  Using suggested version: $entered_version"
            fi
            validate_version_format "$entered_version"
            if is_version_greater "$entered_version" "$CURRENT_VERSION"; then
                 read -p "  Confirm release version $entered_version? (y/n) " -n 1 -r
                 echo
                 if [[ $REPLY =~ ^[Yy]$ ]]; then
                     VERSION="$entered_version"
                     break
                 else
                     echo "  Version not confirmed. Please try again."
                 fi
            else
                echo "  ❌ ERROR: New version '$entered_version' must be greater than current version '$CURRENT_VERSION'." >&2
            fi
        done
    fi
fi

# --- Version Validation (if provided via flag) ---
if [ "$VERSION_SET" = true ]; then
    validate_version_format "$VERSION"
    # Add check against current version if needed, though less critical if flag is used explicitly
    # CURRENT_VERSION=$(get_current_version)
    # if ! is_version_greater "$VERSION" "$CURRENT_VERSION"; then 
    #    echo "❌ ERROR: Specified version $VERSION is not greater than current version $CURRENT_VERSION." >&2
    #    exit 1
    # fi
fi

# Final check: Ensure VERSION is determined
if [ -z "$VERSION" ]; then
    echo "❌ ERROR: Release version could not be determined." >&2
    exit 1
fi

echo ""
echo "🚀 Starting Release Process for Version: $VERSION"
echo "--------------------------------------------------"
echo "Configuration:"
echo "  Skip TestPyPI Build/Test: $SKIP_TESTPYPI"
echo "  TestPyPI Only:            $TEST_ONLY"
echo "  Update Target for Cursor: $UPDATE_TARGET"
echo "  Non-interactive:          $YES_FLAG"
echo "--------------------------------------------------"

# Confirmation prompt
if [ "$YES_FLAG" = false ]; then
    read -p "Proceed with this release plan? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Release cancelled by user."
        exit 1
    fi
fi

# --- TestPyPI Phase ---
if [ "$SKIP_TESTPYPI" = false ]; then
    echo ""
    echo "📦 Phase 1: Building and Publishing to TestPyPI..."
    
    # Check if version already exists on TestPyPI BEFORE publishing
    check_if_version_exists "$PACKAGE_NAME" "$VERSION" "$TESTPYPI_URL" "TestPyPI"
    if [ $? -ne 0 ]; then exit 1; fi # Exit if version exists

    # Call publish script (which updates pyproject.toml)
    echo "  Calling publish.sh to build and publish to TestPyPI..."
    "${SCRIPT_DIR}/publish.sh" -t -y -v "$VERSION"
    if [ $? -ne 0 ]; then echo "❌ ERROR: Failed to publish to TestPyPI."; exit 1; fi
    echo "✅ Successfully published to TestPyPI."

    echo ""
    echo "🔧 Phase 2: Testing Local Installation..."
    "${SCRIPT_DIR}/test_uvx_install.sh"
    if [ $? -ne 0 ]; then echo "❌ ERROR: Local installation test failed."; exit 1; fi
    echo "✅ Local installation test successful."

    if [ "$TEST_ONLY" = true ]; then
        echo ""
        echo "✅ TestPyPI phase complete (--test-only specified). Exiting."
        exit 0
    fi
else
    echo "⏩ Skipping TestPyPI build and test phases."
fi

# --- Production Phase ---
echo ""
echo "📦 Phase 3: Building and Publishing to Production PyPI..."

# Check if version already exists on Production PyPI BEFORE publishing
check_if_version_exists "$PACKAGE_NAME" "$VERSION" "$PYPI_URL" "Production PyPI"
if [ $? -ne 0 ]; then exit 1; fi # Exit if version exists

# Extra confirmation for production unless -y is set
if [ "$YES_FLAG" = false ]; then
    read -p "🚨 REALLY publish version $VERSION to Production PyPI? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Production release cancelled by user."
        exit 1
    fi
fi

# Call publish script (which updates pyproject.toml again if needed, harmless)
"${SCRIPT_DIR}/publish.sh" -p -y -v "$VERSION"
if [ $? -ne 0 ]; then echo "❌ ERROR: Failed to publish to Production PyPI."; exit 1; fi
echo "✅ Successfully published to Production PyPI."

# --- Update Phase ---
echo ""
echo "🔧 Phase 4: Installing Release Version for Local UVX (Target: $UPDATE_TARGET)..."

INSTALL_ARGS=""
STRATEGY_ARG=""
PACKAGE_SPEC="$PACKAGE_NAME@$VERSION"

if [ "$UPDATE_TARGET" == "test" ]; then
    echo "  Installing version $VERSION from TestPyPI for local uvx command..."
    INSTALL_ARGS="--default-index $TESTPYPI_URL --index $PYPI_URL"
    STRATEGY_ARG="--index-strategy unsafe-best-match"
else
    echo "  Installing version $VERSION from PyPI for local uvx command..."
    # INSTALL_ARGS="--refresh --default-index $PYPI_URL" # Explicitly use PyPI
    INSTALL_ARGS="--refresh" # Avoid using default-index for pypi as this does not work
fi

install_command="uvx ${INSTALL_ARGS} ${STRATEGY_ARG} ${PACKAGE_SPEC}"
echo "  Running: $install_command"
eval $install_command # Use eval to handle args correctly

if [ $? -ne 0 ]; then echo "❌ ERROR: Failed to install $UPDATE_TARGET version $VERSION locally via uvx."; exit 1; fi
echo "  ✅ $UPDATE_TARGET version $VERSION installed for local uvx command."

echo "  Refreshing local UVX cache (may not be necessary with direct install)..."
if command -v uvx &> /dev/null; then
    # Refresh might still help ensure internal links are updated
    uvx --refresh $PACKAGE_NAME --version 
    echo "  ✅ UVX cache refreshed (or attempted)."
else
     echo "  ⚠️ UVX command not found, skipping cache refresh."
fi

echo ""
echo "🎉 Release process for $VERSION completed successfully!"
echo "ℹ️ Remember to commit and push the updated pyproject.toml and potentially tag the release in Git."
echo "ℹ️ Restart Cursor or the MCP Server if needed to pick up the new version."

exit 0 