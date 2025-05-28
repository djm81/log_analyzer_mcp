# Testing Documentation for Log Analyzer MCP

This directory (`tests/`) and related documentation (`docs/testing/`) cover testing for the `log_analyzer_mcp` project.

## Running Tests

Tests are managed and run using `hatch`. Refer to the [Testing and Build Guide](../rules/testing-and-build-guide.md) for primary instructions.

**Key Commands:**

- **Run all tests (default matrix):**

  ```bash
  hatch test
  ```

- **Run tests with coverage and verbose output:**

  ```bash
  hatch test --cover -v
  ```

- **Run tests for a specific Python version (e.g., 3.10):**

  ```bash
  hatch test --python 3.10
  ```

## Test Structure

- Tests for the MCP server logic (`src/log_analyzer_mcp`) are located in `tests/log_analyzer_mcp/`.
- Tests for the CLI client (`src/log_analyzer_client`) are located in `tests/log_analyzer_client/` (if/when implemented as per refactoring plan).

## MCP Server Tools (for testing and usage context)

The MCP server (`src/log_analyzer_mcp/log_analyzer_mcp_server.py`) provides the following tools, which are tested and can be used by Cursor or other MCP clients:

1. **`ping`**: Checks if the MCP server is alive.
    - Features: Returns server status and timestamp.

2. **`analyze_tests`**: Analyzes the results of the most recent test run.
    - Parameters:
        - `summary_only` (boolean, optional): If true, returns only a summary.
    - Features: Parses `pytest` logs, details failures, categorizes errors.

3. **`run_tests_no_verbosity`**: Runs all tests with minimal output (verbosity level 0).

4. **`run_tests_verbose`**: Runs all tests with verbosity level 1.

5. **`run_tests_very_verbose`**: Runs all tests with verbosity level 2.

6. **`run_unit_test`**: Runs tests for a specific component (e.g., an agent in a larger system, or a specific test file/module pattern).
    - Parameters:
        - `agent` (string, required): The pattern or identifier for the tests to run.
        - `verbosity` (integer, optional, default=1): Verbosity level (0, 1, or 2).
    - Features: Significantly reduces test execution time for focused development.

7. **`create_coverage_report`**: Generates test coverage reports.
    - Parameters:
        - `force_rebuild` (boolean, optional): If true, forces rebuilding the report.
    - Features: Generates HTML and XML coverage reports.

8. **`search_log_all_records`**: Searches for all log records matching criteria.
    - Parameters: `scope: str`, `context_before: int`, `context_after: int`, `log_dirs_override: Optional[str]`, `log_content_patterns_override: Optional[str]`.

9. **`search_log_time_based`**: Searches log records within a time window.
    - Parameters: `minutes: int`, `hours: int`, `days: int`, `scope: str`, `context_before: int`, `context_after: int`, `log_dirs_override: Optional[str]`, `log_content_patterns_override: Optional[str]`.

10. **`search_log_first_n_records`**: Searches for the first N matching records.
    - Parameters: `count: int`, `scope: str`, `context_before: int`, `context_after: int`, `log_dirs_override: Optional[str]`, `log_content_patterns_override: Optional[str]`.

11. **`search_log_last_n_records`**: Searches for the last N matching records.
    - Parameters: `count: int`, `scope: str`, `context_before: int`, `context_after: int`, `log_dirs_override: Optional[str]`, `log_content_patterns_override: Optional[str]`.

*(Note: For detailed parameters and behavior of each tool, refer to the [log_analyzer_refactoring_v2.md](../refactoring/log_analyzer_refactoring_v2.md) plan and the server source code, as this overview may not be exhaustive or reflect the absolute latest state.)*

## Server Configuration Example (Conceptual)

The MCP server itself is typically configured by the client environment (e.g., Cursor's `mcp.json`). An example snippet for `mcp.json` might look like:

```json
{
  "mcpServers": {
    "log_analyzer_mcp_server": {
      "command": "/path/to/your/project/log_analyzer_mcp/.venv/bin/python",
      "args": [
        "/path/to/your/project/log_analyzer_mcp/src/log_analyzer_mcp/log_analyzer_mcp_server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "/path/to/your/project/log_analyzer_mcp/src",
        "MCP_LOG_LEVEL": "DEBUG",
        "MCP_LOG_FILE": "~/cursor_mcp_logs/log_analyzer_mcp_server.log" // Example path
      }
    }
  }
}
```

*(Ensure paths are correct for your specific setup. The `.venv` path is managed by Hatch.)*

## Log Directory Structure

The project uses the following log directory structure within the project root:

```shell
log_analyzer_mcp/
├── logs/
│   ├── mcp/                # Logs specifically from MCP server operations
│   │   └── log_analyzer_mcp_server.log
│   ├── runtime/            # General runtime logs (if applications write here)
│   └── tests/              # Logs related to test execution
│       ├── coverage/         # Coverage data files (.coverage)
│       │   ├── coverage.xml    # XML coverage report
│       │   └── htmlcov/        # HTML coverage report
│       └── junit/            # JUnit XML test results (if configured)
│           └── test-results.xml
```

## Troubleshooting

If you encounter issues with the MCP server or tests:

1. Check the MCP server logs (e.g., `logs/mcp/log_analyzer_mcp_server.log` or the path configured in `MCP_LOG_FILE`).
2. Ensure your Hatch environment is active (`hatch shell`) and all dependencies are installed.
3. Verify the MCP server tools using direct calls (e.g., via a simple Python client script or a tool like `mcp-cli` if available) before testing through a complex client like Cursor.
4. Consult the [Testing and Build Guide](../rules/testing-and-build-guide.md) for correct test execution procedures.

## Old Script Information (Historical / To Be Removed or Updated)

*The following sections refer to scripts and configurations that may be outdated or significantly changed due to refactoring. They are kept temporarily for reference and will be removed or updated once the new documentation structure (Usage, Configuration guides) is complete.*

### (Example: `analyze_runtime_errors.py` - Functionality integrated into core engine)

Previously, a standalone `analyze_runtime_errors.py` script existed. Its functionality for searching runtime logs is now intended to be covered by the new search tools using the core `AnalysisEngine`.

### (Example: `create_coverage_report.sh` - Functionality handled by Hatch)

A previous `create_coverage_report.sh` script was used. Coverage generation is now handled by `hatch test --cover -v` and related Hatch commands for report formatting (e.g., `hatch run cov-report:html`).

*This document will be further refined as the refactoring progresses and dedicated Usage/Configuration guides are created.*
