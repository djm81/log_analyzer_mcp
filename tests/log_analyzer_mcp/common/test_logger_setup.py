import logging
import os
import shutil
import sys
import tempfile
from unittest.mock import MagicMock, mock_open, patch

import pytest

from log_analyzer_mcp.common.logger_setup import (
    LOGS_BASE_DIR,
    PROJECT_ROOT,
    LoggerSetup,
    MessageFlowFormatter,
    find_project_root,
    get_logs_dir,
    setup_logger,
)
from logging import handlers


# Helper to reset LoggerSetup._active_loggers for test isolation
@pytest.fixture(autouse=True)
def reset_active_loggers():
    LoggerSetup.reset_loggers_for_testing()  # Use the new robust reset method
    yield
    LoggerSetup.reset_loggers_for_testing()  # Ensure clean state after each test


# --- Tests for find_project_root ---
def test_find_project_root_fallback(tmp_path):
    """Test find_project_root fallback when marker_file is not found."""
    # Ensure no pyproject.toml is found upwards from tmp_path
    # This test relies on the fallback logic calculating from __file__ of logger_setup.py
    # We can't easily mock the entire filesystem structure up to root for this specific test.
    # Instead, we'll check if it returns *a* path and doesn't crash.
    # A more robust test would involve creating a known deep structure without the marker.

    # For now, let's test the fallback by starting from a path where it won't find the marker
    # and ensure it returns a path based on the __file__ of the logger_setup module.
    # This part is tricky to test perfectly without a complex setup.
    # We can assert that it returns a path that is 3 levels up from logger_setup.py's location.

    module_spec = sys.modules["log_analyzer_mcp.common.logger_setup"]
    assert module_spec is not None, "Module spec should not be None"
    module_file = module_spec.__file__
    assert module_file is not None, "Module file path should not be None"
    logger_setup_file_path = os.path.abspath(module_file)
    expected_fallback_root = os.path.dirname(os.path.dirname(os.path.dirname(logger_setup_file_path)))

    # To simulate not finding it, we pass a non-existent marker and start path far from project
    # This forces it to go up to the filesystem root and trigger the fallback.
    # We need to be careful as the real PROJECT_ROOT might interfere.
    # Let's patch os.path.exists to simulate marker not being found
    with patch("os.path.exists", return_value=False) as mock_exists:
        # And patch abspath for the __file__ to be consistent if needed, though usually not.
        # Call from a deep, unrelated path
        unrelated_deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"
        unrelated_deep_path.mkdir(parents=True, exist_ok=True)

        # Use a marker that definitely won't exist to force fallback
        calculated_root = find_project_root(str(unrelated_deep_path), "THIS_MARKER_DOES_NOT_EXIST.txt")

        # The fallback is 3 levels up from the *actual* logger_setup.py file
        assert calculated_root == expected_fallback_root
        # Ensure os.path.exists was called multiple times during the upward search
        assert mock_exists.call_count > 1


# --- Tests for get_logs_dir ---
def test_get_logs_dir_exists(tmp_path):
    """Test get_logs_dir when the directory already exists."""
    # Use a temporary logs base dir for this test
    temp_logs_base = tmp_path / "test_logs"
    temp_logs_base.mkdir()
    with patch("log_analyzer_mcp.common.logger_setup.LOGS_BASE_DIR", str(temp_logs_base)):
        assert get_logs_dir() == str(temp_logs_base)
        assert temp_logs_base.exists()


def test_get_logs_dir_creates_if_not_exists(tmp_path):
    """Test get_logs_dir creates the directory if it doesn't exist."""
    temp_logs_base = tmp_path / "test_logs_new"
    with patch("log_analyzer_mcp.common.logger_setup.LOGS_BASE_DIR", str(temp_logs_base)):
        assert not temp_logs_base.exists()
        assert get_logs_dir() == str(temp_logs_base)
        assert temp_logs_base.exists()


