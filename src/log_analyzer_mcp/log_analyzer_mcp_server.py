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
import traceback
from datetime import datetime
from typing import Any

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
async def server_lifespan(server: FastMCP) -> AsyncIterator[None]:  # Simple lifespan, no app context needed
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

    if not isinstance(summary_only, bool):
        error_msg = f"Invalid summary_only value: {summary_only}. Must be a boolean."
        logger.error(error_msg)
        return {"error": error_msg, "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}}

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
        # Correctly reference PROJECT_ROOT from the logger_setup module
        from log_analyzer_mcp.common import logger_setup as common_logger_setup  # ADDED import for clarity

        current_project_root = common_logger_setup.PROJECT_ROOT  # ADDED variable

        logger.info("Executing hatch command: %s with cwd=%s", " ".join(hatch_cmd), current_project_root)  # MODIFIED
        with subprocess.Popen(
            hatch_cmd,
            cwd=current_project_root,  # MODIFIED
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line-buffered
            universal_newlines=True,  # Ensure text mode works consistently
        ) as process:
            logger.info("Subprocess for hatch test started with PID: %s", process.pid)

            stdout_full = ""
            stderr_full = ""
            try:
                logger.info("Waiting for hatch test subprocess (PID: %s) to complete...", process.pid)
                stdout_full, stderr_full = process.communicate(timeout=170)  # Slightly less than main timeout
                logger.info(
                    "Subprocess (PID: %s) stdout captured (first 500 chars):\n%s", process.pid, stdout_full[:500]
                )
                logger.info(
                    "Subprocess (PID: %s) stderr captured (first 500 chars):\n%s", process.pid, stderr_full[:500]
                )
            except subprocess.TimeoutExpired:
                logger.error("Subprocess (PID: %s) timed out during communicate(). Killing process.", process.pid)
                process.kill()
                # Attempt to get remaining output after kill
                stdout_full, stderr_full = process.communicate()
                logger.error(
                    "Subprocess (PID: %s) stdout after kill (first 500 chars):\n%s", process.pid, stdout_full[:500]
                )
                logger.error(
                    "Subprocess (PID: %s) stderr after kill (first 500 chars):\n%s", process.pid, stderr_full[:500]
                )
                return {
                    "success": False,
                    "error": "Test execution (hatch test) timed out internally.",
                    "test_output": stdout_full + "\n" + stderr_full,
                    "analysis_log_path": None,
                }
            except (OSError, ValueError) as e:  # More specific errors for communicate()
                logger.error("Error during process.communicate() for PID %s: %s", process.pid, e, exc_info=True)
                # process.kill() # Consider if kill is needed for other OSErrors
                # stdout_full, stderr_full = process.communicate() # May also fail
                return {
                    "success": False,
                    "error": f"OS/Value error during test execution: {e}",
                    "test_output": stdout_full + "\n" + stderr_full,  # May be incomplete
                    "analysis_log_path": None,
                }

            return_code = process.returncode
            logger.info("Hatch test subprocess (PID: %s) completed with return code: %s", process.pid, return_code)

            # Pytest exit codes:
            # 0: All tests passed
            # 1: Tests were collected and run but some tests failed
            # 2: Test execution was interrupted by the user
            # 3: Internal error occurred during test execution
            # 4: pytest command line usage error
            # 5: No tests were collected
            # We consider 0, 1, and 5 as "successful" execution of pytest itself.
            if return_code not in [0, 1, 5]:
                logger.error("Hatch test command failed with unexpected pytest return code: %s", return_code)
                logger.error("STDOUT:\n%s", stdout_full)
                logger.error("STDERR:\n%s", stderr_full)
                return {
                    "success": False,
                    "error": f"Test execution failed with code {return_code}",
                    "test_output": stdout_full + "\n" + stderr_full,
                    "analysis_log_path": None,
                }

            logger.debug("Saving combined stdout/stderr from hatch test to %s", test_log_output_path)
            with open(test_log_output_path, "w", encoding="utf-8") as f:
                f.write(stdout_full)
                f.write("\n")
                f.write(stderr_full)
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
                "return_code": return_code,
                "test_output": stdout_full + "\n" + stderr_full,
                "analysis_log_path": test_log_output_path,  # Provide path to the log for analysis
                # "analysis" field is removed from here as _run_tests no longer parses.
            }

    except FileNotFoundError:
        logger.error("Error: Hatch command not found. Ensure hatch is installed and in PATH.", exc_info=True)
        return {
            "success": False,
            "error": "Hatch command not found.",
            "test_output": "",
            "analysis_log_path": None,
        }
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("An unexpected error occurred in _run_tests: %s", e, exc_info=True)
        # Capture output if process started
        final_stdout = ""
        final_stderr = ""
        if "stdout_full" in locals() and "stderr_full" in locals():  # Check if communicate() was reached
            final_stdout = stdout_full
            final_stderr = stderr_full
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
    Run tests with coverage, generate XML and HTML reports using hatch, and capture text summary.

    Args:
        force_rebuild: This parameter is respected by always running the generation commands.

    Returns:
        Dictionary containing execution results and report paths.
    """
    import anyio

    logger.info("Running coverage generation using hatch (force_rebuild=%s)...", force_rebuild)

    coverage_xml_report_path = os.path.join(
        logs_base_dir, "tests", "coverage", "coverage.xml"
    )  # RESTORED logs_base_dir
    coverage_html_report_dir = os.path.join(logs_base_dir, "tests", "coverage", "html")  # RESTORED logs_base_dir
    coverage_html_index_path = os.path.join(coverage_html_report_dir, "index.html")

    # Step 1: Run tests with coverage enabled using our _run_tests helper
    # This ensures .coverage data file is up-to-date.
    # Verbosity for this internal test run can be minimal unless errors occur.
    logger.info("Step 1: Running 'hatch test --cover' via _run_tests...")
    test_run_results = await _run_tests(verbosity="0", run_with_coverage=True)

    if test_run_results["return_code"] != 0:
        logger.error(
            "Test run with coverage failed. Aborting coverage report generation. Output:\n%s",
            test_run_results["test_output"],
        )
        return {
            "success": False,
            "error": "Test run with coverage failed. See test_output.",
            "test_output": test_run_results["test_output"],
            "details": test_run_results,
        }
    logger.info("Step 1: 'hatch test --cover' completed successfully.")

    # Step 2: Generate XML report using hatch script
    logger.info("Step 2: Generating XML coverage report with 'hatch run xml'...")
    hatch_xml_cmd = ["hatch", "run", "xml"]
    xml_output_text = ""
    xml_success = False
    try:
        # Correctly reference PROJECT_ROOT from the logger_setup module
        from log_analyzer_mcp.common import logger_setup as common_logger_setup  # Ensure import if not already visible

        current_project_root = common_logger_setup.PROJECT_ROOT  # ADDED variable

        # Use anyio.run_process for better async/await and cancellation handling
        process = await anyio.run_process(
            hatch_xml_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )  # MODIFIED
        stdout = process.stdout
        stderr = process.stderr
        xml_output_text = stdout + stderr
        if process.returncode == 0 and os.path.exists(coverage_xml_report_path):
            logger.info("XML coverage report generated: %s", coverage_xml_report_path)
            xml_success = True
        else:
            logger.error(
                "'hatch run xml' failed. RC: %s. Output:\\n%s",
                process.returncode,
                (process.stdout + process.stderr).decode("utf-8", errors="ignore"),
            )  # Decode
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception during 'hatch run xml': %s", e)
        xml_output_text = str(e).encode("utf-8")  # Ensure bytes for consistency if error

    # Step 3: Generate HTML report using hatch script
    logger.info("Step 3: Generating HTML coverage report with 'hatch run run-html'...")
    hatch_html_cmd = ["hatch", "run", "run-html"]
    html_output_text = ""
    html_success = False
    try:
        # Correctly reference PROJECT_ROOT from the logger_setup module
        from log_analyzer_mcp.common import logger_setup as common_logger_setup  # Ensure import if not already visible

        current_project_root = common_logger_setup.PROJECT_ROOT  # ADDED variable

        # Use anyio.run_process for better async/await and cancellation handling
        process = await anyio.run_process(
            hatch_html_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )  # MODIFIED
        stdout = process.stdout
        stderr = process.stderr
        html_output_text = stdout + stderr
        if process.returncode == 0 and os.path.exists(coverage_html_index_path):
            logger.info("HTML coverage report generated in: %s", coverage_html_report_dir)
            html_success = True
        else:
            logger.error(
                "'hatch run run-html' failed. RC: %s. Output:\\n%s",
                process.returncode,
                (process.stdout + process.stderr).decode("utf-8", errors="ignore"),
            )  # Decode
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception during 'hatch run run-html': %s", e)
        html_output_text = str(e).encode("utf-8")  # Ensure bytes for consistency if error

    # Step 4: Get text summary report using hatch script
    logger.info("Step 4: Generating text coverage summary with 'hatch run default:cov-text-summary'...")
    hatch_summary_cmd = ["hatch", "run", "default:cov-text-summary"]
    summary_output_text = ""
    summary_success = False
    try:
        # Correctly reference PROJECT_ROOT from the logger_setup module
        from log_analyzer_mcp.common import logger_setup as common_logger_setup  # Ensure import if not already visible

        current_project_root = common_logger_setup.PROJECT_ROOT  # ADDED variable

        # Use anyio.run_process for better async/await and cancellation handling
        process = await anyio.run_process(
            hatch_summary_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
        )  # MODIFIED
        # stdout = process.stdout # Not needed directly
        # stderr = process.stderr # Not needed directly
        # return_code = process.returncode # Not needed directly
        if process.returncode == 0:
            summary_output_text_bytes = process.stdout + process.stderr
            summary_output_text = summary_output_text_bytes.decode("utf-8", errors="ignore")  # Decode once
            logger.info(
                "Text coverage summary command executed. Captured output (first 500 chars):\\n%s",
                summary_output_text[:500],  # Use decoded string
            )
            summary_success = True
        else:
            summary_output_text_bytes = process.stdout + process.stderr
            summary_output_text = summary_output_text_bytes.decode("utf-8", errors="ignore")  # Decode for logging
            logger.error(
                "'hatch run default:cov-text-summary' failed. RC: %s. Output:\\n%s",
                process.returncode,  # Use process.returncode
                summary_output_text,  # Use decoded string
            )
            # summary_output_text = summary_output_text_bytes  # Keep as bytes if needed elsewhere, or ensure consistent type
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Exception during 'hatch run default:cov-text-summary': %s", e)
        summary_output_text = str(e)  # Ensure string for consistency if error

    final_success = xml_success and html_success and summary_success
    overall_message = (
        "Coverage reports generated successfully." if final_success else "One or more coverage generation steps failed."
    )

    # Try to parse overall coverage percentage from the text summary for convenience
    overall_coverage_percent = None
    if summary_success:
        # Ensure summary_output_text is a string for re.search
        # summary_str = summary_output_text.decode('utf-8', errors='ignore') if isinstance(summary_output_text, bytes) else summary_output_text
        # The variable summary_output_text should be string type by now if summary_success is true.
        match = re.search(r"TOTAL\\s+\\d+\\s+\\d+\\s+(\\d+)%", summary_output_text)  # Use summary_output_text directly
        if match:
            overall_coverage_percent = int(match.group(1))
            logger.info("Extracted overall coverage: %s%%", overall_coverage_percent)

    return {
        "success": final_success,
        "message": overall_message,
        "overall_coverage_percent": overall_coverage_percent,  # From text report
        "coverage_xml_path": coverage_xml_report_path if xml_success else None,
        "coverage_html_dir": coverage_html_report_dir if html_success else None,
        "coverage_html_index": coverage_html_index_path if html_success else None,
        "text_summary_output": summary_output_text,
        "hatch_xml_output": (
            xml_output_text.decode("utf-8", errors="ignore") if isinstance(xml_output_text, bytes) else xml_output_text
        ),  # Decode for return
        "hatch_html_output": (
            html_output_text.decode("utf-8", errors="ignore")
            if isinstance(html_output_text, bytes)
            else html_output_text
        ),  # Decode for return
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


@mcp.tool()
async def request_server_shutdown() -> str:
    """Requests the MCP server to shut down gracefully by calling sys.exit(0) after a delay."""
    logger.info("Server shutdown requested. Scheduling sys.exit(0) after a short delay.")

    loop = asyncio.get_event_loop()

    async def do_shutdown_soon():
        await asyncio.sleep(0.1)  # Ensure response is sent before exit
        logger.info("Attempting to call sys.exit(0) via loop.call_soon_threadsafe.")
        # Using call_soon_threadsafe is generally for calling from another thread,
        # but it's a robust way to schedule something on the loop.
        # For a single-threaded asyncio app, call_soon would also work.
        # If mcp.run() runs its own loop or integrates differently, this might be safer.
        loop.call_soon_threadsafe(sys.exit, 0)
        # If sys.exit(0) from here doesn't work as expected with mcp.run(),
        # we might need to explore mcp's internal signal handling if any, or rely on KeyboardInterrupt
        # and fix the client side.

    asyncio.create_task(do_shutdown_soon())

    return "Shutdown initiated (sys.exit(0) scheduled). Server should terminate shortly."


if __name__ == "__main__":
    logger.info("Script started with Python %s", sys.version)
    logger.info("Current working directory: %s", os.getcwd())
    logger.info("Script directory: %s", script_dir)

    try:
        logger.info("Starting MCP server with FastMCP")
        logger.debug("MCP transport: stdio")
        logger.debug("MCP server name: log_analyzer")
        # Manually listing known tools to avoid issues with mcp.tools attribute
        # and the Pylint error "Attribute 'tools' is unknown".
        known_tool_names = [
            "analyze_tests",
            "run_tests_no_verbosity",
            "run_tests_verbose",
            "run_tests_very_verbose",
            "run_unit_test",
            "ping",
            "create_coverage_report",
            "search_log_all_records",
            "search_log_time_based",
            "search_log_first_n_records",
            "search_log_last_n_records",
            "get_server_env_details",
            "request_server_shutdown",
        ]
        logger.debug("Available tools (manually listed for logging): %s", ", ".join(known_tool_names))

        # Monkey patch the FastMCP.run method to add more logging
        original_run = mcp.run

        def patched_run(*args, **kwargs):
            logger.info("Entering patched FastMCP.run method")
            transport = kwargs.get("transport", args[0] if args else "stdio")
            logger.info("Using transport: %s", transport)

            try:
                logger.info("About to call original run method")
                result = original_run(*args, **kwargs)
                logger.info("Original run method completed")
                return result
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Exception in FastMCP.run: %s", e)
                logger.error("Traceback: %s", traceback.format_exc())
                raise

        # Assign the patched method
        mcp.run = patched_run

        # Run the server
        logger.info("About to run MCP server")
        mcp.run(transport="stdio")
        logger.info("MCP server run completed")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.critical("Critical error running MCP server: %s", e)
        logger.critical("Traceback: %s", traceback.format_exc())
        sys.exit(1)
