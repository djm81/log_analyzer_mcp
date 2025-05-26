#!/usr/bin/env python3
"""
Test Log Analyzer

This script parses run_all_tests.py log files to extract and organize error information.
It can be used with Cursor's MCP to analyze test failures without uploading the entire log.
"""

import sys
import os
import re
import argparse
from typing import List, Dict, Any
import json

# Add venv support - REMOVED as hatch manages the environment
# try:
#     script_dir = os.path.dirname(os.path.abspath(__file__))  # test_analyzer_mcp directory
#     project_root = os.path.dirname(os.path.dirname(script_dir))  # coding-factory directory
#     if project_root not in sys.path:
#         sys.path.insert(0, project_root)
#     from src.common.venv_helper import setup_venv
#     
#     # Parse arguments early to check format
#     parser = argparse.ArgumentParser(description='Analyze test log files')
#     parser.add_argument('log_file', help='Path to the log file', 
#                         default=os.path.join(os.path.dirname(os.path.dirname(script_dir)), 
#                                            'logs/run_all_tests.log'), nargs='?')
#     parser.add_argument('--format', choices=['text', 'json'], default='text',
#                         help='Output format (text or json)')
#     parser.add_argument('--summary-only', action='store_true',
#                         help='Show only the summary information')
#     args = parser.parse_args()
#     
#     # Ensure we're running in venv before importing other modules
#     # Always suppress output to keep it clean
#     setup_venv(os.path.join(project_root, 'src', 'requirements.txt'), suppress_output=True)
# except ImportError as e:
#     print(f"Warning: Could not import venv_helper. Running without virtual environment: {e}")

# script_dir needs to be defined for default log_file path calculation later
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(script_dir))

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Analyze test log files')
    # Corrected default path for log_file to be relative to project_root after removing old script_dir logic context
    parser.add_argument('log_file', help='Path to the log file', 
                        default=os.path.join(project_root, 'logs', 'run_all_tests.log'), nargs='?')
    parser.add_argument('--format', choices=['text', 'json'], default='text',
                        help='Output format (text or json)')
    parser.add_argument('--summary-only', action='store_true',
                        help='Show only the summary information')
    return parser.parse_args()

def extract_failed_tests(log_contents: str) -> List[Dict[str, Any]]:
    """Extract information about failed tests from the log file"""
    failed_tests = []
    
    # Try different patterns to match failed tests
    
    # First attempt: Look for the "Failed tests by module:" section
    module_failures_pattern = r"Failed tests by module:(.*?)(?:={10,}|\Z)"
    module_failures_match = re.search(module_failures_pattern, log_contents, re.DOTALL)
    
    if module_failures_match:
        module_failures_section = module_failures_match.group(1).strip()
        
        # Extract module and test information
        current_module = None
        
        for line in module_failures_section.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Match module line
            module_match = re.match(r"Module: ([^-]+) - (\d+) failed tests", line)
            if module_match:
                current_module = module_match.group(1).strip()
                continue
                
            # Match test file line
            test_match = re.match(r"(?:- )?(.+\.py)$", line)
            if test_match and current_module:
                test_file = test_match.group(1).strip()
                failed_tests.append({
                    "module": current_module,
                    "test_file": test_file
                })
    
    # Second attempt: Look for failed tests directly in the pytest output section
    if not failed_tests:
        pytest_output_pattern = r"Unit tests output:(.*?)(?:Unit tests errors:|\n\n\S|\Z)"
        pytest_output_match = re.search(pytest_output_pattern, log_contents, re.DOTALL)
        
        if pytest_output_match:
            pytest_output = pytest_output_match.group(1).strip()
            
            # Find all test failures in pytest output
            failed_test_pattern = r"(tests/[^\s]+)::([^\s]+) FAILED"
            test_failures = re.findall(failed_test_pattern, pytest_output)
            
            for test_file, test_name in test_failures:
                module = test_file.split('/')[1] if '/' in test_file else "Unit Tests"
                failed_tests.append({
                    "module": module,
                    "test_file": test_file,
                    "test_name": test_name
                })
    
    # Third attempt: Look for FAILED markers in the log
    if not failed_tests:
        failed_pattern = r"(tests/[^\s]+)::([^\s]+) FAILED"
        all_failures = re.findall(failed_pattern, log_contents)
        
        for test_file, test_name in all_failures:
            module = test_file.split('/')[1] if '/' in test_file else "Unit Tests"
            failed_tests.append({
                "module": module,
                "test_file": test_file,
                "test_name": test_name
            })
    
    return failed_tests

