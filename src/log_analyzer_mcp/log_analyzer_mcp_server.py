#!/usr/bin/env python3
"""
Test Analyzer MCP Server

Implements the Model Context Protocol (MCP) for Cursor to analyze test results.
"""

import asyncio
import anyio
import os
import re
import subprocess
import sys
import functools
from datetime import datetime
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

# MCP and Pydantic related imports
from mcp.shared.exceptions import McpError
from mcp.types import (
    ErrorData,
)
from pydantic import BaseModel, Field

# Project-specific imports
from log_analyzer_mcp.common.logger_setup import LoggerSetup, get_logs_dir
from log_analyzer_mcp.common.utils import build_filter_criteria
from log_analyzer_mcp.core.analysis_engine import AnalysisEngine
from log_analyzer_mcp.test_log_parser import analyze_pytest_log_content

# Explicitly attempt to initialize coverage for subprocesses
if "COVERAGE_PROCESS_START" in os.environ:
    try:
        import coverage

        coverage.process_startup()
        # If your logger is configured very early, you could add a log here:
        # print("DEBUG: coverage.process_startup() called in subprocess.", flush=True)
    except ImportError:
        # print("DEBUG: COVERAGE_PROCESS_START set, but coverage module not found.", flush=True)
        pass  # Or handle error if coverage is mandatory for the subprocess
    except Exception:  # pylint: disable=broad-exception-caught
        # print(f"DEBUG: Error calling coverage.process_startup(): {e}", flush=True)
        pass

# Define project_root and script_dir here as they are used for path definitions
script_dir = os.path.dirname(os.path.abspath(__file__))
# project_root = os.path.dirname(os.path.dirname(script_dir)) # No longer needed here if logger_setup is robust

# Set up logging using centralized configuration
logs_base_dir = get_logs_dir()  # RESTORED - this should now be correct
mcp_log_dir = os.path.join(logs_base_dir, "mcp")  # RESTORED
# Ensure project_root is correctly determined as the actual project root
# Forcing a known-good structure relative to where log_analyzer_mcp_server.py is.
# __file__ is src/log_analyzer_mcp/log_analyzer_mcp_server.py
# script_dir is src/log_analyzer_mcp/
# parent of script_dir is src/
# parent of parent of script_dir is PROJECT_ROOT
# actual_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # REMOVE direct calculation here

# mcp_log_dir = os.path.join(actual_project_root, "logs", "mcp") # REMOVE direct calculation here
os.makedirs(mcp_log_dir, exist_ok=True)  # This is fine, mcp_log_dir is now from get_logs_dir()

# Determine the log file path, prioritizing MCP_LOG_FILE env var
env_log_file = os.getenv("MCP_LOG_FILE")
if env_log_file:
    log_file_path = os.path.abspath(env_log_file)
    # Ensure the directory for the environment-specified log file exists
    env_log_file_dir = os.path.dirname(log_file_path)
    if not os.path.exists(env_log_file_dir):
        try:
            os.makedirs(env_log_file_dir, exist_ok=True)
            # Temporary print to confirm this path is taken
            print(
                f"DEBUG_MCP_SERVER: Ensured directory exists for MCP_LOG_FILE: {env_log_file_dir}",
                file=sys.stderr,
                flush=True,
            )
        except OSError as e:
            print(
                f"Warning: Could not create directory for MCP_LOG_FILE {env_log_file_dir}: {e}",
                file=sys.stderr,
                flush=True,
            )
            # Fallback to default if directory creation fails for env var path
            log_file_path = os.path.join(mcp_log_dir, "log_analyzer_mcp_server.log")
    print(
        f"DEBUG_MCP_SERVER: Using MCP_LOG_FILE from environment: {log_file_path}", file=sys.stderr, flush=True
    )  # ADDED
else:
    log_file_path = os.path.join(mcp_log_dir, "log_analyzer_mcp_server.log")
    print(f"DEBUG_MCP_SERVER: Using default log_file_path: {log_file_path}", file=sys.stderr, flush=True)  # ADDED

logger = LoggerSetup.create_logger("LogAnalyzerMCP", log_file_path, agent_name="LogAnalyzerMCP")
logger.setLevel("DEBUG")  # Set to debug level for MCP server

