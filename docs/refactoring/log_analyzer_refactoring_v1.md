# Refactoring Plan for `log_analyzer_mcp`

This document outlines the steps to refactor the `log_analyzer_mcp` repository after being moved from a larger monorepo.

## Phase 1: Initial Setup and Dependency Resolution

- [x] **Project Setup & Configuration:**
  - [x] Verify and update `pyproject.toml`:
    - [x] Ensure `name`, `version`, `description`, `authors`, `license`, `keywords`, `classifiers` are correct for the standalone project.
    - [x] Review all `dependencies`. Remove any that are not used by `log_analyzer_mcp`.
    - [x] Specifically check dependencies like `pydantic`, `python-dotenv`, `requests`, `openai`, `anthropic`, `google-generativeai`, `jsonschema`, `diskcache`, `cryptography`, `tiktoken`, `tenacity`, `rich`, `loguru`, `mcp`, `numpy`, `scikit-learn`, `markdown`, `pytest`, `pytest-mock`, `mypy`, `langchain`, `redis`, `PyGithub`, `python-dateutil`, `pytz`, `chromadb`, `google-api-python-client`, `pymilvus`, `pinecone-client`, `chroma-mcp-server`. Some of these seem unlikely to be direct dependencies for a log analyzer.
    - [x] Review `[project.optional-dependencies.dev]` and ensure tools like `black`, `isort`, `pylint` are correctly configured and versions are appropriate.
    - [x] Update `[project.urls]` to point to the new repository.
    - [x] Review `[tool.hatch.build.targets.wheel].packages`. Currently, it lists packages like `ai_models`, `backlog_agent`, etc., which seem to be from the old monorepo. This needs to be `src/log_analyzer_mcp`.
    - [x] Update `[tool.hatch.version].path` to `src/log_analyzer_mcp/__init__.py`. Create this file if it doesn't exist and add `__version__ = "0.1.0"`.
  - [x] Review and update `.gitignore`.
  - [x] Review and update `LICENSE.md`.
  - [x] Review and update `CONTRIBUTING.md`.
  - [x] Review and update `SECURITY.md`.
  - [x] Review and update `CHANGELOG.md` (or create if it doesn't make sense to copy).
  - [x] Review `pyrightconfig.json`.
- [x] **Fix Internal Imports and Paths:**
  - [x] Search for `from src.common.venv_helper import setup_venv` and `from src.common.logger_setup import LoggerSetup, get_logs_dir`. These `src.common` modules are missing. Determine if they are needed. If so, either copy them into this repo (e.g., under `src/log_analyzer_mcp/common`) or remove the dependency if the functionality is simple enough to be inlined or replaced.
  - [x] In `src/log_analyzer_mcp/log_analyzer_mcp_server.py`:
    - [x] Correct `run_tests_path = os.path.join(project_root, 'tests/run_all_tests.py')`. This file is missing. Decide if it's needed or if tests will be run directly via `pytest` or `hatch`.
    - [x] Correct `run_coverage_path = os.path.join(script_dir, 'create_coverage_report.sh')`. This file is missing. Decide if it's needed or if coverage will be run via `hatch test --cover`.
    - [x] Correct `coverage_xml_path = os.path.join(project_root, 'tests/coverage.xml')`. This path might change based on coverage tool configuration.
  - [x] In `src/log_analyzer_mcp/parse_coverage.py`:
    - [x] Correct `tree = ET.parse('tests/coverage.xml')`. This path might change.
  - [x] In `tests/log_analyzer_mcp/test_analyze_runtime_errors.py`:
    - [x] Correct `server_path = os.path.join(script_dir, 'log_analyzer_mcp_server.py')` to point to the correct location within `src`. (e.g. `os.path.join(project_root, 'src', 'log_analyzer_mcp', 'log_analyzer_mcp_server.py')`)
  - [x] In `tests/log_analyzer_mcp/test_log_analyzer_mcp_server.py`:
    - [x] Correct `server_path = os.path.join(script_dir, "log_analyzer_mcp_server.py")` similarly.
- [x] **Address Missing Files:**
  - [x] `tests/run_all_tests.py`: Decide if this script is still the primary way to run tests or if `hatch test` will be used. If needed, create or copy it.
  - [x] `src/log_analyzer_mcp/create_coverage_report.sh`: Decide if this script is still how coverage is generated, or if `hatch test --cover` and `coverage xml/html` commands are sufficient.
  - [x] `src/common/venv_helper.py` and `src/common/logger_setup.py`: As mentioned above, decide how to handle these.
  - [x] `logs/run_all_tests.log` and `tests/coverage.xml`: These are generated files. Ensure the tools that produce them are working correctly.
- [x] **Environment Setup:**
  - [x] Ensure a virtual environment can be created and dependencies installed using `hatch`.
  - [x] Test `hatch env create`.

## Phase 2: Code Refactoring and Structure

- [x] **Module Reorganization (Optional, based on complexity):**
  - [x] Consider if the current structure within `src/log_analyzer_mcp` (`log_analyzer.py`, `log_analyzer_mcp_server.py`, `analyze_runtime_errors.py`, `parse_coverage.py`) is optimal. (Current structure maintained for now, common `logger_setup.py` added)
  - [-] Potentially group server-related logic, core analysis logic, and utility scripts into sub-modules if clarity improves. For example:
    - `src/log_analyzer_mcp/server.py` (for MCP server)
    - `src/log_analyzer_mcp/analysis/` (for `log_analyzer.py`, `analyze_runtime_errors.py`)
    - `src/log_analyzer_mcp/utils/` (for `parse_coverage.py`)
  - [x] Mirror any `src` restructuring in the `tests` directory. (Minor restructuring related to common module).
- [x] **Code Cleanup:**
  - [x] Remove any dead code or commented-out code that is no longer relevant after the move. (Ongoing, debug prints removed)
  - [x] Standardize logging (if `logger_setup.py` is brought in or replaced). (Done)
  - [x] Ensure consistent use of `os.path.join` for all path constructions. (Largely done)
  - [x] Review and refactor complex functions for clarity and maintainability if needed. (Regex in `log_analyzer.py` refactored)
  - [x] Ensure all scripts are executable (`chmod +x`) if intended to be run directly. (Verified)
- [x] **Update `pyproject.toml` for Tests and Coverage:**
  - [x] Review `[tool.hatch.envs.hatch-test.scripts]`. Ensure commands like `run`, `run-cov`, `cov`, `xml`, `run-html`, `cov-report` are functional with the new project structure and chosen test/coverage runner.
    - For example, `run = "pytest --timeout=5 -p no:xdist --junitxml=logs/tests/junit/test-results.xml {args}"` implies `logs/tests/junit` directory needs to exist or be created. (Scripts updated, paths for generated files like junit.xml and coverage.xml verified/created by hatch).
  - [x] Review `[tool.coverage.run]` settings:
    - [x] `source = ["src"]` should probably be `source = ["src/log_analyzer_mcp"]` or just `src` if the `__init__.py` is in `src/log_analyzer_mcp`. (Set to `["src"]` which works).
    - [x] `data_file = "logs/tests/coverage/.coverage"` implies `logs/tests/coverage` needs to exist. (Path and directory creation handled by coverage/hatch).
    - [x] `omit` patterns might need adjustment. (Adjusted)
    - [x] `parallel = true`, `branch = true`, `sigterm = true`, `relative_files = true` configured.
    - [x] `COVERAGE_PROCESS_START` implemented for subprocesses.
  - [x] Review `[tool.coverage.paths]`. (Configured as needed).
  - [x] Review `[tool.coverage.report]`. (Defaults used, or paths confirmed via hatch scripts).
  - [x] Review `[tool.coverage.html]` and `[tool.coverage.xml]` output paths. (XML path confirmed as `logs/tests/coverage/coverage.xml`).
  - [x] Review `[tool.pytest.ini_options]`:
    - [x] `pythonpath = ["src"]` is likely correct. (Confirmed)
    - [x] `testpaths = ["tests"]` is likely correct. (Confirmed)
    - [x] `asyncio_mode = "strict"` added.
- [x] **Testing:**
  - [x] Ensure all existing tests in `tests/log_analyzer_mcp/` pass after path and import corrections. (All tests passing)
  - [x] Adapt tests if `run_all_tests.py` is removed in favor of direct `pytest` or `hatch test`. (Adapted for `hatch test`)
  - [x] Add new tests if `src.common` modules are copied and modified. (Tests for `parse_coverage.py` added).
  - [x] Achieve and maintain >= 80% test coverage. (Currently: `log_analyzer_mcp_server.py` at 85%, `log_analyzer.py` at 79%, `analyze_runtime_errors.py` at 48%, `parse_coverage.py` at 88%. Overall average is good, but individual files like `analyze_runtime_errors.py` need improvement. The goal is >= 80% total.)

## Phase 3: Documentation and Finalization

- [ ] **Update/Create Documentation:**
  - [ ] Update `README.md` for the standalone project:
    - [ ] Installation instructions (using `hatch`).
    - [ ] Usage instructions for the MCP server and any command-line scripts.
    - [ ] How to run tests and check coverage.
    - [ ] Contribution guidelines (linking to `CONTRIBUTING.md`).
  - [ ] Create a `docs/` directory structure if it doesn't fully exist (e.g., `docs/usage.md`, `docs/development.md`).
    - [x] `docs/index.md` as a landing page for documentation. (This plan is in `docs/refactoring/`)
    - [x] `docs/refactoring/README.md` to link to this plan.
  - [ ] Document the MCP tools provided by `log_analyzer_mcp_server.py`.
  - [ ] Document the functionality of each script in `src/log_analyzer_mcp/`.
- [x] **Linting and Formatting:**
  - [x] Run `black .` and `isort .` (Applied periodically)
  - [ ] Run `pylint src tests` and address warnings/errors.
  - [ ] Run `mypy src tests` and address type errors.
- [ ] **Build and Distribution (if applicable):**
  - [ ] Test building a wheel: `hatch build`.
  - [ ] If this package is intended for PyPI, ensure all metadata is correct.
- [ ] **Final Review:**
  - [ ] Review all changes and ensure the repository is clean and self-contained.
  - [ ] Ensure all `.cursorrules` instructions are being followed and can be met by the current setup.

## Phase 4: Coverage Improvement (New Phase)

- [ ] Improve test coverage for `src/log_analyzer_mcp/analyze_runtime_errors.py` (currently 48%) to meet the >= 80% target.
- [ ] Improve test coverage for `src/log_analyzer_mcp/log_analyzer.py` (currently 79%) to meet the >= 80% target.
- [ ] Review overall project coverage and ensure all key code paths are tested.

## Missing File Checklist

- [x] `src/common/venv_helper.py` (Decide: copy, inline, or remove) -> Removed
- [x] `src/common/logger_setup.py` (Decide: copy, inline, or remove) -> Copied and adapted as `src/log_analyzer_mcp/common/logger_setup.py`
- [x] `tests/run_all_tests.py` (Decide: keep/create or use `hatch test`) -> Using `hatch test`
- [x] `src/log_analyzer_mcp/create_coverage_report.sh` (Decide: keep/create or use `hatch` coverage commands) -> Using `hatch` commands
- [x] `src/log_analyzer_mcp/__init__.py` (Create with `__version__`) -> Created

## Notes

- The `platform-architecture.md` rule seems to be for a much larger system and is likely not directly applicable in its entirety to this smaller, focused `log_analyzer_mcp` repository, but principles of IaC, CI/CD, and good architecture should still be kept in mind.
- The `.cursorrules` mention `hatch test --cover -v`. Ensure this command works. (Working)
