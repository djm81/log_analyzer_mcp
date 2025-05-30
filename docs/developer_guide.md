# Developer Guide for Log Analyzer MCP

This guide provides instructions for developers working on the `log-analyzer-mcp` project, covering environment setup, testing, building, running the MCP server, and release procedures.

## Development Environment

This project uses `hatch` for environment and project management.

1. **Install Hatch:**
    Follow the instructions on the [official Hatch website](https://hatch.pypa.io/latest/install/).

2. **Clone the repository:**

    ```bash
    git clone <repository-url> # Replace <repository-url> with the actual URL
    cd log_analyzer_mcp
    ```

3. **Activate the Hatch environment:**
    From the project root directory:

    ```bash
    hatch shell
    ```

    This command creates a virtual environment (if it doesn't exist) and installs all project dependencies defined in `pyproject.toml`. The `log-analyzer` CLI tool will also become available within this activated shell.

## Testing Guidelines

Consistent and thorough testing is crucial.

### Always Use Hatch for Tests

Standard tests should **always** be run via the built-in Hatch `test` command, not directly with `pytest` or custom wrappers. Using `hatch test` ensures:

- The proper Python versions (matrix) are used as defined in `pyproject.toml`.
- Dependencies are correctly resolved for the test environment.
- Environment variables are properly set.
- Coverage reports are correctly generated and aggregated.

**Common Test Commands:**

- **Run all tests (default matrix, standard output):**

    ```bash
    hatch test
    ```

- **Run tests with coverage report and verbose output:**

    ```bash
    hatch test --cover -v
    ```

    (The `-v` flag increases verbosity. Coverage data is typically stored in `logs/tests/coverage/`)

- **Generate HTML coverage report:**
    After running tests with `--cover`, you can generate an HTML report. The specific command might be an alias in `pyproject.toml` (e.g., `run-cov-report:html`) or a direct `coverage` command:

    ```bash
    # Example using a hatch script alias (check pyproject.toml for exact command)
    hatch run cov-report:html
    # Or, if run-cov has already created the .coverage file:
    hatch run coverage html -d logs/tests/coverage/htmlcov
    ```

    The HTML report is typically generated in `logs/tests/coverage/htmlcov/`.

- **Run tests for a specific Python version (e.g., Python 3.10):**
    (Assumes `3.10` is defined in your hatch test environment matrix in `pyproject.toml`)

    ```bash
    hatch -e py310 test # Or the specific environment name, e.g., hatch -e test-py310 test
    # To run with coverage for a specific version:
    hatch -e py310 run test-cov # Assuming 'test-cov' is a script in hatch.toml for that env
    ```

- **Target specific test files or directories:**
    You can pass arguments to `pytest` through `hatch test`:

    ```bash
    hatch test tests/log_analyzer_mcp/test_analysis_engine.py
    hatch test --cover -v tests/log_analyzer_mcp/
    ```

### Integrating `chroma-mcp-server` for Enhanced Testing

If the `chroma-mcp-server` package (included as a development dependency) is available in your Hatch environment, it enables an enhanced testing workflow. This is activated by adding the `--auto-capture-workflow` flag to your `hatch test` commands.

**Purpose:**

The primary benefit of this integration is to capture detailed information about test runs, including failures and subsequent fixes. This data can be used by `chroma-mcp-server` to build a knowledge base, facilitating "Test-Driven Learning" and helping to identify patterns or recurring issues.

**How to Use:**

When `chroma-mcp-server` is part of your development setup, modify your test commands as follows:

- **Run all tests with auto-capture:**

  ```bash
  hatch test --auto-capture-workflow
  ```

- **Run tests with coverage, verbose output, and auto-capture:**

  ```bash
  hatch test --cover -v --auto-capture-workflow
  ```

- **Target specific tests with auto-capture:**

  ```bash
  hatch test --cover -v --auto-capture-workflow tests/log_analyzer_mcp/
  ```

By including `--auto-capture-workflow`, `pytest` (via a plugin provided by `chroma-mcp-server`) will automatically log the necessary details of the test session for further analysis and learning.

### Avoid Direct `pytest` Usage

❌ **Incorrect:**

```bash
python -m pytest tests/
```

✅ **Correct (using Hatch):**

```bash
hatch test
```

## Build Guidelines

To build the package (e.g., for distribution or local installation):

1. **Using the `build.sh` script (Recommended):**
    This script may handle additional pre-build steps like version synchronization.

    ```bash
    ./scripts/build.sh
    ```

2. **Using Hatch directly:**

    ```bash
    hatch build
    ```

Both methods generate the distributable files (e.g., `.whl` and `.tar.gz`) in the `dist/` directory.

## Installing and Testing Local Builds (IDE/CLI)

After making changes to the MCP server or CLI, you need to rebuild and reinstall the package within the Hatch environment for those changes to be reflected when:

- Cursor (or another IDE) runs the MCP server.
- You use the `log-analyzer` CLI directly.

**Steps:**

1. **Build the package:**

    ```bash
    hatch build
    ```

2. **Uninstall the previous version and install the new build:**
    Replace `<version>` with the actual version string from the generated wheel file in `dist/` (e.g., `0.2.7`).

    ```bash
    hatch run pip uninstall log-analyzer-mcp -y && hatch run pip install dist/log_analyzer_mcp-<version>-py3-none-any.whl
    ```

3. **Reload MCP in IDE:**
    If you are testing with Cursor or a similar IDE, you **must manually reload the MCP server** within the IDE. Cursor does not automatically pick up changes to reinstalled MCP packages.

## Running the MCP Server

The `.cursor/mcp.json` file defines configurations for running the MCP server in different modes. Here's how to understand and use them:

### Development Mode (`log_analyzer_mcp_server_dev`)

- **Purpose:** For local development and iterative testing. Uses the local source code directly via a shell script.
- **Configuration (`.cursor/mcp.json` snippet):**

    ```json
    "log_analyzer_mcp_server_dev": {
      "command": "/Users/dominikus/git/nold-ai/log_analyzer_mcp/scripts/run_log_analyzer_mcp_dev.sh",
      "args": [],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "/Users/dominikus/git/nold-ai/log_analyzer_mcp", // Points to project root
        "MCP_LOG_LEVEL": "DEBUG",
        "MCP_LOG_FILE": "/Users/dominikus/git/nold-ai/log_analyzer_mcp/logs/mcp/log_analyzer_mcp_server.log"
      }
    }
    ```

- **How to run:** This configuration is typically selected within Cursor when pointing to your local development setup. The `run_log_analyzer_mcp_dev.sh` script likely activates the Hatch environment and runs `src/log_analyzer_mcp/log_analyzer_mcp_server.py`.

### Test Package Mode (`log_analyzer_mcp_server_test`)

- **Purpose:** For testing the packaged version of the server, usually installed from TestPyPI. This helps verify that packaging, dependencies, and entry points work correctly.
- **Configuration (`.cursor/mcp.json` snippet):**

    ```jsonc
    "log_analyzer_mcp_server_test": {
      "command": "uvx", // uvx is a tool to run python executables from venvs
      "args": [
        "--refresh",
        "--default-index", "https://test.pypi.org/simple/",
        "--index", "https://pypi.org/simple/",
        "--index-strategy", "unsafe-best-match",
        "log_analyzer_mcp_server@latest" // Installs/runs the latest from TestPyPI
      ],
      "env": {
        "MCP_LOG_LEVEL": "INFO",
        "MCP_LOG_FILE": "/Users/dominikus/git/nold-ai/log_analyzer_mcp/logs/mcp/log_analyzer_mcp_server.log"
      }
    }
    ```

- **How to run:** This configuration would be selected in an environment where you want to test the package as if it were installed from TestPyPI.

### Production Mode (`log_analyzer_mcp_server_prod`)

- **Purpose:** For running the stable, released version of the MCP server, typically installed from PyPI.
- **Configuration (`.cursor/mcp.json` snippet):**

    ```jsonc
    "log_analyzer_mcp_server_prod": {
      "command": "uvx",
      "args": [
        "log_analyzer_mcp_server" // Installs/runs the latest from PyPI (or specific version)
      ],
      "env": {
        "MCP_LOG_LEVEL": "INFO",
        "MCP_LOG_FILE": "/Users/dominikus/git/nold-ai/log_analyzer_mcp/logs/mcp/log_analyzer_mcp_server.log"
      }
    }
    ```

- **How to run:** This is how an end-user project would typically integrate the released `log-analyzer-mcp` package.

*(Note: The absolute paths in the `_dev` configuration are specific to the user's machine. In a shared context, these would use relative paths or environment variables.)*

## Release Guidelines

When preparing a new release:

1. **Update `CHANGELOG.md`:**
    - Add a new section at the top for the new version (e.g., `## [0.2.0] - YYYY-MM-DD`).
    - Document all significant changes under "Added", "Fixed", "Changed", or "Removed" subheadings.
    - Use clear, concise language.

2. **Update Version:**
    The version number is primarily managed in `pyproject.toml`.
    - If using `hatch-vcs`, the version might be derived from Git tags.
    - If `[tool.hatch.version].path` is set (e.g., to `src/log_analyzer_mcp/__init__.py`), ensure that file is updated.
    - The `/scripts/release.sh` script (if used) should handle version bumping and consistency. A `setup.py` file, if present, is typically minimal, and its versioning is also handled by Hatch or the release script.

3. **Build and Test:**
    - Build the package: `./scripts/build.sh` or `hatch build`.
    - Verify the correct version appears in the built artifacts (`dist/`).
    - Thoroughly test the new version, including installing and testing the built package.

4. **Tag and Release:**
    - Create a Git tag for the release (e.g., `git tag v0.2.0`).
    - Push the tag to the remote: `git push origin v0.2.0`.
    - Publish the package to PyPI (usually handled by the release script or a CI/CD pipeline).

5. **Complete Documentation:**
    - Ensure all documentation (READMEs, user guides, developer guides) is updated to reflect the new version and any changes.

*(This Developer Guide supersedes `docs/rules/testing-and-build-guide.md`. The latter can be removed or archived after this guide is finalized.)*
