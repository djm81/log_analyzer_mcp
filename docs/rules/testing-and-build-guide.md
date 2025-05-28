# Rule: Testing and Build Guidelines

**Description:** This rule provides essential instructions for testing and building the project correctly, avoiding common pitfalls with test environment management.

## Testing Guidelines

### Always Use Hatch Test Command

Standard tests should **always** be run via the built-in Hatch `test` command, not directly with pytest or custom wrappers:

```bash
# Run all tests (default matrix, quiet)
hatch test

# Run tests with coverage report (via run-cov alias)
# Select a specific Python version (e.g., Python 3.10):
hatch -e hatch-test.py3.10 run run-cov

# Generate HTML coverage report (via run-html alias)
# Select a specific Python version (e.g., Python 3.10):
hatch -e hatch-test.py3.10 run run-html

# Run tests for a specific Python version only
hatch test --python 3.10

# Combine options and target specific paths
hatch test --cover --python 3.12 tests/tools/
```

### Avoid Direct pytest Usage

❌ **Incorrect:**

```bash
python -m pytest tests/
```

✅ **Correct:**

```bash
hatch test
```

Using Hatch ensures:

- The proper Python matrix is used
- Dependencies are correctly resolved
- Environment variables are properly set
- Coverage reports are correctly generated

## Build Guidelines

Build the package using either:

```bash
# Using the provided script (recommended as it is the only way to ensure the correct version is built, calls hatch build internally)
./scripts/build.sh
```

This generates the distributable files in the `dist/` directory.

## Installing for IDE and CLI Usage

After modifying and testing the MCP server package, you need to rebuild and install it in the Hatch environment for the changes to take effect in Cursor (or any other IDE) or when using the `loganalyzer` CLI:

### Default package

```bash
# Replace <version> with the actual version built (e.g., 0.2.7)
hatch build && hatch run pip uninstall log-analyzer-mcp -y && hatch run pip install 'dist/log_analyzer_mcp-<version>-py3-none-any.whl'
```

Please note, that for the MCP to be updated within the IDE, ask the user to manually reload the MCP server as there is no automated way available as of now, before continuing to try to talk to the updated MCP via tools call.

## Development Environment

Remember to activate the Hatch environment before making changes:

```bash
hatch shell
```

## Release Guidelines

When preparing a new release or updating the version:

1. **Update CHANGELOG.md** with the new version information:
   - Add a new section at the top after the `# Changelog` header with the next block of lines, but before the first `## [version] - TIMESTAMP` entry with the new version number and date
   - Document all significant changes under "Added", "Fixed", "Changed", or "Removed" sections
   - Use clear, concise language to describe each change

    ```markdown
    ## [0.1.x] - YYYY-MM-DD

    **Added:**
    - New feature description

    **Fixed:**
    - Bug fix description

    **Changed:**
    - Change description
    ```

2. Ensure the version number is updated in `pyproject.toml`
3. Build the package and verify the correct version appears in the build artifacts
4. Test the new version to ensure all changes work
5. Complete Documentation

For comprehensive instructions, refer to the [Developer Guide](../developer_guide.md).
