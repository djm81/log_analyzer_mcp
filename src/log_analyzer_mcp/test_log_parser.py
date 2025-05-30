"""
Specialized parser for pytest log output (e.g., from run_all_tests.py).
This module contains functions extracted and adapted from the original log_analyzer.py script.
"""

import re
from typing import Any, Dict, List


def extract_failed_tests(log_contents: str) -> List[Dict[str, Any]]:
    """Extract information about failed tests from the log file"""
    failed_tests = []

    # Try different patterns to match failed tests

    # First attempt: Look for the "Failed tests by module:" section
    module_failures_pattern = r"Failed tests by module:(.*?)(?:={10,}|\Z)"
    module_failures_match = re.search(module_failures_pattern, log_contents, re.DOTALL)

    if module_failures_match:
        module_failures_section = module_failures_match.group(1).strip()

        current_module = None

        for line in module_failures_section.split("\n"):
            line = line.strip()
            if not line:
                continue

            module_match = re.match(r"Module: ([^-]+) - (\d+) failed tests", line)
            if module_match:
                current_module = module_match.group(1).strip()
                continue

            test_match = re.match(r"(?:- )?(.+\.py)$", line)
            if test_match and current_module:
                test_file = test_match.group(1).strip()
                failed_tests.append({"module": current_module, "test_file": test_file})

    # Second attempt: Look for failed tests directly in the pytest output section
    if not failed_tests:
        pytest_output_pattern = r"Unit tests output:(.*?)(?:Unit tests errors:|\n\n\S|\Z)"
        pytest_output_match = re.search(pytest_output_pattern, log_contents, re.DOTALL)

        if pytest_output_match:
            pytest_output = pytest_output_match.group(1).strip()

            failed_test_pattern = r"(tests/[^\s]+)::([^\s]+) FAILED"
            test_failures = re.findall(failed_test_pattern, pytest_output)

            for test_file, test_name in test_failures:
                module_full_name = test_file.split("/")[1] if "/" in test_file else "Unit Tests"
                module = module_full_name.replace(".py", "") if module_full_name != "Unit Tests" else "Unit Tests"
                failed_tests.append({"module": module, "test_file": test_file, "test_name": test_name})

    # Third attempt: Look for FAILED markers in the log
    if not failed_tests:
        failed_pattern = r"(tests/[^\s]+)::([^\s]+) FAILED"
        all_failures = re.findall(failed_pattern, log_contents)

        for test_file, test_name in all_failures:
            module_full_name = test_file.split("/")[1] if "/" in test_file else "Unit Tests"
            module = module_full_name.replace(".py", "") if module_full_name != "Unit Tests" else "Unit Tests"
            failed_tests.append({"module": module, "test_file": test_file, "test_name": test_name})

    return failed_tests