def extract_error_details(log_contents: str) -> List[Dict[str, Any]]:
    """Extract detailed error messages from the log file"""
    error_details = []
    
    # Pattern to match test failures in both formats
    test_error_patterns = [
        r"❌ ([^F]+) FAILED.*?(?:INFO|\Z)",  # Original format
        r"Test Summary:.*?Failed tests by module:.*?- ([^\n]+).*?(?:={10,}|\Z)"  # New format
    ]
    
    for pattern in test_error_patterns:
        test_error_matches = re.finditer(pattern, log_contents, re.DOTALL)
        
        for match in test_error_matches:
            error_text = match.group(0)
            test_name = match.group(1).strip()
            
            # Try to extract the return code if present
            return_code_match = re.search(r"return code (\d+)", error_text)
            return_code = int(return_code_match.group(1)) if return_code_match else None
            
            # Try to extract exception information if present
            exception_match = re.search(r"Error.*?: (.+)", error_text)
            exception = exception_match.group(1) if exception_match else None
            
            error_details.append({
                "test_name": test_name,
                "return_code": return_code,
                "exception": exception,
                "error_message": error_text.strip(),
                "type": "test_failure"
            })
    
    # Pattern to match type checking errors
    type_error_pattern = r"Type checking found issues.*?Found (\d+) errors? in (\d+) files?.*?(?=\n\S|\Z)"
    type_error_matches = re.finditer(type_error_pattern, log_contents, re.DOTALL | re.MULTILINE)
    
    for match in type_error_matches:
        error_text = match.group(0)
        num_errors = int(match.group(1))
        num_files = int(match.group(2))
        
        # Extract individual type errors
        individual_errors = re.finditer(r"([^:\n]+\.py:\d+): error: ([^\n]+)", error_text)
        for err in individual_errors:
            file_loc = err.group(1)
            error_msg = err.group(2)
            
            error_details.append({
                "test_name": "Type Check",
                "file_location": file_loc,
                "error_message": error_msg,
                "type": "type_error",
                "context": f"Found {num_errors} errors in {num_files} files"
            })
    
    # Pattern to match class structure validation failures
    class_structure_pattern = r"❌ ([^:\n]+)(?: missing method: ([^\n]+)|: (.+))"
    class_structure_matches = re.finditer(class_structure_pattern, log_contents)
    
    for match in class_structure_matches:
        class_name = match.group(1).strip()
        method_name = match.group(2) if match.group(2) else None
        error_msg = match.group(3) if match.group(3) else None
        
        error_details.append({
            "test_name": "Class Structure",
            "class_name": class_name,
            "missing_method": method_name,
            "error_message": error_msg or f"Missing required method: {method_name}",
            "type": "class_structure"
        })
    
    # Pattern to match import failures
    import_pattern = r"Failed to import ([^\n:]+)(?:[^:]*): ([^\n]+)"
    import_matches = re.finditer(import_pattern, log_contents)
    
    for match in import_matches:
        module_name = match.group(1).strip()
        error_msg = match.group(2).strip()
        
        error_details.append({
            "test_name": "Import Test",
            "module": module_name,
            "error_message": error_msg,
            "type": "import_failure"
        })
    
    return error_details

