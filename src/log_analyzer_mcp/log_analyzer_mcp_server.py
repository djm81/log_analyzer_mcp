#!/usr/bin/env python3
"""
Test Analyzer MCP Server

Implements the Model Context Protocol (MCP) for Cursor to analyze test results.
"""

import os
# Explicitly attempt to initialize coverage for subprocesses
if 'COVERAGE_PROCESS_START' in os.environ:
    try:
        import coverage
        coverage.process_startup()
        # If your logger is configured very early, you could add a log here:
        # print("DEBUG: coverage.process_startup() called in subprocess.", flush=True)
    except ImportError:
        # print("DEBUG: COVERAGE_PROCESS_START set, but coverage module not found.", flush=True)
        pass # Or handle error if coverage is mandatory for the subprocess
    except Exception as e:
        # print(f"DEBUG: Error calling coverage.process_startup(): {e}", flush=True)
        pass

import sys
import json
import subprocess
import re
from datetime import datetime
import time
import asyncio
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, List

from log_analyzer_mcp import log_analyzer

# Add venv support - REMOVED as hatch manages the environment
# try:
#     script_dir = os.path.dirname(os.path.abspath(__file__))  # log_analyzer_mcp directory
#     project_root = os.path.dirname(os.path.dirname(script_dir))  # coding-factory directory
#     if project_root not in sys.path:
#         sys.path.insert(0, project_root)
#     from src.common.venv_helper import setup_venv
#     setup_venv(
#         os.path.join(project_root, 'src', 'requirements.txt'),
#         suppress_output=True
#     )
# except ImportError:
#     print("Warning: Could not import venv_helper. Running without virtual environment.")


