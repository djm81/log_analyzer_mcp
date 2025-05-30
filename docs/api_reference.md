# Log Analyzer MCP API Reference

This document provides a detailed reference for the tools and endpoints exposed by the Log Analyzer MCP Server and the commands available through its CLI client.

## Table of Contents

- [MCP Server Tools](#mcp-server-tools)
  - [Test Analysis and Execution](#test-analysis-and-execution)
  - [Log Searching](#log-searching)
  - [Server Utilities](#server-utilities)
- [CLI Client (`log-analyzer`)](#cli-client-log-analyzer)
  - [Global Options](#global-options)
  - [Search Commands (`log-analyzer search`)](#search-commands-log-analyzer-search)
    - [Common Search Options](#common-search-options)
    - [`log-analyzer search all`](#log-analyzer-search-all)
    - [`log-analyzer search time`](#log-analyzer-search-time)
    - [`log-analyzer search first`](#log-analyzer-search-first)
    - [`log-analyzer search last`](#log-analyzer-search-last)
- [Error Handling](#error-handling)

---

## MCP Server Tools

The Log Analyzer MCP Server provides tools for test analysis, log searching, and server introspection.

### Test Analysis and Execution

Tools related to running tests, analyzing results, and managing coverage reports.

#### `analyze_tests`

Analyzes the most recent test run and provides detailed information about failures.

**Parameters:**

| Name           | Type    | Required | Default | Description                                        |
|----------------|---------|----------|---------|----------------------------------------------------|
| `summary_only` | boolean | No       | `False` | Whether to return only a summary of the test results |

**Returns:**

A JSON object containing the test analysis, including:

- `summary`: Overall summary (status, passed, failed, skipped).
- `error_details`: (If not `summary_only`) List of detailed error information.
- `log_file`: Path to the analyzed log file.
- `log_timestamp`: Timestamp of the log file.
- `log_age_minutes`: Age of the log file in minutes.
- `error`: (If an error occurred during analysis) Error message.

**Example Call:**

```json
{
  "tool_name": "analyze_tests",
  "arguments": {
    "summary_only": true
  }
}
```

#### `run_tests_no_verbosity`

Runs all tests with minimal output (verbosity level 0). Excludes server integration tests to prevent recursion.

**Parameters:** None

**Returns:**

A JSON object with:

- `success`: Boolean indicating if the test execution command was successful.
- `return_code`: Exit code from the test runner.
- `test_output`: Combined stdout and stderr from the test run.
- `analysis_log_path`: Path to the log file where test output was saved.
- `error`: (If an error occurred) Error message.

**Example Call:**

```json
{
  "tool_name": "run_tests_no_verbosity",
  "arguments": {}
}
```

#### `run_tests_verbose`

Runs all tests with verbose output (verbosity level 1). Excludes server integration tests.

**Parameters:** None

**Returns:** (Same structure as `run_tests_no_verbosity`)

**Example Call:**

```json
{
  "tool_name": "run_tests_verbose",
  "arguments": {}
}
```

#### `run_tests_very_verbose`

Runs all tests with very verbose output (verbosity level 2) and enables coverage. Excludes server integration tests.

**Parameters:** None

**Returns:** (Same structure as `run_tests_no_verbosity`, coverage data is generated)

**Example Call:**

```json
{
  "tool_name": "run_tests_very_verbose",
  "arguments": {}
}
```

#### `run_unit_test`

Runs tests for a specific agent only.

**Parameters:**

| Name        | Type    | Required | Default | Description                                                    |
|-------------|---------|----------|---------|----------------------------------------------------------------|
| `agent`     | string  | Yes      |         | The agent to run tests for (e.g., 'qa_agent', 'backlog_agent') |
| `verbosity` | integer | No       | `1`     | Verbosity level (0=minimal, 1=normal, 2=detailed)              |

**Returns:** (Same structure as `run_tests_no_verbosity`)

**Example Call:**

```json
{
  "tool_name": "run_unit_test",
  "arguments": {
    "agent": "my_agent",
    "verbosity": 0
  }
}
```

#### `create_coverage_report`

Runs tests with coverage and generates HTML and XML reports using `hatch`.

**Parameters:**

| Name            | Type    | Required | Default | Description                                                           |
|-----------------|---------|----------|---------|-----------------------------------------------------------------------|
| `force_rebuild` | boolean | No       | `False` | Whether to force rebuilding the report even if it already exists      |

**Returns:**

A JSON object with:

- `success`: Boolean indicating overall success of report generation steps.
- `message`: Summary message.
- `overall_coverage_percent`: Parsed overall coverage percentage.
- `coverage_xml_path`: Path to the generated XML coverage report.
- `coverage_html_dir`: Path to the directory of the HTML coverage report.
- `coverage_html_index`: Path to the main `index.html` of the HTML report.
- `text_summary_output`: Text summary from the coverage tool.
- `hatch_xml_output`: Output from the hatch XML generation command.
- `hatch_html_output`: Output from the hatch HTML generation command.
- `timestamp`: Timestamp of the report generation.

**Example Call:**

```json
{
  "tool_name": "create_coverage_report",
  "arguments": {
    "force_rebuild": true
  }
}
```

### Log Searching

Tools for searching and filtering log files managed by the `AnalysisEngine`.

#### Common Parameters for Search Tools

These parameters are available for `search_log_all_records`, `search_log_time_based`, `search_log_first_n_records`, and `search_log_last_n_records`.

| Name                            | Type    | Required | Default   | Description                                                                                                |
|---------------------------------|---------|----------|-----------|------------------------------------------------------------------------------------------------------------|
| `scope`                         | string  | No       | "default" | Logging scope to search within (from `.env` scopes or default).                                            |
| `context_before`                | integer | No       | `2`       | Number of lines before a match.                                                                            |
| `context_after`                 | integer | No       | `2`       | Number of lines after a match.                                                                             |
| `log_dirs_override`             | string  | No       | `""`      | Comma-separated list of log directories, files, or glob patterns (overrides `.env` for file locations).      |
| `log_content_patterns_override` | string  | No       | `""`      | Comma-separated list of REGEX patterns for log messages (overrides `.env` content filters).                  |

#### `search_log_all_records`

Searches for all log records, optionally filtering by scope and content patterns, with context.

**Parameters:** (Includes Common Search Parameters)

**Returns:**

A list of JSON objects, where each object represents a found log entry and includes:

- `timestamp`: Parsed timestamp of the log entry.
- `raw_line`: The original log line.
- `file_path`: Path to the log file containing the entry.
- `line_number`: Line number in the file.
- `context_before_lines`: List of lines before the matched line.
- `context_after_lines`: List of lines after the matched line.
- (Other fields from `LogEntry` model)

**Example Call:**

```json
{
  "tool_name": "search_log_all_records",
  "arguments": {
    "scope": "my_app_scope",
    "log_content_patterns_override": "ERROR.*database"
  }
}
```

#### `search_log_time_based`

Searches logs within a time window, optionally filtering, with context.

**Parameters:** (Includes Common Search Parameters plus)

| Name      | Type    | Required | Default | Description                                |
|-----------|---------|----------|---------|--------------------------------------------|
| `minutes` | integer | No       | `0`     | Search logs from the last N minutes.       |
| `hours`   | integer | No       | `0`     | Search logs from the last N hours.         |
| `days`    | integer | No       | `0`     | Search logs from the last N days.          |

**Returns:** (List of JSON objects, same structure as `search_log_all_records`)

**Example Call:**

```json
{
  "tool_name": "search_log_time_based",
  "arguments": {
    "hours": 2,
    "scope": "server_logs",
    "context_after": 5
  }
}
```

#### `search_log_first_n_records`

Searches for the first N (oldest) records, optionally filtering, with context.

**Parameters:** (Includes Common Search Parameters plus)

| Name    | Type    | Required | Default | Description                                                   |
|---------|---------|----------|---------|---------------------------------------------------------------|
| `count` | integer | Yes      |         | Number of first (oldest) matching records to return (must be > 0). |

**Returns:** (List of JSON objects, same structure as `search_log_all_records`)

**Example Call:**

```json
{
  "tool_name": "search_log_first_n_records",
  "arguments": {
    "count": 10,
    "log_dirs_override": "/var/log/app_archive/*.log"
  }
}
```

#### `search_log_last_n_records`

Search for the last N (newest) records, optionally filtering, with context.

**Parameters:** (Includes Common Search Parameters plus)

| Name    | Type    | Required | Default | Description                                                  |
|---------|---------|----------|---------|--------------------------------------------------------------|
| `count` | integer | Yes      |         | Number of last (newest) matching records to return (must be > 0). |

**Returns:** (List of JSON objects, same structure as `search_log_all_records`)

**Example Call:**

```json
{
  "tool_name": "search_log_last_n_records",
  "arguments": {
    "count": 50,
    "scope": "realtime_feed"
  }
}
```

### Server Utilities

General utility tools for the MCP server.

#### `ping`

Checks if the MCP server is alive and returns status information.

**Parameters:** None

**Returns:**

A string with status, timestamp, and a message indicating the server is running.

**Example Call:**

```json
{
  "tool_name": "ping",
  "arguments": {}
}
```

#### `get_server_env_details`

Returns `sys.path` and `sys.executable` and other environment details from the running MCP server.

**Parameters:** None

**Returns:**

A JSON object with:

- `sys_executable`: Path to the Python interpreter running the server.
- `sys_path`: List of paths in `sys.path`.
- `cwd`: Current working directory of the server.
- `environ_pythonpath`: Value of the `PYTHONPATH` environment variable, if set.

**Example Call:**

```json
{
  "tool_name": "get_server_env_details",
  "arguments": {}
}
```

#### `request_server_shutdown`

Requests the MCP server to shut down gracefully.

**Parameters:** None

**Returns:**

A string confirming that the shutdown has been initiated.

**Example Call:**

```json
{
  "tool_name": "request_server_shutdown",
  "arguments": {}
}
```

---

## CLI Client (`log-analyzer`)

The `log-analyzer` command-line interface provides access to log searching functionalities.

### Global Options

These options apply to the main `log-analyzer` command and are available before specifying a sub-command.

| Option              | Argument Type | Description                                   |
|---------------------|---------------|-----------------------------------------------|
| `-h`, `--help`      |               | Show help message and exit.                   |
| `--env-file`        | PATH          | Path to a custom `.env` file for configuration. |

### Search Commands (`log-analyzer search`)

Base command: `log-analyzer search [OPTIONS] COMMAND [ARGS]...`

#### Common Search Options

These options can be used with `all`, `time`, `first`, and `last` search commands.

| Option                             | Alias    | Type    | Default   | Description                                                                                                |
|------------------------------------|----------|---------|-----------|------------------------------------------------------------------------------------------------------------|
| `--scope`                          |          | STRING  | "default" | Logging scope to search within (from .env or default).                                                     |
| `--before`                         |          | INTEGER | `2`       | Number of context lines before a match.                                                                    |
| `--after`                          |          | INTEGER | `2`       | Number of context lines after a match.                                                                     |
| `--log-dirs`                       |          | STRING  | `None`    | Comma-separated list of log directories, files, or glob patterns to search (overrides .env for file locations).|
| `--log-patterns`                   |          | STRING  | `None`    | Comma-separated list of REGEX patterns to filter log messages (overrides .env content filters).                |

#### `log-analyzer search all`

Searches for all log records matching configured patterns.
Usage: `log-analyzer search all [COMMON_SEARCH_OPTIONS]`

**Example:**

```shell
log-analyzer search all --scope my_scope --log-patterns "CRITICAL" --before 1 --after 1
```

#### `log-analyzer search time`

Searches logs within a specified time window.
Usage: `log-analyzer search time [TIME_OPTIONS] [COMMON_SEARCH_OPTIONS]`

**Time Options:**

| Option      | Type    | Default | Description                                |
|-------------|---------|---------|--------------------------------------------|
| `--minutes` | INTEGER | `0`     | Search logs from the last N minutes.       |
| `--hours`   | INTEGER | `0`     | Search logs from the last N hours.         |
| `--days`    | INTEGER | `0`     | Search logs from the last N days.          |

**Example:**

```shell
log-analyzer search time --hours 1 --log-dirs "/var/log/app.log"
```

#### `log-analyzer search first`

Searches for the first N (oldest) matching log records.
Usage: `log-analyzer search first --count INTEGER [COMMON_SEARCH_OPTIONS]`

**Required Option:**

| Option    | Type    | Description                                                   |
|-----------|---------|---------------------------------------------------------------|
| `--count` | INTEGER | Number of first (oldest) matching records to return.          |

**Example:**

```shell
log-analyzer search first --count 5 --scope important_logs
```

#### `log-analyzer search last`

Searches for the last N (newest) matching log records.
Usage: `log-analyzer search last --count INTEGER [COMMON_SEARCH_OPTIONS]`

**Required Option:**

| Option    | Type    | Description                                                  |
|-----------|---------|--------------------------------------------------------------|
| `--count` | INTEGER | Number of last (newest) matching records to return.          |

**Example:**

```shell
log-analyzer search last --count 20
```

---

## Error Handling

- **MCP Server:** Errors are returned as JSON objects with `code` and `message` fields, conforming to MCP error standards.
- **CLI Client:** Errors are typically printed to stderr.

Common error types include invalid parameters, file not found, or issues with the underlying `AnalysisEngine` configuration or execution.