# CRITICAL DEBUG: Print to stderr immediately after logger setup
print(f"DEBUG_MCP_SERVER: Logger initialized. Attempting to log to: {log_file_path}", file=sys.stderr, flush=True)

logger.info("Log Analyzer MCP Server starting. Logging to %s", log_file_path)

# Initialize AnalysisEngine instance (can be done once)
# It will load .env settings by default upon instantiation.
analysis_engine = AnalysisEngine(logger_instance=logger)

# Update paths for scripts and logs (using project_root and script_dir)
# log_analyzer_path = os.path.join(script_dir, 'log_analyzer.py') # REMOVED
# run_tests_path = os.path.join(project_root, 'tests/run_all_tests.py') # REMOVED - using hatch test directly
# run_coverage_path = os.path.join(script_dir, 'create_coverage_report.sh') # REMOVED - using hatch run hatch-test:* directly
# analyze_runtime_errors_path = os.path.join(script_dir, 'analyze_runtime_errors.py') # REMOVED
test_log_file = os.path.join(
    logs_base_dir, "run_all_tests.log"  # RESTORED logs_base_dir
)  # Main test log, now populated by hatch test output
# coverage_xml_path = os.path.join(logs_base_dir, 'tests', 'coverage', 'coverage.xml') # RESTORED logs_base_dir

# Initialize FastMCP server
# Add lifespan support for startup/shutdown with strong typing
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager


@asynccontextmanager
async def server_lifespan(_server: FastMCP) -> AsyncIterator[None]:  # Simple lifespan, no app context needed
    logger.info("MCP Server Lifespan: Startup phase entered.")
    try:
        yield
    finally:
        logger.info("MCP Server Lifespan: Shutdown phase entered (finally block).")


mcp = FastMCP("log_analyzer", lifespan=server_lifespan)


# Define input models for tool validation
class AnalyzeTestsInput(BaseModel):
    """Parameters for analyzing tests."""

    summary_only: bool = Field(default=False, description="Whether to return only a summary of the test results")


class RunTestsInput(BaseModel):
    """Parameters for running tests."""

    verbosity: int = Field(default=1, description="Verbosity level for the test runner (0-2)", ge=0, le=2)


class CreateCoverageReportInput(BaseModel):
    """Parameters for creating coverage report."""

    force_rebuild: bool = Field(
        default=False, description="Whether to force rebuilding the coverage report even if it already exists"
    )


class RunUnitTestInput(BaseModel):
    """Parameters for running specific unit tests."""

    agent: str = Field(description="The agent to run tests for (e.g., 'qa_agent', 'backlog_agent')")
    verbosity: int = Field(default=1, description="Verbosity level (0=minimal, 1=normal, 2=detailed)", ge=0, le=2)


# Define default runtime logs directory
DEFAULT_RUNTIME_LOGS_DIR = os.path.join(logs_base_dir, "runtime")  # RESTORED logs_base_dir


# async def analyze_test_log(log_file_path: str, summary_only: bool = False) -> Dict[str, Any]: # REMOVED: Functionality moved to test_log_parser
#     """
#     Analyze a test log file and return structured results.
#     ...
#     """
#     ...


@mcp.tool()
async def analyze_tests(summary_only: bool = False) -> dict[str, Any]:
    """Analyze the most recent test run and provide detailed information about failures.

    Args:
        summary_only: Whether to return only a summary of the test results
    """
    logger.info("Analyzing test results (summary_only=%s)...", summary_only)

    log_file = test_log_file

    if not os.path.exists(log_file):
        error_msg = f"Test log file not found at: {log_file}. Please run tests first."
        logger.error(error_msg)
        return {"error": error_msg, "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}}

    try:
        with open(log_file, encoding="utf-8", errors="ignore") as f:
            log_contents = f.read()

        if not log_contents.strip():
            error_msg = f"Test log file is empty: {log_file}"
            logger.warning(error_msg)
            return {"error": error_msg, "summary": {"status": "EMPTY", "passed": 0, "failed": 0, "skipped": 0}}

        analysis = analyze_pytest_log_content(log_contents, summary_only=summary_only)

        # Add metadata similar to the old analyze_test_log function
        log_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        time_elapsed = (datetime.now() - log_time).total_seconds() / 60  # minutes
        analysis["log_file"] = log_file
        analysis["log_timestamp"] = log_time.isoformat()
        analysis["log_age_minutes"] = round(time_elapsed, 1)

        # The analyze_pytest_log_content already returns a structure including 'overall_summary'.
        # If summary_only is true, it returns only that. Otherwise, it returns more details.
        # We can directly return this analysis dictionary.

        # Ensure there's always a summary structure for consistent access, even if minimal
        if "overall_summary" not in analysis:
            analysis["overall_summary"] = {"status": "UNKNOWN", "passed": 0, "failed": 0, "skipped": 0}
        if "summary" not in analysis:  # for backward compatibility or general access
            analysis["summary"] = analysis["overall_summary"]

        logger.info(
            "Test log analysis completed using test_log_parser. Summary status: %s",
            analysis.get("summary", {}).get("status"),
        )
        return analysis

    except Exception as e:  # pylint: disable=broad-exception-caught
        error_msg = f"Error analyzing test log file with test_log_parser: {e}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg, "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}}


