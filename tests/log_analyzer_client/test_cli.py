import json
from unittest.mock import MagicMock, patch, ANY

import pytest
from click.testing import CliRunner

from log_analyzer_client.cli import cli

# FilterCriteria is not a class to be imported, it's a dict returned by build_filter_criteria
# from log_analyzer_mcp.common.utils import FilterCriteria # This import will be removed
from log_analyzer_mcp.core.analysis_engine import AnalysisEngine


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_analysis_engine_instance():
    mock_engine = MagicMock()
    mock_engine.search_logs.return_value = {"results": [{"line": "mocked_log_line_1"}]}
    return mock_engine


@pytest.fixture
def mock_analysis_engine_class(mock_analysis_engine_instance):
    # Patching AnalysisEngine in the module where it's LOOKED UP (cli.py uses it)
    with patch("log_analyzer_client.cli.AnalysisEngine", return_value=mock_analysis_engine_instance) as mock_class:
        yield mock_class


def test_cli_invoked(runner):
    """Test that the main CLI group can be invoked."""
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Log Analyzer CLI" in result.output
    assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output


def test_search_all_default_options(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test the 'search all' command with default options."""
    result = runner.invoke(cli, ["search", "all"])

    assert result.exit_code == 0
    mock_analysis_engine_instance.search_logs.assert_called_once()

    # Check the dictionary passed to search_logs
    args, _ = mock_analysis_engine_instance.search_logs.call_args
    called_filter_criteria_dict = args[0]

    assert isinstance(called_filter_criteria_dict, dict)
    assert called_filter_criteria_dict.get("scope") == "default"
    assert called_filter_criteria_dict.get("context_before") == 2
    assert called_filter_criteria_dict.get("context_after") == 2
    assert called_filter_criteria_dict.get("log_dirs_override") is None
    assert called_filter_criteria_dict.get("log_content_patterns_override") is None
    # The build_filter_criteria function doesn't explicitly add a "search_type" key based on its implementation.
    # We should check for the keys that are actually added.

    # Check output
    assert f"Searching all records in scope: default, context: 2B/2A" in result.output
    assert "mocked_log_line_1" in result.output


def test_search_all_custom_options(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test the 'search all' command with custom options."""
    custom_scope = "custom_scope"
    custom_before = 5
    custom_after = 5
    custom_log_dirs = "/logs/a,/logs/b"
    custom_log_patterns = "ERROR,WARN"

    result = runner.invoke(
        cli,
        [
            "search",
            "all",
            "--scope",
            custom_scope,
            "--before",
            str(custom_before),
            "--after",
            str(custom_after),
            "--log-dirs",
            custom_log_dirs,
            "--log-patterns",
            custom_log_patterns,
        ],
    )

    assert result.exit_code == 0
    mock_analysis_engine_instance.search_logs.assert_called_once()

    args, _ = mock_analysis_engine_instance.search_logs.call_args
    called_filter_criteria_dict = args[0]

    assert called_filter_criteria_dict.get("scope") == custom_scope
    assert called_filter_criteria_dict.get("context_before") == custom_before
    assert called_filter_criteria_dict.get("context_after") == custom_after
    assert called_filter_criteria_dict.get("log_dirs_override") == ["/logs/a", "/logs/b"]
    assert called_filter_criteria_dict.get("log_content_patterns_override") == ["ERROR", "WARN"]

    assert f"Searching all records in scope: {custom_scope}, context: {custom_before}B/{custom_after}A" in result.output
    assert "mocked_log_line_1" in result.output


def test_search_all_engine_exception(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search all' when AnalysisEngine throws an exception."""
    error_message = "Engine exploded!"
    mock_analysis_engine_instance.search_logs.side_effect = Exception(error_message)

    result = runner.invoke(cli, ["search", "all"])

    assert result.exit_code == 0  # CLI itself doesn't exit with error, but prints error message
    assert f"Error during search: {error_message}" in result.output
    mock_analysis_engine_instance.search_logs.assert_called_once()


def test_cli_with_env_file(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test CLI initialization with a custom .env file."""
    # Create a dummy .env file for testing
    with runner.isolated_filesystem():
        with open(".env.test", "w") as f:
            f.write("TEST_VAR=test_value\n")

        result = runner.invoke(cli, ["--env-file", ".env.test", "search", "all"])

        assert result.exit_code == 0
        assert "Using custom .env file: .env.test" in result.output
        # Check that AnalysisEngine was initialized with the env_file_path and a logger
        mock_analysis_engine_class.assert_called_once_with(logger_instance=ANY, env_file_path=".env.test")
        mock_analysis_engine_instance.search_logs.assert_called_once()


# --- Tests for 'search time' ---


@pytest.mark.parametrize(
    "time_args, expected_criteria_updates",
    [
        (["--minutes", "30"], {"minutes": 30, "hours": 0, "days": 0}),
        (["--hours", "2"], {"minutes": 0, "hours": 2, "days": 0}),
        (["--days", "1"], {"minutes": 0, "hours": 0, "days": 1}),
        (["--days", "1", "--hours", "2"], {"minutes": 0, "hours": 2, "days": 1}),  # Engine prioritizes
    ],
)
def test_search_time_various_units(
    runner, mock_analysis_engine_class, mock_analysis_engine_instance, time_args, expected_criteria_updates
):
    """Test 'search time' with different time unit specifications."""
    base_command = ["search", "time"]
    full_command = base_command + time_args

    result = runner.invoke(cli, full_command)

    assert result.exit_code == 0
    mock_analysis_engine_instance.search_logs.assert_called_once()

    args, _ = mock_analysis_engine_instance.search_logs.call_args
    called_filter_criteria_dict = args[0]

    assert called_filter_criteria_dict.get("minutes") == expected_criteria_updates["minutes"]
    assert called_filter_criteria_dict.get("hours") == expected_criteria_updates["hours"]
    assert called_filter_criteria_dict.get("days") == expected_criteria_updates["days"]

    # Verify default scope, context etc.
    assert called_filter_criteria_dict.get("scope") == "default"
    assert called_filter_criteria_dict.get("context_before") == 2
    assert called_filter_criteria_dict.get("context_after") == 2

    assert "mocked_log_line_1" in result.output
    if len(time_args) > 2:  # Multiple time units
        assert "Warning: Multiple time units" in result.output


def test_search_time_no_time_units(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search time' when no time units are specified."""
    result = runner.invoke(cli, ["search", "time"])

    assert result.exit_code == 0  # The command itself completes
    assert "Error: Please specify at least one of --minutes, --hours, or --days greater than zero." in result.output
    mock_analysis_engine_instance.search_logs.assert_not_called()


def test_search_time_engine_exception(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search time' when AnalysisEngine throws an exception."""
    error_message = "Time engine exploded!"
    mock_analysis_engine_instance.search_logs.side_effect = Exception(error_message)

    result = runner.invoke(cli, ["search", "time", "--minutes", "10"])

    assert result.exit_code == 0
    assert f"Error during time-based search: {error_message}" in result.output
    mock_analysis_engine_instance.search_logs.assert_called_once()


# --- Tests for 'search first' ---


def test_search_first_valid_count(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search first' with a valid count."""
    count = 5
    result = runner.invoke(cli, ["search", "first", "--count", str(count)])

    assert result.exit_code == 0
    mock_analysis_engine_instance.search_logs.assert_called_once()

    args, _ = mock_analysis_engine_instance.search_logs.call_args
    called_filter_criteria_dict = args[0]

    assert called_filter_criteria_dict.get("first_n") == count
    assert called_filter_criteria_dict.get("scope") == "default"

    assert f"Searching first {count} records" in result.output
    assert "mocked_log_line_1" in result.output


@pytest.mark.parametrize("invalid_count", ["0", "-1", "abc"])
def test_search_first_invalid_count(runner, mock_analysis_engine_class, mock_analysis_engine_instance, invalid_count):
    """Test 'search first' with invalid counts."""
    result = runner.invoke(cli, ["search", "first", "--count", invalid_count])

    if invalid_count.lstrip("-").isdigit() and int(invalid_count) <= 0:  # Handle negative numbers too
        assert "Error: --count must be a positive integer." in result.output
    else:  # handles non-integer case like 'abc'
        assert "Error: Invalid value for '--count'" in result.output  # Click's default error for type mismatch

    mock_analysis_engine_instance.search_logs.assert_not_called()


def test_search_first_engine_exception(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search first' when AnalysisEngine throws an exception."""
    error_message = "First engine exploded!"
    mock_analysis_engine_instance.search_logs.side_effect = Exception(error_message)

    result = runner.invoke(cli, ["search", "first", "--count", "3"])

    assert result.exit_code == 0
    assert f"Error during search for first N records: {error_message}" in result.output
    mock_analysis_engine_instance.search_logs.assert_called_once()


# --- Tests for 'search last' ---


def test_search_last_valid_count(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search last' with a valid count."""
    count = 7
    result = runner.invoke(cli, ["search", "last", "--count", str(count)])

    assert result.exit_code == 0
    mock_analysis_engine_instance.search_logs.assert_called_once()

    args, _ = mock_analysis_engine_instance.search_logs.call_args
    called_filter_criteria_dict = args[0]

    assert called_filter_criteria_dict.get("last_n") == count
    assert called_filter_criteria_dict.get("scope") == "default"

    assert f"Searching last {count} records" in result.output
    assert "mocked_log_line_1" in result.output


@pytest.mark.parametrize("invalid_count", ["0", "-1", "xyz"])
def test_search_last_invalid_count(runner, mock_analysis_engine_class, mock_analysis_engine_instance, invalid_count):
    """Test 'search last' with invalid counts."""
    result = runner.invoke(cli, ["search", "last", "--count", invalid_count])

    if invalid_count.lstrip("-").isdigit() and int(invalid_count) <= 0:  # Handle negative numbers too
        assert "Error: --count must be a positive integer." in result.output
    else:
        assert "Error: Invalid value for '--count'" in result.output  # Click's default error

    mock_analysis_engine_instance.search_logs.assert_not_called()


def test_search_last_engine_exception(runner, mock_analysis_engine_class, mock_analysis_engine_instance):
    """Test 'search last' when AnalysisEngine throws an exception."""
    error_message = "Last engine exploded!"
    mock_analysis_engine_instance.search_logs.side_effect = Exception(error_message)

    result = runner.invoke(cli, ["search", "last", "--count", "4"])

    assert result.exit_code == 0
    assert f"Error during search for last N records: {error_message}" in result.output
    mock_analysis_engine_instance.search_logs.assert_called_once()
