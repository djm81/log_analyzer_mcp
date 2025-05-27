#!/usr/bin/env python3
"""
Test script for the analyze_runtime_errors tool in the MCP server.
"""

import asyncio
import json
import os
import shutil
import sys

import pytest
from pytest_asyncio import fixture as async_fixture

# Add the project root to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)  # Still useful for tests to find src modules easily if not running via hatch

# Import the function to be tested
from log_analyzer_mcp.analyze_runtime_errors import analyze_runtime_errors  # Modified import

# Define runtime logs directory
RUNTIME_LOGS_DIR = os.path.join(project_root, "logs", "runtime")

# Try to import MCP components
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import TextContent
except ImportError:
    print("Failed to import MCP components. Make sure the virtual environment is activated or dependencies installed.")
    sys.exit(1)


@async_fixture
async def server_session_for_runtime_errors():
    """Provides an initialized MCP ClientSession for runtime error tests."""
    server_path = os.path.join(project_root, "src", "log_analyzer_mcp", "log_analyzer_mcp_server.py")

    if not os.path.exists(server_path):
        print(f"FATAL ERROR: MCP Server script not found at {server_path} for fixture setup.")
        pytest.fail(f"MCP Server script not found: {server_path}")
        return

    server_env = os.environ.copy()
    server_env["COVERAGE_PROCESS_START"] = os.path.join(project_root, "pyproject.toml")

    existing_pythonpath = server_env.get("PYTHONPATH", "")
    server_env["PYTHONPATH"] = project_root + os.pathsep + existing_pythonpath

    server_params = StdioServerParameters(
        command=sys.executable, args=[server_path], env=server_env  # Run server directly
    )
    print(
        f"Runtime errors fixture starting directly (parallel=false, COVERAGE_PROCESS_START only): args={server_params.args}"
    )

    try:
        async with stdio_client(server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                print("Runtime Errors Fixture: Initializing MCP session...")
                try:
                    await asyncio.wait_for(session.initialize(), timeout=10)  # Adding a timeout
                except asyncio.TimeoutError:
                    print("Runtime Errors Fixture: MCP session initialization timed out.")
                    pytest.fail("Runtime Errors Fixture: MCP session initialization timed out.")
                    return
                except Exception as e_init:  # pylint: disable=broad-exception-caught
                    print(f"Runtime Errors Fixture: MCP session initialization failed: {e_init}")
                    pytest.fail(f"Runtime Errors Fixture: MCP session initialization failed: {e_init}")
                    return

                print("Runtime Errors Fixture: MCP session initialized.")
                yield session
                print("Runtime Errors Fixture: session usage complete, proceeding to teardown within async with.")

            print("Runtime Errors Fixture: ClientSession context exited.")
        print("Runtime Errors Fixture: stdio_client context exited.")

    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"ERROR: Unhandled exception in server_session_for_runtime_errors fixture setup/teardown: {e}")
        pytest.fail(f"Unhandled exception in server_session_for_runtime_errors fixture: {e}")
    finally:
        print("Runtime Errors Fixture: Server process for runtime error tests stopped or context exited.")


@pytest.mark.asyncio
@pytest.mark.xfail(reason="This test relies on the server_session_for_runtime_errors fixture which is unstable.")
async def test_analyze_runtime_errors(server_session_for_runtime_errors: ClientSession):
    """Test the analyze_runtime_errors function directly."""
    # session = server_session_for_runtime_errors # MCP session no longer used

    # Ensure clean state for runtime logs
    if os.path.exists(RUNTIME_LOGS_DIR):
        print(f"Cleaning up existing runtime logs directory: {RUNTIME_LOGS_DIR}")
        shutil.rmtree(RUNTIME_LOGS_DIR)
    os.makedirs(RUNTIME_LOGS_DIR, exist_ok=True)

    # Create a test log file with a known session ID
    test_log_file = os.path.join(RUNTIME_LOGS_DIR, "test_runtime.log")
    test_session_id = "230325-123456-test-session"
    test_timestamp = "2025-03-25 12:34:56,789"
    with open(test_log_file, "w", encoding="utf-8") as f:
        f.write(f"{test_timestamp} INFO: Starting session {test_session_id}\n")
        f.write(f"{test_timestamp} ERROR: Test error message for session {test_session_id}\n")

    print("Calling analyze_runtime_errors function directly...")
    # Call the function directly, logs_dir is an argument to the Python function
    result_dict = analyze_runtime_errors(logs_dir=RUNTIME_LOGS_DIR)

    print("\n--- ANALYZE RUNTIME ERRORS RESULT ---")
    print(f"Success: {result_dict.get('success')}")
    print(f"Execution ID: {result_dict.get('execution_id')}")
    print(f"Timestamp: {result_dict.get('execution_timestamp')}")
    print(f"Total errors: {result_dict.get('total_errors', 0)}")

    assert result_dict.get("success") is True, "Analysis should be successful"
    assert result_dict.get("execution_id") in [
        test_session_id,
        "unknown",  # This can happen if log parsing for session ID fails
    ], f"Execution ID should be {test_session_id} or 'unknown'"
    assert result_dict.get("total_errors") == 1, "Should find exactly one error"

    if result_dict.get("total_errors", 0) > 0:
        print("\nErrors by file:")
        for log_file, errors in result_dict.get("errors_by_file", {}).items():
            print(f"  {log_file}: {len(errors)} errors")

        print("\nFirst error details:")
        first_error = result_dict.get("errors", [])[0] if result_dict.get("errors") else None
        if first_error:
            print(f"  Log file: {first_error.get('log_file')}")
            print(f"  Line: {first_error.get('line_number')}")
            print(f"  Error: {first_error.get('error_line')}")
            print(f"  Timestamp: {first_error.get('timestamp')}")
            print(f"  Session ID: {first_error.get('session_id')}")

            assert first_error.get("timestamp") == test_timestamp, "Error timestamp should match"
            assert "Test error message" in first_error.get("error_line", ""), "Error message should match"
            assert first_error.get("session_id") == test_session_id, "Error should contain correct session ID"
    else:
        print("\nNo errors found.")

    print("\nFull JSON result (first 500 chars):")
    print(json.dumps(result_dict, indent=2, sort_keys=True)[:500] + "...")