async def _run_tests(
    verbosity: Any | None = None,
    agent: str | None = None,
    pattern: str | None = None,
    run_with_coverage: bool = False,
) -> dict[str, Any]:
    """Internal helper function to run tests using hatch.

    Args:
        verbosity: Optional verbosity level (0=minimal, 1=normal, 2=detailed for pytest)
        agent: Optional agent name to run only tests for that agent (e.g., 'qa_agent')
        pattern: Optional pattern to filter test files (e.g., 'test_qa_*.py')
        run_with_coverage: Whether to run tests with coverage enabled via 'hatch test --cover'.
    """
    logger.info(
        "Preparing to run tests via hatch (verbosity=%s, agent=%s, pattern=%s, coverage=%s)...",
        verbosity,
        agent,
        pattern,
        run_with_coverage,
    )

    hatch_base_cmd = ["hatch", "test"]
    pytest_args = []

    # ALWAYS add arguments to ignore the server integration tests to prevent recursion
    # when tests are run *by this tool*.
    pytest_args.extend(
        [
            "--ignore=tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py",
            "--ignore=tests/log_analyzer_mcp/test_analyze_runtime_errors.py",
        ]
    )
    logger.debug("Added ignore patterns for server integration tests (tool-invoked run).")

    if run_with_coverage:
        hatch_base_cmd.append("--cover")
        logger.debug("Coverage enabled for hatch test run.")
        # Tell pytest not to activate its own coverage plugin, as 'coverage run' is handling it.
        pytest_args.append("-p")
        pytest_args.append("no:cov")
        logger.debug("Added '-p no:cov' to pytest arguments for coverage run.")

    # Verbosity for pytest: -q (0), (1), -v (2), -vv (3+)
    if verbosity is not None:
        try:
            v_int = int(verbosity)
            if v_int == 0:
                pytest_args.append("-q")
            elif v_int == 2:
                pytest_args.append("-v")
            elif v_int >= 3:
                pytest_args.append("-vv")
            # Default (verbosity=1) means no specific pytest verbosity arg, relies on hatch default
        except ValueError:
            logger.warning("Invalid verbosity value '%s', using default.", verbosity)

    # Construct pytest -k argument if agent or pattern is specified
    k_expressions = []
    if agent:
        # Assuming agent name can be part of test names like test_agent_... or ..._agent_...
        k_expressions.append(f"{agent}")  # This f-string is for constructing a command argument, not direct logging.
        logger.debug("Added agent '%s' to -k filter expressions.", agent)
    if pattern:
        k_expressions.append(pattern)
        logger.debug("Added pattern '%s' to -k filter expressions.", pattern)

    if k_expressions:
        pytest_args.extend(["-k", " or ".join(k_expressions)])  # pytest -k "expr1 or expr2"

    hatch_cmd = hatch_base_cmd
    if pytest_args:  # Pass pytest arguments after --
        hatch_cmd.extend(["--"] + pytest_args)

    logger.info("Constructed hatch command: %s", " ".join(hatch_cmd))

    # Ensure the log file is cleared or managed before test run if it's always written to the same path
    # For now, assuming log_analyzer.py handles this or we analyze the latest run.
    test_log_output_path = os.path.join(logs_base_dir, "run_all_tests.log")  # RESTORED logs_base_dir
    logger.debug("Expected test output log path for analysis: %s", test_log_output_path)

    try:
        # Run the command using anyio.to_thread to avoid blocking asyncio event loop
        # Ensure text=True for automatic decoding of stdout/stderr to string
        process = await anyio.to_thread.run_sync(  # type: ignore[attr-defined]
            functools.partial(
                subprocess.run,
                hatch_cmd,
                capture_output=True,
                text=True,  # Decode stdout/stderr as text (usually UTF-8)
                check=False,  # Don't raise exception for non-zero exit, handle manually
                timeout=120,  # Add timeout
            )
        )
        stdout_output: str = process.stdout
        stderr_output: str = process.stderr
        rc = process.returncode

        if rc not in [0, 1, 5]:
            logger.error("Hatch test command failed with unexpected pytest return code: %s", rc)
            logger.error("STDOUT:\n%s", stdout_output)
            logger.error("STDERR:\n%s", stderr_output)
            return {
                "success": False,
                "error": f"Test execution failed with code {rc}",
                "test_output": stdout_output + "\n" + stderr_output,
                "analysis_log_path": None,
            }

        logger.debug("Saving combined stdout/stderr from hatch test to %s", test_log_output_path)
        with open(test_log_output_path, "w", encoding="utf-8") as f:
            f.write(stdout_output)
            f.write("\n")
            f.write(stderr_output)
        logger.debug("Content saved to %s", test_log_output_path)

        # _run_tests now only runs tests and saves the log.
        # Analysis is done by the analyze_tests tool or by the caller if needed.

        # The old log_analyzer.main() call is removed.
        # If an agent was specified, the caller of _run_tests might want to know.
        # We can still populate this in the result.
        if agent:
            # analysis_to_return is None, so we can create a small dict or add to a base dict
            # For now, let's just focus on returning the essential info
            pass

        return {
            "success": True,
            "return_code": rc,
            "test_output": stdout_output + "\n" + stderr_output,
            "analysis_log_path": test_log_output_path,  # Provide path to the log for analysis
            # "analysis" field is removed from here as _run_tests no longer parses.
        }

    except subprocess.TimeoutExpired as e:
        stdout_output = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
        stderr_output = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
        stderr_output += f"\nError: Test execution timed out after 170 seconds."
        rc = 1  # Indicate failure
        logger.error("Test execution in _run_tests timed out: %s", e)
        return {
            "success": False,
            "error": stderr_output,
            "test_output": stdout_output + "\n" + stderr_output,
            "analysis_log_path": None,
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("An unexpected error occurred in _run_tests: %s", e, exc_info=True)
        # Capture output if process started
        final_stdout = ""
        final_stderr = ""
        if "stdout_output" in locals() and "stderr_output" in locals():  # Check if communicate() was reached
            final_stdout = stdout_output
            final_stderr = stderr_output
        # else: process might not have been initialized or communicate not called.
        # No direct access to process.stdout/stderr here as it's out of 'with' scope.

        return {
            "success": False,
            "error": f"Unexpected error: {e}",
            "test_output": final_stdout + "\n" + final_stderr,
            "analysis_log_path": None,
        }


@mcp.tool()
async def run_tests_no_verbosity() -> dict[str, Any]:
    """Run all tests with minimal output (verbosity level 0)."""
    return await _run_tests("0")


@mcp.tool()
async def run_tests_verbose() -> dict[str, Any]:
    """Run all tests with verbose output (verbosity level 1)."""
    return await _run_tests("1")


@mcp.tool()
async def run_tests_very_verbose() -> dict[str, Any]:
    """Run all tests with very verbose output (verbosity level 2)."""
    logger.info("Running tests with verbosity 2...")
    return await _run_tests(verbosity=2, run_with_coverage=True)


@mcp.tool()
async def ping() -> str:
    """Check if the MCP server is alive."""
    logger.debug("ping called")
    return f"Status: ok\n" f"Timestamp: {datetime.now().isoformat()}\n" f"Message: Log Analyzer MCP Server is running"


async def run_coverage_script(force_rebuild: bool = False) -> dict[str, Any]:
    """
    Run the coverage report script and generate HTML and XML reports.
    Now uses hatch scripts for better integration.
    """
    logger.info("Running coverage script...")
    # Correctly reference PROJECT_ROOT from the logger_setup module
    from log_analyzer_mcp.common import logger_setup as common_logger_setup  # Ensure this import is here or global

    current_project_root = common_logger_setup.PROJECT_ROOT
    # Define different timeouts for different steps
    timeout_run_cov = 300  # Longer timeout for running tests with coverage
    timeout_cov_report = 120  # Shorter timeout for generating the report

    # Command parts for running the coverage script via hatch
    # This assumes 'run-cov' and 'cov-report' are defined in hatch envs.
    # Step 1: Run tests with coverage enabled
    cmd_parts_run_cov = ["hatch", "run", "hatch-test.py3.12:run-cov"]  # Example: Target specific py version
    # Step 2: Generate combined report (HTML and XML)
    cmd_parts_report = ["hatch", "run", "hatch-test.py3.12:cov-report"]  # Example

    outputs = []
    errors_encountered = []

    steps_with_timeouts = [
        ("run-cov", cmd_parts_run_cov, timeout_run_cov),
        ("cov-report", cmd_parts_report, timeout_cov_report),
    ]

    for step_name, cmd_parts, current_timeout_seconds in steps_with_timeouts:
        logger.info(
            "Executing coverage step '%s': %s (timeout: %ss)", step_name, " ".join(cmd_parts), current_timeout_seconds
        )
        try:
            # Use functools.partial for subprocess.run
            configured_subprocess_run_step = functools.partial(
                subprocess.run,
                cmd_parts,
                cwd=current_project_root,
                capture_output=True,
                text=True,  # Decode stdout/stderr as text
                check=False,  # Handle non-zero exit manually
                timeout=current_timeout_seconds,  # Use current step's timeout
            )
            process = await anyio.to_thread.run_sync(configured_subprocess_run_step)  # type: ignore[attr-defined]
            stdout_output: str = process.stdout
            stderr_output: str = process.stderr
            rc = process.returncode

            outputs.append(f"--- {step_name} STDOUT ---\n{stdout_output}")
            if stderr_output:
                outputs.append(f"--- {step_name} STDERR ---\n{stderr_output}")

            if rc != 0:
                error_msg = f"Coverage step '{step_name}' failed with return code {rc}."
                logger.error("%s\nSTDERR:\n%s", error_msg, stderr_output)
                errors_encountered.append(error_msg)
                # Optionally break if a step fails, or collect all errors
                # break

        except subprocess.TimeoutExpired as e:
            stdout_output = e.stdout.decode("utf-8", errors="replace") if e.stdout else ""
            stderr_output = e.stderr.decode("utf-8", errors="replace") if e.stderr else ""
            error_msg = f"Coverage step '{step_name}' timed out after {current_timeout_seconds} seconds."
            logger.error("%s: %s", error_msg, e)
            errors_encountered.append(error_msg)
            outputs.append(f"--- {step_name} TIMEOUT STDOUT ---\n{stdout_output}")
            outputs.append(f"--- {step_name} TIMEOUT STDERR ---\n{stderr_output}")
            # break
        except Exception as e:  # pylint: disable=broad-exception-caught
            error_msg = f"Error during coverage step '{step_name}': {e}"
            logger.error(error_msg, exc_info=True)
            errors_encountered.append(error_msg)
            # break

    # Ensure a dictionary is always returned, even if errors occurred.
    final_success = not errors_encountered
    overall_message = (
        "Coverage script steps completed." if final_success else "Errors encountered during coverage script execution."
    )
    # Placeholder for actual report paths, adapt as needed
    coverage_xml_report_path = os.path.join(logs_base_dir, "tests", "coverage", "coverage.xml")
    coverage_html_index_path = os.path.join(logs_base_dir, "tests", "coverage", "html", "index.html")

    return {
        "success": final_success,
        "message": overall_message,
        "details": "\n".join(outputs),
        "errors": errors_encountered,
        "coverage_xml_path": coverage_xml_report_path if final_success else None,  # Example path
        "coverage_html_index": coverage_html_index_path if final_success else None,  # Example path
        "timestamp": datetime.now().isoformat(),
    }


@mcp.tool()
async def create_coverage_report(force_rebuild: bool = False) -> dict[str, Any]:
    """
    Run the coverage report script and generate HTML and XML reports.

    Args:
        force_rebuild: Whether to force rebuilding the report even if it exists

    Returns:
        Dictionary containing execution results and report paths
    """
    return await run_coverage_script(force_rebuild)


@mcp.tool()
async def run_unit_test(agent: str, verbosity: int = 1) -> dict[str, Any]:
    """
    Run tests for a specific agent only.

    This tool runs tests that match the agent's patterns including both main agent tests
    and healthcheck tests, significantly reducing test execution time compared to running all tests.
    Use this tool when you need to focus on testing a specific agent component.

    Args:
        agent: The agent to run tests for (e.g., 'qa_agent', 'backlog_agent')
        verbosity: Verbosity level (0=minimal, 1=normal, 2=detailed), default is 1

    Returns:
        Dictionary containing test results and analysis
    """
    logger.info("Running unit tests for agent: %s with verbosity %s", agent, verbosity)

    # The _run_tests function now handles pattern creation from agent name.
    # We call _run_tests once, and it will construct a pattern like "test_agent.py or test_healthcheck.py"
    # No need for separate calls for main and healthcheck unless _run_tests logic changes.

    # For verbosity, _run_tests expects 0, 1, or 2 as string or int.
    # The pattern is derived by _run_tests from the agent name.
    results = await _run_tests(agent=agent, verbosity=verbosity, run_with_coverage=False)

    # The structure of the response from _run_tests is already good for run_unit_test.
    # It includes success, return_code, test_output, and analysis (which contains agent_tested).
    # No need to combine results manually here if _run_tests handles the agent pattern correctly.

    return results


# --- Pydantic Models for Search Tools ---
class BaseSearchInput(BaseModel):
    """Base model for common search parameters."""

    scope: str = Field(default="default", description="Logging scope to search within (from .env scopes or default).")
    context_before: int = Field(default=2, description="Number of lines before a match.", ge=0)
    context_after: int = Field(default=2, description="Number of lines after a match.", ge=0)
    log_dirs_override: str = Field(
        default="",
        description="Comma-separated list of log directories, files, or glob patterns (overrides .env for file locations).",
    )
    log_content_patterns_override: str = Field(
        default="",
        description="Comma-separated list of REGEX patterns for log messages (overrides .env content filters).",
    )


class SearchLogAllInput(BaseSearchInput):
    """Input for search_log_all_records."""


@mcp.tool()
async def search_log_all_records(
    scope: str = "default",
    context_before: int = 2,
    context_after: int = 2,
    log_dirs_override: str = "",
    log_content_patterns_override: str = "",
) -> list[dict[str, Any]]:
    """Search for all log records, optionally filtering by scope and content patterns, with context."""
    # Forcing re-initialization of analysis_engine for debugging module caching.
    # Pass project_root_for_config=None to allow AnalysisEngine to determine it.
    current_analysis_engine = AnalysisEngine(logger_instance=logger, project_root_for_config=None)
    print(
        f"DEBUG_MCP_TOOL_SEARCH_ALL: Entered search_log_all_records with log_dirs_override='{log_dirs_override}'",
        file=sys.stderr,
        flush=True,
    )
    logger.info(
        "MCP search_log_all_records called with scope='%s', context=%sB/%sA, "
        "log_dirs_override='%s', log_content_patterns_override='%s'",
        scope,
        context_before,
        context_after,
        log_dirs_override,
        log_content_patterns_override,
    )
    log_dirs_list = log_dirs_override.split(",") if log_dirs_override else None
    log_content_patterns_list = log_content_patterns_override.split(",") if log_content_patterns_override else None

    filter_criteria = build_filter_criteria(
        scope=scope,
        context_before=context_before,
        context_after=context_after,
        log_dirs_override=log_dirs_list,
        log_content_patterns_override=log_content_patterns_list,
    )
    try:
        results = await asyncio.to_thread(current_analysis_engine.search_logs, filter_criteria)
        logger.info("search_log_all_records returning %s records.", len(results))
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error in search_log_all_records: %s", e, exc_info=True)
        custom_message = f"Failed to search all logs: {e!s}"
        raise McpError(ErrorData(code=-32603, message=custom_message)) from e


class SearchLogTimeBasedInput(BaseSearchInput):
    """Input for search_log_time_based."""

    minutes: int = Field(default=0, description="Search logs from the last N minutes.", ge=0)
    hours: int = Field(default=0, description="Search logs from the last N hours.", ge=0)
    days: int = Field(default=0, description="Search logs from the last N days.", ge=0)

    # Custom validation to ensure at least one time field is set if others are default (0)
    # Pydantic v2: @model_validator(mode='after')
    # Pydantic v1: @root_validator(pre=False)
    # For simplicity here, relying on tool logic to handle it, or can add validator if needed.


@mcp.tool()
async def search_log_time_based(
    minutes: int = 0,
    hours: int = 0,
    days: int = 0,
    scope: str = "default",
    context_before: int = 2,
    context_after: int = 2,
    log_dirs_override: str = "",
    log_content_patterns_override: str = "",
) -> list[dict[str, Any]]:
    """Search logs within a time window, optionally filtering, with context."""
    logger.info(
        "MCP search_log_time_based called with time=%sd/%sh/%sm, scope='%s', "
        "context=%sB/%sA, log_dirs_override='%s', "
        "log_content_patterns_override='%s'",
        days,
        hours,
        minutes,
        scope,
        context_before,
        context_after,
        log_dirs_override,
        log_content_patterns_override,
    )

    if minutes == 0 and hours == 0 and days == 0:
        logger.warning("search_log_time_based called without a time window (all minutes/hours/days are 0).")

    log_dirs_list = log_dirs_override.split(",") if log_dirs_override else None
    log_content_patterns_list = log_content_patterns_override.split(",") if log_content_patterns_override else None

    filter_criteria = build_filter_criteria(
        minutes=minutes,
        hours=hours,
        days=days,
        scope=scope,
        context_before=context_before,
        context_after=context_after,
        log_dirs_override=log_dirs_list,
        log_content_patterns_override=log_content_patterns_list,
    )
    try:
        results = await asyncio.to_thread(analysis_engine.search_logs, filter_criteria)
        logger.info("search_log_time_based returning %s records.", len(results))
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error in search_log_time_based: %s", e, exc_info=True)
        custom_message = f"Failed to search time-based logs: {e!s}"
        raise McpError(ErrorData(code=-32603, message=custom_message)) from e


class SearchLogFirstNInput(BaseSearchInput):
    """Input for search_log_first_n_records."""

    count: int = Field(description="Number of first (oldest) matching records to return.", gt=0)


@mcp.tool()
async def search_log_first_n_records(
    count: int,
    scope: str = "default",
    context_before: int = 2,
    context_after: int = 2,
    log_dirs_override: str = "",
    log_content_patterns_override: str = "",
) -> list[dict[str, Any]]:
    """Search for the first N (oldest) records, optionally filtering, with context."""
    logger.info(
        "MCP search_log_first_n_records called with count=%s, scope='%s', "
        "context=%sB/%sA, log_dirs_override='%s', "
        "log_content_patterns_override='%s'",
        count,
        scope,
        context_before,
        context_after,
        log_dirs_override,
        log_content_patterns_override,
    )
    if count <= 0:
        logger.error("Invalid count for search_log_first_n_records: %s. Must be > 0.", count)
        raise McpError(ErrorData(code=-32602, message="Count must be a positive integer."))

    log_dirs_list = log_dirs_override.split(",") if log_dirs_override else None
    log_content_patterns_list = log_content_patterns_override.split(",") if log_content_patterns_override else None

    filter_criteria = build_filter_criteria(
        first_n=count,
        scope=scope,
        context_before=context_before,
        context_after=context_after,
        log_dirs_override=log_dirs_list,
        log_content_patterns_override=log_content_patterns_list,
    )
    try:
        results = await asyncio.to_thread(analysis_engine.search_logs, filter_criteria)
        logger.info("search_log_first_n_records returning %s records.", len(results))
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error in search_log_first_n_records: %s", e, exc_info=True)
        custom_message = f"Failed to search first N logs: {e!s}"
        raise McpError(ErrorData(code=-32603, message=custom_message)) from e


class SearchLogLastNInput(BaseSearchInput):
    """Input for search_log_last_n_records."""

    count: int = Field(description="Number of last (newest) matching records to return.", gt=0)


@mcp.tool()
async def search_log_last_n_records(
    count: int,
    scope: str = "default",
    context_before: int = 2,
    context_after: int = 2,
    log_dirs_override: str = "",
    log_content_patterns_override: str = "",
) -> list[dict[str, Any]]:
    """Search for the last N (newest) records, optionally filtering, with context."""
    logger.info(
        "MCP search_log_last_n_records called with count=%s, scope='%s', "
        "context=%sB/%sA, log_dirs_override='%s', "
        "log_content_patterns_override='%s'",
        count,
        scope,
        context_before,
        context_after,
        log_dirs_override,
        log_content_patterns_override,
    )
    if count <= 0:
        logger.error("Invalid count for search_log_last_n_records: %s. Must be > 0.", count)
        raise McpError(ErrorData(code=-32602, message="Count must be a positive integer."))

    log_dirs_list = log_dirs_override.split(",") if log_dirs_override else None
    log_content_patterns_list = log_content_patterns_override.split(",") if log_content_patterns_override else None

    filter_criteria = build_filter_criteria(
        last_n=count,
        scope=scope,
        context_before=context_before,
        context_after=context_after,
        log_dirs_override=log_dirs_list,
        log_content_patterns_override=log_content_patterns_list,
    )
    try:
        results = await asyncio.to_thread(analysis_engine.search_logs, filter_criteria)
        logger.info("search_log_last_n_records returning %s records.", len(results))
        return results
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error in search_log_last_n_records: %s", e, exc_info=True)
        custom_message = f"Failed to search last N logs: {e!s}"
        raise McpError(ErrorData(code=-32603, message=custom_message)) from e


@mcp.tool()
async def get_server_env_details() -> dict[str, Any]:
    """Returns sys.path and sys.executable from the running MCP server."""
    logger.info("get_server_env_details called.")
    details = {
        "sys_executable": sys.executable,
        "sys_path": sys.path,
        "cwd": os.getcwd(),
        "environ_pythonpath": os.environ.get("PYTHONPATH"),
    }
    logger.info(f"Server env details: {details}")
    return details


# Main entry point for Uvicorn or direct stdio run via script
# Ref: https://fastmcp.numaru.com/usage/server-integration/#uvicorn-integration
# Ref: https://fastmcp.numaru.com/usage/server-integration/#stdio-transport


def main() -> None:
    """Runs the MCP server, choosing transport based on arguments."""
    import argparse

    # Argument parsing should be done first
    parser = argparse.ArgumentParser(description="Log Analyzer MCP Server")
    parser.add_argument(
        "--transport",
        type=str,
        choices=["stdio", "http"],
        default=os.getenv("MCP_DEFAULT_TRANSPORT", "stdio"),  # Default to stdio
        help="Transport protocol to use: 'stdio' or 'http' (default: stdio or MCP_DEFAULT_TRANSPORT env var)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.getenv("MCP_HTTP_HOST", "127.0.0.1"),
        help="Host for HTTP transport (default: 127.0.0.1 or MCP_HTTP_HOST env var)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_HTTP_PORT", "8000")),
        help="Port for HTTP transport (default: 8000 or MCP_HTTP_PORT env var)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=os.getenv("MCP_LOG_LEVEL", "info"),
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging level for Uvicorn (default: info or MCP_LOG_LEVEL env var)",
    )
    args = parser.parse_args()

    # Uses the global mcp instance and logger already configured at module level.
    # logger.info("Logger for main() using global instance.") # Optional: confirm logger usage

    if args.transport == "stdio":
        logger.info("Starting Log Analyzer MCP server in stdio mode via main().")
        mcp.run(transport="stdio")  # FastMCP handles stdio internally
    elif args.transport == "http":
        # Only import uvicorn and ASGIApplication if http transport is selected
        try:
            import uvicorn
            from asgiref.typing import ASGIApplication  # For type hinting
            from typing import cast
        except ImportError as e:
            logger.error("Required packages for HTTP transport (uvicorn, asgiref) are not installed. %s", e)
            sys.exit(1)

        logger.info(
            "Starting Log Analyzer MCP server with Uvicorn on %s:%s (log_level: %s)",
            args.host,
            args.port,
            args.log_level,
        )
        uvicorn.run(cast(ASGIApplication, mcp), host=args.host, port=args.port, log_level=args.log_level)
    else:
        # Should not happen due to choices in argparse, but as a fallback:
        logger.error("Unsupported transport type: %s. Exiting.", args.transport)
        sys.exit(1)


if __name__ == "__main__":
    # This block now directly calls main() to handle argument parsing and server start.
    # This ensures consistency whether run as a script or via the entry point.
    logger.info("Log Analyzer MCP Server script execution (__name__ == '__main__'). Calling main().")
    main()
