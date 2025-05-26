# MCP (Model-Context-Protocol) Scripts

This directory contains scripts for testing and verifying the MCP server functionality.

## Available Scripts

### log_analyzer_mcp_server.py

The main MCP server implementation that provides log analysis tools for Cursor.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/log_analyzer_mcp_server.py

# From coding-factory directory
./tests/log_analyzer_mcp/log_analyzer_mcp_server.py
```

### test_log_analyzer_mcp_server.py

A test script to verify the functionality of the Log Analyzer MCP Server.

**Usage:**

```bash
# Run full test suite
./coding-factory/tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py

# Run quick tests (skips lengthy test runs)
./coding-factory/tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py --quick

# Run quick tests including the lengthy run_tests_no_verbosity
./coding-factory/tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py --quick --run-all

# Test specific agent unit tests using run_unit_test
./coding-factory/tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py --test-agent qa_agent
```

### analyze_runtime_errors.py

A script that analyzes runtime logs for errors in the most recent execution.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/analyze_runtime_errors.py [--logs-dir PATH] [--format json|text]

# Default behavior uses runtime logs directory at coding-factory/logs/runtime/
./coding-factory/tests/log_analyzer_mcp/analyze_runtime_errors.py

# Specify custom logs directory
./coding-factory/tests/log_analyzer_mcp/analyze_runtime_errors.py --logs-dir /path/to/logs

# Output in JSON format
./coding-factory/tests/log_analyzer_mcp/analyze_runtime_errors.py --format json
```

### create_coverage_report.sh

A script that generates test coverage reports for the project codebase.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/create_coverage_report.sh

# From coding-factory directory
./tests/log_analyzer_mcp/create_coverage_report.sh
```

This script generates:

- A terminal output with coverage statistics
- An HTML coverage report at `tests/coverage_html_report/index.html`
- An XML coverage report at `tests/coverage.xml`
- A coverage data file at `tests/.coverage`

### verify_mcp.py

A simple script to verify that the MCP server is running and responding to requests.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/verify_mcp.py

# From coding-factory directory
./tests/log_analyzer_mcp/verify_mcp.py
```

### run_mcp_test.sh

A simple shell script to test the MCP server connection with colored output.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/run_mcp_test.sh

# From coding-factory directory
./tests/log_analyzer_mcp/run_mcp_test.sh
```

### cleanup.sh

A utility script to remove temporary files and logs related to the MCP server.

**Usage:**

```bash
# From project root
./coding-factory/tests/log_analyzer_mcp/cleanup.sh

