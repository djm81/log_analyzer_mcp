# Getting Started with Log Analyzer MCP

This guide helps you get started with using the **Log Analyzer MCP**, whether you intend to use its Command-Line Interface (CLI) or integrate its MCP server into a client application like Cursor.

## What is Log Analyzer MCP?

Log Analyzer MCP is a powerful tool designed to parse, analyze, and search log files. It offers:

- A **Core Log Analysis Engine** for flexible log processing.
- An **MCP Server** that exposes analysis capabilities to MCP-compatible clients (like Cursor).
- A **`log-analyzer` CLI** for direct command-line interaction and scripting.

Key use cases include:

- Analyzing `pytest` test run outputs.
- Searching and filtering application logs based on time, content, and position.
- Generating code coverage reports.

## Prerequisites

- **Python**: Version 3.9 or higher.
- **Hatch**: For package management and running development tasks if you are contributing or building from source. Installation instructions can be found on the [official Hatch website](https://hatch.pypa.io/latest/install/).

## Using the `log-analyzer` CLI

If you have cloned the repository and set up the development environment (see [Developer Guide](./developer_guide.md)), the `log-analyzer` CLI is available within the Hatch shell.

```bash
# Activate the Hatch environment (if not already active)
cd path/to/log_analyzer_mcp # Navigate to the project root
hatch shell

# Now you can use the CLI
log-analyzer --help

# Example: Search all records in a specific log directory
# (Configuration for log directories, patterns, etc., is typically done via a .env file or environment variables)
log-analyzer search all --scope my_app_logs
```

For detailed CLI commands and options, refer to:

- `log-analyzer --help`
- The upcoming CLI Usage Guide (link to be added once created).
- The [Refactoring Plan](./refactoring/log_analyzer_refactoring_v2.md) for tool parameters which mirror CLI arguments.

## Integrating the MCP Server

To use the Log Analyzer MCP server with an MCP client application like Cursor, you need to configure the client to launch the server.

The recommended way to run the MCP server in a production-like or stable integration is by using the version installed from PyPI.

### Example MCP Client Configuration (e.g., `.cursor/mcp.json`)

This snippet shows how you might configure Cursor (or a similar client) to use the `log-analyzer-mcp` package installed from PyPI. The `uvx` command is a utility to run Python executables from dynamically created virtual environments.

```jsonc
{
  "mcpServers": {
    "log_analyzer_mcp_server_prod": {
      "command": "uvx",
      "args": [
        "log-analyzer-mcp" // This invokes the entry point defined in pyproject.toml
                         // Ensure the package name matches what's on PyPI.
                         // Use "log-analyzer-mcp==<version>" for a specific version.
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "MCP_LOG_LEVEL": "INFO", // Recommended for production
        // MCP_LOG_FILE is optional; if not set, logs might go to stderr/stdout or a default location.
        // "MCP_LOG_FILE": "/path/to/your/project/logs/mcp/log_analyzer_mcp_server.log",
        // --- Other Environment Variables for Configuration ---
        // The Log Analyzer MCP can be configured via environment variables.
        // Refer to the main README or upcoming Configuration Guide for details.
        // Examples (these would be set in your client's environment or this env block):
        // "LOG_DIRECTORIES": "[\"/path/to/your/app/logs\", \"/another/log/path\"]",
        // "LOG_PATTERNS_ERROR": "[\"Exception:.*\", \"Traceback (most recent call last):\"]"
      }
    }
    // ... other MCP server configurations ...
  }
}
```

**Key considerations for integration:**

1. **Package Name:** Ensure the package name in the `args` (e.g., `log-analyzer-mcp`) matches the name on PyPI.
2. **Versioning:** You can specify a version (e.g., `log-analyzer-mcp==0.2.0`) to ensure stability.
3. **Environment Variables:** The Log Analyzer MCP uses environment variables for configuration (e.g., log directories, filter patterns, context lines). These must be set in the environment where the MCP server process is launched. Consult the main `README.md` or the forthcoming Configuration Guide for details on available environment variables.
4. **Logging:** `MCP_LOG_LEVEL` and `MCP_LOG_FILE` control the MCP server's own logging.

## Next Steps

- For developing or contributing to Log Analyzer MCP, see the [Developer Guide](./developer_guide.md).
- For more details on the available tools and their parameters, consult the [Refactoring Plan](./refactoring/log_analyzer_refactoring_v2.md) (which outlines the tool specifications) or the upcoming dedicated Usage Guide.