def extract_exception_traces(log_contents: str) -> List[str]:
    """Extract Python exception traces from the log file"""
    # Pattern to match traceback sections
    traceback_pattern = r"Traceback \(most recent call last\):.*?(?=\n\S|\Z)"
    traceback_matches = re.finditer(traceback_pattern, log_contents, re.DOTALL)
    
    traces = []
    for match in traceback_matches:
        traces.append(match.group(0).strip())
    
    return traces

def extract_overall_summary(log_contents: str) -> Dict[str, Any]:
    """Extract the overall test summary from the log file"""
    # Initialize default values
    passed = 0
    failed = 0
    skipped = 0
    status = "UNKNOWN"
    duration = None
    
    # Try different patterns to find the test summary
    
    # First attempt: Use the explicit test summary format created by LoggerSetup.write_test_summary
    test_session_pattern = r"=============== test session starts ===============\n([^=]*?)(?:={10,}|\Z)"
    test_session_match = re.search(test_session_pattern, log_contents, re.DOTALL)
    if test_session_match:
        summary_section = test_session_match.group(1).strip()
        summary_pattern = r"(\d+) passed, (\d+) failed, (\d+) skipped"
        summary_match = re.search(summary_pattern, summary_section)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))
            skipped = int(summary_match.group(3))
            
            # Extract duration from the same section
            duration_pattern = r"Duration: ([\d.]+) seconds"
            duration_match = re.search(duration_pattern, summary_section)
            if duration_match:
                duration = float(duration_match.group(1))
    
    # Second attempt: Try the standard Test Summary line
    if passed == 0 and failed == 0:
        summary_pattern = r"Test Summary: (\d+) passed, (\d+) failed, (\d+) skipped"
        summary_match = re.search(summary_pattern, log_contents)
        if summary_match:
            passed = int(summary_match.group(1))
            failed = int(summary_match.group(2))
            skipped = int(summary_match.group(3))
    
    # Third attempt: Extract directly from pytest output if no counts found yet
    if passed == 0 and failed == 0 and skipped == 0:
        # This regex is designed to be flexible for various pytest summary line formats.
        # Example: "========= 3 passed in 0.02s ========="
        # Example: "========= 1 failed, 2 passed, 1 skipped in 0.12s ========="
        final_summary_regex = (
            r"=+.*?"  # Start with equals and non-greedy stuff
            r"(?:(\d+) failed)?(?:, ?)?"      # Optional failed
            r"(?:(\d+) passed)?(?:, ?)?"      # Optional passed
            r"(?:(\d+) skipped)?(?:, ?)?"     # Optional skipped
            r"(?:(\d+) deselected)?(?:, ?)?" # Optional deselected
            r"(?:(\d+) errors?)?(?:, ?)?"    # Optional errors
            r"(?:(\d+) warnings?)?(?:, ?)?"  # Optional warnings
            r"(?:(\d+) xfailed)?(?:, ?)?"    # Optional xfailed
            r"(?:(\d+) xpassed)?"           # Optional xpassed (no comma after this one before "in")
            r" in (\d[\d.]*)s"               # Duration is mandatory for this pattern
            r" =+"                         # End with equals
        )
        
        final_summary_match = re.search(final_summary_regex, log_contents, re.IGNORECASE)

        if final_summary_match:
            # Groups are: 1:failed, 2:passed, 3:skipped, 4:deselected, 5:errors, 
            #             6:warnings, 7:xfailed, 8:xpassed, 9:duration
            _failed = final_summary_match.group(1)
            _passed = final_summary_match.group(2)
            _skipped = final_summary_match.group(3)
            # _deselected = final_summary_match.group(4)
            # _errors = final_summary_match.group(5)
            # _warnings = final_summary_match.group(6)
            # _xfailed = final_summary_match.group(7)
            # _xpassed = final_summary_match.group(8)
            _duration = final_summary_match.group(9)

            if _failed: failed = int(_failed)
            if _passed: passed = int(_passed)
            if _skipped: skipped = int(_skipped)
            if _duration: duration = float(_duration)
        else:
            # Fallback to even simpler individual counters if the full summary line isn't matched.
            # These are less reliable as they might pick up counts from intermediate lines or other sections.
            # Only update if still zero, to avoid overwriting more specific matches from earlier attempts.
            if passed == 0:
                passed_matches = re.findall(r"(\d+) passed", log_contents) # Simpler pattern
                if passed_matches: passed = int(passed_matches[-1]) # take last one
            if failed == 0:
                failed_matches = re.findall(r"(\d+) failed", log_contents)
                if failed_matches: failed = int(failed_matches[-1])
            if skipped == 0:
                skipped_matches = re.findall(r"(\d+) skipped", log_contents)
                if skipped_matches: skipped = int(skipped_matches[-1])

    # Fallback counts if all else fails (original fourth attempt)
    if passed == 0 and failed == 0:
        passed = len(re.findall(r"✅.*?PASSED", log_contents))
        failed = len(re.findall(r"❌.*?FAILED", log_contents))
    
    # Count other kinds of failures
    class_structure_failures = len(re.findall(r"❌ ([^:\n]+)(?: missing method: ([^\n]+)|: (.+))", log_contents))
    import_failures = len(re.findall(r"Failed to import ([^\n:]+)(?:[^:]*): ([^\n]+)", log_contents))
    failed += class_structure_failures + import_failures
    
    # Check for type checking errors
    type_errors = re.search(r"Type checking found issues.*?Found (\d+) errors?", log_contents, re.DOTALL)
    if type_errors:
        failed += int(type_errors.group(1))
    
    # Extract duration if not already found
    if duration is None:
        duration_pattern = r"Duration: ([\d.]+) seconds"
        duration_match = re.search(duration_pattern, log_contents)
        if duration_match:
            duration = float(duration_match.group(1))
        else:
            # Look for test duration in unit test output
            duration_pattern = r"Unit tests: .*? in ([\d.]+)s"
            duration_match = re.search(duration_pattern, log_contents)
            if duration_match:
                duration = float(duration_match.group(1))
    
    # Determine overall status
    status = "PASSED" if failed == 0 else "FAILED"
    
    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "status": status,
        "duration": duration
    }

