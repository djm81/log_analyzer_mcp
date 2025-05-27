"""Common utility functions."""

from typing import Any, Dict, List, Optional


def build_filter_criteria(
    scope: Optional[str] = None,
    context_before: Optional[int] = None,
    context_after: Optional[int] = None,
    log_dirs_override: Optional[List[str]] = None,  # Expecting list here
    log_content_patterns_override: Optional[List[str]] = None,  # Expecting list here
    minutes: Optional[int] = None,
    hours: Optional[int] = None,
    days: Optional[int] = None,
    first_n: Optional[int] = None,
    last_n: Optional[int] = None,
) -> Dict[str, Any]:
    """Helper function to build the filter_criteria dictionary."""
    criteria: Dict[str, Any] = {}

    if scope is not None:
        criteria["scope"] = scope
    if context_before is not None:
        criteria["context_before"] = context_before
    if context_after is not None:
        criteria["context_after"] = context_after
    if log_dirs_override is not None:  # Already a list or None
        criteria["log_dirs_override"] = log_dirs_override
    if log_content_patterns_override is not None:  # Already a list or None
        criteria["log_content_patterns_override"] = log_content_patterns_override
    if minutes is not None:
        criteria["minutes"] = minutes
    if hours is not None:
        criteria["hours"] = hours
    if days is not None:
        criteria["days"] = days
    if first_n is not None:
        criteria["first_n"] = first_n
    if last_n is not None:
        criteria["last_n"] = last_n

    return criteria
