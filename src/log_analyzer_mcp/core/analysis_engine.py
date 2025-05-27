# src/log_analyzer_mcp/core/analysis_engine.py

import datetime as dt  # Import datetime module as dt
import glob
import os
import re  # For basic parsing
from datetime import datetime as DateTimeClassForCheck  # Specific import for isinstance check
from typing import Any, Dict, List, Optional  # Added Any for filter_criteria flexibility

from ..common.config_loader import ConfigLoader

# Define a structure for a parsed log entry
# Using a simple dict for now, could be a Pydantic model later for stricter validation
ParsedLogEntry = Dict[str, Any]  # Keys: 'timestamp', 'level', 'message', 'raw_line', 'file_path', 'line_number'
# Adding 'context_before_lines', 'context_after_lines' to store context directly in the entry
# And 'full_context_log' which would be the original line plus its context


class AnalysisEngine:
    def __init__(self, env_file_path: Optional[str] = None, project_root_for_config: Optional[str] = None):
        self.config_loader = ConfigLoader(env_file_path=env_file_path, project_root=project_root_for_config)

        # Load configurations
        self.log_directories: List[str] = (
            self.config_loader.get_log_directories()
        )  # Default log dirs/patterns from config
        self.log_content_patterns: Dict[str, List[str]] = (
            self.config_loader.get_log_patterns()
        )  # Default content regexes
        # These are loaded from config, but can be overridden by filter_criteria per call
        self.default_context_lines_before: int = self.config_loader.get_context_lines_before()
        self.default_context_lines_after: int = self.config_loader.get_context_lines_after()
        self.logging_scopes: Dict[str, str] = self.config_loader.get_logging_scopes()

        # TODO: Potentially add more sophisticated validation or processing of loaded configs

    def _get_target_log_files(
        self, scope: Optional[str] = None, log_dirs_override: Optional[List[str]] = None
    ) -> List[str]:
        """
        Determines the list of log files to search.
        Uses log_dirs_override if provided, otherwise falls back to scope or general config.
        log_dirs_override can contain direct file paths, directory paths, or glob patterns.
        If a directory path is provided, it searches for '*.log' files recursively.
        """
        target_paths_or_patterns: List[str] = []
        # Use the project_root from the config_loader, which can be set for tests
        project_root = self.config_loader.project_root

        using_override_dirs = False
        if log_dirs_override:
            target_paths_or_patterns.extend(log_dirs_override)
            using_override_dirs = True
        elif scope and scope.lower() in self.logging_scopes:
            path_or_pattern = self.logging_scopes[scope.lower()]
            abs_scope_path = os.path.abspath(os.path.join(project_root, path_or_pattern))
            if not abs_scope_path.startswith(project_root):
                print(f"Warning: Scope '{scope}' path '{path_or_pattern}' resolves outside project root. Skipping.")
                return []
            target_paths_or_patterns.append(abs_scope_path)
        elif scope:  # Scope was provided but not found in self.logging_scopes
            print(f"[AnalysisEngine] Scope '{scope}' not found in configuration. Returning no files for this scope.")
            return []  # Explicitly return empty list for unknown scope
        else:
            # Fallback to default configured log directories ONLY if no scope was given
            for log_dir_pattern in self.log_directories:
                abs_log_dir_pattern = os.path.abspath(os.path.join(project_root, log_dir_pattern))
                if not abs_log_dir_pattern.startswith(project_root):
                    print(
                        f"Warning: Log directory pattern '{log_dir_pattern}' resolves outside project root. Skipping."
                    )
                    continue
                target_paths_or_patterns.append(abs_log_dir_pattern)

        resolved_files: List[str] = []
        for path_or_pattern_input in target_paths_or_patterns:
            # Normalize path: if relative, join with project_root. If absolute, use as is.
            # This is crucial for glob and safety checks.
            if not os.path.isabs(path_or_pattern_input):
                current_search_item = os.path.abspath(os.path.join(project_root, path_or_pattern_input))
            else:
                current_search_item = os.path.abspath(path_or_pattern_input)

            # Safety check: Ensure the path is within the project root
            if not current_search_item.startswith(project_root):
                continue

            if os.path.isfile(current_search_item):
                # If current_search_item came from a scope that resolved to a direct file,
                # or from an override that was a direct file, include it.
                # The `using_override_dirs` flag helps distinguish.
                # If it came from a scope, `using_override_dirs` is False.
                is_from_scope_direct_file = not using_override_dirs and any(
                    current_search_item == os.path.abspath(os.path.join(project_root, self.logging_scopes[s_key]))
                    for s_key in self.logging_scopes
                    if not glob.has_magic(self.logging_scopes[s_key])
                    and not os.path.isdir(os.path.join(project_root, self.logging_scopes[s_key]))
                )

                if using_override_dirs or is_from_scope_direct_file:
                    resolved_files.append(current_search_item)
                elif current_search_item.endswith(".log"):  # Default behavior for non-override, non-direct-scope-file
                    resolved_files.append(current_search_item)
            elif os.path.isdir(current_search_item):
                # Search for *.log files recursively in the directory
                for filepath in glob.glob(
                    os.path.join(glob.escape(current_search_item), "**", "*.log"), recursive=True
                ):
                    if os.path.isfile(filepath) and os.path.abspath(filepath).startswith(
                        project_root
                    ):  # Double check resolved path
                        resolved_files.append(os.path.abspath(filepath))
            else:  # Assumed to be a glob pattern
                # For glob patterns, ensure they are rooted or handled carefully.
                # If an override is a glob like "specific_module/logs/*.log", it should work.
                # If it's just "*.log", it will glob from CWD unless we force it relative to project_root.
                # The normalization above should handle making it absolute from project_root if it was relative.

                # The glob pattern itself (current_search_item) is already an absolute path or made absolute starting from project_root
                is_recursive_glob = "**" in path_or_pattern_input  # Check original input for "**"

                for filepath in glob.glob(current_search_item, recursive=is_recursive_glob):
                    abs_filepath = os.path.abspath(filepath)
                    if (
                        os.path.isfile(abs_filepath)
                        and abs_filepath.endswith(".log")
                        and abs_filepath.startswith(project_root)
                    ):
                        resolved_files.append(abs_filepath)
                    elif (
                        os.path.isfile(abs_filepath)
                        and not abs_filepath.endswith(".log")
                        and using_override_dirs
                        and not os.path.isdir(path_or_pattern_input)
                        and (
                            os.path.splitext(abs_filepath)[1] in os.path.splitext(current_search_item)[1]
                            if not glob.has_magic(current_search_item)
                            else True
                        )
                    ):
                        # If using override_dirs and the override was a specific file path (not a pattern or dir) that doesn't end with .log, still include it.
                        # This was changed above: if os.path.isfile(current_search_item) and using_override_dirs, it's added.
                        # This elif handles globs from override_dirs that might pick up non-.log files
                        # if the glob pattern itself was specific (e.g., *.txt)
                        # The original logic for specific file override (path_or_pattern_input == filepath) was too restrictive.
                        # current_search_item is the absolute version of path_or_pattern_input.
                        # abs_filepath is the file found by glob.
                        # This part needs to correctly identify if a non-.log file found by a glob from an override should be included.
                        # If the original glob pattern explicitly asked for non-.log (e.g. *.txt), then yes.
                        # If the glob was generic (e.g. dir/*) and picked up a .txt, then probably no, unless it was the only match for a specific file.
                        # The current logic seems to have simplified: if os.path.isfile(current_search_item) and using_override_dirs, it adds.
                        # This new elif is for results from glob.glob(...)
                        # Let's ensure that if the original path_or_pattern_input (from override) was a glob,
                        # and that glob resolves to a non-.log file, we include it.
                        # This means the user explicitly asked for it via a pattern.
                        if glob.has_magic(path_or_pattern_input) or glob.has_magic(current_search_item):
                            # If original input or its absolute form was a glob, include what it finds.
                            resolved_files.append(abs_filepath)
                        # No 'else' needed here, if it's not a .log and not from an override glob, it's skipped by the main 'if .endswith(".log")'

        return sorted(list(set(resolved_files)))  # Unique sorted list

    def _parse_log_line(self, line: str, file_path: str, line_number: int) -> Optional[ParsedLogEntry]:
        """Parses a single log line. Placeholder implementation."""
        # Example: "2024-05-27 10:00:00 INFO This is a log message."
        # This regex is a placeholder and needs to be made configurable.
        # It also doesn't handle multi-line logs yet.
        # Ensure LOG_CONTENT_REGEX_PATTERN_<LEVEL> from .env or a default is used here.
        # For now, sticking to a generic one.
        match = re.match(
            r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+(?P<level>[A-Z]+)\s+(?P<message>.*)$",
            line,
        )
        if match:
            try:
                groups = match.groupdict()
                return {
                    "timestamp": dt.datetime.strptime(
                        groups["timestamp"].split(",")[0], "%Y-%m-%d %H:%M:%S"
                    ),  # Use dt.datetime.strptime
                    "level": groups["level"].upper(),
                    "message": groups["message"].strip(),
                    "raw_line": line.strip(),
                    "file_path": file_path,
                    "line_number": line_number,
                }
            except ValueError:
                pass
        # Fallback for lines that don't match the primary pattern (e.g. stack traces, multi-line messages)
        # For now, we create a basic entry. Proper multi-line handling is a TODO.
        return {
            "timestamp": None,  # Or a file's modification time as a rough estimate if needed
            "level": "UNKNOWN",
            "message": line.strip(),  # The whole line becomes the message
            "raw_line": line.strip(),
            "file_path": file_path,
            "line_number": line_number,
        }

    def _apply_content_filters(
        self, entries: List[ParsedLogEntry], filter_criteria: Dict[str, Any]
    ) -> List[ParsedLogEntry]:
        """
        Filters entries based on content patterns.
        Uses 'log_content_patterns_override' from filter_criteria if available (as a list of general regexes).
        Otherwise, uses level-specific regexes from self.log_content_patterns (config).
        """
        override_patterns: Optional[List[str]] = filter_criteria.get("log_content_patterns_override")

        if override_patterns is not None:  # Check if the key exists, even if list is empty
            # Apply general override patterns
            if not override_patterns:  # Empty list provided (e.g. override_patterns == [])
                return entries  # Return all entries if override is explicitly an empty list

            filtered_entries: List[ParsedLogEntry] = []
            for entry in entries:
                message = entry.get("message", "")

                entry_added = False
                for pattern_str in override_patterns:
                    try:
                        if re.search(pattern_str, message, re.IGNORECASE):
                            filtered_entries.append(entry)
                            entry_added = True
                            break  # Matched one pattern, include entry and move to next entry
                    except re.error as e:
                        print(
                            f"Warning: Invalid regex in override_patterns: '{pattern_str}'. Error: {e}. Skipping this pattern."
                        )
            return filtered_entries
        else:
            # Use configured level-specific patterns
            if not self.log_content_patterns or not any(
                self.log_content_patterns.values()
            ):  # No patterns defined in config
                return entries

            filtered_entries: List[ParsedLogEntry] = []
            for entry in entries:
                level = entry.get("level", "").lower()  # Match config keys like 'info', 'error'
                message = entry.get("message", "")
                entry_matches = False

                # Check against patterns for the specific level (e.g., self.log_content_patterns['error'])
                level_specific_patterns = self.log_content_patterns.get(level, [])
                if level_specific_patterns:
                    for pattern_str in level_specific_patterns:
                        try:
                            if re.search(pattern_str, message, re.IGNORECASE):
                                entry_matches = True
                                break
                        except re.error as e:
                            print(
                                f"Warning: Invalid regex for level '{level}': '{pattern_str}'. Error: {e}. Skipping this pattern."
                            )

                # Check against 'general' patterns if defined (e.g. self.log_content_patterns['general'])
                # This allows for patterns that apply to all log levels if not matched by a specific level.
                general_patterns = self.log_content_patterns.get("general", [])
                if not entry_matches and general_patterns:  # Only check general if not already matched by specific
                    for pattern_str in general_patterns:
                        try:
                            if re.search(pattern_str, message, re.IGNORECASE):
                                entry_matches = True
                                break
                        except re.error as e:
                            print(
                                f"Warning: Invalid regex in 'general' patterns: '{pattern_str}'. Error: {e}. Skipping this pattern."
                            )

                if entry_matches:
                    filtered_entries.append(entry)

            if not filtered_entries:  # If no patterns specified (neither override nor config), match all
                return entries

            return filtered_entries

    def _apply_time_filters(
        self, entries: List[ParsedLogEntry], filter_criteria: Dict[str, Any]
    ) -> List[ParsedLogEntry]:
        """Filters entries based on time window from filter_criteria."""
        now = dt.datetime.now()  # Use dt.datetime.now()
        time_window_applied = False
        earliest_time: Optional[dt.datetime] = None  # Use dt.datetime for type hint

        if filter_criteria.get("minutes", 0) > 0:
            earliest_time = now - dt.timedelta(minutes=filter_criteria["minutes"])
            time_window_applied = True
        elif filter_criteria.get("hours", 0) > 0:
            earliest_time = now - dt.timedelta(hours=filter_criteria["hours"])
            time_window_applied = True
        elif filter_criteria.get("days", 0) > 0:
            earliest_time = now - dt.timedelta(days=filter_criteria["days"])
            time_window_applied = True

        if not time_window_applied or earliest_time is None:
            return entries  # No time filter to apply or invalid criteria

        filtered_entries: List[ParsedLogEntry] = []
        for entry in entries:
            entry_timestamp = entry.get("timestamp")
            # Ensure entry_timestamp is a datetime.datetime object before comparison
            if (
                isinstance(entry_timestamp, DateTimeClassForCheck) and entry_timestamp >= earliest_time
            ):  # Use DateTimeClassForCheck for isinstance
                filtered_entries.append(entry)

        return filtered_entries

    def _apply_positional_filters(
        self, entries: List[ParsedLogEntry], filter_criteria: Dict[str, Any]
    ) -> List[ParsedLogEntry]:
        """Filters entries based on positional criteria (first_n, last_n)."""
        # Filter out entries with no timestamp before sorting for positional filters
        entries_with_timestamp = [e for e in entries if e.get("timestamp") is not None]

        # Ensure entries are sorted by timestamp before applying positional filters
        # ParsedLogEntry includes 'timestamp', which is a datetime object
        # Using e["timestamp"] as we've filtered for its existence and non-None value.
        sorted_entries = sorted(entries_with_timestamp, key=lambda e: e["timestamp"])

        first_n = filter_criteria.get("first_n")
        last_n = filter_criteria.get("last_n")

        if first_n is not None and isinstance(first_n, int) and first_n > 0:
            return sorted_entries[:first_n]
        elif last_n is not None and isinstance(last_n, int) and last_n > 0:
            return sorted_entries[-last_n:]

        return sorted_entries  # Return sorted if no positional filter or if criteria are invalid

    def _extract_context_lines(
        self,
        entries: List[ParsedLogEntry],
        all_lines_by_file: Dict[str, List[str]],
        context_before: int,
        context_after: int,
    ) -> List[ParsedLogEntry]:
        """Extracts context lines for each entry."""
        if context_before == 0 and context_after == 0:
            # Add empty context if no context lines are requested, to maintain structure
            for entry in entries:
                entry["context_before_lines"] = []
                entry["context_after_lines"] = []
                entry["full_context_log"] = entry["raw_line"]
            return entries

        entries_with_context: List[ParsedLogEntry] = []
        for entry in entries:
            file_path = entry["file_path"]
            line_number = entry["line_number"]  # 1-indexed from original file

            if file_path not in all_lines_by_file:
                # This shouldn't happen if all_lines_by_file is populated correctly
                entry["context_before_lines"] = []
                entry["context_after_lines"] = []
                entry["full_context_log"] = entry["raw_line"]
                entries_with_context.append(entry)
                print(f"Warning: File {file_path} not found in all_lines_by_file for context extraction.")
                continue

            file_lines = all_lines_by_file[file_path]
            actual_line_index = line_number - 1  # Convert to 0-indexed for list access

            start_index = max(0, actual_line_index - context_before)
            end_index = min(len(file_lines), actual_line_index + context_after + 1)

            entry_copy = entry.copy()  # Avoid modifying the original entry directly in the list
            entry_copy["context_before_lines"] = [line.strip() for line in file_lines[start_index:actual_line_index]]
            entry_copy["context_after_lines"] = [line.strip() for line in file_lines[actual_line_index + 1 : end_index]]

            # Construct full_context_log
            full_context_list = (
                entry_copy["context_before_lines"] + [entry_copy["raw_line"]] + entry_copy["context_after_lines"]
            )
            entry_copy["full_context_log"] = "\n".join(full_context_list)

            entries_with_context.append(entry_copy)

        return entries_with_context

    def search_logs(self, filter_criteria: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Main method to search logs based on various criteria.
        filter_criteria is a dictionary that can contain:
        - log_dirs_override: List[str] (paths/globs to search instead of config)
        - scope: str (e.g., "mcp", "runtime" to use predefined paths from config)
        - log_content_patterns_override: List[str] (regexes for log message content)
        - level_filter: str (e.g., "ERROR", "WARNING")
        - time_filter_type: str ("minutes", "hours", "days")
        - time_filter_value: int (e.g., 30 for 30 minutes)
        - positional_filter_type: str ("first_n", "last_n")
        - positional_filter_value: int (e.g., 10 for first 10 records)
        - context_before: int (lines of context before match)
        - context_after: int (lines of context after match)
        """
        final_results: List[ParsedLogEntry] = []
        all_raw_lines_by_file: Dict[str, List[str]] = {}  # For context extraction

        # 1. Determine target log files
        # Prioritize direct override, then scope, then default config
        target_files = self._get_target_log_files(
            scope=filter_criteria.get("scope"),
            log_dirs_override=filter_criteria.get("log_dirs_override"),
        )

        if not target_files:
            print("[AnalysisEngine] No log files found to search.")
            return []

        # 2. Read and parse all relevant log files
        parsed_entries: List[ParsedLogEntry] = []
        for file_path in target_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    all_raw_lines_by_file[file_path] = [line.rstrip("\n") for line in lines]  # Store for context
                    for i, line_content in enumerate(lines):
                        entry = self._parse_log_line(line_content.strip(), file_path, i + 1)
                        if entry:
                            parsed_entries.append(entry)
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"Error reading or parsing file {file_path}: {e}")
                continue  # Skip to the next file if one fails

        # 3. Apply content filters (Regex on message, or level-specific from config)
        # This uses log_content_patterns_override or configured patterns
        filtered_by_content = self._apply_content_filters(parsed_entries, filter_criteria)

        # 4. Apply level filter (if any)
        level_filter = filter_criteria.get("level_filter")
        if level_filter:
            filtered_by_level = [entry for entry in filtered_by_content if entry["level"] == level_filter.upper()]
            filtered_by_content = filtered_by_level

        # 5. Apply time filters
        if any(key in filter_criteria for key in ["minutes", "hours", "days"]):
            filtered_by_time = self._apply_time_filters(filtered_by_content, filter_criteria)
        else:
            filtered_by_time = filtered_by_content

        # 6. Apply positional filters (first_n, last_n)
        if "first_n" in filter_criteria or "last_n" in filter_criteria:
            filtered_by_position = self._apply_positional_filters(filtered_by_time, filter_criteria)
        else:
            filtered_by_position = filtered_by_time

        # 7. Extract context lines
        entries_with_context = self._extract_context_lines(
            filtered_by_position,
            all_raw_lines_by_file,
            filter_criteria.get("context_before", self.default_context_lines_before),
            filter_criteria.get("context_after", self.default_context_lines_after),
        )

        return entries_with_context


# TODO: Add helper functions for parsing, filtering, file handling etc. as needed.