def extract_module_statistics(log_contents: str) -> List[Dict[str, Any]]:
    """Extract statistics by module from the log file"""
    # Find the module statistics section
    module_stats_pattern = r"Results by Module:(.*?)(?:Failed tests by module:|\n\n|={10,}|\Z)"
    module_stats_match = re.search(module_stats_pattern, log_contents, re.DOTALL)
    
    if not module_stats_match:
        return []
    
    module_stats_section = module_stats_match.group(1).strip()
    module_stats = []
    
    # Pattern to match module statistics lines
    # Matches both formats:
    # - "  module_name: ✅ PASSED - 2/2 passed (100.0%)"
    # - "  module_name: ❌ FAILED - 8/10 passed (80.0%)"
    module_line_pattern = r"\s*([^:]+):\s*(✅|❌)\s*(PASSED|FAILED)\s*-\s*(\d+)/(\d+)\s*passed\s*\(([\d.]+)%\)"
    
    for line in module_stats_section.split('\n'):
        line = line.strip()
        if not line:
            continue
            
        match = re.match(module_line_pattern, line)
        if match:
            module_name = match.group(1).strip()
            status = match.group(3)
            passed = int(match.group(4))
            total = int(match.group(5))
            pass_rate = float(match.group(6))
            
            module_stats.append({
                "module": module_name,
                "status": status,
                "passed": passed,
                "total": total,
                "pass_rate": pass_rate
            })
    
    return module_stats

