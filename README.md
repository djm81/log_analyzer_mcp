# Log Analyzer MCP

[![CI](https://github.com/djm81/log_analyzer_mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/djm81/log_analyzer_mcp/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/djm81/log_analyzer_mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/djm81/log_analyzer_mcp)
[![PyPI - Version](https://img.shields.io/pypi/v/log-analyzer-mcp?color=blue)](https://pypi.org/project/log-analyzer-mcp)

## Overview

**Log Analyzer MCP** is a specialized Model-Context-Protocol (MCP) server designed to integrate with Cursor. It provides tools for analyzing test logs, runtime errors, and code coverage reports, streamlining the development and debugging workflow.

The system is built with Python, utilizing `hatch` for project management and `pytest` for testing. It's designed to be robust and provide actionable insights from various log and report files.

## Key Features

- **MCP Server Implementation**: Provides a suite of tools accessible via the Model-Context-Protocol.
- **Test Log Analysis**: Parses `pytest` output to summarize test results, identify failures, and extract error details.
- **Runtime Error Analysis**: Scans application runtime logs to find and contextualize errors based on execution IDs.
- **Code Coverage Reporting**: Generates and parses code coverage reports (XML format) to provide insights into test effectiveness.
- **Hatch Integration**: Uses `hatch` for dependency management, environment control, and running tests/coverage.
- **Subprocess Coverage**: Includes mechanisms to capture code coverage from subprocesses started by the MCP server tools.

## Getting Started

This project uses `hatch` for environment and project management.

1. **Install Hatch:**
    Follow the instructions on the [official Hatch website](https://hatch.pypa.io/latest/install/).

2. **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd log_analyzer_mcp
    ```

3. **Activate the Hatch environment:**

    ```bash
    hatch shell
    ```

    This will create a virtual environment and install all dependencies if it's the first time.

4. **Run Tests:**

    ```bash
    hatch test
    ```

5. **Run Tests with Coverage:**

    ```bash
    hatch test --cover -v
    ```

For more detailed information on development, testing, and refactoring, please refer to our documentation:

- **[Refactoring Plan](./docs/refactoring/log_analyzer_refactoring_v1.md)**
- **[Testing Overview](./docs/testing/README.md)**

## MCP Server Tools

The server provides tools such as:

- `ping`: Checks server status.
- `analyze_tests`: Analyzes test logs.
- `run_tests_no_verbosity`, `run_tests_verbose`: Runs tests with different verbosity.
- `run_unit_test`: Runs specific unit tests.
- `analyze_runtime_errors`: Analyzes runtime application logs.
- `create_coverage_report`: Generates coverage XML.
- `get_coverage_report`: Parses and returns coverage data.

(Refer to `docs/testing/README.md` for more details on server tools, though this file might need an update to reflect the current state precisely).

## Contributing

Please see `CONTRIBUTING.md` for guidelines.

## License

This project is licensed under the MIT License. See the [LICENSE.md](LICENSE.md) file for the complete license text.