@patch("os.makedirs")
def test_get_logs_dir_os_error_on_create(mock_makedirs, tmp_path, capsys):
    """Test get_logs_dir when os.makedirs raises an OSError."""
    mock_makedirs.side_effect = OSError("Test OS error")
    temp_logs_base = tmp_path / "test_logs_error"
    with patch("log_analyzer_mcp.common.logger_setup.LOGS_BASE_DIR", str(temp_logs_base)):
        assert get_logs_dir() == str(temp_logs_base)  # Should still return the path
        # Check stderr for the warning
        captured = capsys.readouterr()
        assert f"Warning: Could not create base logs directory {str(temp_logs_base)}" in captured.err


# --- Tests for MessageFlowFormatter ---
@pytest.fixture
def mock_log_record():
    record = MagicMock(spec=logging.LogRecord)
    record.getMessage = MagicMock(return_value="A normal log message")
    record.levelno = logging.INFO
    record.levelname = "INFO"
    record.created = 1678886400  # A fixed time
    record.msecs = 123
    record.name = "TestLogger"
    record.args = ()  # Ensure args is an empty tuple
    record.exc_info = None  # Add exc_info attribute
    record.exc_text = None  # Add exc_text attribute
    record.stack_info = None  # Add stack_info attribute
    return record


def test_message_flow_formatter_standard_message(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent")
    formatted = formatter.format(mock_log_record)
    assert "TestAgent |" in formatted
    assert "| A normal log message" in formatted


def test_message_flow_formatter_with_session_id(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent", session_id="sess123")
    mock_log_record.getMessage.return_value = "Another message"
    formatted = formatter.format(mock_log_record)
    assert "TestAgent |" in formatted
    assert "| sess123 |" in formatted
    assert "| Another message" in formatted


def test_message_flow_formatter_flow_pattern(mock_log_record):
    formatter = MessageFlowFormatter("ReceiverAgent", session_id="s456")
    mock_log_record.getMessage.return_value = "SenderAgent => ReceiverAgent | Flow details here"
    formatted = formatter.format(mock_log_record)
    # Receiver | Timestamp | SessionID | Sender => Receiver | Message
    assert "ReceiverAgent |" in formatted  # Receiver is the first part
    assert "| s456 |" in formatted  # Session ID
    assert "| SenderAgent => ReceiverAgent | Flow details here" in formatted  # The original flow part
    assert "ReceiverAgent => ReceiverAgent" not in formatted  # Ensure agent_name not misused


def test_message_flow_formatter_already_formatted(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent")
    # Simulate an already formatted message (e.g., from a different handler)
    already_formatted_msg = "2023-03-15 10:00:00,123 - TestAgent - INFO - Already done"
    mock_log_record.getMessage.return_value = already_formatted_msg
    formatted = formatter.format(mock_log_record)
    assert formatted == already_formatted_msg

    already_formatted_flow_msg = "OtherAgent | 2023-03-15 10:00:00,123 | SomeSender => OtherAgent | Done this way"
    mock_log_record.getMessage.return_value = already_formatted_flow_msg
    formatted = formatter.format(mock_log_record)
    assert formatted == already_formatted_flow_msg


def test_message_flow_formatter_test_summary(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent")
    test_summary_msg = "Test Summary: 5 passed, 0 failed"
    mock_log_record.getMessage.return_value = test_summary_msg
    formatted = formatter.format(mock_log_record)
    assert formatted == test_summary_msg  # Should be returned as-is

    pytest_output_msg = "============================= test session starts =============================="
    mock_log_record.getMessage.return_value = pytest_output_msg
    formatted = formatter.format(mock_log_record)
    assert formatted == pytest_output_msg  # Should also be returned as-is


def test_message_flow_formatter_multiline(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent", session_id="multi789")
    multiline_msg = "First line\nSecond line\nThird line"
    mock_log_record.getMessage.return_value = multiline_msg
    formatted = formatter.format(mock_log_record)
    lines = formatted.split("\n")
    assert len(lines) == 3
    assert "TestAgent |" in lines[0]
    assert "| multi789 |" in lines[0]
    assert "| First line" in lines[0]
    assert lines[1] == "Second line"
    assert lines[2] == "Third line"


def test_message_flow_formatter_no_preserve_newlines(mock_log_record):
    formatter = MessageFlowFormatter("TestAgent", preserve_newlines=False)
    # Use an actual newline character in the message, not a literal '\\n' string
    multiline_msg = "First line\nSecond line"
    mock_log_record.getMessage.return_value = multiline_msg
    formatted = formatter.format(mock_log_record)
    # When not preserving, it should format the whole thing as one line (newlines replaced by \n in record.msg)
    # The format method does `record.msg = formatted_message` then `super().format(record)` would be called.
    # Our current implementation returns the formatted string directly, so it won't go to super().format.
    # It handles multiline splitting itself. If preserve_newlines is false, it just formats original_message
    # as a single line.
    assert "\\n" not in formatted  # The formatted output string should not contain raw newlines
    assert "TestAgent |" in formatted
    # The expected behavior now is that newlines are removed and the message is on a single line.
    assert "| First line Second line" in formatted  # Adjusted expectation: newlines replaced by space


# --- Tests for LoggerSetup ---
@pytest.fixture
def temp_log_file(tmp_path):
    log_file = tmp_path / "test.log"
    yield str(log_file)
    if log_file.exists():
        log_file.unlink()


def test_logger_setup_create_logger_basic(temp_log_file):
    logger = LoggerSetup.create_logger("MyLogger", log_file=temp_log_file, agent_name="MyAgent")
    assert logger.name == "MyLogger"
    assert logger.level == logging.INFO  # Default
    assert len(logger.handlers) == 2  # Console and File
    assert isinstance(logger.handlers[0], logging.StreamHandler)  # Console
    assert isinstance(logger.handlers[1], handlers.RotatingFileHandler)  # File

    # Check if formatter is MessageFlowFormatter
    for handler in logger.handlers:
        assert isinstance(handler.formatter, MessageFlowFormatter)
        if isinstance(handler, logging.FileHandler):  # Check path of file handler
            assert handler.baseFilename == temp_log_file

    # Check if it's stored
    assert LoggerSetup.get_logger("MyLogger") is logger


def test_logger_setup_create_logger_levels(temp_log_file):
    logger_debug = LoggerSetup.create_logger("DebugLogger", log_file=temp_log_file, log_level="DEBUG")
    assert logger_debug.level == logging.DEBUG
    for handler in logger_debug.handlers:
        assert handler.level == logging.DEBUG

    logger_warning = LoggerSetup.create_logger("WarnLogger", log_file=temp_log_file, log_level="WARNING")
    assert logger_warning.level == logging.WARNING


def test_logger_setup_create_logger_no_file():
    logger = LoggerSetup.create_logger("NoFileLogger")
    assert len(logger.handlers) == 1  # Only console
    assert isinstance(logger.handlers[0], logging.StreamHandler)


def test_logger_setup_create_logger_agent_name(temp_log_file):
    logger = LoggerSetup.create_logger("AgentLoggerTest", log_file=temp_log_file, agent_name="SpecificAgent")
    console_formatter = logger.handlers[0].formatter
    assert isinstance(console_formatter, MessageFlowFormatter)
    assert console_formatter.agent_name == "SpecificAgent"

    # Test default agent_name derivation
    logger_default_agent = LoggerSetup.create_logger("MyAgentLogger", log_file=temp_log_file)
    default_agent_formatter = logger_default_agent.handlers[0].formatter
    assert isinstance(default_agent_formatter, MessageFlowFormatter)
    assert default_agent_formatter.agent_name == "my_agent"  # MyAgentLogger -> my_agent

    logger_simple_name = LoggerSetup.create_logger("MyLogger", log_file=temp_log_file)
    simple_name_formatter = logger_simple_name.handlers[0].formatter
    assert isinstance(simple_name_formatter, MessageFlowFormatter)
    assert simple_name_formatter.agent_name == "my_agent"  # MyLogger -> my_agent

    logger_just_agent = LoggerSetup.create_logger("Agent", log_file=temp_log_file)
    just_agent_formatter = logger_just_agent.handlers[0].formatter
    assert isinstance(just_agent_formatter, MessageFlowFormatter)
    assert just_agent_formatter.agent_name == "default_agent"  # Agent -> default_agent

    logger_empty_derivation = LoggerSetup.create_logger("AgentLogger", log_file=temp_log_file)
    empty_deriv_formatter = logger_empty_derivation.handlers[0].formatter
    assert isinstance(empty_deriv_formatter, MessageFlowFormatter)
    assert empty_deriv_formatter.agent_name == "default_agent"  # AgentLogger -> default_agent


def test_logger_setup_create_logger_session_id(temp_log_file):
    logger = LoggerSetup.create_logger("SessionLogger", log_file=temp_log_file, session_id="sessABC")
    formatter = logger.handlers[0].formatter
    assert isinstance(formatter, MessageFlowFormatter)
    assert formatter.session_id == "sessABC"


def test_logger_setup_create_logger_no_rotating_file(temp_log_file):
    logger = LoggerSetup.create_logger("SimpleFileLogger", log_file=temp_log_file, use_rotating_file=False)
    assert isinstance(logger.handlers[1], logging.FileHandler)
    assert not isinstance(logger.handlers[1], handlers.RotatingFileHandler)


def test_logger_setup_create_logger_overwrite_mode(tmp_path):
    log_file_overwrite = tmp_path / "overwrite.log"
    log_file_overwrite.write_text("Previous content\n")

    # Create logger in append mode (default)
    logger_append = LoggerSetup.create_logger("AppendLogger", log_file=str(log_file_overwrite), use_rotating_file=False)
    logger_append.warning("Append test")
    LoggerSetup.flush_logger("AppendLogger")  # Ensure written

    # Create logger in overwrite mode, ensure non-rotating for this specific test of 'w' mode.
    logger_overwrite = LoggerSetup.create_logger(
        "OverwriteLogger",
        log_file=str(log_file_overwrite),
        append_mode=False,
        use_rotating_file=False,  # Use simple FileHandler to test 'w' mode directly
    )
    logger_overwrite.error("Overwrite test")
    LoggerSetup.flush_logger("OverwriteLogger")  # Ensure written

    content = log_file_overwrite.read_text()
    assert "Previous content" not in content
    assert "Append test" not in content
    assert "Overwrite test" in content
    assert "overwrite_agent |" in content  # agent name will be derived


def test_logger_setup_create_logger_preserve_test_format(temp_log_file, mock_log_record):
    logger = LoggerSetup.create_logger("TestFormatLogger", log_file=temp_log_file, preserve_test_format=True)

    file_handler = logger.handlers[1]  # File handler
    assert isinstance(file_handler.formatter, logging.Formatter)  # Plain Formatter
    assert not isinstance(file_handler.formatter, MessageFlowFormatter)

    # Console handler should use standard Formatter when preserve_test_format is True
    console_handler = logger.handlers[0]
    assert isinstance(console_handler.formatter, logging.Formatter)
    assert not isinstance(
        console_handler.formatter, MessageFlowFormatter
    )  # Explicitly check it's NOT MessageFlowFormatter

    # Test logging a test summary line
    test_summary_msg = "Test Summary: 1 passed"
    mock_log_record.getMessage.return_value = test_summary_msg

    # File handler with simple formatter should just output the message
    formatted_file = file_handler.formatter.format(mock_log_record)
    assert formatted_file == test_summary_msg

    # Console handler (standard Formatter) when preserve_test_format=True
    # should output using LEGACY_LOG_FORMAT.
    console_handler_formatter = console_handler.formatter
    expected_console_output = console_handler_formatter.format(mock_log_record)  # Format with the actual formatter
    formatted_console = console_handler.formatter.format(mock_log_record)
    assert formatted_console == expected_console_output
    assert "Test Summary: 1 passed" in formatted_console  # Check if the message is part of it
    assert mock_log_record.name in formatted_console  # e.g. TestLogger
    assert mock_log_record.levelname in formatted_console  # e.g. INFO


@patch("os.makedirs")
def test_logger_setup_create_logger_log_dir_creation_failure(mock_makedirs, tmp_path, capsys):
    mock_makedirs.side_effect = OSError("Cannot create dir")
    # Use a log file path that would require directory creation
    log_file_in_new_dir = tmp_path / "new_log_subdir" / "error.log"

    logger = LoggerSetup.create_logger("ErrorDirLogger", log_file=str(log_file_in_new_dir))

    # Should have only console handler if file dir creation failed
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)

    captured = capsys.readouterr()
    expected_dir = str(tmp_path / "new_log_subdir")
    assert f"ERROR: Could not create log directory {expected_dir}" in captured.err
    assert mock_makedirs.call_count == 1  # Should have attempted to create it


def test_logger_setup_clear_handlers_on_recreate(temp_log_file):
    logger1 = LoggerSetup.create_logger("RecreateTest", log_file=temp_log_file)
    assert len(logger1.handlers) == 2

    # Get the actual underlying logger instance
    underlying_logger = logging.getLogger("RecreateTest")
    assert len(underlying_logger.handlers) == 2

    logger2 = LoggerSetup.create_logger("RecreateTest", log_file=temp_log_file, log_level="DEBUG")
    assert logger2 is logger1  # Should be the same logger object
    assert len(logger2.handlers) == 2  # Handlers should be replaced, not added
    assert len(underlying_logger.handlers) == 2


def test_logger_setup_flush_logger(temp_log_file):
    logger = LoggerSetup.create_logger("FlushTest", log_file=temp_log_file)
    mock_handler = MagicMock(spec=logging.Handler)
    mock_handler.flush = MagicMock()

    # Replace handlers for testing flush
    original_handlers = list(logger.handlers)  # Keep a copy
    logger.handlers = [mock_handler]

    assert LoggerSetup.flush_logger("FlushTest") is True
    mock_handler.flush.assert_called_once()

    logger.handlers = original_handlers  # Restore original handlers
    # Ensure original handlers are closed if they were file handlers, to avoid ResourceWarning
    for handler in original_handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()

    assert LoggerSetup.flush_logger("NonExistentLogger") is False


def test_logger_setup_flush_all_loggers(temp_log_file):
    logger_a = LoggerSetup.create_logger("FlushAllA", log_file=temp_log_file)
    logger_b = LoggerSetup.create_logger("FlushAllB", log_file=None)  # Console only

    # Before replacing logger_a's handlers with mocks, clear its existing (real) handlers
    # to ensure its file handler is properly closed.
    LoggerSetup._clear_and_close_handlers(logger_a)

    mock_handler_a_file = MagicMock(spec=logging.FileHandler)
    mock_handler_a_file.flush = MagicMock()
    mock_handler_a_console = MagicMock(spec=logging.StreamHandler)
    mock_handler_a_console.flush = MagicMock()
    # Simulate stream attribute for StreamHandler mocks if _clear_and_close_handlers might access it
    # However, the refined _clear_and_close_handlers uses getattr(handler, 'stream', None)
    # so this might not be strictly necessary unless we want to test specific stream interactions.
    # mock_handler_a_console.stream = sys.stdout
    # Ensure logger_a uses these mocked handlers
    logger_a.handlers = [mock_handler_a_console, mock_handler_a_file]

    mock_handler_b_console = MagicMock(spec=logging.StreamHandler)
    mock_handler_b_console.flush = MagicMock()
    # mock_handler_b_console.stream = sys.stdout
    logger_b.handlers = [mock_handler_b_console]

    LoggerSetup.flush_all_loggers()

    mock_handler_a_file.flush.assert_called_once()
    mock_handler_a_console.flush.assert_called_once()
    mock_handler_b_console.flush.assert_called_once()

    # Clean up / close handlers to avoid ResourceWarning
    # This is a bit tricky because flush_all_loggers doesn't return the loggers
    # We rely on the autouse fixture to clear _active_loggers, which should lead to
    # handlers being closed eventually if create_logger handles it well on re-creation.
    # For more direct control in this specific test, we would need to access
    # LoggerSetup._active_loggers, which is an internal detail.
    # However, the fix in create_logger to close handlers should mitigate this.
    # The new reset_loggers_for_testing in the autouse fixture should handle this.
    # LoggerSetup._active_loggers.clear() # No longer needed here due to autouse fixture


def test_logger_setup_write_test_summary(temp_log_file):
    logger = LoggerSetup.create_logger("TestSummaryLogger", log_file=temp_log_file, preserve_test_format=True)

    # Mock the file handler to capture output
    mock_file_handler_write = mock_open()

    # Find the file handler and patch its write method
    original_file_handler = None
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler):
            original_file_handler = handler
            break

    if original_file_handler:
        # To capture output from file handler, we can check the file content
        # or mock its stream's write method. Checking file content is more robust.
        log_file_path = original_file_handler.baseFilename
    else:
        pytest.fail("File handler not found on TestSummaryLogger")

    summary_data = {
        "passed": 5,
        "failed": 2,
        "skipped": 1,
        "duration": 1.234,
        "failed_tests": ["test_one", "test_two"],  # This structure might differ from actual use
        "failed_modules": {"moduleA": ["test_one_a"], "moduleB": ["test_two_b"]},
    }
    LoggerSetup.write_test_summary(logger, summary_data)

    LoggerSetup.flush_logger("TestSummaryLogger")  # Ensure all written to file

    # Read the log file content
    with open(log_file_path, "r") as f:
        log_content = f.read()

    assert "=============== test session starts ===============" in log_content
    assert "5 passed, 2 failed, 1 skipped in 1.23s" in log_content
    assert "Test Summary: 5 passed, 2 failed, 1 skipped" in log_content
    assert "Status: FAILED" in log_content
    assert "Duration: 1.23 seconds" in log_content
    assert "Failed tests by module:" in log_content
    assert "Module: moduleA - 1 failed tests" in log_content
    assert "- test_one_a" in log_content
    assert "Module: moduleB - 1 failed tests" in log_content
    assert "- test_two_b" in log_content
    assert "==================================================" in log_content


# --- Tests for setup_logger (convenience function) ---
def test_setup_logger_convenience_function(temp_log_file):
    with patch.object(LoggerSetup, "create_logger", wraps=LoggerSetup.create_logger) as mock_create_logger:
        logger = setup_logger(
            "ConvenienceAgent", log_level="DEBUG", session_id="conv123", log_file=temp_log_file, use_rotating_file=False
        )

        mock_create_logger.assert_called_once_with(
            "ConvenienceAgent",  # name
            log_file=temp_log_file,
            agent_name="ConvenienceAgent",  # agent_name also from first arg
            log_level="DEBUG",
            session_id="conv123",
            use_rotating_file=False,
            # append_mode and preserve_test_format use defaults from create_logger
        )
        assert logger.name == "ConvenienceAgent"
        assert logger.level == logging.DEBUG


# Test PROJECT_ROOT and LOGS_BASE_DIR for basic correctness
def test_project_root_and_logs_base_dir_paths():
    # PROJECT_ROOT should be a valid directory
    assert os.path.isdir(PROJECT_ROOT), f"PROJECT_ROOT is not a valid directory: {PROJECT_ROOT}"
    # pyproject.toml should exist in PROJECT_ROOT
    assert os.path.exists(os.path.join(PROJECT_ROOT, "pyproject.toml")), "pyproject.toml not found in PROJECT_ROOT"

    # LOGS_BASE_DIR should also be valid or creatable
    assert os.path.isdir(LOGS_BASE_DIR) or not os.path.exists(
        LOGS_BASE_DIR
    ), f"LOGS_BASE_DIR is not valid or creatable: {LOGS_BASE_DIR}"
    # LOGS_BASE_DIR should be under PROJECT_ROOT
    assert LOGS_BASE_DIR.startswith(PROJECT_ROOT), "LOGS_BASE_DIR is not under PROJECT_ROOT"

    # Test get_logs_dir() directly too
    retrieved_logs_dir = get_logs_dir()
    assert os.path.isdir(retrieved_logs_dir)
    assert retrieved_logs_dir == LOGS_BASE_DIR


# --- Tests for find_project_root ---
def test_find_project_root_finds_marker(tmp_path):
    """Test find_project_root when pyproject.toml exists."""
    marker_file = "pyproject.toml"
    # Create