def analyze_log_file(log_file_path: str, summary_only: bool = False) -> Dict[str, Any]:
    """Analyze the test log file and extract relevant information"""
    try:
        with open(log_file_path, 'r') as f:
            log_contents = f.read()
        
        # Always extract the overall summary
        overall_summary = extract_overall_summary(log_contents)
        
        # If summary_only, only include summary and failed test names
        if summary_only:
            failed_tests = extract_failed_tests(log_contents)
            return {
                "summary": overall_summary,
                "failed_tests": failed_tests,
                "summary_only": True
            }
        
        # Otherwise extract all information
        failed_tests = extract_failed_tests(log_contents)
        error_details = extract_error_details(log_contents)
        exception_traces = extract_exception_traces(log_contents)
        module_stats = extract_module_statistics(log_contents)
        
        # Compile all results
        analysis_results = {
            "summary": overall_summary,
            "module_stats": module_stats,
            "failed_tests": failed_tests,
            "error_details": error_details,
            "exception_traces": exception_traces,
            "summary_only": False
        }
        
        return analysis_results
        
    except Exception as e:
        return {
            "error": str(e),
            "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0},
            "module_stats": [],
            "failed_tests": [],
            "error_details": [],
            "exception_traces": [],
            "summary_only": summary_only
        }

def format_text_output(analysis_results: Dict[str, Any]) -> str:
    """Format the analysis results as readable text"""
    output = []
    
    # Overall Summary
    output.append("Analysis Results:\n")
    summary = analysis_results["summary"]
    output.append(f"Test Status: {summary['status']}")
    output.append(f"Tests: {summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped")
    if summary.get('duration'):
        output.append(f"Duration: {summary['duration']} seconds")
    
    # If summary_only, only show failed test names if any
    if analysis_results.get("summary_only"):
        if analysis_results.get("failed_tests"):
            output.append("\nFailed Tests:")
            for test in analysis_results["failed_tests"]:
                output.append(f"❌ {test['module']}: {test['test_file']}")
        return "\n".join(output)
    
    output.append("")
    
    # Module Statistics
    if analysis_results.get("module_stats"):
        output.append("=== MODULE STATISTICS ===")
        for stat in analysis_results["module_stats"]:
            status_icon = "✅" if stat["status"] == "PASSED" else "❌"
            output.append(f"  {stat['module']}: {status_icon} {stat['status']} - {stat['passed']}/{stat['total']} passed ({stat['pass_rate']}%)")
        output.append("")
    
    # Failed Tests and Errors
    if analysis_results["error_details"]:
        output.append("=== ERRORS AND FAILURES ===")
        
        # Group errors by type
        test_failures = [e for e in analysis_results["error_details"] if e["type"] == "test_failure"]
        type_errors = [e for e in analysis_results["error_details"] if e["type"] == "type_error"]
        class_structure_errors = [e for e in analysis_results["error_details"] if e["type"] == "class_structure"]
        import_failures = [e for e in analysis_results["error_details"] if e["type"] == "import_failure"]
        
        if test_failures:
            output.append("\nTest Failures:")
            for error in test_failures:
                output.append(f"❌ {error['test_name']}")
                if error.get("return_code"):
                    output.append(f"Return Code: {error['return_code']}")
                if error.get("exception"):
                    output.append(f"Exception: {error['exception']}")
                output.append("---")
        
        if type_errors:
            output.append("\nType Check Errors:")
            for error in type_errors:
                output.append(f"Location: {error['file_location']}")
                output.append(f"Error: {error['error_message']}")
                output.append("---")
            if type_errors[0].get("context"):
                output.append(f"\nSummary: {type_errors[0]['context']}")
        
        if class_structure_errors:
            output.append("\nClass Structure Validation Failures:")
            current_class = None
            for error in class_structure_errors:
                if current_class != error['class_name']:
                    current_class = error['class_name']
                    output.append(f"\n❌ {current_class}:")
                if error.get('missing_method'):
                    output.append(f"  - Missing method: {error['missing_method']}")
                else:
                    output.append(f"  - {error['error_message']}")
            output.append("")
        
        if import_failures:
            output.append("\nImport Failures:")
            for error in import_failures:
                output.append(f"❌ {error['module']}")
                output.append(f"Error: {error['error_message']}")
                output.append("---")
        
        output.append("")
    
    # Exception Traces
    if analysis_results["exception_traces"]:
        output.append("=== EXCEPTION TRACES ===")
        for i, trace in enumerate(analysis_results["exception_traces"], 1):
            output.append(f"Trace {i}:")
            output.append(trace)
            output.append("---")
        output.append("")
    
    return "\n".join(output)

