#!/usr/bin/env python3
"""
Test script for the analyze_runtime_errors tool in the MCP server.
"""

import os
import sys
import asyncio
import json
import shutil
import pytest
from pytest_asyncio import fixture as async_fixture
import uuid # Import uuid for unique coverage file names

# Add the project root to the path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root) # Still useful for tests to find src modules easily if not running via hatch

# Define runtime logs directory
RUNTIME_LOGS_DIR = os.path.join(project_root, 'logs', 'runtime')

# Try to import MCP components
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.types import TextContent
    from mcp.client.stdio import stdio_client
except ImportError:
    print("Failed to import MCP components. Make sure the virtual environment is activated or dependencies installed.")
    sys.exit(1)

@async_fixture
async def server_session_for_runtime_errors():
    """Provides an initialized MCP ClientSession for runtime error tests."""
    server_path = os.path.join(project_root, 'src', 'log_analyzer_mcp', 'log_analyzer_mcp_server.py')
    
    if not os.path.exists(server_path):
        print(f"FATAL ERROR: MCP Server script not found at {server_path} for fixture setup.")
        pytest.fail(f"MCP Server script not found: {server_path}")
        return

    server_env = os.environ.copy()
    server_env["COVERAGE_PROCESS_START"] = os.path.join(project_root, 'pyproject.toml')

    existing_pythonpath = server_env.get("PYTHONPATH", "")
    server_env["PYTHONPATH"] = project_root + os.pathsep + existing_pythonpath

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[
            server_path # Run server directly
        ],
        env=server_env
    )
    print(f"Runtime errors fixture starting directly (parallel=false, COVERAGE_PROCESS_START only): args={{server_params.args}}")
    
    stdio_client_cm = stdio_client(server_params)
    client_session_cm = None
    session = None

    try:
        read_stream, write_stream = await stdio_client_cm.__aenter__()
        client_session_cm = ClientSession(read_stream, write_stream)
        session = await client_session_cm.__aenter__()
        
        print("Runtime Errors Fixture: Initializing MCP session...")
        try:
            await asyncio.wait_for(session.initialize(), timeout=10) # Adding a timeout
        except asyncio.TimeoutError:
            print("Runtime Errors Fixture: MCP session initialization timed out.")
            pytest.fail("Runtime Errors Fixture: MCP session initialization timed out.")
            return
        print("Runtime Errors Fixture: MCP session initialized.")
        yield session
    finally:
        print("Runtime Errors Fixture: Tearing down MCP session...")
        if session and client_session_cm and hasattr(client_session_cm, '__aexit__'):
            print("Runtime Errors Fixture: Exiting ClientSession context manager...")
            try:
                await client_session_cm.__aexit__(None, None, None)
                print("Runtime Errors Fixture: ClientSession context manager exited.")
            except Exception as e:
                print(f"Runtime Errors Fixture: Error during ClientSession __aexit__: {e}")

        if hasattr(stdio_client_cm, '__aexit__'):
            print("Runtime Errors Fixture: Exiting stdio_client context manager...")
            try:
                await stdio_client_cm.__aexit__(None, None, None)
                print("Runtime Errors Fixture: stdio_client context manager exited.")
            except Exception as e:
                print(f"Runtime Errors Fixture: Error during stdio_client __aexit__: {e}")
        print("Runtime Errors Fixture: Server process for runtime error tests stopped or context exited.")

@pytest.mark.asyncio
async def test_analyze_runtime_errors(server_session_for_runtime_errors: ClientSession):
    """Test the analyze_runtime_errors tool in the MCP server."""
    session = server_session_for_runtime_errors

    # Ensure clean state for runtime logs (moved from fixture as it's test-specific data setup)
    if os.path.exists(RUNTIME_LOGS_DIR):
        print(f"Cleaning up existing runtime logs directory: {RUNTIME_LOGS_DIR}")
        shutil.rmtree(RUNTIME_LOGS_DIR)
    os.makedirs(RUNTIME_LOGS_DIR, exist_ok=True)
    
    # Create a test log file with a known session ID
    test_log_file = os.path.join(RUNTIME_LOGS_DIR, 'test_runtime.log')
    test_session_id = '230325-123456-test-session'
    test_timestamp = '2025-03-25 12:34:56,789'
    with open(test_log_file, 'w') as f:
        f.write(f"{test_timestamp} INFO: Starting session {test_session_id}\n")
        f.write(f"{test_timestamp} ERROR: Test error message for session {test_session_id}\n")
    
    print("Calling analyze_runtime_errors tool...")
    result = await session.call_tool('analyze_runtime_errors', {})
    
    # Access content from CallToolResult
    if hasattr(result, 'content') and result.content and len(result.content) > 0:
        content_item = result.content[0]
        if isinstance(content_item, TextContent):
            text_content = content_item.text
            try:
                result_dict = json.loads(text_content)
            except json.JSONDecodeError:
                print(f"Error: Failed to parse text content as JSON: {text_content[:100]}...")
                assert False, "Failed to parse JSON response"
        else:
            print(f"Error: Expected TextContent, got {type(content_item)}")
            assert False, f"Expected TextContent, got {type(content_item)}"
    else:
        print("Error: No content in the result")
        assert False, "No content in MCP response"
    
    print("\n--- ANALYZE RUNTIME ERRORS RESULT ---")
    print(f"Success: {result_dict.get('success')}")
    print(f"Execution ID: {result_dict.get('execution_id')}")
    print(f"Timestamp: {result_dict.get('execution_timestamp')}")
    print(f"Total errors: {result_dict.get('total_errors', 0)}")
    
    assert result_dict.get('success') is True, "Analysis should be successful"
    assert result_dict.get('execution_id') in [test_session_id, "unknown"], f"Execution ID should be either {test_session_id} or 'unknown'"
    assert result_dict.get('total_errors') == 1, "Should find exactly one error"
    
    if result_dict.get('total_errors', 0) > 0:
        print("\nErrors by file:")
        for log_file, errors in result_dict.get('errors_by_file', {}).items():
            print(f"  {log_file}: {len(errors)} errors")
            
        print("\nFirst error details:")
        first_error = result_dict.get('errors', [])[0] if result_dict.get('errors') else None
        if first_error:
            print(f"  Log file: {first_error.get('log_file')}")
            print(f"  Line: {first_error.get('line_number')}")
            print(f"  Error: {first_error.get('error_line')}")
            print(f"  Timestamp: {first_error.get('timestamp')}")
            print(f"  Session ID: {first_error.get('session_id')}")
            
            assert first_error.get('timestamp') == test_timestamp, "Error timestamp should match"
            assert "Test error message" in first_error.get('error_line', ''), "Error message should match"
            assert first_error.get('session_id') == test_session_id, "Error should contain correct session ID"
    else:
        print("\nNo errors found.")
    
    print("\nFull JSON result:")
    print(json.dumps(result_dict, indent=2, sort_keys=True)[:500] + "...") 