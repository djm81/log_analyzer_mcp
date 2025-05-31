# src/log_analyzer_client/cli.py
import json
import logging
import sys
from typing import Callable, Optional

import click

from log_analyzer_mcp.common.utils import build_filter_criteria

# Assuming AnalysisEngine will be accessible; adjust import path as needed
# This might require log_analyzer_mcp to be installed or PYTHONPATH to be set up correctly
# For development, if log_analyzer_mcp and log_analyzer_client are part of the same top-level src structure:
from log_analyzer_mcp.core.analysis_engine import AnalysisEngine

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


# Create a simple logger for the CLI
# This logger will output to stdout by default.
# More sophisticated logging (e.g., to a file, configurable levels) can be added later if needed.
def get_cli_logger() -> logging.Logger:
    logger = logging.getLogger("LogAnalyzerCLI")
    if not logger.handlers:  # Avoid adding multiple handlers if re-invoked (e.g. in tests)
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter("[%(levelname)s] %(message)s")  # Simple format
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)  # Default level, can be made configurable
    return logger


# Global instance of AnalysisEngine for the CLI
# The CLI can optionally take a path to a custom .env file.
@click.group(context_settings=CONTEXT_SETTINGS)
@click.option(
    "--env-file", type=click.Path(exists=True, dir_okay=False), help="Path to a custom .env file for configuration."
)
@click.pass_context
def cli(ctx: click.Context, env_file: Optional[str]) -> None:
    """Log Analyzer CLI - A tool to search and filter log files."""
    ctx.ensure_object(dict)
    cli_logger = get_cli_logger()  # Get logger instance
    # Initialize AnalysisEngine with the specified .env file or default
    ctx.obj["analysis_engine"] = AnalysisEngine(logger_instance=cli_logger, env_file_path=env_file)
    if env_file:
        click.echo(f"Using custom .env file: {env_file}")


@cli.group("search")
def search() -> None:
    """Search log files with different criteria."""
    pass


# Common options for search commands
def common_search_options(func: Callable) -> Callable:
    func = click.option(
        "--scope", default="default", show_default=True, help="Logging scope to search within (from .env or default)."
    )(func)
    func = click.option(
        "--before",
        "context_before",
        type=int,
        default=2,
        show_default=True,
        help="Number of context lines before a match.",
    )(func)
    func = click.option(
        "--after",
        "context_after",
        type=int,
        default=2,
        show_default=True,
        help="Number of context lines after a match.",
    )(func)
    func = click.option(
        "--log-dirs",
        "log_dirs_override",
        type=str,
        default=None,
        help="Comma-separated list of log directories, files, or glob patterns to search (overrides .env for file locations).",
    )(func)
    func = click.option(
        "--log-patterns",
        "log_content_patterns_override",
        type=str,
        default=None,
        help="Comma-separated list of REGEX patterns to filter log messages (overrides .env content filters).",
    )(func)
    return func


@search.command("all")
@common_search_options
@click.pass_context
def search_all(
    ctx: click.Context,
    scope: str,
    context_before: int,
    context_after: int,
    log_dirs_override: Optional[str],
    log_content_patterns_override: Optional[str],
) -> None:
    """Search for all log records matching configured patterns."""
    engine: AnalysisEngine = ctx.obj["analysis_engine"]
    click.echo(f"Searching all records in scope: {scope}, context: {context_before}B/{context_after}A")

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
        results = engine.search_logs(filter_criteria)
        click.echo(json.dumps(results, indent=2, default=str))  # Use default=str for datetime etc.
    except Exception as e:  # pylint: disable=broad-exception-caught
        click.echo(f"Error during search: {e}", err=True)


@search.command("time")
@click.option("--minutes", type=int, default=0, show_default=True, help="Search logs from the last N minutes.")
@click.option("--hours", type=int, default=0, show_default=True, help="Search logs from the last N hours.")
@click.option("--days", type=int, default=0, show_default=True, help="Search logs from the last N days.")
@common_search_options
@click.pass_context
def search_time(
    ctx: click.Context,
    minutes: int,
    hours: int,
    days: int,
    scope: str,
    context_before: int,
    context_after: int,
    log_dirs_override: Optional[str],
    log_content_patterns_override: Optional[str],
) -> None:
    """Search logs within a specified time window."""
    engine: AnalysisEngine = ctx.obj["analysis_engine"]

    active_time_options = sum(1 for x in [minutes, hours, days] if x > 0)
    if active_time_options == 0:
        click.echo("Error: Please specify at least one of --minutes, --hours, or --days greater than zero.", err=True)
        return
    # AnalysisEngine handles preference if multiple are set, but good to inform user.
    if active_time_options > 1:
        click.echo("Warning: Multiple time units (minutes, hours, days) specified. Engine will prioritize.", err=True)

    click.echo(
        f"Searching time-based records: {days}d {hours}h {minutes}m in scope: {scope}, context: {context_before}B/{context_after}A"
    )
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
        results = engine.search_logs(filter_criteria)
        click.echo(json.dumps(results, indent=2, default=str))
    except Exception as e:  # pylint: disable=broad-exception-caught
        click.echo(f"Error during time-based search: {e}", err=True)


@search.command("first")
@click.option("--count", type=int, required=True, help="Number of first (oldest) matching records to return.")
@common_search_options
@click.pass_context
def search_first(
    ctx: click.Context,
    count: int,
    scope: str,
    context_before: int,
    context_after: int,
    log_dirs_override: Optional[str],
    log_content_patterns_override: Optional[str],
) -> None:
    """Search for the first N (oldest) matching log records."""
    engine: AnalysisEngine = ctx.obj["analysis_engine"]
    if count <= 0:
        click.echo("Error: --count must be a positive integer.", err=True)
        return

    click.echo(f"Searching first {count} records in scope: {scope}, context: {context_before}B/{context_after}A")

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
        results = engine.search_logs(filter_criteria)
        click.echo(json.dumps(results, indent=2, default=str))
    except Exception as e:  # pylint: disable=broad-exception-caught
        click.echo(f"Error during search for first N records: {e}", err=True)


@search.command("last")
@click.option("--count", type=int, required=True, help="Number of last (newest) matching records to return.")
@common_search_options
@click.pass_context
def search_last(
    ctx: click.Context,
    count: int,
    scope: str,
    context_before: int,
    context_after: int,
    log_dirs_override: Optional[str],
    log_content_patterns_override: Optional[str],
) -> None:
    """Search for the last N (newest) matching log records."""
    engine: AnalysisEngine = ctx.obj["analysis_engine"]
    if count <= 0:
        click.echo("Error: --count must be a positive integer.", err=True)
        return

    click.echo(f"Searching last {count} records in scope: {scope}, context: {context_before}B/{context_after}A")

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
        results = engine.search_logs(filter_criteria)
        click.echo(json.dumps(results, indent=2, default=str))
    except Exception as e:  # pylint: disable=broad-exception-caught
        click.echo(f"Error during search for last N records: {e}", err=True)


if __name__ == "__main__":
    cli.main()