# From coding-factory directory
./tests/log_analyzer_mcp/cleanup.sh
```

This script cleans up:

- MCP logs in the `~/cursor_mcp_logs` directory
- Temporary Python files (*.pyc, `__pycache__`)
- Log files in the MCP directory
- Temporary files (*.tmp)

Note: This script does not remove the main system logs in the `coding-factory/logs` directory.

## Server Configuration

The MCP server is configured in `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "log_analyzer_mcp_server": {
      "command": "<path-to-your-repository>/.venv/bin/python",
      "args": [
        "<path-to-your-repository>/coding-factory/tests/log_analyzer_mcp/log_analyzer_mcp_server.py"
      ],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": "<path-to-your-repository>/coding-factory",
        "MCP_LOG_LEVEL": "DEBUG",
        "MCP_LOG_FILE": "~/cursor_mcp_logs/log_analyzer_mcp_sdk.log"
      }
    }
  }
}
```

## Log Directory Structure

The MCP server uses the following log directory structure:

```shell
coding-factory/
├── logs/
│   ├── runtime/          # Runtime logs directory for execution analysis
│   │   └── *.log        # Runtime log files with session IDs
│   └── run_all_tests.log # Test execution logs
```

The `runtime/` directory is automatically created and managed by the MCP server for storing runtime logs. Each service in the Docker environment has access to this directory through volume mapping.

## Troubleshooting

If you encounter issues with the MCP server:

1. Check the logs in `~/cursor_mcp_logs/log_analyzer_mcp_sdk.log`
2. Ensure the server is running properly by executing `verify_mcp.py`
3. Make sure your Python environment is set up correctly with all required dependencies
4. Verify that the runtime logs directory exists at `coding-factory/logs/runtime/`
5. If necessary, restart Cursor after making changes to the MCP server implementation

## MCP Server Tools

The MCP server provides the following tools that can be used by Cursor:

1. `analyze_tests` - Analyzes the results of the most recent test run and provides detailed information about failures.

    - Parameters:
        - `summary_only` (boolean, optional) - Whether to return only a summary of the test results

    - Features:
        - When `summary_only=false` (default), provides detailed information about each failed test
        - Includes test names, modules, files, error messages, and tracebacks for failed tests
        - Provides recommendations based on common failure patterns detected
        - Categorizes failures by error type (import errors, assertion errors, timeouts, etc.)
        - Returns error counts by type (test failures, type errors, class structure errors, import failures)

2. `run_tests_no_verbosity` - Runs all tests with minimal output (verbosity level 0).

    - Features:
        - Shows only errors and test summary
        - Filters output to show critical information only
        - Includes class structure and import failures
        - Returns basic test statistics
        - Can take up to 5 minutes to complete (timeout set to 300 seconds)

3. `run_tests_verbose` - Runs all tests with verbosity level 1 (verbose).

    - Features:
        - Shows errors, warnings, and basic test progress
        - Includes module-level test statistics
        - Provides error counts by category
        - Shows test execution progress
        - Returns filtered analysis with relevant error details
        - Can take up to 5 minutes to complete (timeout set to 300 seconds)

4. `run_tests_very_verbose` - Runs all tests with verbosity level 2 (very verbose).

    - Features:
        - Shows all test output including passed tests
        - Includes detailed diagnostics
        - Provides comprehensive test execution information
        - Returns complete analysis with all available details
        - Can take up to 5 minutes to complete (timeout set to 300 seconds)

5. `run_unit_test` - Runs tests for a specific agent only, significantly improving performance during focused development.

    - Parameters:
        - `agent` (string, required) - The name of the agent to test (e.g., 'qa_agent', 'backlog_agent')
        - `verbosity` (integer, optional, default=1) - The verbosity level (0, 1, or 2)

    - Features:
        - Runs tests matching the agent's patterns including both main agent tests and healthcheck tests
        - Significantly reduces test execution time compared to running all tests
        - Automatically skips type checks and import checks for faster execution
        - Dramatically improves performance (up to 44x faster than running all tests)
        - Supports all verbosity levels (0, 1, or 2)
        - Returns structured test results for both main agent tests and healthcheck tests
        - Special handling for unique cases like `redis_shutdown_monitor`
        - Creates correctly located coverage files in the `tests/` directory
        - Returns combined summary showing results of both test types in a consistent format
        - Ideal for iterative development on specific agent modules
        - Can complete in seconds rather than minutes for large test suites

6. `analyze_runtime_errors` - Analyzes runtime logs for errors in the most recent execution.

    - Features:
        - Uses dedicated runtime logs directory (`logs/runtime/`) for better organization
        - Automatically finds the most recent session ID from runtime logs
        - Searches all log files in the runtime directory for errors related to the session
        - Extracts error context (surrounding lines) for better understanding
        - Groups errors by log file for easier troubleshooting
        - Returns structured error information with timestamps
        - Shows the total number of errors across all log files
        - Provides a backward-compatible flat list of errors
        - Creates runtime logs directory if it doesn't exist
        - Supports custom logs directory via `--logs-dir` argument

7. `create_coverage_report` - Generates test coverage reports for the codebase.

    - Parameters:
        - `force_rebuild` (boolean, optional) - Whether to force rebuilding the report even if it exists

    - Features:
        - Generates HTML and XML coverage reports
        - Calculates overall code coverage percentage
        - Creates detailed reports showing which lines of code are covered by tests
        - Automatically uses the coverage threshold from `.coveragerc` (default: 80%)
        - Returns paths to generated reports and coverage statistics

8. `get_coverage_report` - Retrieves and parses detailed coverage data from the most recent report.

    - Features:
        - Provides overall coverage percentage and threshold comparison
        - Groups modules by coverage level (critical, poor, medium, good, excellent)
        - Lists specific lines not covered by tests for each module
        - Calculates coverage gap to meet the required threshold
        - Returns detailed module-by-module coverage statistics

9. `ping` - Checks if the MCP server is alive.

    - Features:
        - Returns server status
        - Includes timestamp
        - Verifies server responsiveness

## Output Formats

Test results and analysis can be output in three verbosity levels:

1. **Minimal Output (Level 0)**

    - Brief overview of test results
    - Pass/fail/skip counts
    - Critical errors only (class structure and import failures)
    - Test execution summary
    - Basic error categorization

2. **Verbose Output (Level 1)**

    - Detailed test results
    - Full error messages and tracebacks
    - Module statistics
    - Error counts by category:
        - Test failures
        - Type errors
        - Class structure errors
        - Import failures
    - Test execution progress
    - Warning messages

3. **Very Verbose Output (Level 2)**

    - Complete test execution details
    - All test output including passed tests
    - Comprehensive diagnostics
    - Full module statistics
    - Detailed error analysis
    - Debug-level information
    - Performance metrics

Each output format includes:

- Overall test status (passed/failed/skipped)
- Test execution time and duration
- Log file metadata (path, timestamp, age)
- Structured error details when applicable
- Human-readable summary text

## Log Analysis

The log analyzer provides detailed analysis of test runs, including:

- Overall test status (passed/failed/skipped)
- Test execution time and performance metrics
- Module-level statistics and pass rates
- Detailed failure analysis with error categorization
- Recommendations for fixing common issues
- Historical test execution data

## Coverage Reports

The coverage reports provide detailed analysis of test coverage, including:

- Overall code coverage percentage
- Comparison against the required threshold (default: 80%)
- Module-by-module coverage statistics
- Categorization of modules by coverage level
- Lists of uncovered lines for each module
- HTML reports for visual inspection of coverage
- XML reports for integration with CI/CD tools

## Performance Improvements

The ability to run unit tests for a specific agent provides significant performance improvements:

- Running tests for a single agent: ~2-3 seconds
- Running the entire test suite: ~113 seconds
- Performance improvement: Up to 44x faster for focused development

This makes iterative development much more efficient by reducing feedback cycles from minutes to seconds.

Additionally, when testing specific agent modules:

- Type checks and import checks are automatically skipped unless explicitly requested
- Full file paths are used to reliably locate test files
- Files are verified to exist before attempting to run tests
- Both main agent tests and corresponding healthcheck tests are run automatically
- Coverage files are generated in the correct `tests/` directory
- Combined summary provides clear results for both test types

To include type and import checks when running tests for a specific agent, use the `--include-all` flag with the `run_all_tests.py` script directly.

## Examples

### Using the Unit Test Runner

To run tests for a specific agent using Python:

```python
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_unit_test():
    server_path = 'tests/log_analyzer_mcp/log_analyzer_mcp_server.py'
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool('run_unit_test', {
                'agent': 'qa_agent',
                'verbosity': 1
            })
            # Process response

