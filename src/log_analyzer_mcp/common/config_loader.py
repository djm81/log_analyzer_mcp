# src/log_analyzer_mcp/common/config_loader.py
import os
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

from dotenv import load_dotenv
from log_analyzer_mcp.common.logger_setup import find_project_root


class ConfigLoader:
    def __init__(self, env_file_path: Optional[str] = None, project_root_for_config: Optional[str] = None):
        self.logger = logging.getLogger(__name__)

        if project_root_for_config:
            self.project_root = str(Path(project_root_for_config).resolve())
        else:
            self.project_root = str(find_project_root(str(Path.cwd())))

        self.config_file_path: Optional[Path] = None

        actual_env_path: Optional[Path] = None
        if env_file_path:
            actual_env_path = Path(env_file_path)
            if not actual_env_path.is_absolute():
                actual_env_path = Path(self.project_root) / env_file_path
        else:
            # Default .env loading should also consider project_root
            default_env_path_in_project = Path(self.project_root) / ".env"
            if default_env_path_in_project.exists():
                actual_env_path = default_env_path_in_project

        if actual_env_path and actual_env_path.exists():
            load_dotenv(dotenv_path=actual_env_path)
            self.logger.info(f"Loaded .env from {actual_env_path}")
        elif not env_file_path:  # Only try default search if no specific path was given
            loaded_default = load_dotenv()  # python-dotenv default search
            if loaded_default:
                self.logger.info("Loaded .env using python-dotenv default search.")
            else:
                self.logger.info(f"No .env file found at specified path or by default search.")
        else:  # Specific env_file_path was given but not found
            self.logger.warning(f"Specified .env file {env_file_path} (resolved to {actual_env_path}) not found.")

    def get_env(self, key: str, default: Optional[Any] = None) -> Optional[Any]:
        return os.getenv(key, default)

    def get_list_env(self, key: str, default: Optional[List[str]] = None) -> List[str]:
        value = os.getenv(key)
        if value:
            return [item.strip() for item in value.split(",")]
        return default if default is not None else []

    def get_int_env(self, key: str, default: Optional[int] = None) -> Optional[int]:
        value = os.getenv(key)
        if value is not None and value.isdigit():
            return int(value)
        return default

    def get_log_patterns(self) -> Dict[str, List[str]]:
        patterns: Dict[str, List[str]] = {}
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            patterns[level.lower()] = self.get_list_env(f"LOG_PATTERNS_{level}")
        return patterns

    def get_logging_scopes(self) -> Dict[str, str]:
        scopes: Dict[str, str] = {}
        # Assuming scopes are defined like LOG_SCOPE_MYAPP=logs/myapp/
        # This part might need a more robust way to discover all LOG_SCOPE_* variables
        for key, value in os.environ.items():
            if key.startswith("LOG_SCOPE_"):
                scope_name = key.replace("LOG_SCOPE_", "").lower()
                scopes[scope_name] = value
        # Add a default scope if not defined
        if "default" not in scopes and not self.get_list_env("LOG_DIRECTORIES"):
            scopes["default"] = "./"
        return scopes

    def get_log_directories(self) -> List[str]:
        return self.get_list_env("LOG_DIRECTORIES", default=["./"])

    def get_context_lines_before(self) -> int:
        value = self.get_int_env("LOG_CONTEXT_LINES_BEFORE", default=2)
        return value if value is not None else 2

    def get_context_lines_after(self) -> int:
        value = self.get_int_env("LOG_CONTEXT_LINES_AFTER", default=2)
        return value if value is not None else 2


# Example usage (for testing purposes, will be integrated into AnalysisEngine)
if __name__ == "__main__":
    # Create a dummy .env for testing
    with open(".env", "w", encoding="utf-8") as f:
        f.write("LOG_DIRECTORIES=logs/,another_log_dir/\n")
        f.write("LOG_PATTERNS_ERROR=Exception:.*,Traceback (most recent call last):\n")
        f.write("LOG_PATTERNS_INFO=Request processed\n")
        f.write("LOG_CONTEXT_LINES_BEFORE=3\n")
        f.write("LOG_CONTEXT_LINES_AFTER=3\n")
        f.write("LOG_SCOPE_MODULE_A=logs/module_a/\n")
        f.write("LOG_SCOPE_SPECIFIC_FILE=logs/specific.log\n")

    config = ConfigLoader()
    print(f"Log Directories: {config.get_log_directories()}")
    print(f"Log Patterns: {config.get_log_patterns()}")
    print(f"Context Lines Before: {config.get_context_lines_before()}")
    print(f"Context Lines After: {config.get_context_lines_after()}")
    print(f"Logging Scopes: {config.get_logging_scopes()}")

    # Clean up dummy .env
    os.remove(".env")