def main():
    """Main entry point for the script"""
    args = parse_arguments()
    
    # Get the correct log file path
    log_file = args.log_file
    script_dir = os.path.dirname(os.path.abspath(__file__))  # mcp directory
    parent_dir = os.path.dirname(script_dir)  # coding-factory directory
    
    # If it's an absolute path, use it as is
    if os.path.isabs(log_file):
        pass
    # If it starts with ../, treat as relative to mcp directory
    elif log_file.startswith('../'):
        log_file = os.path.join(script_dir, log_file)
    # Try multiple locations in order of preference
    else:
        # For any path, prioritize coding-factory/logs
        possible_paths = [
            os.path.join(parent_dir, 'logs', os.path.basename(log_file)),  # coding-factory/logs/
            os.path.join(script_dir, 'logs', os.path.basename(log_file)),  # mcp/logs/
            os.path.join(parent_dir, log_file),  # coding-factory/
            os.path.join(script_dir, log_file),  # mcp/
            os.path.join(os.getcwd(), 'logs', os.path.basename(log_file)),  # ./logs/
            os.path.join(os.getcwd(), log_file)  # ./
        ]
        
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                log_file = path
                found = True
                break
        
        if not found:
            # Default to coding-factory/logs which is where the file should be
            log_file = os.path.join(parent_dir, 'logs', os.path.basename(log_file))
    
    # Verify the log file exists
    if not os.path.exists(log_file):
        error_msg = {
            "error": "Log file not found",
            "searched_paths": [
                os.path.join(parent_dir, 'logs'),
                os.path.join(script_dir, 'logs'),
                parent_dir,
                script_dir,
                os.path.join(os.getcwd(), 'logs'),
                os.getcwd()
            ],
            "final_path": log_file,
            "summary": {"status": "ERROR", "passed": 0, "failed": 0, "skipped": 0}
        }
        if args.format == 'json':
            print(json.dumps(error_msg))
        else:
            print("Error: Log file not found. Searched in multiple locations including:")
            print(f"- {os.path.join(parent_dir, 'logs')} (coding-factory/logs)")
            print(f"- {os.path.join(script_dir, 'logs')} (mcp/logs)")
            print(f"- {parent_dir} (coding-factory)")
            print(f"- {script_dir} (mcp)")
            print(f"- {os.path.join(os.getcwd(), 'logs')} (current dir/logs)")
            print(f"- {os.getcwd()} (current dir)")
            print(f"\nFinal path attempted: {log_file}")
        return 1
    
    # Analyze the log file
    analysis_results = analyze_log_file(log_file, args.summary_only)
    
    # Output in requested format
    if args.format == 'json':
        # print(f"DEBUG_LOG_ANALYZER_MAIN_RETURN_JSON: {json.dumps(analysis_results, indent=2)}", file=sys.stderr) # DEBUG REMOVED
        print(json.dumps(analysis_results, indent=2))
    else:
        print(format_text_output(analysis_results))
    
    # Return success or failure
    # When format is json, main() is expected to return the dict or a status code by some conventions.
    # For now, if json, let's ensure it returns the dictionary itself if successful.
    if args.format == 'json':
        # If analysis_results is already what we want to return (the dict)
        # and not just a status code, return it directly.
        # If it was meant to be a status code, this needs adjustment.
        return analysis_results # This is what _run_tests in server expects for JSON format

    return 0 if analysis_results.get("summary", {}).get("status") not in ["FAILED", "ERROR", "UNKNOWN"] else 1

if __name__ == "__main__":
    # sys.exit(main()) # Old call
    main_return_value = main()
    if isinstance(main_return_value, dict): # If main returned the JSON dict
        # Assume success if it got to the point of returning the dict via JSON mode
        sys.exit(0)
    else: # Otherwise, it returned an int status code
        sys.exit(main_return_value)