def extract_overall_summary(log_contents: str) -> Dict[str, Any]:
    """Extract the overall test summary from the log file"""
    passed = 0
    failed = 0
    skipped = 0
    xfailed = 0
    xpassed = 0
    errors = 0
    status = "UNKNOWN"
    duration = None
    summary_line = ""

    # Pytest summary line patterns (order matters for specificity)
    # Example: "========= 2 failed, 4 passed, 1 skipped, 1 xfailed, 1 xpassed, 1 error in 0.12s =========="
    # Example: "============ 1 failed, 10 passed, 2 skipped in 0.05s ============"
    # Example: "=============== 819 passed, 13 skipped in 11.01s ==============="
    summary_patterns = [
        r"==+ (?:(\d+) failed(?:, )?)?(?:(\d+) passed(?:, )?)?(?:(\d+) skipped(?:, )?)?(?:(\d+) xfailed(?:, )?)?(?:(\d+) xpassed(?:, )?)?(?:(\d+) error(?:s)?(?:, )?)? in ([\d\.]+)s ={10,}",
        r"==+ (?:(\d+) passed(?:, )?)?(?:(\d+) failed(?:, )?)?(?:(\d+) skipped(?:, )?)?(?:(\d+) xfailed(?:, )?)?(?:(\d+) xpassed(?:, )?)?(?:(\d+) error(?:s)?(?:, )?)? in ([\d\.]+)s ={10,}",
        # Simpler patterns if some elements are missing
        r"==+ (\d+) failed, (\d+) passed in ([\d\.]+)s ={10,}",
        r"==+ (\d+) passed in ([\d\.]+)s ={10,}",
        r"==+ (\d+) failed in ([\d\.]+)s ={10,}",
        r"==+ (\d+) skipped in ([\d\.]+)s ={10,}",
    ]

    # Search for summary lines in reverse to get the last one (most relevant)
    for line in reversed(log_contents.splitlines()):
        for i, pattern in enumerate(summary_patterns):
            match = re.search(pattern, line)
            if match:
                summary_line = line  # Store the matched line
                groups = match.groups()
                # print(f"Matched pattern {i} with groups: {groups}") # Debugging

                if i == 0 or i == 1:  # Corresponds to the more complex patterns
                    failed_str, passed_str, skipped_str, xfailed_str, xpassed_str, errors_str, duration_str = groups
                    failed = int(failed_str) if failed_str else 0
                    passed = int(passed_str) if passed_str else 0
                    skipped = int(skipped_str) if skipped_str else 0
                    xfailed = int(xfailed_str) if xfailed_str else 0
                    xpassed = int(xpassed_str) if xpassed_str else 0
                    errors = int(errors_str) if errors_str else 0
                    duration = float(duration_str) if duration_str else None
                elif i == 2:  # failed, passed, duration
                    failed = int(groups[0]) if groups[0] else 0
                    passed = int(groups[1]) if groups[1] else 0
                    duration = float(groups[2]) if groups[2] else None
                elif i == 3:  # passed, duration
                    passed = int(groups[0]) if groups[0] else 0
                    duration = float(groups[1]) if groups[1] else None
                elif i == 4:  # failed, duration
                    failed = int(groups[0]) if groups[0] else 0
                    duration = float(groups[1]) if groups[1] else None
                elif i == 5:  # skipped, duration
                    skipped = int(groups[0]) if groups[0] else 0
                    duration = float(groups[1]) if groups[1] else None
                break  # Found a match for this line, move to determining status
        if summary_line:  # If a summary line was matched and processed
            break

    if failed > 0 or errors > 0:
        status = "FAILED"
    elif passed > 0 and failed == 0 and errors == 0:
        status = "PASSED"
    elif skipped > 0 and passed == 0 and failed == 0 and errors == 0:
        status = "SKIPPED"
    else:
        # Fallback: try to find simple pass/fail count from pytest's short test summary info
        # Example: "1 failed, 10 passed, 2 skipped in 0.04s"
        # This section is usually just before the long "====...====" line
        short_summary_match = re.search(
            r"(\d+ failed)?(?:, )?(\d+ passed)?(?:, )?(\d+ skipped)?(?:, )?(\d+ xfailed)?(?:, )?(\d+ xpassed)?(?:, )?(\d+ warnings?)?(?:, )?(\d+ errors?)? in (\d+\.\d+)s",
            log_contents,
        )
        if short_summary_match:
            groups = short_summary_match.groups()
            if groups[0]:
                failed = int(groups[0].split()[0])
            if groups[1]:
                passed = int(groups[1].split()[0])
            if groups[2]:
                skipped = int(groups[2].split()[0])
            if groups[3]:
                xfailed = int(groups[3].split()[0])
            if groups[4]:
                xpassed = int(groups[4].split()[0])
            # Warnings are not typically part of overall status but can be counted
            # errors_str from group 6
            if groups[6]:
                errors = int(groups[6].split()[0])
            if groups[7]:
                duration = float(groups[7])

            if failed > 0 or errors > 0:
                status = "FAILED"
            elif passed > 0:
                status = "PASSED"
            elif skipped > 0:
                status = "SKIPPED"

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "errors": errors,
        "status": status,
        "duration_seconds": duration,
        "summary_line": summary_line.strip(),
    }


def analyze_pytest_log_content(log_contents: str, summary_only: bool = False) -> Dict[str, Any]:
    """
    Analyzes the full string content of a pytest log.

    Args:
        log_contents: The string content of the pytest log.
        summary_only: If True, returns only the overall summary.
                      Otherwise, includes details like failed tests.

    Returns:
        A dictionary containing the analysis results.
    """
    overall_summary = extract_overall_summary(log_contents)

    if summary_only:
        return {"overall_summary": overall_summary}

    failed_tests = extract_failed_tests(log_contents)
    # Placeholder for other details to be added once their extraction functions are moved/implemented
    # error_details = extract_error_details(log_contents)
    # exception_traces = extract_exception_traces(log_contents)
    # module_statistics = extract_module_statistics(log_contents)

    return {
        "overall_summary": overall_summary,
        "failed_tests": failed_tests,
        # "error_details": error_details, # Uncomment when available
        # "exception_traces": exception_traces, # Uncomment when available
        # "module_statistics": module_statistics, # Uncomment when available
    }


# TODO: Move other relevant functions: extract_error_details, extract_exception_traces, extract_module_statistics
# TODO: Create a main orchestrator function if needed, e.g., analyze_pytest_log(log_contents: str)
