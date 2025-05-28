"""
Logging utility for standardized log setup across all agents
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Literal, Optional

# Explicitly attempt to initialize coverage for subprocesses
# if "COVERAGE_PROCESS_START" in os.environ:
#     try:
#         import coverage
#
#         coverage.process_startup()
#     except Exception:  # nosec B110 # pylint: disable=broad-exception-caught
#         pass  # Or handle error if coverage is mandatory

# Determine the project root directory from the location of this script
# Expected structure: /project_root/src/log_analyzer_mcp/common/logger_setup.py
# _common_dir = os.path.dirname(os.path.abspath(__file__))
# _log_analyzer_mcp_dir = os.path.dirname(_common_dir)
# _src_dir = os.path.dirname(_log_analyzer_mcp_dir)
# PROJECT_ROOT = os.path.dirname(_src_dir) # Old method


def find_project_root(start_path: str, marker_file: str = "pyproject.toml") -> str:
    """Searches upwards from start_path for a directory containing marker_file."""
    current_path = os.path.abspath(start_path)
    while True:
        if os.path.exists(os.path.join(current_path, marker_file)):
            return current_path
        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:  # Reached filesystem root
            # Fallback to a less reliable method if pyproject.toml not found
            # This could happen if script is run from outside a typical project structure
            # Default to 3 levels up from current file, similar to old logic but from __file__ directly
            fallback_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            sys.stderr.write(f"Warning: '{marker_file}' not found. Falling back to project root: {fallback_root}\n")
            return fallback_root
        current_path = parent_path


PROJECT_ROOT = find_project_root(os.path.abspath(__file__))

# Define the base logs directory at the project root
LOGS_BASE_DIR = os.path.join(PROJECT_ROOT, "logs")


def get_logs_dir() -> str:
    """Returns the absolute path to the base logs directory for the project."""
    # Ensure the base logs directory exists
    if not os.path.exists(LOGS_BASE_DIR):
        try:
            os.makedirs(LOGS_BASE_DIR, exist_ok=True)
        except OSError as e:
            # Fallback or error if cannot create logs dir, though basic logging might still work to console
            sys.stderr.write(f"Warning: Could not create base logs directory {LOGS_BASE_DIR}: {e}\n")
            # As a last resort, can try to use a local logs dir if in a restricted env
            # For now, we assume it can be created or will be handled by calling code.
    return LOGS_BASE_DIR


class MessageFlowFormatter(logging.Formatter):
    """
    Custom formatter that recognizes message flow patterns and formats them accordingly
    """

    # Pattern to match "sender => receiver | message" format
    FLOW_PATTERN = re.compile(r"^(\w+) => (\w+) \| (.*)$")

    # Pattern to match already formatted messages (both standard and flow formats)
    # This includes timestamp pattern \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}
    # and agent | timestamp format
    ALREADY_FORMATTED_PATTERN = re.compile(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}|^\w+ \| \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})"
    )

    def __init__(
        self,
        agent_name: str,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        style: Literal["%", "{", "$"] = "%",
        session_id: Optional[str] = None,
        preserve_newlines: bool = True,
    ):
        """
        Initialize the formatter with the agent name

        Args:
            agent_name: Name of the agent (used when no flow information is in the message)
            fmt: Format string
            datefmt: Date format string
            style: Style of format string
            session_id: Optional unique session ID to include in log messages
            preserve_newlines: Whether to preserve newlines in the original message
        """
        super().__init__(fmt, datefmt, style)
        self.agent_name = agent_name
        self.session_id = session_id
        self.preserve_newlines = preserve_newlines

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record according to message flow patterns

        Args:
            record: The log record to format

        Returns:
            Formatted log string
        """
        # Extract the message
        original_message = record.getMessage()

        # Special case for test summary format (always preserve exact format)
        if "Test Summary:" in original_message or "===" in original_message:
            # Special case for test analyzer compatibility - don't prepend anything
            return original_message

        # Guard against already formatted messages to prevent recursive formatting
        # Check for timestamp pattern to identify already formatted messages
        if self.ALREADY_FORMATTED_PATTERN.search(original_message):
            # Log message is already formatted, return as is
            return original_message

        # Check if this is a message flow log
        flow_match = self.FLOW_PATTERN.match(original_message)
        if flow_match:
            sender, receiver, message = flow_match.groups()

            # Format the timestamp
            timestamp = self.formatTime(record, self.datefmt)

            # Format the message with flow information and session ID if available
            if self.session_id:
                formatted_message = f"{receiver} | {timestamp} | {self.session_id} | {sender} => {receiver} | {message}"
            else:
                formatted_message = f"{receiver} | {timestamp} | {sender} => {receiver} | {message}"

            # Override the message in the record
            record.msg = formatted_message
            record.args = ()

            # Return the formatted message directly
            return formatted_message
        else:
            # Standard formatting for non-flow messages
            timestamp = self.formatTime(record, self.datefmt)

            # Handle multiline messages
            if self.preserve_newlines and "\n" in original_message:
                lines = original_message.split("\n")
                # Format the first line with the timestamp
                if self.session_id:
                    first_line = f"{self.agent_name} | {timestamp} | {self.session_id} | {lines[0]}"
                else:
                    first_line = f"{self.agent_name} | {timestamp} | {lines[0]}"

                # Return the first line and the rest as is
                return first_line + "\n" + "\n".join(lines[1:])
            else:
                # Regular single-line message
                if self.session_id:
                    formatted_message = f"{self.agent_name} | {timestamp} | {self.session_id} | {original_message}"
                else:
                    formatted_message = f"{self.agent_name} | {timestamp} | {original_message}"

                # Override the message in the record
                record.msg = formatted_message
                record.args = ()

                # Return the formatted message
                return formatted_message