# Import required MCP components
from mcp.shared.exceptions import McpError
from mcp.server.fastmcp import FastMCP
from mcp.types import (
    ErrorData,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import BaseModel, Field
from log_analyzer_mcp.common.logger_setup import LoggerSetup, get_logs_dir

# Define project_root and script_dir here as they are used for path definitions
script_dir = os.path.dirname(os.path.abspath(__file__))  # .../project_root/src/log_analyzer_mcp
project_root = os.path.dirname(os.path.dirname(script_dir)) # .../project_root/

# Set up logging using centralized configuration
logs_base_dir = get_logs_dir() # Using get_logs_dir from common
mcp_log_dir = os.path.join(logs_base_dir, 'mcp')
os.makedirs(mcp_log_dir, exist_ok=True)
log_file_path = os.path.join(mcp_log_dir, "log_analyzer_mcp_server.log")

logger = LoggerSetup.create_logger("LogAnalyzerMCP", log_file_path, agent_name="LogAnalyzerMCP")
logger.setLevel("DEBUG")  # Set to debug level for MCP server

logger.info(f"Log Analyzer MCP Server starting. Logging to {log_file_path}")

# Update paths for scripts and logs (using project_root and script_dir)
log_analyzer_path = os.path.join(script_dir, 'log_analyzer.py')
# run_tests_path = os.path.join(project_root, 'tests/run_all_tests.py') # REMOVED - using hatch test directly
# run_coverage_path = os.path.join(script_dir, 'create_coverage_report.sh') # REMOVED - using hatch run hatch-test:* directly
analyze_runtime_errors_path = os.path.join(script_dir, 'analyze_runtime_errors.py')
test_log_file = os.path.join(logs_base_dir, 'run_all_tests.log') # Main test log, now populated by hatch test output
coverage_xml_path = os.path.join(logs_base_dir, 'tests', 'coverage', 'coverage.xml') # Used by parse_coverage_xml

# Initialize FastMCP server
mcp = FastMCP("log_analyzer")

# Define input models for tool validation
class AnalyzeTestsInput(BaseModel):
    """Parameters for analyzing tests."""
    summary_only: bool = Field(
        default=False,
        description="Whether to return only a summary of the test results"
    )


class RunTestsInput(BaseModel):
    """Parameters for running tests."""
    verbosity: Optional[Any] = Field(
        default=None,
        description="Verbosity level for the test runner (0-2)",
        examples=["0", "1", "2", 0, 1, 2, None]
    )


class CreateCoverageReportInput(BaseModel):
    """Parameters for creating coverage report."""
    force_rebuild: bool = Field(
        default=False,
        description="Whether to force rebuilding the coverage report even if it already exists"
    )


class RunUnitTestInput(BaseModel):
    """Parameters for running specific unit tests."""
    agent: str = Field(
        description="The agent to run tests for (e.g., 'qa_agent', 'backlog_agent')"
    )
    verbosity: int = Field(
        default=1,
        description="Verbosity level (0=minimal, 1=normal, 2=detailed)",
        ge=0,
        le=2
    )


# Define default runtime logs directory
DEFAULT_RUNTIME_LOGS_DIR = os.path.join(logs_base_dir, 'runtime')


async def analyze_test_log(log_file_path: str, summary_only: bool = False) -> Dict[str, Any]:
    """
    Analyze a test log file and return structured results.
    
    Args:
        log_file_path: Path to the test log file
        summary_only: Whether to return only a summary
        
    Returns:
        Dictionary containing analysis results
        
    Raises:
        McpError: If analysis fails
    """
    # Build command
    format_arg = "--format=json"
    cmd = [sys.executable, log_analyzer_path, log_file_path, format_arg]
    if summary_only:
        cmd.append("--summary-only")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Parse the output
        analysis = json.loads(result.stdout)

        # Add metadata
        log_time = datetime.fromtimestamp(os.path.getmtime(log_file_path))
        time_elapsed = (datetime.now() - log_time).total_seconds() / 60  # minutes
        
        analysis["log_file"] = log_file_path
        analysis["log_timestamp"] = log_time.isoformat()
        analysis["log_age_minutes"] = round(time_elapsed, 1)

        # Create a human-readable summary
        summary = []
        summary.append(f"Test Status: {analysis['summary']['status']}")
        summary.append(f"Tests: {analysis['summary']['passed']} passed, {analysis['summary']['failed']} failed, {analysis['summary']['skipped']} skipped")

        if analysis['summary']['duration']:
            summary.append(f"Duration: {analysis['summary']['duration']:.2f} seconds")

        # Add failure details to summary if available
        if analysis.get('error_details'):
            # Group errors by type
            test_failures = [e for e in analysis['error_details'] if e["type"] == "test_failure"]
            type_errors = [e for e in analysis['error_details'] if e["type"] == "type_error"]
            class_structure_errors = [e for e in analysis['error_details'] if e["type"] == "class_structure"]
            import_failures = [e for e in analysis['error_details'] if e["type"] == "import_failure"]
            
            if class_structure_errors:
                summary.append("\nClass Structure Validation Failures:")
                current_class = None
                for error in class_structure_errors:
                    if current_class != error['class_name']:
                        current_class = error['class_name']
                        summary.append(f"  ❌ {current_class}")
                    if error.get('missing_method'):
                        summary.append(f"    - Missing method: {error['missing_method']}")
                    else:
                        summary.append(f"    - {error['error_message']}")
            
            if import_failures:
                summary.append("\nImport Failures:")
                for error in import_failures:
                    summary.append(f"  ❌ {error['module']}: {error['error_message']}")
            
            if test_failures:
                summary.append("\nTest Failures:")
                for error in test_failures:
                    summary.append(f"  ❌ {error['test_name']}")
                    if error.get('exception'):
                        summary.append(f"    Error: {error['exception']}")
            
            if type_errors:
                summary.append("\nType Check Errors:")
                for error in type_errors:
                    summary.append(f"  Location: {error['file_location']}")
                    summary.append(f"  Error: {error['error_message']}")

        analysis["summary_text"] = "\n".join(summary)
        return analysis

    except subprocess.CalledProcessError as e:
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"Failed to analyze test results: {e}.\nStderr: {e.stderr}"
        ))
    except json.JSONDecodeError as e:
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"Failed to parse analyzer output as JSON: {e}"
        ))
    except Exception as e:
        raise McpError(ErrorData(
            code=INTERNAL_ERROR,
            message=f"An unexpected error occurred: {str(e)}"
        ))


