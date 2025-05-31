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
- **Hatch**: For package management and running development tasks if you are contributing or building from source. Installation instructions for Hatch can be found on the [official Hatch website](https://hatch.pypa.io/latest/install/).

For instructions on how to install the **Log Analyzer MCP** package itself, please refer to the [Installation section in the main README.md](../README.md#installation).

## Using the `log-analyzer` CLI

Once Log Analyzer MCP is installed, the `log-analyzer` command-line tool will be available in your environment (or within the Hatch shell if you installed a local build into it).

**Basic Invocation:**

```bash
log-analyzer --help
```

**Example Usage (conceptual):**

```bash
# Example: Search all records, assuming configuration is in .env or environment variables
log-analyzer search all --scope my_app_logs
```

**Configuration:**
The CLI tool uses the same configuration mechanism as the MCP server (environment variables or a `.env` file). Please see the [Configuration section in the main README.md](../README.md#configuration) for more details, and refer to the upcoming `docs/configuration.md` for a full list of options.
*(Note: An `.env.template` file should be created and added to the repository to provide a starting point for users.)*

For detailed CLI commands, options, and more examples, refer to:

- `log-analyzer --help` (for a quick reference)
- The **(Upcoming) [CLI Usage Guide](./cli_usage_guide.md)** for comprehensive documentation.
- The [API Reference for CLI commands](./api_reference.md#cli-client-log-analyzer) for a technical breakdown.

## Integrating the MCP Server

After installing Log Analyzer MCP (see [Installation section in the main README.md](../README.md#installation)), the MCP server component is ready for integration with compatible clients like Cursor.

Refer to the main [README.md section on Configuring and Running the MCP Server](../README.md#configuring-and-running-the-mcp-server) for details on:

- How to configure the server (environment variables, `.env` file).
- Example client configurations (e.g., for Cursor using `uvx`).
- How to run the server directly.

Key aspects like the server's own logging (`MCP_LOG_LEVEL`, `MCP_LOG_FILE`) and the analysis engine configuration (`LOG_DIRECTORIES`, `LOG_PATTERNS_*`, etc.) are covered there and in the upcoming `docs/configuration.md`.

## Next Steps

- **Explore the CLI:** Try `log-analyzer --help` and experiment with some search commands based on the [API Reference for CLI commands](./api_reference.md#cli-client-log-analyzer).
- **Configure for Your Logs:** Set up your `.env` file (once `.env.template` is available) or environment variables to point to your log directories and define any custom patterns.
- **Integrate with MCP Client:** If you use an MCP client like Cursor, configure it to use the `log-analyzer-mcp` server.
- **For Developing or Contributing:** See the [Developer Guide](./developer_guide.md).
- **For Detailed Tool/Command Reference:** Consult the [API Reference](./api_reference.md).
