import pytest

from log_analyzer_mcp.test_log_parser import (
    analyze_pytest_log_content,
    extract_failed_tests,
    extract_overall_summary,
)

# Sample Log Snippets for Testing

LOG_NO_FAILURES = """
============================= test session starts ==============================
platform linux -- Python 3.9.5, pytest-6.2.4, py-1.10.0, pluggy-0.13.1
rootdir: /project
plugins: asyncio-0.15.1
collected 10 items

tests/test_module_alpha.py ..........                                    [100%]

============================== 10 passed in 0.05s ==============================
"""

LOG_WITH_MODULE_FAILURES = """
Unit tests output:
tests/test_module_beta.py::test_beta_one FAILED
tests/test_module_beta.py::test_beta_two PASSED
tests/test_module_gamma.py::test_gamma_one FAILED

Failed tests by module:
Module: test_module_beta - 1 failed tests
- tests/test_module_beta.py
Module: test_module_gamma - 1 failed tests
- tests/test_module_gamma.py

================= 2 failed, 1 passed in 0.12s =================
"""

LOG_WITH_DIRECT_FAILURES = """
============================= test session starts ==============================
collected 3 items

tests/test_data_processing.py::test_process_normal_data PASSED           [ 33%]
tests/test_data_processing.py::test_process_edge_case FAILED             [ 66%]
tests/test_another_feature.py::test_main_feature PASSED                  [100%]

=================================== FAILURES ===================================
___________________________ test_process_edge_case ___________________________

    def test_process_edge_case():
>       assert 1 == 0
E       assert 1 == 0

tests/test_data_processing.py:15: AssertionError
=========================== short test summary info ============================
FAILED tests/test_data_processing.py::test_process_edge_case - assert 1 == 0
!!!!!!!!!!!!!!!!!!!!!!!!!! Interrupted by signal !!!!!!!!!!!!!!!!!!!!!!!!!!!
========================= 1 failed, 2 passed in 0.02s =========================
"""

LOG_WITH_MIXED_FAILURES_AND_XFAIL_XPASS = """
collected 5 items
tests/test_ops.py::test_op_add PASSED
tests/test_ops.py::test_op_subtract FAILED
tests/test_advanced.py::test_complex_logic_xfail XFAIL
tests/test_advanced.py::test_another_one_xpass XPASS
tests/test_misc.py::test_simple PASSED

=================================== FAILURES ===================================
____________________________ test_op_subtract _____________________________
    def test_op_subtract():
>       assert 5 - 3 == 1
E       assert 2 == 1
tests/test_ops.py:10: AssertionError
=============== 1 failed, 2 passed, 1 xfailed, 1 xpassed in 0.03s ==============
"""

LOG_ONLY_SKIPPED = """
============================= test session starts ==============================
collected 2 items
tests/test_module_delta.py ..                                            [100%]
============================== 2 skipped in 0.01s ==============================
"""

LOG_WITH_ERRORS = """
============================= test session starts ==============================
collected 1 item
tests/test_setup_issue.py E                                              [100%]
==================================== ERRORS ====================================
_____________________ ERROR at setup of test_setup_issue _____________________
Setup failed
=========================== short test summary info ============================
ERROR tests/test_setup_issue.py::test_setup_issue
========================= 1 error in 0.01s =========================
"""

LOG_SHORT_SUMMARY_ONLY = """
session duration: 0.11s
tests/test_api.py::TestAPI::test_get_users PASSED (fixtures used: 'db_session', 'user_factory')
tests/test_api.py::TestAPI::test_create_user FAILED (fixtures used: 'db_session', 'user_payload')
1 failed, 1 passed, 2 skipped in 0.04s
"""  # This doesn't have the ===== border, tests fallback

LOG_NO_SUMMARY_LINE = """
Some random output without a clear pytest summary.
Maybe a crash before summary.
"""


class TestExtractFailedTests:
    def test_no_failures(self) -> None:
        assert extract_failed_tests(LOG_NO_FAILURES) == []

    def test_module_failures(self) -> None:
        expected = [
            {"module": "test_module_beta", "test_file": "tests/test_module_beta.py"},
            {"module": "test_module_gamma", "test_file": "tests/test_module_gamma.py"},
        ]
        assert extract_failed_tests(LOG_WITH_MODULE_FAILURES) == expected

    def test_direct_failures(self):
        expected = [
            {
                "module": "test_data_processing",
                "test_file": "tests/test_data_processing.py",
                "test_name": "test_process_edge_case",
            }
        ]
        assert extract_failed_tests(LOG_WITH_DIRECT_FAILURES) == expected

    def test_mixed_failures(self):
        # LOG_WITH_MIXED_FAILURES_AND_XFAIL_XPASS uses the third pattern (direct FAILED)
        expected = [
            {
                "module": "test_ops",
                "test_file": "tests/test_ops.py",
                "test_name": "test_op_subtract",
            }
        ]
        assert extract_failed_tests(LOG_WITH_MIXED_FAILURES_AND_XFAIL_XPASS) == expected