@mcp.tool()
async def analyze_tests(summary_only: bool = False) -> Dict[str, Any]:
    """Analyze the most recent test run and provide detailed information about failures.
    
    Args:
        summary_only: Whether to return only a summary of the test results
    """
    logger.info(f"Analyzing test results (summary_only={summary_only})...")
    
    # Validate input type
    if not isinstance(summary_only, bool):
        error_msg = f"Invalid summary_only value: {summary_only}. Must be a boolean."
        logger.error(error_msg)
        return {
            "error": error_msg,
            "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
        }
    
    # Get log file path
    log_file = test_log_file  # Use the global path
    
    if not os.path.exists(log_file):
        error_msg = f"Test log file not found at: {log_file}. Please run tests first."
        logger.error(error_msg)
        return {
            "error": error_msg,
            "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
        }
    
    try:
        # Run log analyzer with JSON output
        cmd = [sys.executable, log_analyzer_path, log_file, '--format', 'json']
        if summary_only:
            cmd.append('--summary-only')
        
        logger.debug(f"Running log analyzer command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = f"Log analyzer failed with return code {result.returncode}. Error: {result.stderr}"
            logger.error(error_msg)
            logger.error(f"Stderr: {result.stderr}")
            return {
                "error": error_msg,
                "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
            }

        # Parse the output as JSON
        output = result.stdout.strip()
        if not output:
            error_msg = "Log analyzer returned empty output"
            logger.error(error_msg)
            return {
                "error": error_msg,
                "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
            }

        try:
            analysis = json.loads(output)
            
            # Validate required fields in analysis
            required_fields = ["summary"]
            missing_fields = [field for field in required_fields if field not in analysis]
            if missing_fields:
                error_msg = f"Missing required fields in analysis: {', '.join(missing_fields)}"
                logger.error(error_msg)
                return {
                    "error": error_msg,
                    "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
                }
            
            # Add metadata
            log_time = datetime.fromtimestamp(os.path.getmtime(log_file))
            time_elapsed = (datetime.now() - log_time).total_seconds() / 60  # minutes
            analysis["log_file"] = log_file
            analysis["log_timestamp"] = log_time.isoformat()
            analysis["log_age_minutes"] = round(time_elapsed, 1)
            
            # If summary_only, return only essential information
            if summary_only:
                return {
                    "summary": analysis.get("summary", {}),
                    "failed_tests": analysis.get("failed_tests", []),
                    "summary_text": analysis.get("summary_text", ""),
                    "log_file": analysis["log_file"],
                    "log_timestamp": analysis["log_timestamp"],
                    "log_age_minutes": analysis["log_age_minutes"]
                }
                
            # For full output, include error counts by type
            if analysis.get("error_details"):
                error_counts = {
                    "test_failures": len([e for e in analysis["error_details"] if e["type"] == "test_failure"]),
                    "type_errors": len([e for e in analysis["error_details"] if e["type"] == "type_error"]),
                    "class_structure_errors": len([e for e in analysis["error_details"] if e["type"] == "class_structure"]),
                    "import_failures": len([e for e in analysis["error_details"] if e["type"] == "import_failure"])
                }
                analysis["error_counts"] = error_counts
            
            logger.info(f"Analysis completed successfully (summary_only={summary_only})")
            return analysis
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse analyzer output as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw output: {output}")
            return {
                "error": error_msg,
                "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
            }
            
    except Exception as e:
        error_msg = f"Error analyzing log file: {e}"
        logger.error(error_msg)
        return {
            "error": error_msg,
            "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
        }


async def _run_tests(verbosity: Optional[Any] = None, agent: Optional[str] = None, 
               pattern: Optional[str] = None, run_with_coverage: bool = False) -> Dict[str, Any]:
    """Internal helper function to run tests using hatch.
    
    Args:
        verbosity: Optional verbosity level (0=minimal, 1=normal, 2=detailed for pytest)
        agent: Optional agent name to run only tests for that agent (e.g., 'qa_agent')
        pattern: Optional pattern to filter test files (e.g., 'test_qa_*.py')
        run_with_coverage: Whether to run tests with coverage enabled via 'hatch test --cover'.
    """
    logger.info(f"Preparing to run tests via hatch (verbosity={verbosity}, agent={agent}, pattern={pattern}, coverage={run_with_coverage})...")

    hatch_base_cmd = ["hatch", "test"]
    pytest_args = []

    # Add arguments to ignore the server tests to prevent recursion
    pytest_args.extend([
        "--ignore=tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py",
        "--ignore=tests/log_analyzer_mcp/test_analyze_runtime_errors.py"
    ])
    logger.debug(f"Added ignore patterns for server integration tests.")

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
            logger.warning(f"Invalid verbosity value '{verbosity}', using default.")

    # Construct pytest -k argument if agent or pattern is specified
    k_expressions = []
    if agent:
        # Assuming agent name can be part of test names like test_agent_... or ..._agent_...
        k_expressions.append(f"{agent}") # General match for agent name
        logger.debug(f"Added agent '{agent}' to -k filter expressions.")
    if pattern:
        k_expressions.append(pattern)
        logger.debug(f"Added pattern '{pattern}' to -k filter expressions.")
    
    if k_expressions:
        pytest_args.extend([
            "-k",
            " or ".join(k_expressions) # pytest -k "expr1 or expr2"
        ])

    hatch_cmd = hatch_base_cmd
    if pytest_args: # Pass pytest arguments after --
        hatch_cmd.extend(["--"] + pytest_args)
    
    logger.info(f"Constructed hatch command: {' '.join(hatch_cmd)}")

    # Ensure the log file is cleared or managed before test run if it's always written to the same path
    # For now, assuming log_analyzer.py handles this or we analyze the latest run.
    test_log_output_path = os.path.join(logs_base_dir, 'run_all_tests.log')
    logger.debug(f"Expected test output log path for analysis: {test_log_output_path}")

    process = None
    try:
        logger.info(f"Executing hatch command: {' '.join(hatch_cmd)} with cwd={project_root}")
        process = subprocess.Popen(
            hatch_cmd, 
            cwd=project_root, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1, # Line-buffered
            universal_newlines=True # Ensure text mode works consistently
        )
        logger.info(f"Subprocess for hatch test started with PID: {process.pid}")

        stdout_full = ""
        stderr_full = ""
        try:
            logger.info(f"Waiting for hatch test subprocess (PID: {process.pid}) to complete...")
            stdout_full, stderr_full = process.communicate(timeout=170) # Slightly less than main timeout
            logger.info(f"Subprocess (PID: {process.pid}) stdout captured (first 500 chars):\n{stdout_full[:500]}")
            logger.info(f"Subprocess (PID: {process.pid}) stderr captured (first 500 chars):\n{stderr_full[:500]}")
        except subprocess.TimeoutExpired:
            logger.error(f"Subprocess (PID: {process.pid}) timed out during communicate(). Killing process.")
            process.kill()
            stdout_full, stderr_full = process.communicate() # Get any remaining output
            logger.error(f"Subprocess (PID: {process.pid}) stdout after kill (first 500 chars):\n{stdout_full[:500]}")
            logger.error(f"Subprocess (PID: {process.pid}) stderr after kill (first 500 chars):\n{stderr_full[:500]}")
            return {"success": "No", "error": "Test execution (hatch test) timed out internally.", "test_output": stdout_full + "\n" + stderr_full, "analysis": None}
        
        return_code = process.returncode
        logger.info(f"Hatch test subprocess (PID: {process.pid}) completed with return code: {return_code}")

        # Pytest exit codes:
        # 0: All tests passed
        # 1: Tests were collected and run but some tests failed
        # 2: Test execution was interrupted by the user
        # 3: Internal error occurred during test execution
        # 4: pytest command line usage error
        # 5: No tests were collected
        # We consider 0, 1, and 5 as "successful" execution of pytest itself.
        if return_code not in [0, 1, 5]: 
            logger.error(f"Hatch test command failed with unexpected pytest return code: {return_code}")
            logger.error(f"STDOUT:\n{stdout_full}")
            logger.error(f"STDERR:\n{stderr_full}")
            return {"success": "No", "error": f"Test execution failed with code {return_code}", "test_output": stdout_full + "\n" + stderr_full, "analysis": None}

        logger.debug(f"Saving combined stdout/stderr from hatch test to {test_log_output_path}")
        with open(test_log_output_path, 'w') as f:
            f.write(stdout_full)
            f.write("\n") 
            f.write(stderr_full) 
        logger.debug(f"Content saved to {test_log_output_path}")

        logger.info(f"Analyzing test results from {test_log_output_path} using log_analyzer.py...")
        try:
            # Temporarily modify sys.argv for log_analyzer.main()
            original_sys_argv = sys.argv
            
            # Construct the arguments for log_analyzer.py
            # sys.argv[0] is the script name, followed by its arguments.
            # log_analyzer.py expects: log_file_path, --format json
            # The --agent-filter was a custom addition I made before, log_analyzer.py's main doesn't directly use it via argparse
            # but it does have internal logic for agent filtering when format is json and agent_filter is in args
            
            simulated_argv = [
                log_analyzer_path, # Script name, sys.argv[0]
                test_log_output_path,
                "--format", "json"
            ]
            # log_analyzer.py does not have an --agent-filter argument in its parser
            # The filtering logic for 'agent' in log_analyzer.main was based on seeing 'agent_filter' in parsed_args.
            # For now, let's omit passing agent_filter to log_analyzer.py via command line,
            # as its main function will perform analysis, and we can filter its results if needed,
            # or adjust log_analyzer.py later if direct filtering via its CLI is desired.
            # The important thing is that it runs and parses the specified log file.

            logger.debug(f"Simulating sys.argv for log_analyzer.main: {simulated_argv}")
            sys.argv = simulated_argv
            
            # log_analyzer.main() calls parse_arguments() internally, which reads from sys.argv
            # It then returns the analysis dictionary when format is json.
            analysis_results = log_analyzer.main() 
            
            logger.info("Test analysis completed by log_analyzer.main.")
            logger.debug(f"Analysis result from log_analyzer.main: {analysis_results}")

        except Exception as e:
            logger.error(f"Error during log_analyzer.main: {e}", exc_info=True)
            return {"success": "No", "error": f"Failed to analyze test results: {e}", "test_output": stdout_full + "\n" + stderr_full, "analysis": None}
        finally:
            sys.argv = original_sys_argv # Restore original sys.argv

        # If an agent was specified for the test run, we might want to indicate this
        # in the results, even if log_analyzer.py didn't directly filter by it via CLI arg.
        # The analysis_results *might* contain info if log_analyzer.py has its own logic
        # to infer agent context from the log content itself.
        # For now, let's add the agent tested to the MCP server's response if one was provided.
        if agent and analysis_results and isinstance(analysis_results, dict):
            analysis_results["agent_tested_by_mcp_run"] = agent

        return {
            "success": "Yes", 
            "return_code": return_code, 
            "test_output": stdout_full + "\n" + stderr_full, 
            "analysis": analysis_results,
            "log_file_analyzed": test_log_output_path
        }

    except FileNotFoundError:
        logger.error(f"Error: Hatch command not found. Ensure hatch is installed and in PATH.", exc_info=True)
        return {"success": "No", "error": "Hatch command not found.", "test_output": "", "analysis": None}
    except Exception as e:
        logger.error(f"An unexpected error occurred in _run_tests: {e}", exc_info=True)
        # Capture output if process started
        final_stdout = ""
        final_stderr = ""
        if process and process.stdout and process.stderr:
            # These might be None if Popen failed early
            # It's safer to check. communicate() might have been called or not.
            # This is a best-effort to get some output if an error happened post-Popen.
            if hasattr(process, 'stdout_full'): # If communicate() was called
                final_stdout = stdout_full
                final_stderr = stderr_full
            else: # communicate() not called, try to read directly (might hang or be empty)
                 try:
                    if process.stdout:
                        final_stdout = process.stdout.read()
                    if process.stderr:
                        final_stderr = process.stderr.read()
                 except Exception as read_err:
                     logger.error(f"Error reading from subprocess streams during exception handling: {read_err}")
        
        return {"success": "No", "error": f"Unexpected error: {e}", "test_output": final_stdout + "\n" + final_stderr, "analysis": None}


@mcp.tool()
async def run_tests_no_verbosity() -> Dict[str, Any]:
    """Run all tests with minimal output (verbosity level 0)."""
    return await _run_tests("0")


@mcp.tool()
async def run_tests_verbose() -> Dict[str, Any]:
    """Run all tests with verbose output (verbosity level 1)."""
    return await _run_tests("1")


@mcp.tool()
async def run_tests_very_verbose() -> Dict[str, Any]:
    """Run all tests with very verbose output (verbosity level 2)."""
    return await _run_tests("2")


@mcp.tool()
async def analyze_runtime_errors() -> Dict[str, Any]:
    """
    Analyze runtime logs for errors in the most recent execution.
    
    Finds the most recent execution ID from logs and searches for errors
    related to that execution across all log files.
    
    Returns:
        Dict with execution ID, timestamp, and structured error information
    """
    logger.info("Starting runtime error analysis...")
    
    try:
        # Ensure runtime logs directory exists
        os.makedirs(DEFAULT_RUNTIME_LOGS_DIR, exist_ok=True)
        
        # Run the analyze_runtime_errors.py script with JSON output and runtime logs directory
        cmd = [
            sys.executable,
            analyze_runtime_errors_path,
            '--format', 'json',
            '--logs-dir', DEFAULT_RUNTIME_LOGS_DIR
        ]
        logger.debug(f"Running command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            error_msg = f"Runtime error analysis failed with return code {result.returncode}"
            logger.error(error_msg)
            logger.error(f"Stderr: {result.stderr}")
            return {
                "success": False,
                "error": error_msg,
                "execution_id": None,
                "errors": []
            }
        
        # Parse the output as JSON
        try:
            analysis = json.loads(result.stdout)
            logger.info(f"Analysis completed successfully. Found {analysis.get('total_errors', 0)} errors.")
            return analysis
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse analyzer output as JSON: {e}"
            logger.error(error_msg)
            logger.error(f"Raw output: {result.stdout}")
            return {
                "success": False,
                "error": error_msg,
                "execution_id": None,
                "errors": []
            }
    
    except Exception as e:
        error_msg = f"Error analyzing runtime logs: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "execution_id": None,
            "errors": []
        }


@mcp.tool()
async def ping() -> str:
    """Check if the MCP server is alive."""
    logger.debug("ping called")
    return (
        f"Status: ok\n"
        f"Timestamp: {datetime.now().isoformat()}\n"
        f"Message: Log Analyzer MCP Server is running"
    )


async def run_coverage_script(force_rebuild: bool = False) -> Dict[str, Any]:
    """
    Run tests with coverage, generate XML and HTML reports using hatch, and capture text summary.
    
    Args:
        force_rebuild: This parameter is respected by always running the generation commands.
    
    Returns:
        Dictionary containing execution results and report paths.
    """
    logger.info(f"Running coverage generation using hatch (force_rebuild={force_rebuild})...")

    coverage_xml_report_path = os.path.join(logs_base_dir, 'tests', 'coverage', 'coverage.xml') 
    coverage_html_report_dir = os.path.join(logs_base_dir, 'tests', 'coverage', 'html')
    coverage_html_index_path = os.path.join(coverage_html_report_dir, 'index.html')

    # Step 1: Run tests with coverage enabled using our _run_tests helper
    # This ensures .coverage data file is up-to-date.
    # Verbosity for this internal test run can be minimal unless errors occur.
    logger.info("Step 1: Running 'hatch test --cover' via _run_tests...")
    test_run_results = await _run_tests(verbosity="0", run_with_coverage=True) 
    
    if test_run_results["return_code"] != 0:
        logger.error(f"Test run with coverage failed. Aborting coverage report generation. Output:\n{test_run_results['test_output']}")
        return {
            "success": False,
            "error": "Test run with coverage failed. See test_output.",
            "test_output": test_run_results['test_output'],
            "details": test_run_results
        }
    logger.info("Step 1: 'hatch test --cover' completed successfully.")

    # Step 2: Generate XML report using hatch script
    logger.info("Step 2: Generating XML coverage report with 'hatch run xml'...")
    hatch_xml_cmd = ["hatch", "run", "xml"]
    xml_output_text = ""
    xml_success = False
    try:
        xml_process = subprocess.run(hatch_xml_cmd, capture_output=True, text=True, cwd=project_root, check=False)
        xml_output_text = xml_process.stdout + xml_process.stderr
        if xml_process.returncode == 0 and os.path.exists(coverage_xml_report_path):
            logger.info(f"XML coverage report generated: {coverage_xml_report_path}")
            xml_success = True
        else:
            logger.error(f"'hatch run xml' failed. RC: {xml_process.returncode}. Output:\n{xml_output_text}")
    except Exception as e:
        logger.error(f"Exception during 'hatch run xml': {e}")
        xml_output_text = str(e)

    # Step 3: Generate HTML report using hatch script
    logger.info("Step 3: Generating HTML coverage report with 'hatch run run-html'...")
    hatch_html_cmd = ["hatch", "run", "run-html"]
    html_output_text = ""
    html_success = False
    try:
        html_process = subprocess.run(hatch_html_cmd, capture_output=True, text=True, cwd=project_root, check=False)
        html_output_text = html_process.stdout + html_process.stderr
        if html_process.returncode == 0 and os.path.exists(coverage_html_index_path):
            logger.info(f"HTML coverage report generated in: {coverage_html_report_dir}")
            html_success = True
        else:
            logger.error(f"'hatch run run-html' failed. RC: {html_process.returncode}. Output:\n{html_output_text}")
    except Exception as e:
        logger.error(f"Exception during 'hatch run run-html': {e}")
        html_output_text = str(e)

    # Step 4: Get text summary report using hatch script
    logger.info("Step 4: Generating text coverage summary with 'hatch run cov'...")
    hatch_summary_cmd = ["hatch", "run", "cov"]
    summary_output_text = ""
    summary_success = False
    try:
        summary_process = subprocess.run(hatch_summary_cmd, capture_output=True, text=True, cwd=project_root, check=False)
        if summary_process.returncode == 0:
            summary_output_text = summary_process.stdout
            logger.info("Text coverage summary generated.")
            summary_success = True
        else:
            logger.error(f"'hatch run cov' failed. RC: {summary_process.returncode}. Output:\n{summary_process.stdout + summary_process.stderr}")
            summary_output_text = summary_process.stdout + summary_process.stderr # Still provide output
    except Exception as e:
        logger.error(f"Exception during 'hatch run cov': {e}")
        summary_output_text = str(e)
    
    final_success = xml_success and html_success and summary_success
    overall_message = "Coverage reports generated successfully." if final_success else "One or more coverage generation steps failed."

    # Try to parse overall coverage percentage from the text summary for convenience
    overall_coverage_percent = None
    if summary_success:
        match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", summary_output_text)
        if match:
            overall_coverage_percent = int(match.group(1))
            logger.info(f"Extracted overall coverage: {overall_coverage_percent}%")

    return {
        "success": final_success,
        "message": overall_message,
        "overall_coverage_percent": overall_coverage_percent, # From text report
        "coverage_xml_path": coverage_xml_report_path if xml_success else None,
        "coverage_html_dir": coverage_html_report_dir if html_success else None,
        "coverage_html_index": coverage_html_index_path if html_success else None,
        "text_summary_output": summary_output_text,
        "hatch_xml_output": xml_output_text,
        "hatch_html_output": html_output_text,
        "timestamp": datetime.now().isoformat()
    }


async def parse_coverage_xml() -> Dict[str, Any]:
    """
    Parse the coverage XML report and return structured data.
    
    Returns:
        Dictionary containing coverage metrics and detailed module information
    """
    logger.info(f"Parsing coverage XML report from {coverage_xml_path}...")
    
    if not os.path.exists(coverage_xml_path):
        error_msg = f"Coverage XML file not found at {coverage_xml_path}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "coverage_percent": 0,
            "modules": []
        }
    
    try:
        tree = ET.parse(coverage_xml_path)
        root = tree.getroot()
        
        # Extract overall coverage
        overall_coverage = None
        if 'line-rate' in root.attrib:
            try:
                overall_coverage = float(root.attrib['line-rate']) * 100
            except (ValueError, TypeError):
                pass
        
        # Get timestamp
        timestamp = None
        if 'timestamp' in root.attrib:
            try:
                timestamp_str = root.attrib['timestamp']
                timestamp = datetime.fromtimestamp(int(timestamp_str)).isoformat()
            except (ValueError, TypeError):
                pass
        
        modules_data = []
        
        # Process each class/module
        for package in root.findall('.//package'):
            package_name = package.attrib.get('name', '')
            
            for module in package.findall('.//class'):
                module_name = module.attrib.get('name', '')
                filename = module.attrib.get('filename', '')
                
                # Get module coverage
                line_rate = float(module.attrib.get('line-rate', 0)) * 100
                branch_rate = float(module.attrib.get('branch-rate', 0)) * 100
                
                # Get missing lines
                missing_lines = []
                for line in module.findall('.//line[@hits="0"]'):
                    try:
                        missing_lines.append(int(line.attrib['number']))
                    except (ValueError, KeyError):
                        pass
                
                # Sort missing lines
                missing_lines.sort()
                
                # Group consecutive missing lines for better readability
                missing_ranges = []
                if missing_lines:
                    range_start = missing_lines[0]
                    range_end = range_start
                    
                    for line in missing_lines[1:]:
                        if line == range_end + 1:
                            range_end = line
                        else:
                            if range_start == range_end:
                                missing_ranges.append(str(range_start))
                            else:
                                missing_ranges.append(f"{range_start}-{range_end}")
                            range_start = line
                            range_end = line
                    
                    # Add the last range
                    if range_start == range_end:
                        missing_ranges.append(str(range_start))
                    else:
                        missing_ranges.append(f"{range_start}-{range_end}")
                
                modules_data.append({
                    "name": module_name,
                    "file": filename,
                    "package": package_name,
                    "line_coverage_percent": round(line_rate, 2),
                    "branch_coverage_percent": round(branch_rate, 2),
                    "missing_line_count": len(missing_lines),
                    "missing_lines": missing_lines[:100] if len(missing_lines) > 100 else missing_lines,  # Limit to prevent very large responses
                    "missing_ranges": missing_ranges[:50] if len(missing_ranges) > 50 else missing_ranges  # Provide ranges for better readability
                })
        
        # Sort modules by coverage (ascending, so lowest coverage first)
        modules_data.sort(key=lambda x: x['line_coverage_percent'])
        
        # Calculate coverage threshold
        threshold = 80.0  # Default from .coveragerc
        try:
            coveragerc_path = os.path.join(project_root, 'tests/.coveragerc')
            if os.path.exists(coveragerc_path):
                with open(coveragerc_path, 'r') as f:
                    for line in f:
                        if 'fail_under' in line:
                            parts = line.strip().split('=')
                            if len(parts) == 2:
                                threshold = float(parts[1].strip())
                                break
        except Exception as e:
            logger.error(f"Error reading coverage threshold: {e}")
        
        # Group modules by coverage range
        coverage_ranges = {
            "critical": [],  # 0-20%
            "poor": [],      # 20-40%
            "medium": [],    # 40-60%
            "good": [],      # 60-80%
            "excellent": []  # 80-100%
        }
        
        for module in modules_data:
            cov = module['line_coverage_percent']
            if cov < 20:
                coverage_ranges["critical"].append(module['name'])
            elif cov < 40:
                coverage_ranges["poor"].append(module['name'])
            elif cov < 60:
                coverage_ranges["medium"].append(module['name'])
            elif cov < 80:
                coverage_ranges["good"].append(module['name'])
            else:
                coverage_ranges["excellent"].append(module['name'])
        
        # Calculate how many more percentage points needed to meet threshold
        coverage_gap = max(0, threshold - (overall_coverage or 0))
        
        result = {
            "success": True,
            "coverage_percent": round(overall_coverage, 2) if overall_coverage is not None else None,
            "threshold_percent": threshold,
            "coverage_gap": round(coverage_gap, 2),
            "timestamp": timestamp,
            "modules_by_coverage_range": coverage_ranges,
            "modules": modules_data
        }
        
        logger.info(f"Coverage XML parsed successfully: {result['coverage_percent']}% coverage")
        return result
    
    except ET.ParseError as e:
        error_msg = f"Failed to parse coverage XML: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "coverage_percent": 0,
            "modules": []
        }
    except Exception as e:
        error_msg = f"Error parsing coverage data: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "coverage_percent": 0,
            "modules": []
        }


