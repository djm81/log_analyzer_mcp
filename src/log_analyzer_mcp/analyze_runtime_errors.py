#!/usr/bin/env python3
"""
Runtime Error Analyzer

Analyzes runtime logs for errors related to a specific execution ID.
"""

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from log_analyzer_mcp.common.logger_setup import LoggerSetup, get_logs_dir  # Corrected import

# Explicitly attempt to initialize coverage for subprocesses
# if "COVERAGE_PROCESS_START" in os.environ:
#     try:
#         import coverage
#
#         coverage.process_startup()
#     except Exception:  # nosec B110 # pylint: disable=broad-exception-caught
#         pass  # Or handle error if coverage is mandatory

# Define project_root and script_dir
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

# Set up logging using centralized configuration
logs_base_dir = get_logs_dir()  # Using get_logs_dir from common
mcp_log_dir = os.path.join(logs_base_dir, "mcp")  # Consistent with mcp_server
os.makedirs(mcp_log_dir, exist_ok=True)
log_file_path = os.path.join(mcp_log_dir, "analyze_runtime_errors.log")

# Initialize logger: try to get existing, then create if not found.
_logger_candidate: Optional[logging.Logger] = LoggerSetup.get_logger("AnalyzeRuntimeErrors")
if not _logger_candidate:
    logger: logging.Logger = LoggerSetup.create_logger(
        "AnalyzeRuntimeErrors", log_file_path, agent_name="AnalyzeRuntimeErrorsUtil"  # Use the defined log_file_path
    )
    logger.setLevel("DEBUG")  # Set level for newly created logger
else:
    logger: logging.Logger = _logger_candidate  # Assign to the module-level logger
    # Optionally, ensure the desired level if retrieved logger might have a different one
    # logger.setLevel("DEBUG")

logger.info("RuntimeErrorAnalyzer initialized. Logging to %s", log_file_path)

# Define default runtime logs directory
DEFAULT_RUNTIME_LOGS_DIR = os.path.join(logs_base_dir, "runtime")


