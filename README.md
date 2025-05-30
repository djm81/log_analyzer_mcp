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

## Getting Started: Using Log Analyzer MCP

There are two primary ways to use Log Analyzer MCP:

1. **As a Command-Line Tool (`loganalyzer`):**
    - Ideal for direct analysis, scripting, or quick checks.
    - Requires Python 3.9+.
    - For installation and usage, please see the [Getting Started Guide](./docs/getting_started.md).

2. **As an MCP Server (e.g., with Cursor):**
    - Integrates log analysis capabilities directly into your AI-assisted development environment.
    - To install and configure the MCP server for use in a client like Cursor, follow the instructions below.

### Installing the MCP Server for Client Integration

To integrate the Log Analyzer MCP server with a client application (like Cursor), you'll typically configure the client to launch the `log-analyzer-mcp` package, which is available on PyPI.

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
        // Example: "LOG_DIRECTORIES": "[\"/path/to/your/app/logs\"]",
        // Example: "LOG_PATTERNS_ERROR": "[\"Exception:.*\"]"
        // (Refer to docs/configuration.md (once created) for all options)
      }
    }
    // You can add other MCP servers here
  }
}
```

**Notes:**

- Replace placeholder paths and consult the [Getting Started Guide](./docs/getting_started.md) and [Developer Guide](./docs/developer_guide.md) for more on configuration options and environment variables.
- The actual package name on PyPI is `log-analyzer-mcp`.

## Documentation

- **[API Reference](./docs/api_reference.md):** Detailed reference for MCP server tools and CLI commands.
- **[Getting Started Guide](./docs/getting_started.md):** For users and integrators.
- **[Developer Guide](./docs/developer_guide.md):** For contributors and those building from source.
- **[Refactoring Plan](./docs/refactoring/log_analyzer_refactoring_v2.md):** Technical details on the ongoing evolution of the project.
- **(Upcoming) Configuration Guide:** Detailed explanation of all `.env` and environment variable settings.
- **(Upcoming) CLI Usage Guide:** Comprehensive guide to all `loganalyzer` commands and options.

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](./CONTRIBUTING.md) and the [Developer Guide](./docs/developer_guide.md) for guidelines on how to set up your environment, test, and contribute.

## License

Log Analyzer MCP is licensed under the MIT License with Commons Clause. See [LICENSE.md](./LICENSE.md) for details.