class LoggerSetup:
    """
    Utility class for standardized logging setup across all agents
    """

    # Keep the old format for backward compatibility
    LEGACY_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    DEFAULT_LOG_LEVEL = "INFO"

    # Store active loggers for management
    _active_loggers: Dict[str, logging.Logger] = {}

    @classmethod
    def get_logger(cls, name: str) -> Optional[logging.Logger]:
        """Retrieve an existing logger by name if it has been created."""
        return cls._active_loggers.get(name)

    @classmethod
    def create_logger(
        cls,
        name: str,
        log_file: Optional[str] = None,
        agent_name: Optional[str] = None,
        log_level: Optional[str] = None,
        session_id: Optional[str] = None,
        use_rotating_file: bool = True,
        append_mode: bool = True,
        preserve_test_format: bool = False,
    ) -> logging.Logger:
        """
        Creates and configures a logger with the given name

        Args:
            name: Name of the logger
            log_file: Optional file path for file logging. If just a filename is provided, it will be created in the centralized logs directory
            agent_name: Optional agent name for message flow formatting (defaults to name)
            log_level: Optional log level (defaults to environment variable or INFO)
            session_id: Optional unique session ID to include in all log messages
            use_rotating_file: Whether to use RotatingFileHandler (True) or simple FileHandler (False)
            append_mode: Whether to append to existing log file (True) or overwrite (False)
            preserve_test_format: Whether to preserve exact format of test-related messages

        Returns:
            Configured logger instance
        """
        # Get log level from parameter, environment, or use default
        log_level_str = log_level or os.getenv("LOG_LEVEL", cls.DEFAULT_LOG_LEVEL)
        log_level_str = log_level_str.upper()
        log_level_num = getattr(logging, log_level_str, logging.INFO)

        # Use agent_name if provided, otherwise use the logger name
        actual_agent_name = agent_name or name.lower().replace("agent", "_agent")

        # Create or get existing logger
        logger = logging.getLogger(name)
        logger.setLevel(log_level_num)

        # Disable propagation to root logger to prevent duplicate logs
        logger.propagate = False

        # Clear existing handlers to avoid duplicates
        if logger.handlers:
            # Properly close file handlers before clearing
            for handler in logger.handlers:
                # Force flush before closing
                handler.flush()
                # Close the handler, which will close any files
                handler.close()
            logger.handlers.clear()

        # Create custom formatter
        preserve_newlines = not preserve_test_format  # Don't preserve newlines for test output
        message_flow_formatter = MessageFlowFormatter(
            actual_agent_name, session_id=session_id, preserve_newlines=preserve_newlines
        )

        # Special formatter for test output that preserves test format
        test_formatter = logging.Formatter("%(message)s") if preserve_test_format else message_flow_formatter

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level_num)
        console_handler.setFormatter(message_flow_formatter)
        logger.addHandler(console_handler)

        # Create file handler if log_file is provided
        if log_file:
            actual_log_file_path = ""
            if os.path.isabs(log_file):
                actual_log_file_path = log_file  # Trust absolute path
            else:
                # It's a relative path or just a filename, place it in get_logs_dir()
                logs_dir = get_logs_dir()  # This uses the (potentially still imperfect) PROJECT_ROOT
                actual_log_file_path = os.path.join(logs_dir, log_file)

            # Ensure the directory for the final log file exists
            log_file_dir = os.path.dirname(actual_log_file_path)
            if log_file_dir and not os.path.exists(log_file_dir):
                try:
                    os.makedirs(log_file_dir, exist_ok=True)
                except OSError as e:
                    # Log to stderr if we can't create the dir, as the file handler will likely fail
                    sys.stderr.write(f"ERROR: Could not create log directory {log_file_dir}: {e}\n")
                    # Return logger without file handler if dir creation fails
                    cls._active_loggers[name] = logger
                    return logger

            # This logger.info will use the console handler to state where it *intends* to write for the file handler.
            logger.info("File logging configured for: %s", actual_log_file_path)

            # Choose the appropriate file handler based on use_rotating_file
            file_mode = "a" if append_mode else "w"
            if use_rotating_file:
                file_handler = RotatingFileHandler(
                    actual_log_file_path, maxBytes=10 * 1024 * 1024, backupCount=5, mode=file_mode  # 10MB
                )
            else:
                # Use simple FileHandler for test scenarios
                file_handler = logging.FileHandler(actual_log_file_path, mode=file_mode)

            file_handler.setLevel(log_level_num)
            file_handler.setFormatter(test_formatter if preserve_test_format else message_flow_formatter)
            logger.addHandler(file_handler)

        # Store the logger in active loggers dictionary
        cls._active_loggers[name] = logger

        return logger

    @classmethod
    def flush_all_loggers(cls) -> None:
        """
        Flush all active loggers to ensure their output is written
        """
        for logger_name, logger in cls._active_loggers.items():
            for handler in logger.handlers:
                handler.flush()

    @classmethod
    def flush_logger(cls, name: str) -> bool:
        """
        Flush a specific logger by name

        Args:
            name: Name of the logger to flush

        Returns:
            True if logger was found and flushed, False otherwise
        """
        if name in cls._active_loggers:
            logger = cls._active_loggers[name]
            for handler in logger.handlers:
                handler.flush()
            return True
        return False

    @classmethod
    def write_test_summary(cls, logger: logging.Logger, summary: Dict[str, Any]) -> None:
        """
        Write test summary in a format that log_analyzer.py can understand

        Args:
            logger: The logger to use
            summary: Dictionary with test summary information
        """
        # Flush any pending logs
        for handler in logger.handlers:
            handler.flush()

        # Log summary in a format compatible with log_analyzer.py
        logger.info("=" * 15 + " test session starts " + "=" * 15)

        # Log test result counts
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        duration = summary.get("duration", 0)

        logger.info(f"{passed} passed, {failed} failed, {skipped} skipped in {duration:.2f}s")
        logger.info(f"Test Summary: {passed} passed, {failed} failed, {skipped} skipped")
        logger.info(f"Status: {'PASSED' if failed == 0 else 'FAILED'}")
        logger.info(f"Duration: {duration:.2f} seconds")

        # Log failed tests if any
        if "failed_tests" in summary and summary["failed_tests"]:
            logger.info("Failed tests by module:")
            for module, tests in summary.get("failed_modules", {}).items():
                logger.info(f"Module: {module} - {len(tests)} failed tests")
                for test in tests:
                    logger.info(f"- {test}")

        logger.info("=" * 50)

        # Ensure everything is written
        for handler in logger.handlers:
            handler.flush()


def setup_logger(
    agent_name: str,
    log_level: str = "INFO",
    session_id: Optional[str] = None,
    log_file: Optional[str] = None,
    use_rotating_file: bool = True,
) -> logging.Logger:
    """
    Set up a logger with the given name and log level

    Args:
        agent_name: Name of the agent
        log_level: Log level (default: INFO)
        session_id: Optional unique session ID to include in all log messages
        log_file: Optional file path for logging
        use_rotating_file: Whether to use rotating file handler (default: True)

    Returns:
        Configured logger
    """
    # Use the LoggerSetup class for consistent logging setup
    return LoggerSetup.create_logger(
        agent_name,
        log_file=log_file,
        agent_name=agent_name,
        log_level=log_level,
        session_id=session_id,
        use_rotating_file=use_rotating_file,
    )