def find_latest_session(logs_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find the most recent session ID from runtime logs.

    Args:
        logs_dir: Directory containing runtime log files

    Returns:
        Tuple of (session_id, timestamp) or (None, None) if not found
    """
    latest_timestamp = None
    latest_session_id = None

    try:
        for log_file_entry in os.listdir(logs_dir):
            if not log_file_entry.endswith(".log"):
                continue

            log_path_full = os.path.join(logs_dir, log_file_entry)
            try:
                with open(log_path_full, "r", encoding="utf-8") as f:
                    for line in f:
                        # Look for session ID pattern
                        session_match = re.search(r"(\d{6}-\d{6}-[a-zA-Z0-9]+-[a-zA-Z0-9]+)", line)
                        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)

                        if session_match and timestamp_match:
                            timestamp_str = timestamp_match.group(1)
                            try:
                                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                            except ValueError as ve:
                                logger.warning(
                                    "Could not parse timestamp '%s' in %s: %s", timestamp_str, log_path_full, ve
                                )
                                continue  # Skip this line

                            if latest_timestamp is None or timestamp > latest_timestamp:
                                latest_timestamp = timestamp
                                latest_session_id = session_match.group(1)

            except FileNotFoundError:
                logger.warning("Log file %s not found during scan, might have been deleted.", log_path_full)
                continue
            except OSError as e:
                logger.error("OS error reading log file %s: %s", log_path_full, e)
                continue
            except (
                Exception
            ) as e:  # pylint: disable=broad-exception-caught # Catch any other unexpected error for this specific file
                logger.error("Unexpected error processing file %s: %s", log_path_full, e)
                continue

    except FileNotFoundError:
        logger.error("Runtime logs directory %s not found.", logs_dir)
        return None, None
    except PermissionError:
        logger.error("Permission denied when trying to list runtime logs directory %s.", logs_dir)
        return None, None
    except OSError as e:
        logger.error("OS error scanning runtime logs directory %s: %s", logs_dir, e)
        return None, None
    except (
        Exception
    ) as e:  # pylint: disable=broad-exception-caught # Catch any other unexpected error during the overall scan
        logger.error("Unexpected error scanning runtime logs directory %s: %s", logs_dir, e)
        return None, None

    return latest_session_id, latest_timestamp.strftime("%Y-%m-%d %H:%M:%S,%f") if latest_timestamp else None


def analyze_runtime_errors(logs_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze runtime logs for errors in the most recent execution.

    Args:
        logs_dir: Directory containing log files. If None, uses default runtime logs directory.

    Returns:
        Dict with execution ID, timestamp, and structured error information
    """
    actual_logs_dir: str
    if logs_dir is None:
        actual_logs_dir = DEFAULT_RUNTIME_LOGS_DIR
        logger.info("No logs directory provided, using default runtime logs directory: %s", actual_logs_dir)
    else:
        actual_logs_dir = logs_dir

    if not os.path.exists(actual_logs_dir):
        logger.warning("Runtime logs directory does not exist: %s", actual_logs_dir)
        # Attempt to create it, though for analysis it should typically exist with logs.
        try:
            os.makedirs(actual_logs_dir, exist_ok=True)
            logger.info("Created runtime logs directory as it was missing: %s", actual_logs_dir)
        except OSError as e:
            logger.error("Failed to create missing runtime logs directory %s: %s", actual_logs_dir, e)
            return {
                "success": False,
                "error": f"Runtime logs directory {actual_logs_dir} does not exist and could not be created.",
                "execution_id": None,
                "errors": [],
            }

    logger.info("RuntimeErrorAnalyzer: Starting analysis in directory: %s", os.path.abspath(actual_logs_dir))

    try:
        # Log files found in the directory before processing
        found_files = []
        try:
            found_files = os.listdir(actual_logs_dir)
            logger.info("RuntimeErrorAnalyzer: Files found in %s: %s", os.path.abspath(actual_logs_dir), found_files)
        except FileNotFoundError:
            logger.error("Runtime logs directory %s not found when listing files.", actual_logs_dir)
            # Proceed with empty found_files, will likely result in no errors found or use execution_id='unknown'
        except PermissionError:
            logger.error("Permission denied when listing files in %s.", actual_logs_dir)
        except OSError as e:
            logger.error("RuntimeErrorAnalyzer: OS error listing files in %s: %s", os.path.abspath(actual_logs_dir), e)
            # Continue, find_latest_session and error scanning will likely also fail or find nothing

        execution_id, execution_timestamp = find_latest_session(actual_logs_dir)  # actual_logs_dir is absolute here

        if not execution_id:
            logger.warning("RuntimeErrorAnalyzer: Could not find any execution ID in the runtime logs.")
            execution_id = "unknown"
            execution_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")
        else:
            logger.info("RuntimeErrorAnalyzer: Found most recent reference execution ID: %s", execution_id)

        errors = []
        # Iterate using the already logged found_files list if it was successful
        files_to_scan = found_files if found_files else []
        # If listdir failed, try to list again, maybe it was a temp issue (though unlikely)
        if not files_to_scan:
            try:
                files_to_scan = os.listdir(actual_logs_dir)
            except Exception:  # pylint: disable=broad-exception-caught
                files_to_scan = []  # Give up if still failing

        for log_file_name in files_to_scan:
            if not log_file_name.endswith(".log"):
                continue

            log_path = os.path.join(actual_logs_dir, log_file_name)
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    # Attempt to read the log file with utf-8, fallback to latin-1 or ignore errors
                    try:
                        lines = f.readlines()
                    except UnicodeDecodeError:
                        try:
                            with open(log_path, "r", encoding="latin-1") as f:
                                lines = f.readlines()
                        except UnicodeDecodeError:
                            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                                lines = f.readlines()
                        except FileNotFoundError:  # Inner open might fail if file deleted between listdir and open
                            logger.warning("Log file %s (latin-1) not found, possibly deleted.", log_path)
                            continue
                        except OSError as e_os_latin1:
                            logger.error("OS error opening/reading %s with latin-1: %s", log_path, e_os_latin1)
                            continue
                    except FileNotFoundError:  # Outer open might fail
                        logger.warning("Log file %s (utf-8) not found, possibly deleted.", log_path)
                        continue
                    except OSError as e_os_utf8:
                        logger.error("OS error opening/reading %s with utf-8: %s", log_path, e_os_utf8)
                        continue

                for i, line in enumerate(lines):
                    # Check if line contains an error keyword
                    if re.search(r"error|fail|exception|traceback", line, re.IGNORECASE):
                        # Get context (up to 2 lines before and after)
                        start = max(0, i - 2)
                        end = min(len(lines), i + 3)
                        context = lines[start:end]

                        # Extract timestamp if available
                        timestamp_match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
                        timestamp = timestamp_match.group(1) if timestamp_match else None

                        # Extract session ID if available
                        session_match = re.search(r"(\d{6}-\d{6}-[a-zA-Z0-9]+-[a-zA-Z0-9]+)", line)
                        session_id = session_match.group(1) if session_match else None

                        errors.append(
                            {
                                "log_file": log_file_name,
                                "line_number": i + 1,
                                "error_line": line.strip(),
                                "context": [l.strip() for l in context],
                                "timestamp": timestamp,
                                "session_id": session_id,
                            }
                        )
            except FileNotFoundError:  # Catch open errors for the main try block for this file
                logger.warning("Log file %s not found when attempting to process errors, possibly deleted.", log_path)
                continue
            except OSError as e_os_file_process:
                logger.error("OS Error processing file %s for errors: %s", log_file_name, e_os_file_process)
                continue
            except (
                Exception
            ) as e_file_process:  # pylint: disable=broad-exception-caught # Catch any other unexpected error for this specific file
                logger.error("Unexpected error processing file %s for errors: %s", log_file_name, e_file_process)

        # Group errors by log file for better readability
        grouped_errors = {}
        for error in errors:
            log_file = error["log_file"]
            if log_file not in grouped_errors:
                grouped_errors[log_file] = []
            grouped_errors[log_file].append(error)

        result = {
            "success": True,
            "execution_id": execution_id,
            "execution_timestamp": execution_timestamp,
            "total_errors": len(errors),
            "errors_by_file": grouped_errors,
            "errors": errors,  # Include flat list for backward compatibility
        }

        logger.info("Analysis complete. Found %s errors in runtime logs", len(errors))
        return result

    except Exception as e:  # pylint: disable=broad-exception-caught # Main try-except for the whole function
        error_msg = f"Error analyzing runtime logs: {e}"  # Keep f-string for custom_message, not logger directly
        logger.error("Error analyzing runtime logs: %s", e)
        return {"success": False, "error": error_msg, "execution_id": None, "errors": []}


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Analyze runtime logs for errors")
    parser.add_argument(
        "--logs-dir",
        default=DEFAULT_RUNTIME_LOGS_DIR,
        help=f"Directory containing log files (default: {DEFAULT_RUNTIME_LOGS_DIR})",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format (text or json)")
    return parser.parse_args()


def format_text_output(result: Dict[str, Any]) -> str:
    """Format the analysis result as readable text."""
    if not result["success"]:
        return f"Error: {result['error']}"

    lines = []
    lines.append(f"Execution ID: {result['execution_id']}")
    lines.append(f"Execution Timestamp: {result['execution_timestamp']}")
    lines.append(f"Total Errors: {result['total_errors']}")
    lines.append("")

    if result["total_errors"] == 0:
        lines.append("No errors found for this execution ID.")
        return "\n".join(lines)

    # Group by log file
    for log_file, errors in result["errors_by_file"].items():
        lines.append(f"=== Errors in {log_file} ({len(errors)}) ===")

        for error in errors:
            lines.append(f"Line {error['line_number']}:")
            lines.append(f"Timestamp: {error['timestamp']}")
            lines.append("Context:")
            for ctx_line in error["context"]:
                lines.append(f"    {ctx_line}")
            lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point for the script."""
    args = parse_args()

    # Run the analysis
    result = analyze_runtime_errors(args.logs_dir)

    # Output in requested format
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result))

    # Return success or failure
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