asyncio.run(run_unit_test())
```

### Analyzing Runtime Errors

To analyze runtime errors using Python:

```python
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def analyze_runtime_errors():
    server_path = 'tests/log_analyzer_mcp/log_analyzer_mcp_server.py'
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            response = await session.call_tool('analyze_runtime_errors', {})
            result = json.loads(response.content[0].text)
            
            if result['success']:
                print(f"Found {result['total_errors']} errors")
                for error in result['errors']:
                    print(f"Error at {error['timestamp']}: {error['error_line']}")

asyncio.run(analyze_runtime_errors())
```

Or using the command line:

```bash
cd /Users/dominikus/git/nold-ai/nold-ai-automation/coding-factory && python -c "import asyncio, sys; from mcp import ClientSession, StdioServerParameters; from mcp.client.stdio import stdio_client; async def run(): server_path = 'tests/log_analyzer_mcp/log_analyzer_mcp_server.py'; server_params = StdioServerParameters(command=sys.executable, args=[server_path]); async with stdio_client(server_params) as (read, write): async with ClientSession(read, write) as session: await session.initialize(); await session.call_tool('analyze_runtime_errors', {}); asyncio.run(run())"
```

## MCP Log Analyzer Tools

This directory contains tools designed to analyze test logs and interact with the MCP server in Cursor.

### Features

The log analyzer tools provide the following capabilities:

1. **Test Analysis**
   - `analyze_tests()` - Parses test logs to extract pass/fail information
   - `run_tests_no_verbosity()` - Runs all tests with minimal output
   - `run_tests_verbose()` - Runs all tests with normal verbosity
   - `run_tests_very_verbose()` - Runs all tests with detailed output
   - `run_unit_test(agent, verbosity)` - Runs tests for a specific agent only, including:
     - Tests matching the agent's patterns (both main agent tests and healthcheck tests)
     - Significantly reduces test execution time compared to running all tests
     - Automatically skips type checks and import checks for faster execution
     - Special handling for unique cases like `redis_shutdown_monitor`
     - Correctly locates coverage files in the `tests/` directory
     - Returns a combined summary showing results of both test types

2. **Coverage Analysis**
   - `create_coverage_report()` - Generates coverage reports in HTML and XML formats
   - `get_coverage_report()` - Parses coverage data to identify test gaps

3. **Runtime Analysis**
   - `analyze_runtime_errors()` - Extracts error information from runtime logs
   - `ping()` - Checks if the MCP server is alive

### Test Performance Improvements

The tools are designed for optimal performance:

- Running tests for a single agent takes approximately 2-3 seconds
- Running the entire test suite takes around 113 seconds
- Performance improvement of up to 44x faster for focused development

### Usage Examples

#### Running Tests for a Specific Agent

```python
run_unit_test(agent="supervisor_agent", verbosity=1)
```

This will:

- Run tests that match the `supervisor_agent` patterns
- Include both main tests (test_supervisor_agent.py) and healthcheck tests (test_supervisor_healthcheck.py)
- Set verbosity to normal (1)
- Output structured results for both test types

#### Analyzing Test Results

```python
analyze_tests(summary_only=True)
```

This will:

- Find the most recent test log file
- Parse the test results
- Return a summary of passes and failures

#### Generating Coverage Reports

```python
create_coverage_report(force_rebuild=True)
```

This will:

- Regenerate the coverage report even if it exists
- Create HTML and XML reports in the tests directory

#### Analyzing Coverage Data

```python
coverage_data = get_coverage_report()
```

This will:

- Parse the coverage.xml file
- Return detailed metrics about test coverage
- Identify modules that need more tests

### Module Structure

The MCP Log Analyzer is structured as follows:

1. **Core Modules**
   - `log_analyzer_mcp_server.py` - Main MCP server implementing the Model Context Protocol
   - `log_analyzer.py` - Core log analysis functionality, usable both as a module and command-line tool
   - `analyze_runtime_errors.py` - Runtime log error analysis for execution IDs, usable both as a module and command-line tool
   - `parse_coverage.py` - Coverage report parsing utilities

2. **Shell Scripts**
   - `create_coverage_report.sh` - Wrapper for generating coverage reports
   - `cleanup.sh` - Utility for cleaning up temporary files
   - `run_mcp_test.sh` - Helper script for running MCP tests

3. **Test Modules**
   - `test_log_analyzer_mcp_server.py` - Unit tests for the MCP server
   - `verify_mcp.py` - Verification script for MCP functionality

### Command-Line Usage

The individual modules can be used directly from the command line:

#### Log Analyzer

```bash
python log_analyzer.py /path/to/logfile.log --format json
```

Options:

- `--format` - Output format (text or json)
- `--summary-only` - Show only summary information

#### Runtime Error Analyzer

```bash
python analyze_runtime_errors.py --format json
```

Options:

- `--logs-dir` - Directory containing log files
- `--format` - Output format (text or json)