class TestExtractOverallSummary:
    def test_no_failures_summary(self) -> None:
        summary = extract_overall_summary(LOG_NO_FAILURES)
        assert summary["passed"] == 10
        assert summary["failed"] == 0
        assert summary["skipped"] == 0
        assert summary["xfailed"] == 0
        assert summary["xpassed"] == 0
        assert summary["errors"] == 0
        assert summary["status"] == "PASSED"
        assert summary["duration_seconds"] == 0.05
        assert (
            summary["summary_line"]
            == "============================== 10 passed in 0.05s =============================="
        )

    def test_module_failures_summary(self):
        summary = extract_overall_summary(LOG_WITH_MODULE_FAILURES)
        assert summary["passed"] == 1
        assert summary["failed"] == 2
        assert summary["status"] == "FAILED"
        assert summary["duration_seconds"] == 0.12
        assert summary["summary_line"] == "================= 2 failed, 1 passed in 0.12s ================="

    def test_direct_failures_summary(self):
        summary = extract_overall_summary(LOG_WITH_DIRECT_FAILURES)
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["status"] == "FAILED"
        assert summary["duration_seconds"] == 0.02
        assert (
            summary["summary_line"] == "========================= 1 failed, 2 passed in 0.02s ========================="
        )

    def test_mixed_failures_xpass_xfail_summary(self):
        summary = extract_overall_summary(LOG_WITH_MIXED_FAILURES_AND_XFAIL_XPASS)
        assert summary["passed"] == 2
        assert summary["failed"] == 1
        assert summary["skipped"] == 0
        assert summary["xfailed"] == 1
        assert summary["xpassed"] == 1
        assert summary["errors"] == 0
        assert summary["status"] == "FAILED"
        assert summary["duration_seconds"] == 0.03
        assert (
            summary["summary_line"]
            == "=============== 1 failed, 2 passed, 1 xfailed, 1 xpassed in 0.03s =============="
        )

    def test_only_skipped_summary(self):
        summary = extract_overall_summary(LOG_ONLY_SKIPPED)
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 2
        assert summary["status"] == "SKIPPED"
        assert summary["duration_seconds"] == 0.01
        assert (
            summary["summary_line"]
            == "============================== 2 skipped in 0.01s =============================="
        )

    def test_errors_summary(self):
        summary = extract_overall_summary(LOG_WITH_ERRORS)
        assert summary["passed"] == 0
        assert summary["failed"] == 0  # Errors are not counted as failed tests by this parser for 'failed' key
        assert summary["skipped"] == 0
        assert summary["errors"] == 1
        assert summary["status"] == "FAILED"  # Status is FAILED due to errors
        assert summary["duration_seconds"] == 0.01
        assert summary["summary_line"] == "========================= 1 error in 0.01s ========================="

    def test_short_summary_fallback(self):
        summary = extract_overall_summary(LOG_SHORT_SUMMARY_ONLY)
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["skipped"] == 2
        assert summary["xfailed"] == 0  # Not in this short summary example
        assert summary["xpassed"] == 0  # Not in this short summary example
        assert summary["errors"] == 0
        assert summary["status"] == "FAILED"
        assert summary["duration_seconds"] == 0.04
        assert summary["summary_line"] == ""  # No main bordered summary line matched

    def test_no_summary_line(self):
        summary = extract_overall_summary(LOG_NO_SUMMARY_LINE)
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["skipped"] == 0
        assert summary["status"] == "UNKNOWN"
        assert summary["duration_seconds"] is None
        assert summary["summary_line"] == ""


class TestAnalyzePytestLogContent:
    def test_analyze_summary_only(self) -> None:
        result = analyze_pytest_log_content(LOG_WITH_MODULE_FAILURES, summary_only=True)
        assert "overall_summary" in result
        assert "failed_tests" not in result
        assert result["overall_summary"]["failed"] == 2
        assert result["overall_summary"]["passed"] == 1

    def test_analyze_full_report(self):
        result = analyze_pytest_log_content(LOG_WITH_DIRECT_FAILURES, summary_only=False)
        assert "overall_summary" in result
        assert "failed_tests" in result
        assert result["overall_summary"]["failed"] == 1
        assert result["overall_summary"]["passed"] == 2
        expected_failed_tests = [
            {
                "module": "test_data_processing",
                "test_file": "tests/test_data_processing.py",
                "test_name": "test_process_edge_case",
            }
        ]
        assert result["failed_tests"] == expected_failed_tests

    def test_analyze_no_failures(self) -> None:
        result = analyze_pytest_log_content(LOG_NO_FAILURES, summary_only=False)
        assert result["overall_summary"]["status"] == "PASSED"
        assert result["overall_summary"]["passed"] == 10
        assert result["failed_tests"] == []

    def test_analyze_with_errors(self) -> None:
        result = analyze_pytest_log_content(LOG_WITH_ERRORS, summary_only=False)
        assert result["overall_summary"]["status"] == "FAILED"
        assert result["overall_summary"]["errors"] == 1
        # extract_failed_tests might not pick up errors as 'failed tests' depending on format
        # For this specific log, it doesn't have typical 'FAILED' markers for extract_failed_tests
        assert result["failed_tests"] == []
