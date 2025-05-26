#!/usr/bin/env python3
"""
Runtime Error Analyzer

Analyzes runtime logs for errors related to a specific execution ID.
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from log_analyzer_mcp.common.logger_setup import LoggerSetup, get_logs_dir # Corrected import

# Explicitly attempt to initialize coverage for subprocesses
if 'COVERAGE_PROCESS_START' in os.environ:
    try:
        import coverage
        coverage.process_startup()
    except Exception: # nosec B110
        pass # Or handle error if coverage is mandatory

# Define project_root and script_dir
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

# Set up logging using centralized configuration
logs_base_dir = get_logs_dir() # Using get_logs_dir from common
mcp_log_dir = os.path.join(logs_base_dir, 'mcp') # Consistent with mcp_server
os.makedirs(mcp_log_dir, exist_ok=True)
log_file_path = os.path.join(mcp_log_dir, "analyze_runtime_errors.log")

logger = LoggerSetup.create_logger("RuntimeErrorAnalyzer", log_file_path, agent_name="RuntimeErrorAnalyzer")
logger.setLevel("DEBUG")

logger.info(f"RuntimeErrorAnalyzer initialized. Logging to {log_file_path}")

# Define default runtime logs directory
DEFAULT_RUNTIME_LOGS_DIR = os.path.join(logs_base_dir, 'runtime')

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
            if not log_file_entry.endswith('.log'):
                continue
                
            log_path_full = os.path.join(logs_dir, log_file_entry) # Renamed to avoid conflict
            try:
                with open(log_path_full, 'r') as f:
                    for line in f:
                        # Look for session ID pattern
                        session_match = re.search(r'(\d{6}-\d{6}-[a-zA-Z0-9]+-[a-zA-Z0-9]+)', line)
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                        
                        if session_match and timestamp_match:
                            timestamp_str = timestamp_match.group(1)
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S,%f')
                            
                            if latest_timestamp is None or timestamp > latest_timestamp:
                                latest_timestamp = timestamp
                                latest_session_id = session_match.group(1)
                                
            except Exception as e:
                logger.error(f"Error reading log file {log_file_entry}: {e}") # Use iterated name
                continue
                
    except Exception as e:
        logger.error(f"Error scanning runtime logs directory: {e}")
        return None, None
        
    return latest_session_id, latest_timestamp.strftime('%Y-%m-%d %H:%M:%S,%f') if latest_timestamp else None

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
        logger.info(f"No logs directory provided, using default runtime logs directory: {actual_logs_dir}")
    else:
        actual_logs_dir = logs_dir
    
    if not os.path.exists(actual_logs_dir):
        logger.warning(f"Runtime logs directory does not exist: {actual_logs_dir}")
        # Attempt to create it, though for analysis it should typically exist with logs.
        try:
            os.makedirs(actual_logs_dir, exist_ok=True)
            logger.info(f"Created runtime logs directory as it was missing: {actual_logs_dir}")
        except OSError as e:
            logger.error(f"Failed to create missing runtime logs directory {actual_logs_dir}: {e}")
            return {
                "success": False,
                "error": f"Runtime logs directory {actual_logs_dir} does not exist and could not be created.",
                "execution_id": None,
                "errors": []
            }
    
    logger.info(f"RuntimeErrorAnalyzer: Starting analysis in directory: {os.path.abspath(actual_logs_dir)}")

    try:
        # Log files found in the directory before processing
        found_files = []
        try:
            found_files = os.listdir(actual_logs_dir)
            logger.info(f"RuntimeErrorAnalyzer: Files found in {os.path.abspath(actual_logs_dir)}: {found_files}")
        except Exception as e:
            logger.error(f"RuntimeErrorAnalyzer: Error listing files in {os.path.abspath(actual_logs_dir)}: {e}")
            # Continue, find_latest_session and error scanning will likely also fail or find nothing

        execution_id, execution_timestamp = find_latest_session(actual_logs_dir) # actual_logs_dir is absolute here
        
        if not execution_id:
            logger.warning("RuntimeErrorAnalyzer: Could not find any execution ID in the runtime logs.")
            execution_id = "unknown"
            execution_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')
        else:
            logger.info(f"RuntimeErrorAnalyzer: Found most recent reference execution ID: {execution_id}")
        
        errors = []
        # Iterate using the already logged found_files list if it was successful
        files_to_scan = found_files if found_files else [] 
        # If listdir failed, try to list again, maybe it was a temp issue (though unlikely)
        if not files_to_scan:
            try:
                files_to_scan = os.listdir(actual_logs_dir)
            except Exception:
                files_to_scan = [] # Give up if still failing

        for log_file_name in files_to_scan:
            if not log_file_name.endswith('.log'):
                continue
                
            log_path = os.path.join(actual_logs_dir, log_file_name)
            try:
                with open(log_path, 'r') as f:
                    log_lines = f.readlines()
                
                for i, line in enumerate(log_lines):
                    # Check if line contains an error keyword
                    if re.search(r'error|fail|exception|traceback', line, re.IGNORECASE):
                        # Get context (up to 2 lines before and after)
                        start = max(0, i - 2)
                        end = min(len(log_lines), i + 3)
                        context = log_lines[start:end]
                        
                        # Extract timestamp if available
                        timestamp_match = re.search(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                        timestamp = timestamp_match.group(1) if timestamp_match else None
                        
                        # Extract session ID if available
                        session_match = re.search(r'(\d{6}-\d{6}-[a-zA-Z0-9]+-[a-zA-Z0-9]+)', line)
                        session_id = session_match.group(1) if session_match else None
                        
                        errors.append({
                            "log_file": log_file_name,
                            "line_number": i + 1,
                            "error_line": line.strip(),
                            "context": [l.strip() for l in context],
                            "timestamp": timestamp,
                            "session_id": session_id
                        })
            except Exception as e:
                logger.error(f"Error reading log file {log_file_name}: {e}")
        
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
            "errors": errors  # Include flat list for backward compatibility
        }
        
        logger.info(f"Analysis complete. Found {len(errors)} errors in runtime logs")
        return result
    
    except Exception as e:
        error_msg = f"Error analyzing runtime logs: {e}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "execution_id": None,
            "errors": []
        }

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze runtime logs for errors')
    parser.add_argument('--logs-dir', 
                       default=DEFAULT_RUNTIME_LOGS_DIR,
                       help=f'Directory containing log files (default: {DEFAULT_RUNTIME_LOGS_DIR})')
    parser.add_argument('--format', 
                       choices=['text', 'json'], 
                       default='text',
                       help='Output format (text or json)')
    return parser.parse_args()

def format_text_output(result: Dict[str, Any]) -> str:
    """Format the analysis result as readable text."""
    if not result['success']:
        return f"Error: {result['error']}"
    
    lines = []
    lines.append(f"Execution ID: {result['execution_id']}")
    lines.append(f"Execution Timestamp: {result['execution_timestamp']}")
    lines.append(f"Total Errors: {result['total_errors']}")
    lines.append("")
    
    if result['total_errors'] == 0:
        lines.append("No errors found for this execution ID.")
        return "\n".join(lines)
    
    # Group by log file
    for log_file, errors in result['errors_by_file'].items():
        lines.append(f"=== Errors in {log_file} ({len(errors)}) ===")
        
        for error in errors:
            lines.append(f"Line {error['line_number']}:")
            lines.append(f"Timestamp: {error['timestamp']}")
            lines.append("Context:")
            for ctx_line in error['context']:
                lines.append(f"    {ctx_line}")
            lines.append("")
    
    return "\n".join(lines)

def main():
    """Main entry point for the script."""
    args = parse_args()
    
    # Run the analysis
    result = analyze_runtime_errors(args.logs_dir)
    
    # Output in requested format
    if args.format == 'json':
        print(json.dumps(result, indent=2))
    else:
        print(format_text_output(result))
    
    # Return success or failure
    return 0 if result['success'] else 1

if __name__ == "__main__":
    sys.exit(main()) 