@mcp.tool()
async def create_coverage_report(force_rebuild: bool = False) -> Dict[str, Any]:
    """
    Run the coverage report script and generate HTML and XML reports.
    
    Args:
        force_rebuild: Whether to force rebuilding the report even if it exists
    
    Returns:
        Dictionary containing execution results and report paths
    """
    return await run_coverage_script(force_rebuild)


@mcp.tool()
async def get_coverage_report() -> Dict[str, Any]:
    """
    Parse and return detailed coverage data from the most recent coverage report.
    
    This tool reads the coverage.xml file and returns structured data about 
    overall coverage, modules with low coverage, and specific missing lines
    that need test coverage.
    
    Returns:
        Dictionary containing detailed coverage metrics and module information
    """
    return await parse_coverage_xml()


@mcp.tool()
async def run_unit_test(agent: str, verbosity: int = 1) -> Dict[str, Any]:
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
    logger.info(f"Running unit tests for agent: {agent} with verbosity {verbosity}")
    
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


if __name__ == "__main__":
    logger.info(f"Script started with Python {sys.version}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script directory: {script_dir}")
    
    try:
        logger.info("Starting MCP server with FastMCP")
        logger.debug(f"MCP transport: stdio")
        logger.debug(f"MCP server name: log_analyzer")
        logger.debug(f"Available tools: analyze_tests, run_tests_no_verbosity, run_tests_verbose, run_tests_very_verbose, run_unit_test, analyze_runtime_errors, ping, create_coverage_report, get_coverage_report")
        
        # Monkey patch the FastMCP.run method to add more logging
        original_run = mcp.run
        
        def patched_run(*args, **kwargs):
            logger.info("Entering patched FastMCP.run method")
            transport = kwargs.get('transport', args[0] if args else 'stdio')
            logger.info(f"Using transport: {transport}")
            
            try:
                logger.info("About to call original run method")
                result = original_run(*args, **kwargs)
                logger.info("Original run method completed")
                return result
            except Exception as e:
                logger.error(f"Exception in FastMCP.run: {e}")
                import traceback
                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        
        # Assign the patched method
        mcp.run = patched_run
        
        # Add more logging to the initialize handler if it exists
        if hasattr(mcp, '_handle_initialize'):
            original_initialize = getattr(mcp, '_handle_initialize')
            
            async def patched_initialize(*args, **kwargs):
                logger.info(f"Handling initialize request with args: {args}, kwargs: {kwargs}")
                try:
                    result = await original_initialize(*args, **kwargs)
                    logger.info(f"Initialize completed successfully: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Exception in _handle_initialize: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    raise
            
            setattr(mcp, '_handle_initialize', patched_initialize)
        
        # Run the server
        logger.info("About to run MCP server")
        mcp.run(transport='stdio')
        logger.info("MCP server run completed")
    except Exception as e:
        logger.critical(f"Critical error running MCP server: {e}")
        import traceback
        logger.critical(f"Traceback: {traceback.format_exc()}")
        sys.exit(1) 