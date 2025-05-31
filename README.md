# Log Analyzer MCP

[![CI](https://github.com/djm81/log_analyzer_mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/djm81/log_analyzer_mcp/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/djm81/log_analyzer_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/djm81/log_analyzer_mcp)
[![PyPI - Version](https://img.shields.io/pypi/v/log-analyzer-mcp?color=blue)](https://pypi.org/project/log-analyzer-mcp)

## Overview: Analyze Logs with Ease

**Log Analyzer MCP** is a powerful Python-based toolkit designed to streamline the way you interact with log files. Whether you're debugging complex applications, monitoring test runs, or simply trying to make sense of verbose log outputs, this tool provides both a Command-Line Interface (CLI) and a Model-Context-Protocol (MCP) server to help you find the insights you need, quickly and efficiently.

**Why use Log Analyzer MCP?**

- **Simplify Log Analysis:** Cut through the noise with flexible parsing, advanced filtering (time-based, content, positional), and configurable context display.
- **Integrate with Your Workflow:** Use it as a standalone `loganalyzer` CLI tool for scripting and direct analysis, or integrate the MCP server with compatible clients like Cursor for an AI-assisted experience.
- **Extensible and Configurable:** Define custom log sources, patterns, and search scopes to tailor the analysis to your specific needs.

## Key Features

- **Core Log Analysis Engine:** Robust backend for parsing and searching various log formats.
- **`loganalyzer` CLI:** Intuitive command-line tool for direct log interaction.
- **MCP Server:** Exposes log analysis capabilities to MCP clients, enabling features like:
  - Test log summarization (`analyze_tests`).
  - Execution of test runs with varying verbosity.
  - Targeted unit test execution (`run_unit_test`).
  - On-demand code coverage report generation (`create_coverage_report`).
  - Advanced log searching: all records, time-based, first/last N records.
- **Hatch Integration:** For easy development, testing, and dependency management.

## Installation

This package can be installed from PyPI (once published) or directly from a local build for development purposes.

### From PyPI (Recommended for Users)

*(Once the package is published to PyPI)*

```bash
pip install log-analyzer-mcp
```

This will install the `loganalyzer` CLI tool and make the MCP server package available for integration.

### From Local Build (For Developers or Testing)

If you have cloned the repository and want to use your local changes:

1. **Ensure Hatch is installed.** (See [Developer Guide](./docs/developer_guide.md#development-environment))
2. **Build the package:**

    ```bash
    hatch build
    ```

    This creates wheel and sdist packages in the `dist/` directory.
3. **Install the local build into your Hatch environment (or any other virtual environment):**
    Replace `<version>` with the actual version from the generated wheel file (e.g., `0.2.7`).

    ```bash
    # If using Hatch environment:
    hatch run pip uninstall log-analyzer-mcp -y && hatch run pip install dist/log_analyzer_mcp-<version>-py3-none-any.whl

    # For other virtual environments:
    # pip uninstall log-analyzer-mcp -y # (If previously installed)
    # pip install dist/log_analyzer_mcp-<version>-py3-none-any.whl
    ```

    For IDEs like Cursor to pick up changes to the MCP server, you may need to manually reload the server in the IDE. See the [Developer Guide](./docs/developer_guide.md#installing-and-testing-local-builds-idecli) for details.

## Getting Started: Using Log Analyzer MCP

There are two primary ways to use Log Analyzer MCP:

1. **As a Command-Line Tool (`loganalyzer`):**
    - Ideal for direct analysis, scripting, or quick checks.
    - Requires Python 3.9+.
    - For installation, see the [Installation](#installation) section above.
    - For detailed usage, see the [CLI Usage Guide](./docs/cli_usage_guide.md) (upcoming) or the [API Reference for CLI commands](./docs/api_reference.md#cli-client-log-analyzer).

2. **As an MCP Server (e.g., with Cursor):**
    - Integrates log analysis capabilities directly into your AI-assisted development environment.
    - For installation, see the [Installation](#installation) section. The MCP server component is included when you install the package.
    - For configuration with a client like Cursor and details on running the server, see [Configuring and Running the MCP Server](#configuring-and-running-the-mcp-server) below and the [Developer Guide](./docs/developer_guide.md#running-the-mcp-server).

## Configuring and Running the MCP Server

### Configuration

Configuration of the Log Analyzer MCP (for both CLI and Server) is primarily handled via environment variables or a `.env` file in your project root.

- **Environment Variables:** Set variables like `LOG_DIRECTORIES`, `LOG_PATTERNS_ERROR`, `LOG_CONTEXT_LINES_BEFORE`, `LOG_CONTEXT_LINES_AFTER`, etc., in the environment where the tool or server runs.
- **`.env` File:** Create a `.env` file by copying `.env.template` (this template file needs to be created and added to the repository) and customize the values.

For a comprehensive list of all configuration options and their usage, please refer to the **(Upcoming) [Configuration Guide](./docs/configuration.md)**.
*(Note: The `.env.template` file should be created and added to the repository to provide a starting point for users.)*

### Running the MCP Server

The MCP server can be launched in several ways:

1. **Via an MCP Client (e.g., Cursor):**
    Configure your client to launch the `log-analyzer-mcp` executable (often using a helper like `uvx`). This is the typical way to integrate the server.

    **Example Client Configuration (e.g., in `.cursor/mcp.json`):**

```jsonc
{
  "mcpServers": {
    "log_analyzer_mcp_server_prod": {
      "command": "uvx", // uvx is a tool to run python executables from venvs
      "args": [
        "log-analyzer-mcp" // Fetches and runs the latest version from PyPI
        // Or, for a specific version: "log-analyzer-mcp==0.2.0"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "MCP_LOG_LEVEL": "INFO", // Recommended for production
        // "MCP_LOG_FILE": "/path/to/your/logs/mcp/log_analyzer_mcp_server.log", // Optional
        // --- Configure Log Analyzer specific settings via environment variables ---
        // These are passed to the analysis engine used by the server.
        // Example: "LOG_DIRECTORIES": "[\"/path/to/your/app/logs\"]",
        // Example: "LOG_PATTERNS_ERROR": "[\"Exception:.*\"]"
        // (Refer to the (Upcoming) docs/configuration.md for all options)
      }
    }
    // You can add other MCP servers here
  }
}
```

**Notes:**

- Replace placeholder paths and consult the [Getting Started Guide](./docs/getting_started.md), the **(Upcoming) [Configuration Guide](./docs/configuration.md)**, and the [Developer Guide](./docs/developer_guide.md) for more on configuration options and environment variables.
- The actual package name on PyPI is `log-analyzer-mcp`.

2. **Directly (for development/testing):**
    You can run the server directly using its entry point if needed. The `log-analyzer-mcp` command (available after installation) can be used:

    ```bash
    log-analyzer-mcp --transport http --port 8080
    # or for stdio transport
    # log-analyzer-mcp --transport stdio
    ```

    Refer to `log-analyzer-mcp --help` for more options. For development, using Hatch scripts defined in `pyproject.toml` or the methods described in the [Developer Guide](./docs/developer_guide.md#running-the-mcp-server) is also common.

## Documentation

- **[API Reference](./docs/api_reference.md):** Detailed reference for MCP server tools and CLI commands.
- **[Getting Started Guide](./docs/getting_started.md):** For users and integrators. This guide provides a general overview.
- **[Developer Guide](./docs/developer_guide.md):** For contributors, covering environment setup, building, detailed testing procedures (including coverage checks), and release guidelines.
- **(Upcoming) [Configuration Guide](./docs/configuration.md):** Detailed explanation of all `.env` and environment variable settings. *(This document needs to be created.)*
- **(Upcoming) [CLI Usage Guide](./docs/cli_usage_guide.md):** Comprehensive guide to all `loganalyzer` commands and options. *(This document needs to be created.)*
- **[.env.template](.env.template):** A template file for configuring environment variables. *(This file needs to be created and added to the repository.)*
- **[Refactoring Plan](./docs/refactoring/log_analyzer_refactoring_v2.md):** Technical details on the ongoing evolution of the project.

## Testing

To run tests and generate coverage reports, please refer to the comprehensive [Testing Guidelines in the Developer Guide](./docs/developer_guide.md#testing-guidelines). This section covers using `hatch test`, running tests with coverage, generating HTML reports, and targeting specific tests.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) and the [Developer Guide](./docs/developer_guide.md) for guidelines on how to set up your environment, test, and contribute.

## License

Log Analyzer MCP is licensed under the MIT License with Commons Clause. See [LICENSE.md](./LICENSE.md) for details.
