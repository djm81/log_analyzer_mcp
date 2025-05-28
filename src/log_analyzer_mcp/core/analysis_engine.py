# src/log_analyzer_mcp/core/analysis_engine.py

import datetime as dt  # Import datetime module as dt
import glob
import os
import re  # For basic parsing
from datetime import datetime as DateTimeClassForCheck  # Specific import for isinstance check
from typing import Any, Dict, List, Optional  # Added Any for filter_criteria flexibility
import logging  # Add logging import

from ..common.config_loader import ConfigLoader

# Define a structure for a parsed log entry
# Using a simple dict for now, could be a Pydantic model later for stricter validation
ParsedLogEntry = Dict[str, Any]  # Keys: 'timestamp', 'level', 'message', 'raw_line', 'file_path', 'line_number'
# Adding 'context_before_lines', 'context_after_lines' to store context directly in the entry
# And 'full_context_log' which would be the original line plus its context


class AnalysisEngine:
    def __init__(
        self,
        logger_instance: logging.Logger,
        env_file_path: Optional[str] = None,
        project_root_for_config: Optional[str] = None,
    ):
        self.logger = logger_instance
        self.config_loader = ConfigLoader(env_file_path=env_file_path, project_root_for_config=project_root_for_config)

        # Load configurations using the correct ConfigLoader methods
        self.log_directories: List[str] = self.config_loader.get_log_directories()
        self.log_content_patterns: Dict[str, List[str]] = self.config_loader.get_log_patterns()
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
        self.logger.info(f"[_get_target_log_files] Called with scope: {scope}, override: {log_dirs_override}")
        target_paths_or_patterns: List[str] = []
        project_root = self.config_loader.project_root
        self.logger.info(f"[_get_target_log_files] Project root: {project_root}")

        using_override_dirs = False
        if log_dirs_override:
            self.logger.info(f"[_get_target_log_files] Using log_dirs_override: {log_dirs_override}")
            target_paths_or_patterns.extend(log_dirs_override)
            using_override_dirs = True
        elif scope and scope.lower() in self.logging_scopes:
            path_or_pattern = self.logging_scopes[scope.lower()]
            self.logger.info(f"[_get_target_log_files] Using scope '{scope}', path_or_pattern: {path_or_pattern}")
            abs_scope_path = os.path.abspath(os.path.join(project_root, path_or_pattern))
            if not abs_scope_path.startswith(project_root):
                self.logger.warning(
                    f"Scope '{scope}' path '{path_or_pattern}' resolves outside project root. Skipping."
                )
                return []
            target_paths_or_patterns.append(abs_scope_path)
        elif scope:  # Scope was provided but not found in self.logging_scopes
            self.logger.info(
                f"[AnalysisEngine] Scope '{scope}' not found in configuration. Returning no files for this scope."
            )
            return []
        else:
            self.logger.info(
                f"[_get_target_log_files] Using default log_directories from config: {self.log_directories}"
            )
            for log_dir_pattern in self.log_directories:
                abs_log_dir_pattern = os.path.abspath(os.path.join(project_root, log_dir_pattern))
                if not abs_log_dir_pattern.startswith(project_root):
                    self.logger.warning(
                        f"Log directory pattern '{log_dir_pattern}' resolves outside project root. Skipping."
                    )
                    continue
                target_paths_or_patterns.append(abs_log_dir_pattern)

        self.logger.info(f"[_get_target_log_files] Effective target_paths_or_patterns: {target_paths_or_patterns}")

        resolved_files: List[str] = []
        for path_or_pattern_input in target_paths_or_patterns:
            self.logger.info(f"[_get_target_log_files] Processing input: {path_or_pattern_input}")
            if not os.path.isabs(path_or_pattern_input):
                current_search_item = os.path.abspath(os.path.join(project_root, path_or_pattern_input))
                self.logger.info(
                    f"[_get_target_log_files] Relative input '{path_or_pattern_input}' made absolute: {current_search_item}"
                )
            else:
                current_search_item = os.path.abspath(path_or_pattern_input)
                self.logger.info(
                    f"[_get_target_log_files] Absolute input '{path_or_pattern_input}' normalized to: {current_search_item}"
                )

            if not current_search_item.startswith(project_root):
                self.logger.warning(
                    f"[_get_target_log_files] Item '{current_search_item}' is outside project root '{project_root}'. Skipping."
                )
                continue

            self.logger.info(f"[_get_target_log_files] Checking item: {current_search_item}")
            if os.path.isfile(current_search_item):
                self.logger.info(f"[_get_target_log_files] Item '{current_search_item}' is a file.")
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
                        and not os.path.isdir(path_or_pattern_input)  # Ensure original input wasn't a directory
                        and (
                            os.path.splitext(abs_filepath)[1]
                            in os.path.splitext(current_search_item)[1]  # Check if glob was for specific ext
                            if not glob.has_magic(
                                current_search_item
                            )  # If current_search_item was specific file (not a glob)
                            else True  # If current_search_item itself was a glob (e.g. *.txt)
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
        """Parses a single log line. Attempts to match a common log format and falls back gracefully."""
        # Regex for "YYYY-MM-DD HH:MM:SS[,ms] LEVEL MESSAGE"
        # It captures timestamp, level, and message. Milliseconds are optional.
        log_pattern = re.compile(
            r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s+"
            r"(?P<level>[A-Z]+(?:\s+[A-Z]+)*)\s+"  # Allow multi-word levels like 'INFO EXAMPLE'
            r"(?P<message>.*)$"
        )
        match = log_pattern.match(line)

        if match:
            groups = match.groupdict()
            timestamp_str = groups.get("timestamp")
            level_str = groups.get("level", "UNKNOWN").upper()
            message_str = groups.get("message", "").strip()

            parsed_timestamp: Optional[dt.datetime] = None
            if timestamp_str:
                # self.logger.debug(f"Attempting to parse timestamp string: '{timestamp_str}' from line: '{line.strip()}'") # DEBUG
                try:
                    # Handle optional milliseconds by splitting at comma
                    timestamp_to_parse = timestamp_str.split(",")[0]
                    parsed_timestamp = dt.datetime.strptime(timestamp_to_parse, "%Y-%m-%d %H:%M:%S")
                except ValueError as e:
                    self.logger.debug(
                        f"ValueError parsing timestamp string: '{timestamp_str}' (tried '{timestamp_to_parse}'). Error: {e}. Line {line_number} in {file_path}: {line.strip()}"
                    )
                    # Fall through to return with None timestamp but other parsed fields

            return {
                "timestamp": parsed_timestamp,
                "level": level_str,
                "message": message_str,
                "raw_line": line.strip(),
                "file_path": file_path,
                "line_number": line_number,
            }

        # Fallback for lines that don't match the primary pattern
        # (e.g., stack traces, multi-line messages not handled by a continuation pattern)
        self.logger.debug(f"Line did not match primary log pattern. Line {line_number} in {file_path}: {line.strip()}")
        return {
            "timestamp": None,
            "level": "UNKNOWN",
            "message": line.strip(),
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
        Otherwise, uses level-specific regexes from self.log_content_patterns (config) IF a level_filter is also provided.
        """
        override_patterns: Optional[List[str]] = filter_criteria.get("log_content_patterns_override")

        if override_patterns is not None:  # Check if the key exists, even if list is empty
            # Apply general override patterns
            if not override_patterns:  # Empty list provided (e.g. override_patterns == [])
                self.logger.info(
                    "[_apply_content_filters] log_content_patterns_override is empty list. Returning all entries."
                )
                return entries

            filtered_entries: List[ParsedLogEntry] = []
            for entry in entries:
                message = entry.get("message", "")
                # level = entry.get("level", "UNKNOWN").upper() # Not used in override path

                # entry_added = False # Not strictly needed with break
                for pattern_str in override_patterns:
                    try:
                        if re.search(pattern_str, message, re.IGNORECASE):
                            filtered_entries.append(entry)
                            # entry_added = True
                            break  # Matched one pattern, include entry and move to next entry
                    except re.error as e:
                        self.logger.warning(
                            f"Invalid regex in override_patterns: '{pattern_str}'. Error: {e}. Skipping this pattern."
                        )
            return filtered_entries
        else:
            # No override_patterns. Use configured level-specific patterns only if a level_filter is present.
            level_filter_str = filter_criteria.get("level_filter", "").upper()

            if not level_filter_str:
                # No specific level_filter provided in criteria, and no override patterns.
                # Content filtering should not apply by default from env/config in this case.
                self.logger.info(
                    "[_apply_content_filters] No override patterns and no level_filter in criteria. Returning all entries."
                )
                return entries

            # A specific level_filter_str IS provided. Use patterns for that level from self.log_content_patterns.
            # self.log_content_patterns is Dict[str (lowercase level), List[str_patterns]]
            # Ensure level_filter_str matches the key format (e.g. "error" not "ERROR")
            relevant_patterns = self.log_content_patterns.get(level_filter_str.lower(), [])

            self.logger.info(
                f"[_apply_content_filters] Using config patterns for level_filter: '{level_filter_str}'. Relevant patterns: {relevant_patterns}"
            )

            # Filter by the specified level first.
            # Then, if there are patterns for that level, apply them.
            # If no patterns for that level, all entries of that level pass.

            filtered_entries = []
            for entry in entries:
                entry_level = entry.get("level", "UNKNOWN").upper()
                message = entry.get("message", "")

                if entry_level == level_filter_str:  # Entry must match the specified level
                    if not relevant_patterns:
                        # No patterns for this level, so include if level matches
                        filtered_entries.append(entry)
                    else:
                        # Patterns exist for this level, try to match them
                        for pattern_str in relevant_patterns:
                            try:
                                if re.search(pattern_str, message, re.IGNORECASE):
                                    filtered_entries.append(entry)
                                    break  # Matched one pattern for this level, include entry
                            except re.error as e:
                                self.logger.warning(
                                    f"Invalid regex in configured patterns for level {level_filter_str}: '{pattern_str}'. Error: {e}. Skipping pattern."
                                )
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
        first_n = filter_criteria.get("first_n")
        last_n = filter_criteria.get("last_n")

        # Only filter by timestamp and sort if a positional filter is active
        if (first_n is not None and isinstance(first_n, int) and first_n > 0) or (
            last_n is not None and isinstance(last_n, int) and last_n > 0
        ):

            # Filter out entries with no timestamp before sorting for positional filters
            entries_with_timestamp = [e for e in entries if e.get("timestamp") is not None]

            # Ensure entries are sorted by timestamp before applying positional filters
            # ParsedLogEntry includes 'timestamp', which is a datetime object
            # Using e["timestamp"] as we've filtered for its existence and non-None value.
            sorted_entries = sorted(entries_with_timestamp, key=lambda e: e["timestamp"])

            if first_n is not None and isinstance(first_n, int) and first_n > 0:
                return sorted_entries[:first_n]
            elif last_n is not None and isinstance(last_n, int) and last_n > 0:
                return sorted_entries[-last_n:]
            else:
                # Should not be reached if the outer if condition is met correctly
                return sorted_entries

        # If no positional filter is active, return the original entries
        # Order might be important, so don't sort unless a positional filter needs it.
        return entries

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
                self.logger.warning(f"Warning: File {file_path} not found in all_lines_by_file for context extraction.")
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
            entry_copy["full_context_log"] = "\\n".join(full_context_list)

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
        - time_filter_type: str ("minutes", "hours", "days") - maps to minutes, hours, days keys
        - time_filter_value: int (e.g., 30 for 30 minutes) - maps to minutes, hours, days values
        - positional_filter_type: str ("first_n", "last_n") - maps to first_n, last_n keys
        - positional_filter_value: int (e.g., 10 for first 10 records) - maps to first_n, last_n values
        - context_before: int (lines of context before match)
        - context_after: int (lines of context after match)
        """
        self.logger.info(f"[AnalysisEngine.search_logs] Called with filter_criteria: {filter_criteria}")

        all_raw_lines_by_file: Dict[str, List[str]] = {}
        parsed_entries: List[ParsedLogEntry] = []

        # 1. Determine target log files
        target_files = self._get_target_log_files(
            scope=filter_criteria.get("scope"),
            log_dirs_override=filter_criteria.get("log_dirs_override"),
        )

        if not target_files:
            self.logger.info(
                "[AnalysisEngine.search_logs] No log files found by _get_target_log_files. Returning pathway OK message."
            )
            # Return a specific message indicating pathway is okay but no files found
            return [{"message": "No target files found, but pathway OK."}]

        self.logger.info(f"[AnalysisEngine.search_logs] Target files found: {target_files}")

        # 2. Parse all lines from target files
        for file_path in target_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                    # Store all lines for context extraction later
                    all_raw_lines_by_file[file_path] = [
                        line.rstrip("\\n") for line in lines
                    ]  # Store raw lines as they are
                    for i, line_content in enumerate(lines):
                        entry = self._parse_log_line(line_content.strip(), file_path, i + 1)  # line_number is 1-indexed
                        if entry:
                            parsed_entries.append(entry)
            except Exception as e:  # pylint: disable=broad-exception-caught
                self.logger.error(f"Error reading or parsing file {file_path}: {e}", exc_info=True)
                continue  # Continue with other files

        self.logger.info(f"[AnalysisEngine.search_logs] Parsed {len(parsed_entries)} entries from all target files.")
        if not parsed_entries:
            self.logger.info("[AnalysisEngine.search_logs] No entries parsed from target files.")
            return []

        # 3. Apply content filters (level and regex)
        filtered_entries = self._apply_content_filters(parsed_entries, filter_criteria)
        if not filtered_entries:
            self.logger.info("[AnalysisEngine.search_logs] No entries left after content filters.")
            return []

        # 4. Apply time filters
        filtered_entries = self._apply_time_filters(filtered_entries, filter_criteria)
        if not filtered_entries:
            self.logger.info("[AnalysisEngine.search_logs] No entries left after time filters.")
            return []

        # 5. Apply positional filters (first_n, last_n)
        # Note: _apply_positional_filters sorts by timestamp and handles entries without timestamps
        filtered_entries = self._apply_positional_filters(filtered_entries, filter_criteria)
        if not filtered_entries:
            self.logger.info("[AnalysisEngine.search_logs] No entries left after positional filters.")
            return []

        # 6. Extract context lines for the final set of entries
        # Use context_before and context_after from filter_criteria, or defaults from config
        context_before = filter_criteria.get("context_before", self.default_context_lines_before)
        context_after = filter_criteria.get("context_after", self.default_context_lines_after)

        final_entries_with_context = self._extract_context_lines(
            filtered_entries, all_raw_lines_by_file, context_before, context_after
        )

        self.logger.info(f"[AnalysisEngine.search_logs] Returning {len(final_entries_with_context)} processed entries.")
        # The tool expects a list of dicts, and ParsedLogEntry is already a Dict[str, Any]
        return final_entries_with_context


# TODO: Add helper functions for parsing, filtering, file handling etc. as needed.
